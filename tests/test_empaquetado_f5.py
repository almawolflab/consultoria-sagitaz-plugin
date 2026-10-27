"""AW-189 — Fase 5 TDD: empaquetado E2E — venv real + import parametrizacion + ausencia imageio-ffmpeg."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REQS = PLUGIN_ROOT / "requirements-plugin.txt"
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"


def _find_python311():
    """Encuentra el intérprete Python 3.11+ disponible en el sistema."""
    for candidate in ("python3.13", "python3.12", "python3.11", "python3"):
        exe = shutil.which(candidate)
        if exe:
            result = subprocess.run(
                [exe, "-c", "import sys; print(sys.version_info.major, sys.version_info.minor)"],
                capture_output=True, text=True,
            )
            if result.returncode == 0:
                major, minor = map(int, result.stdout.strip().split())
                if (major, minor) >= (3, 11):
                    return exe
    return None


def test_import_scripts_con_venv(tmp_path):
    """Crea un venv real, instala requirements-plugin.txt, importa parametrizacion (el módulo
    principal del plugin) y verifica que imageio-ffmpeg NO está en el venv.

    Este es el test de empaquetado E2E: prueba que el plugin es funcional en macOS/Windows
    sin arrastrar dependencias Linux-only.

    Puede tardar ~30s en la primera ejecución (descarga openpyxl de PyPI).
    """
    import pytest

    python311 = _find_python311()
    if python311 is None:
        pytest.skip("No se encontró Python 3.11+ en el sistema para el test E2E")

    # 1. Crear venv con Python 3.11+
    venv_dir = tmp_path / "venv"
    subprocess.run([python311, "-m", "venv", str(venv_dir)], check=True)

    if os.name == "nt":
        python_bin = venv_dir / "Scripts" / "python.exe"
    else:
        python_bin = venv_dir / "bin" / "python"

    assert python_bin.exists(), f"Intérprete no encontrado: {python_bin}"

    # 2. Instalar requirements-plugin.txt (solo puro Python/cross-platform)
    assert REQS.exists(), f"No existe {REQS}"
    result = subprocess.run(
        [str(python_bin), "-m", "pip", "install", "--quiet", "-r", str(REQS)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"pip install falló.\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )

    # 3. Importar parametrizacion con el intérprete del venv
    # Añadir SCRIPTS_DIR al PYTHONPATH del subproceso
    import_code = (
        "import sys; "
        f"sys.path.insert(0, r'{SCRIPTS_DIR}'); "
        "import parametrizacion; "
        "from parametrizacion import crm, applicator; "
        "print('OK:', parametrizacion.__file__)"
    )
    check_import = subprocess.run(
        [str(python_bin), "-c", import_code],
        capture_output=True,
        text=True,
    )
    assert check_import.returncode == 0, (
        f"import parametrizacion falló con el intérprete del venv.\n"
        f"stdout: {check_import.stdout}\nstderr: {check_import.stderr}"
    )
    assert "OK:" in check_import.stdout, (
        f"La importación no produjo la salida esperada: {check_import.stdout!r}"
    )

    # 4. Verificar que openpyxl importa
    check_openpyxl = subprocess.run(
        [str(python_bin), "-c", "import openpyxl; print('openpyxl', openpyxl.__version__)"],
        capture_output=True,
        text=True,
    )
    assert check_openpyxl.returncode == 0, (
        f"openpyxl no importa en el venv E2E.\n"
        f"stdout: {check_openpyxl.stdout}\nstderr: {check_openpyxl.stderr}"
    )

    # 5. Verificar que imageio-ffmpeg NO está en el venv
    check_imageio = subprocess.run(
        [str(python_bin), "-c", "import imageio_ffmpeg"],
        capture_output=True,
        text=True,
    )
    assert check_imageio.returncode != 0, (
        "imageio-ffmpeg NO debería estar en el venv del plugin; "
        "pertenece al worker de Catalyst (servidor)."
    )
