from __future__ import annotations

import asyncio
import json
import re
import shlex
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

from ion import config
from ion.brain import IonBrain, extract_json
from ion.models import ProjectPlan, WorkTask
from ion.providers import GeminiProvider, NvidiaProvider


def _slug(value: str) -> str:
    result = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip()).strip("-_").lower()
    return (result or "ion-project")[:64]


def _safe_relative(value: str) -> str:
    value = str(value or "").replace("\\", "/").strip()
    path = PurePosixPath(value)
    if not value or path.is_absolute() or any(part in {"..", ""} for part in path.parts):
        raise ValueError(f"Caminho de arquivo inválido: {value!r}")
    if any(part in {".git", ".ion", ".venv", "venv", "node_modules"} for part in path.parts):
        raise ValueError(f"O supervisor não permite gravar em {value!r}.")
    if path.name.lower().startswith(".env") or path.as_posix().lower() == "config/api_keys.json":
        raise ValueError("Agentes não podem gravar arquivos de segredo .env.")
    return str(path)


def _read_workspace_file(root: Path, relative: str, cap: int = 18000) -> str:
    path = root / relative
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")[:cap]
    except (OSError, UnicodeError):
        return ""


def _test_command(command: str, root: Path, timeout: int = 180) -> dict:
    raw = str(command or "").strip()
    if not raw or any(x in raw for x in (";", "&&", "||", "|", ">", "<", "\n", "\r")):
        return {"command": raw, "passed": False, "blocked": True, "output": "Comando vazio ou contém operador de shell não permitido."}
    try:
        args = shlex.split(raw, posix=True)
    except ValueError as exc:
        return {"command": raw, "passed": False, "blocked": True, "output": str(exc)}
    if not args:
        return {"command": raw, "passed": False, "blocked": True, "output": "Comando vazio."}
    exe = args[0].lower()
    cmd = None
    if exe in {"python", "python3", "py"} and len(args) >= 3 and args[1] == "-m" and args[2] in {"pytest", "unittest", "compileall"}:
        cmd = [sys.executable, *args[1:]]
    elif exe == "pytest":
        cmd = [sys.executable, "-m", "pytest", *args[1:]]
    elif exe == "node" and len(args) >= 3 and args[1] == "--check":
        cmd = ["node", *args[1:]]
    elif exe == "npm" and len(args) >= 2 and (args[1] == "test" or (args[1] == "run" and len(args) >= 3 and args[2] in {"build", "test", "lint"})):
        cmd = ["npm", *args[1:]]
    elif exe == "npx" and len(args) >= 3 and args[1] == "playwright" and args[2] == "test":
        cmd = ["npx", *args[1:]]
    if cmd is None:
        return {"command": raw, "passed": False, "blocked": True, "output": "Comando fora da lista permitida pelo supervisor."}
    try:
        done = subprocess.run(
            cmd, cwd=str(root), capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, shell=False,
        )
        output = ((done.stdout or "") + "\n" + (done.stderr or "")).strip()
        return {"command": raw, "passed": done.returncode == 0, "blocked": False,
                "exit_code": done.returncode, "output": output[-6000:]}
    except FileNotFoundError as exc:
        return {"command": raw, "passed": False, "blocked": True, "output": f"Dependência ausente: {exc}"}
    except subprocess.TimeoutExpired as exc:
        out = (exc.stdout or b"").decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        return {"command": raw, "passed": False, "blocked": False, "output": f"Tempo limite excedido. {out[-2000:]}"}


