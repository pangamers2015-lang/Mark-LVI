"""Safely remove the desktop-webview packages no longer used by Yon.

Run inside the project's activated .venv:
    python scripts/cleanup_unused_ui_packages.py

The script starts with pywebview and only includes its dependencies when no
other installed distribution declares a dependency on them. It never removes
PyQt6 or any audio, AI, camera, automation, or backend package.
"""
from __future__ import annotations

import subprocess
import sys
from importlib import metadata

try:
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
except ImportError:
    print("O pacote 'packaging' é necessário para analisar dependências.")
    raise SystemExit(2)


def installed_distributions():
    return {
        canonicalize_name(dist.metadata.get("Name", "")): dist
        for dist in metadata.distributions()
        if dist.metadata.get("Name")
    }


def requirements_of(dist):
    result = set()
    for raw in dist.requires or ():
        try:
            req = Requirement(raw)
            if req.marker is None or req.marker.evaluate():
                result.add(canonicalize_name(req.name))
        except Exception:
            continue
    return result


def main():
    installed = installed_distributions()
    target = "pywebview"
    if target not in installed:
        print("pywebview já não está instalado. Nada a fazer.")
        return

    dependencies = {name: requirements_of(dist) for name, dist in installed.items()}
    removal = {target}
    changed = True
    while changed:
        changed = False
        for parent in tuple(removal):
            for dependency in dependencies.get(parent, ()):
                if dependency not in installed or dependency in removal:
                    continue
                other_users = {
                    name for name, required in dependencies.items()
                    if dependency in required and name not in removal
                }
                if not other_users:
                    removal.add(dependency)
                    changed = True

    names = sorted(removal)
    print("Pacotes de interface que serão removidos:")
    for name in names:
        print(f"  - {name}")
    print("\nNenhuma outra biblioteca do Yon será removida.")
    answer = input("\nConfirmar desinstalação? [s/N] ").strip().lower()
    if answer not in {"s", "sim"}:
        print("Cancelado; nada foi desinstalado.")
        return

    subprocess.run(
        [sys.executable, "-m", "pip", "uninstall", "-y", *names],
        check=False,
    )
    print("\nVerificando dependências restantes...")
    subprocess.run([sys.executable, "-m", "pip", "check"], check=False)


if __name__ == "__main__":
    main()
