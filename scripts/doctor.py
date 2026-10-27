#!/usr/bin/env python3
"""doctor.py — Self-check del entorno del plugin consultoria-sagitaz.

Verifica los requisitos mínimos para que el pipeline funcione correctamente:

Checks OBLIGATORIOS (exit != 0 si alguno falla):
  [A] Python >= 3.11 en el venv (o sistema si no hay venv).
  [B] openpyxl importa sin error en el venv.
  [C] imageio-ffmpeg NO está instalado en el venv.
  [D] Existe el fichero OAuth del consultor (zoho_crm_oauth.json).
  [E] api_domain NO apunta a producción (www.zohoapis.com) — reutiliza la regla de crm.py.

Checks OPCIONALES/AVISOS (no cambian el exit code):
  [F] Alcanzabilidad de TRANSCRIPCIONES_ENDPOINT (requiere red).

Uso:
    python3 scripts/doctor.py [--venv-dir <path>] [--oauth-path <path>]

Env vars para tests (no requieren argumentos):
    DOCTOR_VENV_DIR      Directorio del venv a verificar (vacío = usar python del sistema).
    DOCTOR_OAUTH_PATH    Ruta al fichero OAuth del consultor.
    DOCTOR_SKIP_NETWORK  Si es "1", omite el check de red (F).
    TRANSCRIPCIONES_ENDPOINT  URL a verificar (check F).

NUNCA imprime secretos ni credenciales.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent

# ---------------------------------------------------------------------------
# Importar la regla de dominio desde crm.py (no duplicar el literal)
# ---------------------------------------------------------------------------
# Importamos CrmClient para reutilizar su guarda dura de dominio en __init__,
# pero sin instanciar con credenciales reales. La regla está en crm.py:56-59.

def _is_production_domain(api_domain: str) -> bool:
    """Reutiliza la regla de dominio de parametrizacion/crm.py (no duplica el literal).

    Instancia CrmClient con credenciales fake y captura el RuntimeError que lanza
    si el dominio es productivo. Así la regla vive solo en crm.py.
    """
    sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
    try:
        from parametrizacion.crm import CrmClient
    except ImportError:
        # Si crm.py no está disponible (entorno de test aislado), usamos la regla inline
        # solo como fallback de seguridad, pero el check canónico es el de crm.py.
        return "www.zohoapis.com" in api_domain
    finally:
        if str(PLUGIN_ROOT / "scripts") in sys.path:
            sys.path.remove(str(PLUGIN_ROOT / "scripts"))

    fake_creds = {
        "client_id": "x",
        "client_secret": "x",
        "refresh_token": "x",
        "api_domain": api_domain,
        "accounts_domain": "https://accounts.zoho.com",
    }
    try:
        CrmClient(creds=fake_creds)
        return False  # No lanzó RuntimeError → dominio no productivo
    except RuntimeError:
        return True  # Lanzó RuntimeError → dominio productivo (www.zohoapis.com)


# ---------------------------------------------------------------------------
# Helpers para inspeccionar el venv
# ---------------------------------------------------------------------------

def _venv_python(venv_dir: Path) -> Path:
    """Ruta al intérprete Python del venv según el SO."""
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def _venv_site_packages(venv_dir: Path):
    """Genera los directorios site-packages del venv (puede haber más de uno)."""
    lib = venv_dir / "lib"
    if lib.exists():
        for version_dir in lib.iterdir():
            sp = version_dir / "site-packages"
            if sp.exists():
                yield sp
    # Windows: Lib/site-packages
    win_sp = venv_dir / "Lib" / "site-packages"
    if win_sp.exists():
        yield win_sp


def _package_in_site_packages(venv_dir: Path, package_name: str) -> bool:
    """Busca si un paquete está presente en los site-packages del venv.

    Comprueba tanto el directorio del paquete como los dist-info/egg-info.
    """
    name_normalized = package_name.lower().replace("-", "_")
    for sp in _venv_site_packages(venv_dir):
        # Buscar dist-info
        for entry in sp.iterdir():
            entry_name = entry.name.lower().replace("-", "_")
            if entry_name.startswith(name_normalized) and (
                entry_name.endswith(".dist-info") or entry_name.endswith(".egg-info")
            ):
                return True
        # Buscar directorio del paquete
        pkg_dir = sp / name_normalized
        if pkg_dir.exists():
            return True
    return False


def _python_version_ok(python_exe: Path) -> tuple[bool, str]:
    """Verifica que Python >= 3.11 en el intérprete dado."""
    result = subprocess.run(
        [str(python_exe), "-c",
         "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False, f"No se pudo ejecutar {python_exe}: {result.stderr.strip()}"
    version_str = result.stdout.strip()
    parts = version_str.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return False, f"Versión no reconocida: {version_str!r}"
    if (major, minor) < (3, 11):
        return False, f"Python {version_str} < 3.11 (requerido: 3.11+)"
    return True, f"Python {version_str} OK"


def _openpyxl_importa(python_exe: Path) -> tuple[bool, str]:
    """Verifica que openpyxl importa correctamente en el intérprete dado."""
    result = subprocess.run(
        [str(python_exe), "-c", "import openpyxl; print(openpyxl.__version__)"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True, f"openpyxl {result.stdout.strip()} OK"
    return False, f"openpyxl no importa: {result.stderr.strip()[:200]}"


# ---------------------------------------------------------------------------
# Checks individuales
# ---------------------------------------------------------------------------

def check_python_version(venv_dir: Path | None) -> tuple[bool, str]:
    """[A] Python >= 3.11."""
    if venv_dir and venv_dir.exists():
        python = _venv_python(venv_dir)
        if not python.exists():
            return False, f"Interprete no encontrado en el venv: {python}"
    else:
        python = Path(sys.executable)
    return _python_version_ok(python)


def check_openpyxl(venv_dir: Path | None) -> tuple[bool, str]:
    """[B] openpyxl importa en el venv."""
    if venv_dir and venv_dir.exists():
        python = _venv_python(venv_dir)
        if not python.exists():
            return False, f"Interprete no encontrado en el venv: {python}"
    else:
        python = Path(sys.executable)
    return _openpyxl_importa(python)


def check_no_imageio(venv_dir: Path | None) -> tuple[bool, str]:
    """[C] imageio-ffmpeg NO está en el venv."""
    if not venv_dir or not venv_dir.exists():
        # Sin venv, buscar en el entorno actual
        result = subprocess.run(
            [sys.executable, "-c", "import imageio_ffmpeg"],
            capture_output=True,
        )
        if result.returncode == 0:
            return False, "imageio-ffmpeg encontrado en el entorno actual (debe eliminarse)"
        return True, "imageio-ffmpeg no encontrado en el entorno actual OK"

    if _package_in_site_packages(venv_dir, "imageio-ffmpeg"):
        return False, (
            "imageio-ffmpeg encontrado en el venv — debe eliminarse; "
            "la transcripcion pertenece al servidor (catalyst), no al plugin"
        )
    return True, "imageio-ffmpeg ausente del venv OK"


def check_oauth_exists(oauth_path: Path) -> tuple[bool, str]:
    """[D] Existe el fichero OAuth del consultor."""
    if not oauth_path.exists():
        return False, (
            f"Fichero OAuth no encontrado: {oauth_path}\n"
            "  Ejecuta el flujo OAuth de la connected app (AW-186) para generarlo."
        )
    return True, f"Fichero OAuth encontrado: {oauth_path}"


def check_api_domain(oauth_path: Path) -> tuple[bool, str]:
    """[E] api_domain en el OAuth no es productivo (www.zohoapis.com)."""
    if not oauth_path.exists():
        return False, f"No se puede verificar api_domain: falta {oauth_path}"
    try:
        data = json.loads(oauth_path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        return False, f"Error leyendo {oauth_path}: {e}"

    api_domain = data.get("api_domain", "")
    if not api_domain:
        return False, "api_domain no encontrado en el fichero OAuth"

    if _is_production_domain(api_domain):
        return False, (
            f"api_domain apunta a PRODUCCION: {api_domain}\n"
            "  Prohibido (spike §10.4 / crm.py:56-59). Usa el sandbox (sandbox.zohoapis.com)."
        )
    return True, f"api_domain OK: {api_domain} (no productivo)"


def check_endpoint_reachable(endpoint: str) -> tuple[bool, str]:
    """[F] OPCIONAL: alcanzabilidad del endpoint de transcripciones."""
    if not endpoint:
        return True, "TRANSCRIPCIONES_ENDPOINT no configurado (aviso: omitido)"
    try:
        req = urllib.request.Request(endpoint, method="HEAD")
        with urllib.request.urlopen(req, timeout=5):
            pass
        return True, f"Endpoint alcanzable: {endpoint}"
    except urllib.error.HTTPError as e:
        # HTTP error = servidor responde; consideramos alcanzable
        return True, f"Endpoint responde (HTTP {e.code}): {endpoint}"
    except Exception as e:
        return False, f"Endpoint NO alcanzable: {endpoint} — {e}"


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def run_doctor(venv_dir: Path | None, oauth_path: Path, skip_network: bool) -> int:
    """Ejecuta todos los checks y muestra un resumen.

    Retorna 0 si todos los obligatorios pasan, 1 si alguno falla.
    """
    endpoint = os.environ.get("TRANSCRIPCIONES_ENDPOINT", "").strip()

    # --- Checks obligatorios ---
    mandatory = [
        ("A", "Python >= 3.11",       lambda: check_python_version(venv_dir)),
        ("B", "openpyxl importa",      lambda: check_openpyxl(venv_dir)),
        ("C", "Sin imageio-ffmpeg",    lambda: check_no_imageio(venv_dir)),
        ("D", "Fichero OAuth existe",  lambda: check_oauth_exists(oauth_path)),
        ("E", "api_domain no productivo", lambda: check_api_domain(oauth_path)),
    ]

    print("=" * 60)
    print("  doctor.py — Self-check del plugin consultoria-sagitaz")
    print("=" * 60)
    print()
    print("Checks obligatorios:")

    failures = []
    for code, label, fn in mandatory:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"Excepcion inesperada: {e}"
        status = "OK" if ok else "FAIL"
        icon = "✓" if ok else "✗"
        print(f"  [{code}] {icon} {label}: {msg}")
        if not ok:
            failures.append((code, label, msg))

    print()

    # --- Checks opcionales ---
    print("Avisos (opcionales):")
    if skip_network:
        print("  [F] — Check de red omitido (DOCTOR_SKIP_NETWORK=1)")
    else:
        ok, msg = check_endpoint_reachable(endpoint)
        icon = "✓" if ok else "!"
        print(f"  [F] {icon} Endpoint transcripciones: {msg}")

    print()

    if failures:
        print(f"RESULTADO: FALLO — {len(failures)} check(s) obligatorio(s) fallaron:")
        for code, label, msg in failures:
            print(f"  [{code}] {label}: {msg}")
        return 1

    print("RESULTADO: OK — todos los checks obligatorios pasaron.")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Self-check del entorno del plugin consultoria-sagitaz."
    )
    parser.add_argument("--venv-dir", default=None,
                        help="Directorio del venv (por defecto: $DOCTOR_VENV_DIR o inferido de bootstrap).")
    parser.add_argument("--oauth-path", default=None,
                        help="Ruta al fichero OAuth (por defecto: $DOCTOR_OAUTH_PATH o DEFAULT_CREDS de crm.py).")
    args = parser.parse_args()

    # Resolver venv_dir
    venv_dir_str = args.venv_dir or os.environ.get("DOCTOR_VENV_DIR", "").strip()
    venv_dir = Path(venv_dir_str) if venv_dir_str else None

    # Resolver oauth_path
    if args.oauth_path:
        oauth_path = Path(args.oauth_path)
    elif os.environ.get("DOCTOR_OAUTH_PATH", "").strip():
        oauth_path = Path(os.environ["DOCTOR_OAUTH_PATH"].strip())
    else:
        # Usar DEFAULT_CREDS de crm.py
        sys.path.insert(0, str(PLUGIN_ROOT / "scripts"))
        try:
            from parametrizacion.crm import DEFAULT_CREDS
            oauth_path = Path(DEFAULT_CREDS)
        except ImportError:
            oauth_path = PLUGIN_ROOT / "scripts" / "zoho_crm_oauth.json"
        finally:
            if str(PLUGIN_ROOT / "scripts") in sys.path:
                sys.path.remove(str(PLUGIN_ROOT / "scripts"))

    skip_network = os.environ.get("DOCTOR_SKIP_NETWORK", "").strip() == "1"

    sys.exit(run_doctor(venv_dir=venv_dir, oauth_path=oauth_path, skip_network=skip_network))


if __name__ == "__main__":
    main()