class IonSupervisor:
    """Single operational supervisor: task routing, file integration and tests."""

    def __init__(self) -> None:
        self.brain = IonBrain()
        self.providers = {"nvidia": NvidiaProvider(), "gemini": GeminiProvider()}

    async def run_project(self, task: str, working_directory: str = "") -> dict:
        if not task.strip():
            raise ValueError("Descreva o que o Ion deve desenvolver.")
        try:
            from ion.orchestration.maf import run_with_microsoft_agent_framework
            return await run_with_microsoft_agent_framework(
                self, {"task": task.strip(), "working_directory": working_directory.strip()}
            )
        except ImportError as exc:
            raise RuntimeError(
                "Microsoft Agent Framework não instalado. Execute: "
                "python -m pip install -r requirements-ion.txt"
            ) from exc

    async def _execute_project(self, request: dict) -> dict:
        started = time.monotonic()
        plan = await self.brain.plan(str(request["task"]))
        if not plan.tasks:
            raise RuntimeError("Ion não gerou tarefas de implementação.")
        self._validate_plan(plan)
        workspace = self._workspace(request.get("working_directory", ""), plan.project_name)
        job_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
        state = {
            "job_id": job_id, "project": plan.project_name, "request": request["task"],
            "workspace": str(workspace), "status": "running", "created_at": datetime.now(timezone.utc).isoformat(),
            "technology_decisions": plan.technology_decisions, "tasks": [],
        }
        self._save_state(workspace, job_id, state)
        pending = list(plan.tasks)
        completed: set[str] = set()
        results: list[dict] = []
        agent_load = {"nvidia": 0, "gemini": 0}

        while pending:
            ready = [t for t in pending if set(t.depends_on).issubset(completed)]
            if not ready:
                raise RuntimeError("Plano inválido: dependências circulares ou tarefa dependente de ID inexistente.")
            batch: list[tuple[WorkTask, str]] = []
            used_files: set[str] = set()
            for task in ready:
                task_files = set(task.files)
                if used_files.intersection(task_files):
                    continue
                preferred = task.preferred_agent if task.preferred_agent in self.providers else ""
                if preferred and agent_load[preferred] <= agent_load["gemini" if preferred == "nvidia" else "nvidia"]:
                    agent = preferred
                else:
                    agent = "nvidia" if agent_load["nvidia"] <= agent_load["gemini"] else "gemini"
                batch.append((task, agent))
                used_files.update(task_files)
                agent_load[agent] += 1
                if len(batch) >= 2:
                    break
            if not batch:
                batch = [(ready[0], "nvidia" if agent_load["nvidia"] <= agent_load["gemini"] else "gemini")]
            state["tasks"].extend({"id": t.id, "title": t.title, "agent": a, "status": "running"} for t, a in batch)
            self._save_state(workspace, job_id, state)
            outcomes = await asyncio.gather(
                *(self._implement_and_test(task, agent, workspace, plan) for task, agent in batch),
                return_exceptions=True,
            )
            for (task, agent), outcome in zip(batch, outcomes):
                if isinstance(outcome, Exception):
                    result = {"id": task.id, "agent": agent, "status": "failed", "error": str(outcome)}
                else:
                    result = {"id": task.id, "agent": agent, **outcome}
                results.append(result)
                state["tasks"] = [
                    {**item, "status": result["status"], "result": result.get("summary", result.get("error", ""))}
                    if item["id"] == task.id else item for item in state["tasks"]
                ]
                if result["status"] == "completed":
                    completed.add(task.id)
                    pending.remove(task)
                else:
                    state["status"] = "blocked" if result.get("status") == "blocked" else "failed"
                    state["results"] = results
                    self._save_state(workspace, job_id, state)
                    return self._final_result(state, plan, results, started)
            state["results"] = results
            self._save_state(workspace, job_id, state)

        state["status"] = "completed"
        self._save_state(workspace, job_id, state)
        return self._final_result(state, plan, results, started)

    def _validate_plan(self, plan: ProjectPlan) -> None:
        ids = {task.id for task in plan.tasks}
        if len(ids) != len(plan.tasks) or "" in ids:
            raise ValueError("Ion gerou IDs de tarefas vazios ou duplicados.")
        for task in plan.tasks:
            if not task.title or not task.description or not task.files:
                raise ValueError(f"Tarefa {task.id!r} precisa de título, instruções e arquivos definidos.")
            task.files = [_safe_relative(path) for path in task.files]
            if any(dep not in ids for dep in task.depends_on):
                raise ValueError(f"Tarefa {task.id} depende de uma tarefa inexistente.")

    def _workspace(self, requested: str, project_name: str) -> Path:
        if requested:
            root = Path(requested).expanduser().resolve()
        else:
            root = config.workspace_root() / _slug(project_name)
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir():
            raise RuntimeError(f"Diretório de projeto inválido: {root}")
        return root

    def _save_state(self, workspace: Path, job_id: str, state: dict) -> None:
        folder = workspace / ".ion"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / f"{job_id}.json"
        temp = target.with_suffix(".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(target)

    def _final_result(self, state: dict, plan: ProjectPlan, results: list[dict], started: float) -> dict:
        return {
            "status": state["status"], "project": plan.project_name,
            "workspace": state["workspace"], "summary": plan.summary,
            "technology_decisions": plan.technology_decisions,
            "completed_tasks": sum(1 for item in results if item["status"] == "completed"),
            "total_tasks": len(plan.tasks), "task_results": results,
            "elapsed_seconds": round(time.monotonic() - started, 1),
            "message": "Projeto concluído." if state["status"] == "completed" else "Projeto interrompido; consulte os erros e dependências informados.",
        }

    async def _implement_and_test(self, task: WorkTask, agent: str, workspace: Path, plan: ProjectPlan) -> dict:
        provider = self.providers[agent]
        actual_agent = agent
        allowed = set(task.files)
        instructions = (
            f"Você é o executor de implementação {agent.upper()} do Ion. "
            "Implemente somente a tarefa recebida. Você pode programar e corrigir seu próprio código. "
            "Não revise outros agentes, não aprove tarefas e não mude a arquitetura decidida por Ion. "
            "Escreva apenas nos arquivos listados. Retorne somente JSON com summary e files, "
            "onde files é uma lista de {path, content}. Não omita arquivos necessários."
        )
        context = []
        for relative in task.files:
            existing = _read_workspace_file(workspace, relative)
            if existing:
                context.append(f"\n--- CONTEÚDO EXISTENTE: {relative} ---\n{existing}")
        prompt = f"""PROJETO: {plan.project_name}
RESUMO: {plan.summary}
DECISÕES TÉCNICAS DE ION: {json.dumps(plan.technology_decisions, ensure_ascii=False)}
TAREFA: {task.id} — {task.title}
INSTRUÇÕES: {task.description}
CRITÉRIOS: {json.dumps(task.acceptance_criteria, ensure_ascii=False)}
ARQUIVOS PERMITIDOS: {json.dumps(task.files, ensure_ascii=False)}
ESTADO DOS ARQUIVOS EXISTENTES:
{''.join(context) or "(nenhum arquivo existente)"}

Retorne JSON:
{{"summary":"o que implementou","files":[{{"path":"caminho/relativo","content":"conteúdo integral do arquivo"}}]}}
"""
        last_checks: list[dict] = []
        summary = ""
        for attempt in range(config.max_correction_attempts() + 1):
            if attempt:
                prompt += (
                    "\nCORREÇÃO NECESSÁRIA. O supervisor executou os testes e encontrou: "
                    + json.dumps(last_checks, ensure_ascii=False)
                    + "\nCorrija somente os arquivos permitidos e retorne o conteúdo integral atualizado em JSON."
                )
            try:
                raw = await provider.complete(instructions, prompt, json_mode=True)
            except Exception as primary_error:
                fallback = "gemini" if actual_agent == "nvidia" else "nvidia"
                if not config.api_key(fallback):
                    raise RuntimeError(f"{actual_agent} indisponível e {fallback} sem chave: {primary_error}") from primary_error
                provider = self.providers[fallback]
                actual_agent = fallback
                raw = await provider.complete(
                    instructions + f" O provedor {agent} falhou; você assumiu a tarefa como {actual_agent.upper()}.",
                    prompt, json_mode=True
                )
            payload = extract_json(raw)
            generated = payload.get("files")
            if not isinstance(generated, list) or not generated:
                raise RuntimeError(f"{agent} não retornou arquivos para {task.id}.")
            written = []
            for item in generated:
                if not isinstance(item, dict):
                    continue
                relative = _safe_relative(item.get("path", ""))
                if relative not in allowed:
                    raise RuntimeError(f"{agent} tentou alterar arquivo não autorizado: {relative}")
                content = item.get("content")
                if not isinstance(content, str) or len(content) > 1_500_000:
                    raise RuntimeError(f"Conteúdo inválido ou excessivo para {relative}.")
                target = (workspace / relative).resolve()
                if not target.is_relative_to(workspace.resolve()):
                    raise RuntimeError(f"Caminho escapou do workspace: {relative}")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8", newline="\n")
                written.append(relative)
            if set(written) != allowed:
                missing = sorted(allowed - set(written))
                raise RuntimeError(f"{agent} não entregou todos os arquivos autorizados: {missing}")
            summary = str(payload.get("summary") or f"{task.title} implementada.")
            commands = task.validation_commands[:8]
            if not commands:
                commands = []
                py_files = [p for p in written if p.endswith(".py")]
                js_files = [p for p in written if p.endswith(".js")]
                commands.extend([f"python -m compileall -q {shlex.quote(p)}" for p in py_files])
                commands.extend([f"node --check {shlex.quote(p)}" for p in js_files])
            last_checks = [_test_command(command, workspace) for command in commands]
            blocked = any(check.get("blocked") for check in last_checks)
            passed = all(check.get("passed") for check in last_checks) if last_checks else True
            if passed:
                return {"status": "completed", "summary": summary, "files": written, "checks": last_checks, "attempts": attempt + 1, "agent_used": actual_agent}
            if blocked:
                return {"status": "blocked", "summary": summary, "files": written, "checks": last_checks, "attempts": attempt + 1, "agent_used": actual_agent}
        return {"status": "failed", "summary": summary, "files": list(allowed), "checks": last_checks, "attempts": config.max_correction_attempts() + 1, "agent_used": actual_agent}
