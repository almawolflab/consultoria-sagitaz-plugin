#!/usr/bin/env python3
"""onboard.py — AW-194: prepara el entorno del plugin (venv) e informa a Claude.

Lo invoca el hook SessionStart (session_start.sh) con un Python >= 3.10 ya validado.

- Detecta rápido si el venv ya está OK; si no (primera vez), avisa a stderr ANTES del install (~15-30s).
- Ejecuta bootstrap idempotente (como subproceso; su salida va a stderr para no contaminar el JSON).
- Emite a stdout el JSON de SessionStart (additionalContext + systemMessage) vía json.dumps.

NUNCA imprime secretos. Exit 0 SIEMPRE (SessionStart no bloquea).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import bootstrap  # noqa: E402  (scripts/ está en sys.path)


# ---------------------------------------------------------------------------
# AW-196 — materialización de userConfig a data_dir()
# ---------------------------------------------------------------------------
# Los valores de userConfig solo llegan a procesos de HOOK como
# CLAUDE_PLUGIN_OPTION_<KEY> (no a los scripts que una skill ejecuta por Bash).
# Este hook los persiste en data_dir() para que fetch_transcripciones.py y
# authorize_crm.py los encuentren por una ruta determinista. NUNCA loguea secretos.

# fichero -> {clave_json: nombre_env (sin el prefijo CLAUDE_PLUGIN_OPTION_)}
_MATERIALIZE_MAP = {
    "transcripciones.json": {
        "endpoint": "TRANSCRIPCIONES_ENDPOINT",
        "token": "TRANSCRIPCIONES_TEAM_TOKEN",
    },
    "crm_connected_app.json": {
        "client_id": "CRM_CLIENT_ID",
        "client_secret": "CRM_CLIENT_SECRET",
    },
}


def _option(env_suffix: str) -> str:
    """Valor de userConfig vía env CLAUDE_PLUGIN_OPTION_<SUFFIX> (vacío si ausente)."""
    return os.environ.get(f"CLAUDE_PLUGIN_OPTION_{env_suffix}", "").strip()


def _materialize_one(path: Path, mapping: dict) -> bool:
    """Materializa un fichero JSON con los valores presentes en env (merge, 0600).

    - Solo escribe claves cuyo valor de env NO esté vacío (no pisa con vacíos).
    - Conserva los valores previos del fichero para las claves no provistas.
    - Devuelve True si se escribió el fichero.
    """
    nuevos = {k: _option(env) for k, env in mapping.items()}
    nuevos = {k: v for k, v in nuevos.items() if v}  # descarta vacíos
    if not nuevos:
        return False  # sin valores nuevos no se toca el fichero (no pisa con vacíos)

    actual = {}
    if path.exists():
        try:
            actual = json.loads(path.read_text(encoding="utf-8")) or {}
        except (ValueError, OSError):
            actual = {}

    merged = {**actual, **nuevos}

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
    return True


def materialize_userconfig(data_dir) -> list:
    """Persiste los userConfig recibidos por env a data_dir(). Devuelve nombres escritos.

    NUNCA imprime ni devuelve valores secretos: solo los nombres de fichero.
    """
    data_dir = Path(data_dir)
    written = []
    for fname, mapping in _MATERIALIZE_MAP.items():
        if _materialize_one(data_dir / fname, mapping):
            written.append(fname)
    return written


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

    # AW-196: materializar userConfig a data_dir() (mejor esfuerzo; nunca rompe el hook).
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        written = materialize_userconfig(data_dir)
        if written:
            print(f"[consultoria-sagitaz] userConfig materializado: {', '.join(written)}",
                  file=sys.stderr, flush=True)
    except Exception as e:  # noqa: BLE001  (SessionStart no debe bloquear nunca)
        print(f"[consultoria-sagitaz] aviso: no se pudo materializar userConfig ({type(e).__name__}).",
              file=sys.stderr, flush=True)

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
