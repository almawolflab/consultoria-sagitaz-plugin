"""AW-189 — Fase 4 TDD: doctor.py — self-check con guarda dura de dominio."""
import json
import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
DOCTOR = PLUGIN_ROOT / "scripts" / "doctor.py"


def _make_oauth(tmp_path: Path, api_domain: str) -> Path:
    """Crea un fichero OAuth fake en tmp_path para los tests de doctor.py."""
    oauth = tmp_path / "zoho_crm_oauth.json"
    oauth.write_text(json.dumps({
        "client_id": "fake_client_id",
        "client_secret": "fake_client_secret",
        "refresh_token": "fake_refresh_token",
        "api_domain": api_domain,
        "accounts_domain": "https://accounts.zoho.com",
    }))
    return oauth


def _run_doctor(env: dict) -> subprocess.CompletedProcess:
    """Ejecuta doctor.py con el entorno dado y captura la salida."""
    return subprocess.run(
        [sys.executable, str(DOCTOR)],
        env={**os.environ, **env},
        capture_output=True,
        text=True,
    )


def test_doctor_detecta_imageio(tmp_path):
    """doctor.py devuelve exit != 0 si imageio-ffmpeg está instalado en el venv."""
    # Simular un venv con imageio-ffmpeg "instalado": crear un paquete fake
    venv_dir = tmp_path / "venv"
    # Crear estructura mínima del venv fake para que doctor lo detecte
    site_pkgs = venv_dir / "lib" / "python3.x" / "site-packages"
    site_pkgs.mkdir(parents=True)
    # Crear un dist-info de imageio-ffmpeg para simular su presencia
    (site_pkgs / "imageio_ffmpeg-0.6.0.dist-info").mkdir()
    (site_pkgs / "imageio_ffmpeg-0.6.0.dist-info" / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: imageio-ffmpeg\nVersion: 0.6.0\n"
    )
    # También crear el directorio del paquete para que pip list lo detecte
    (site_pkgs / "imageio_ffmpeg").mkdir()
    (site_pkgs / "imageio_ffmpeg" / "__init__.py").write_text("")

    # OAuth OK (sandbox) para que no falle por otro check
    oauth = _make_oauth(tmp_path, "https://sandbox.zohoapis.com")

    env = {
        "DOCTOR_VENV_DIR": str(venv_dir),
        "DOCTOR_OAUTH_PATH": str(oauth),
        "DOCTOR_SKIP_NETWORK": "1",
    }
    result = _run_doctor(env)
    assert result.returncode != 0, (
        f"doctor.py debería fallar cuando imageio-ffmpeg está en el venv.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    # Debe mencionar imageio en la salida
    combined = result.stdout + result.stderr
    assert "imageio" in combined.lower(), (
        f"doctor.py debería mencionar imageio-ffmpeg en la salida.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def test_doctor_bloquea_dominio_productivo(tmp_path):
    """doctor.py devuelve exit != 0 si el OAuth apunta a www.zohoapis.com."""
    oauth = _make_oauth(tmp_path, "https://www.zohoapis.com")
    env = {
        "DOCTOR_OAUTH_PATH": str(oauth),
        "DOCTOR_SKIP_NETWORK": "1",
        # No hay venv real: usar el Python del sistema para el check de versión
        "DOCTOR_VENV_DIR": "",
    }
    result = _run_doctor(env)
    assert result.returncode != 0, (
        f"doctor.py debería fallar cuando api_domain es www.zohoapis.com.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    combined = result.stdout + result.stderr
    assert any(kw in combined.lower() for kw in ("produccion", "producción", "www.zohoapis", "prohibido")), (
        f"doctor.py debería mencionar el dominio productivo en la salida.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def _find_python311():
    """Encuentra el intérprete Python 3.11+ disponible en el sistema."""
    import shutil
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


def test_doctor_ok_sandbox(tmp_path):
    """doctor.py devuelve exit 0 cuando el entorno está OK (sandbox + openpyxl disponible)."""
    python311 = _find_python311()
    if python311 is None:
        import pytest
        pytest.skip("No se encontró Python 3.11+ en el sistema para este test")

    # Crear un venv con Python 3.11+ para que el check [A] pase
    venv_dir = tmp_path / "venv"
    subprocess.run([python311, "-m", "venv", str(venv_dir)], check=True)
    if os.name == "nt":
        python = venv_dir / "Scripts" / "python.exe"
    else:
        python = venv_dir / "bin" / "python"

    # Instalar openpyxl
    subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "openpyxl==3.1.5", "et-xmlfile==2.0.0"],
        check=True,
    )

    oauth = _make_oauth(tmp_path, "https://sandbox.zohoapis.com")

    env = {
        "DOCTOR_VENV_DIR": str(venv_dir),
        "DOCTOR_OAUTH_PATH": str(oauth),
        "DOCTOR_SKIP_NETWORK": "1",
    }
    result = _run_doctor(env)
    assert result.returncode == 0, (
        f"doctor.py debería pasar en sandbox con openpyxl instalado.\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
