#!/usr/bin/env python3
"""onboard.py — AW-194: prepara el entorno del plugin (venv) e informa a Claude.

Lo invoca el hook SessionStart (session_start.sh) con un Python >= 3.10 ya validado.

- Detecta rápido si el venv ya está OK; si no (primera vez), avisa a stderr ANTES del install (~15-30s).
- Ejecuta bootstrap idempotente (como subproceso; su salida va a stderr para no contaminar el JSON).
- Emite a stdout el JSON de SessionStart (additionalContext + systemMessage) vía json.dumps.

NUNCA imprime secretos. Exit 0 SIEMPRE (SessionStart no bloquea).
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import bootstrap  # noqa: E402  (scripts/ está en sys.path)


def _emit(additional_context: str, system_message: str) -> None:
    """Imprime a stdout el único objeto JSON que el hook SessionStart espera."""
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": additional_context,
            "systemMessage": system_message,
        }
    }))


def main() -> int:
    data_dir = bootstrap.data_dir()
    venv_dir = data_dir / "venv"
    reqs = bootstrap.plugin_root_dir() / "requirements-plugin.txt"
    ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

    first_time = not bootstrap.venv_is_ok(venv_dir, reqs)
    if first_time:
        # Aviso de progreso (mejor esfuerzo) ANTES del install largo.
        print("[consultoria-sagitaz] Preparando el entorno del plugin por primera vez (~15-30s)…",
              file=sys.stderr, flush=True)

    # bootstrap como subproceso: toda su salida (incl. pip) va a stderr; stdout queda limpio.
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "bootstrap.py")],
        capture_output=True, text=True,
    )
    if proc.stdout:
        print(proc.stdout, file=sys.stderr)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)

    if proc.returncode == 0 and bootstrap.venv_is_ok(venv_dir, reqs):
        msg = ("✓ consultoria-sagitaz: entorno preparado por primera vez"
               if first_time else "✓ consultoria-sagitaz: entorno listo")
        _emit(
            f"Entorno del plugin consultoria-sagitaz LISTO. Interprete: Python {ver}. "
            f"venv en {venv_dir} con openpyxl. Las skills matriz/plan/dercas pueden ejecutar "
            f"sus scripts. (doctor: [A][B][C] en verde; [D]/[E] de OAuth solo para /implementar).",
            msg,
        )
    else:
        _emit(
            f"El plugin consultoria-sagitaz encontro Python {ver} pero NO pudo preparar el venv "
            f"(dependencia openpyxl). Pide al consultor que ejecute 'scripts/bootstrap.py' y revise "
            f"la salida, o 'scripts/doctor.py' para diagnostico.",
            "consultoria-sagitaz: no se pudo preparar el entorno (venv). Revisa bootstrap/doctor.",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
