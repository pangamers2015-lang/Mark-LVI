"""Safe bidirectional sync for the user-managed knowledge/shared folder.

Only UTF-8 text documents (.txt/.md) are synchronized. No deletions are
propagated; divergent edits are reported as conflicts and never overwritten.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path

from memory import cognitive_store as store

ROOT = Path(__file__).resolve().parents[1]
SHARED_ROOT = ROOT / "knowledge" / "shared"
REPOSITORY = os.environ.get("YON_GITHUB_REPOSITORY", "pangamers2015-lang/Mark-LVI")
BRANCH = os.environ.get("YON_GITHUB_BRANCH", "main")
POLL_SECONDS = max(30, min(int(os.environ.get("YON_GITHUB_SYNC_SECONDS", "60")), 600))
MAX_FILE_BYTES = 256_000
ALLOWED_SUFFIXES = {".txt", ".md"}
_API_ROOT = "https://api.github.com"
_LAST_SYNC = 0.0


def _db():
    path = Path(store.DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE IF NOT EXISTS github_shared_sync_state ("
                 "path TEXT PRIMARY KEY, local_digest TEXT NOT NULL, "
                 "remote_sha TEXT NOT NULL, synced_at TEXT NOT NULL)")
    conn.commit()
    return conn


def _token() -> str:
    value = os.environ.get("YON_GITHUB_TOKEN", "").strip()
    if not value:
        raise RuntimeError("YON_GITHUB_TOKEN is not configured.")
    return value


def _request(method: str, path: str, payload: dict | None = None):
    owner_repo = REPOSITORY.strip("/")
    if owner_repo.count("/") != 1:
        raise ValueError("YON_GITHUB_REPOSITORY must be owner/repository.")
    url = _API_ROOT + "/repos/" + owner_repo + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + _token(),
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Yon-Bidirectional-Sync",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(2_000_000)
            return json.loads(raw.decode("utf-8")) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read(2000).decode("utf-8", "replace")
        if exc.code in (403, 429):
            raise RuntimeError(
                "GitHub recusou a sincronização (403/429). Verifique o limite da API "
                "e se o token tem Contents: Read and write. " + detail[:500]
            ) from exc
        raise RuntimeError(f"GitHub API HTTP {exc.code}: {detail[:500]}") from exc


def _safe_relative(value: str) -> str | None:
    path = Path(value)
    if path.is_absolute() or not path.parts or any(p in {"", ".", ".."} for p in path.parts):
        return None
    if any(p.startswith(".") for p in path.parts):
        return None
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        return None
    return path.as_posix()


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def _local_files() -> dict[str, bytes]:
    SHARED_ROOT.mkdir(parents=True, exist_ok=True)
    found = {}
    for path in SHARED_ROOT.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        relative = _safe_relative(path.relative_to(SHARED_ROOT).as_posix())
        if not relative:
            continue
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_FILE_BYTES:
            continue
        raw.decode("utf-8-sig")
        found[relative] = raw
    return found


def _remote_files() -> dict[str, str]:
    ref = urllib.parse.quote(BRANCH, safe="")
    tree = _request("GET", f"/git/trees/{ref}?recursive=1")
    if tree.get("truncated"):
        raise RuntimeError("Árvore do GitHub veio truncada; sincronização cancelada por segurança.")
    prefix = "knowledge/shared/"
    result = {}
    for item in tree.get("tree", []):
        path = str(item.get("path", ""))
        if not path.startswith(prefix) or item.get("type") != "blob":
            continue
        relative = _safe_relative(path[len(prefix):])
        if relative and int(item.get("size") or 0) <= MAX_FILE_BYTES:
            result[relative] = str(item.get("sha", ""))
    return result


def _download(relative: str) -> bytes:
    encoded = urllib.parse.quote("knowledge/shared/" + relative, safe="/")
    ref = urllib.parse.quote(BRANCH, safe="")
    item = _request("GET", f"/contents/{encoded}?ref={ref}")
    if item.get("encoding") != "base64":
        raise RuntimeError(f"Formato inesperado ao baixar {relative}.")
    raw = base64.b64decode(item.get("content", ""), validate=False)
    if not raw or len(raw) > MAX_FILE_BYTES:
        raise RuntimeError(f"Arquivo remoto fora do limite: {relative}.")
    raw.decode("utf-8-sig")
    return raw


def _upload(relative: str, raw: bytes, remote_sha: str | None):
    encoded = urllib.parse.quote("knowledge/shared/" + relative, safe="/")
    payload = {
        "message": f"Yon sync: atualizar knowledge/shared/{relative}",
        "content": base64.b64encode(raw).decode("ascii"),
        "branch": BRANCH,
    }
    if remote_sha:
        payload["sha"] = remote_sha
    return _request("PUT", f"/contents/{encoded}", payload)


def _save_local(relative: str, raw: bytes):
    target = SHARED_ROOT / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.resolve().relative_to(SHARED_ROOT.resolve())
    fd, temporary = tempfile.mkstemp(prefix=".yon-sync-", dir=str(target.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def sync_shared_folder(force: bool = False) -> dict:
    """Synchronize the dedicated shared folder without deleting or overwriting conflicts."""
    global _LAST_SYNC
    import time
    now = time.monotonic()
    if not force and now - _LAST_SYNC < POLL_SECONDS:
        return {"ok": True, "throttled": True, "uploaded": 0, "downloaded": 0, "conflicts": []}
    _LAST_SYNC = now
    uploaded = downloaded = 0
    conflicts = []
    try:
        local = _local_files()
        remote = _remote_files()
        with store._LOCK, closing(_db()) as conn:
                state = {row[0]: (row[1], row[2]) for row in conn.execute(
                    "SELECT path,local_digest,remote_sha FROM github_shared_sync_state"
                ).fetchall()}

        for relative in sorted(set(local) | set(remote)):
            local_raw = local.get(relative)
            remote_sha = remote.get(relative)
            old = state.get(relative)
            local_digest = hashlib.sha256(local_raw).hexdigest() if local_raw is not None else None
            local_git_sha = _git_blob_sha(local_raw) if local_raw is not None else None

            if local_raw is None and remote_sha:
                raw = _download(relative)
                _save_local(relative, raw)
                local[relative] = raw
                local_digest = hashlib.sha256(raw).hexdigest()
                remote_sha = _git_blob_sha(raw)
                downloaded += 1
            elif local_raw is not None and remote_sha is None:
                # New local file, or a remote deletion: preserve local data by publishing it.
                response = _upload(relative, local_raw, None)
                remote_sha = response.get("content", {}).get("sha") or local_git_sha
                uploaded += 1
            elif local_raw is not None and remote_sha and local_git_sha != remote_sha:
                if old is None:
                    conflicts.append(relative)
                    continue
                old_local, old_remote = old
                local_changed = local_digest != old_local
                remote_changed = remote_sha != old_remote
                if local_changed and remote_changed:
                    conflicts.append(relative)
                    continue
                if local_changed:
                    response = _upload(relative, local_raw, remote_sha)
                    remote_sha = response.get("content", {}).get("sha") or local_git_sha
                    uploaded += 1
                elif remote_changed:
                    raw = _download(relative)
                    _save_local(relative, raw)
                    local[relative] = raw
                    local_digest = hashlib.sha256(raw).hexdigest()
                    remote_sha = _git_blob_sha(raw)
                    downloaded += 1
                else:
                    conflicts.append(relative)
                    continue

            if local_raw is None:
                local_raw = local.get(relative)
                local_digest = hashlib.sha256(local_raw).hexdigest() if local_raw else ""
            if remote_sha and local_digest:
                with store._LOCK, closing(_db()) as conn:
                        conn.execute(
                            "INSERT INTO github_shared_sync_state(path,local_digest,remote_sha,synced_at) "
                            "VALUES(?,?,?,?) ON CONFLICT(path) DO UPDATE SET "
                            "local_digest=excluded.local_digest,remote_sha=excluded.remote_sha,"
                            "synced_at=excluded.synced_at",
                            (relative, local_digest, remote_sha, datetime.now(timezone.utc).isoformat()),
                        )
                        conn.commit()

        return {"ok": not conflicts, "uploaded": uploaded, "downloaded": downloaded,
                "conflicts": conflicts, "folder": str(SHARED_ROOT)}
    except Exception as exc:
        return {"ok": False, "uploaded": uploaded, "downloaded": downloaded,
                "conflicts": conflicts, "errors": [f"{type(exc).__name__}: {exc}"],
                "folder": str(SHARED_ROOT)}
