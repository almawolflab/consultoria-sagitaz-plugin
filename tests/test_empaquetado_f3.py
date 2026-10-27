"""AW-189 — Fase 3 TDD: bootstrap.py — venv idempotente, multiplataforma."""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = PLUGIN_ROOT / "scripts" / "bootstrap.py"
REQS = PLUGIN_ROOT / "requirements-plugin.txt"


def _run_bootstrap(env: dict) -> subprocess.CompletedProcess:
    """Ejecuta bootstrap.py con el entorno dado."""
    return subprocess.run(
        [sys.executable, str(BOOTSTRAP)],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
    )


def test_bootstrap_crea_venv(tmp_path):
    """bootstrap.py crea el venv en CLAUDE_PLUGIN_DATA/venv e instala requirements-plugin.txt.

    La segunda ejecución (idempotencia) también debe terminar con exit 0.
    El test instala openpyxl de PyPI: puede tardar ~30s en la primera ejecución.
    """
    data_dir = tmp_path / "plugin_data"
    data_dir.mkdir()
    env = {
        "CLAUDE_PLUGIN_DATA": str(data_dir),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
    }

    # Primera ejecución: crea el venv
    result1 = _run_bootstrap(env)
    assert result1.returncode == 0, (
        f"bootstrap.py falló en primera ejecución.\n"
        f"stdout: {result1.stdout}\nstderr: {result1.stderr}"
    )
    venv_dir = data_dir / "venv"
    assert venv_dir.exists(), f"No se creó el venv en {venv_dir}"

    # Debe existir el intérprete según el SO
    if os.name == "nt":
        python_bin = venv_dir / "Scripts" / "python.exe"
    else:
        python_bin = venv_dir / "bin" / "python"
    assert python_bin.exists(), f"No se encontró el intérprete en {python_bin}"

    # openpyxl debe estar instalado en el venv
    check = subprocess.run(
        [str(python_bin), "-c", "import openpyxl; print(openpyxl.__version__)"],
        capture_output=True,
        text=True,
    )
    assert check.returncode == 0, (
        f"openpyxl no importa en el venv.\nstdout: {check.stdout}\nstderr: {check.stderr}"
    )

    # Segunda ejecución: idempotente — no falla ni reinstala si ya está OK
    result2 = _run_bootstrap(env)
    assert result2.returncode == 0, (
        f"bootstrap.py falló en segunda ejecución (idempotencia).\n"
        f"stdout: {result2.stdout}\nstderr: {result2.stderr}"
    )


def test_bootstrap_ruta_interprete_por_so(tmp_path, monkeypatch):
    """bootstrap.py resuelve la ruta del intérprete según el SO (bin/python vs Scripts/python.exe)."""
    # Importamos el módulo sin ejecutarlo para inspeccionar la función de resolución
    spec = importlib.util.spec_from_file_location("bootstrap", BOOTSTRAP)
    bootstrap = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bootstrap)

    venv_dir = tmp_path / "venv"
    venv_dir.mkdir()
    (venv_dir / "bin").mkdir()
    (venv_dir / "Scripts").mkdir()

    # Simular POSIX
    monkeypatch.setattr("os.name", "posix")
    posix_path = bootstrap.venv_python(venv_dir)
    assert "bin" in str(posix_path) and "python" in str(posix_path).lower(), (
        f"En POSIX, venv_python debe usar bin/python, obtuvo: {posix_path}"
    )
    assert "Scripts" not in str(posix_path), (
        f"En POSIX, venv_python NO debe usar Scripts\\, obtuvo: {posix_path}"
    )

    # Simular Windows
    monkeypatch.setattr("os.name", "nt")
    nt_path = bootstrap.venv_python(venv_dir)
    assert "Scripts" in str(nt_path) and "python" in str(nt_path).lower(), (
        f"En Windows, venv_python debe usar Scripts\\python.exe, obtuvo: {nt_path}"
    )
