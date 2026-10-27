#!/usr/bin/env python3
"""bootstrap.py — Crea e inicializa el venv del plugin consultoria-sagitaz.

Uso:
    python3 scripts/bootstrap.py [--force]

Env vars reconocidas:
    CLAUDE_PLUGIN_DATA   Directorio de datos persistentes del plugin (lo gestiona Claude Code).
                         Si no está definida, se usa ~/.local/share/consultoria-sagitaz.
    CLAUDE_PLUGIN_ROOT   Raíz del plugin (se usa para localizar requirements-plugin.txt).
                         Si no está definida, se infiere a partir de la ubicación de este script.

Flags:
    --force   Borra el venv existente y lo recrea desde cero.

Solo usa stdlib (venv, subprocess, argparse, os, sys, pathlib): sin dependencias externas.
NUNCA imprime secretos ni credenciales.
"""
import argparse
import os
import shutil
import subprocess
import sys
import venv
from pathlib import Path


# ---------------------------------------------------------------------------
# Resolución de rutas
# ---------------------------------------------------------------------------

def plugin_data_dir() -> Path:
    """Devuelve el directorio de datos persistentes del plugin.

    Orden de preferencia:
    1. $CLAUDE_PLUGIN_DATA (definida por Claude Code al ejecutar el plugin).
    2. ~/.local/share/consultoria-sagitaz (fallback para ejecución manual/CI).
    """
    env_val = os.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    if env_val:
        return Path(env_val)
    return Path.home() / ".local" / "share" / "consultoria-sagitaz"


def plugin_root_dir() -> Path:
    """Devuelve la raíz del plugin (donde está requirements-plugin.txt).

    Orden de preferencia:
    1. $CLAUDE_PLUGIN_ROOT (definida por Claude Code).
    2. El directorio padre de scripts/ (inferido desde la ubicación de este fichero).
    """
    env_val = os.environ.get("CLAUDE_PLUGIN_ROOT", "").strip()
    if env_val:
        return Path(env_val)
    # Este script está en <plugin-root>/scripts/bootstrap.py
    return Path(__file__).resolve().parent.parent


def venv_python(venv_dir: Path) -> Path:
    """Devuelve la ruta al intérprete Python dentro del venv según el SO.

    - POSIX (macOS, Linux): <venv>/bin/python
    - Windows (nt):         <venv>\\Scripts\\python.exe
    """
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


# ---------------------------------------------------------------------------
# Comprobación de idempotencia
# ---------------------------------------------------------------------------

def venv_is_ok(venv_dir: Path, reqs_path: Path) -> bool:
    """Devuelve True si el venv existe, tiene intérprete y openpyxl importa correctamente."""
    python = venv_python(venv_dir)
    if not python.exists():
        return False
    result = subprocess.run(
        [str(python), "-c", "import openpyxl"],
        capture_output=True,
    )
    return result.returncode == 0


# ---------------------------------------------------------------------------
# Lógica principal
# ---------------------------------------------------------------------------

def bootstrap(force: bool = False) -> int:
    """Crea/verifica el venv e instala las dependencias del plugin.

    Retorna 0 en éxito, 1 en error.
    """
    data_dir = plugin_data_dir()
    root_dir = plugin_root_dir()
    reqs_path = root_dir / "requirements-plugin.txt"
    venv_dir = data_dir / "venv"

    print(f"[bootstrap] Plugin data dir : {data_dir}")
    print(f"[bootstrap] Plugin root dir : {root_dir}")
    print(f"[bootstrap] requirements    : {reqs_path}")
    print(f"[bootstrap] venv            : {venv_dir}")

    if not reqs_path.exists():
        print(f"[bootstrap] ERROR: no existe {reqs_path}", file=sys.stderr)
        return 1

    # --force: destruir venv existente
    if force and venv_dir.exists():
        print(f"[bootstrap] --force: eliminando venv existente en {venv_dir}")
        shutil.rmtree(venv_dir)

    # Idempotencia: si el venv ya está OK, no reinstalar
    if not force and venv_dir.exists() and venv_is_ok(venv_dir, reqs_path):
        print("[bootstrap] El venv ya está listo (idempotente — no se reinstala).")
        return 0

    # Crear el venv
    data_dir.mkdir(parents=True, exist_ok=True)
    print(f"[bootstrap] Creando venv en {venv_dir} ...")
    venv.create(str(venv_dir), with_pip=True, clear=True)

    python = venv_python(venv_dir)
    if not python.exists():
        print(f"[bootstrap] ERROR: intérprete no encontrado en {python}", file=sys.stderr)
        return 1

    # Actualizar pip silenciosamente
    print("[bootstrap] Actualizando pip ...")
    subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        check=True,
    )

    # Instalar dependencias
    print(f"[bootstrap] Instalando dependencias desde {reqs_path.name} ...")
    result = subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "-r", str(reqs_path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[bootstrap] ERROR al instalar dependencias:", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        return 1

    print("[bootstrap] Instalacion completada.")
    print(f"[bootstrap] Interprete del venv: {python}")
    print("[bootstrap] Listo. Ejecuta 'scripts/doctor.py' para verificar el entorno.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Crea e inicializa el venv del plugin consultoria-sagitaz."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Elimina el venv existente y lo recrea desde cero.",
    )
    args = parser.parse_args()
    sys.exit(bootstrap(force=args.force))


if __name__ == "__main__":
    main()
