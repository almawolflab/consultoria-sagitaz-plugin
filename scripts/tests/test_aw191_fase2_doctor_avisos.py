"""AW-191 Fase 2 — doctor: [D]/[E] como avisos, --require-oauth (AC-4, AC-5).

AC-4: doctor sin flags y sin OAuth → exit 0 si [A][B][C] pasan; [D]/[E] son avisos.
AC-5: doctor --require-oauth sin OAuth → exit 1.
"""
import os
import sys
import subprocess
from pathlib import Path

import pytest

# conftest.py añade scripts/ al sys.path
import doctor as doc_mod


SCRIPTS = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_doctor(*extra_args, env=None, venv_dir=None, oauth_path=None):
    """Ejecuta doctor.py como subproceso y devuelve (returncode, stdout)."""
    args = [sys.executable, str(SCRIPTS / "doctor.py")]
    if venv_dir:
        args += ["--venv-dir", str(venv_dir)]
    if oauth_path:
        args += ["--oauth-path", str(oauth_path)]
    args.extend(extra_args)

    e = dict(os.environ)
    e["DOCTOR_SKIP_NETWORK"] = "1"
    if env:
        e.update(env)
    result = subprocess.run(args, capture_output=True, text=True, env=e)
    return result.returncode, result.stdout + result.stderr


# ---------------------------------------------------------------------------
# Helpers para tests unitarios de run_doctor
# ---------------------------------------------------------------------------

def _fake_venv(tmp_path: Path) -> Path:
    """Crea un venv mínimo funcional con openpyxl para que [A][B][C] pasen."""
    import venv as venv_mod
    venv_dir = tmp_path / "venv"
    venv_mod.create(str(venv_dir), with_pip=True)
    python = venv_dir / "bin" / "python"
    subprocess.run(
        [str(python), "-m", "pip", "install", "--quiet", "openpyxl"],
        check=True, capture_output=True,
    )
    return venv_dir


# ---------------------------------------------------------------------------
# AC-4 — sin flags y sin OAuth → exit 0
# ---------------------------------------------------------------------------

class TestDoctorAvisosExitCode:
    """[D]/[E] como avisos: sin OAuth → exit 0 si [A][B][C] pasan."""

    def test_sin_oauth_sin_flag_exit_0(self, tmp_path):
        """Con venv OK y sin OAuth → exit 0 (AC-4)."""
        venv_dir = _fake_venv(tmp_path)
        oauth_path = tmp_path / "nonexistent_oauth.json"  # NO existe

        rc = doc_mod.run_doctor(
            venv_dir=venv_dir,
            oauth_path=oauth_path,
            skip_network=True,
            require_oauth=False,
        )
        assert rc == 0, "Sin --require-oauth y sin OAuth debe ser exit 0"

    def test_sin_oauth_con_require_oauth_exit_1(self, tmp_path):
        """Con venv OK y sin OAuth pero --require-oauth → exit 1 (AC-5)."""
        venv_dir = _fake_venv(tmp_path)
        oauth_path = tmp_path / "nonexistent_oauth.json"

        rc = doc_mod.run_doctor(
            venv_dir=venv_dir,
            oauth_path=oauth_path,
            skip_network=True,
            require_oauth=True,
        )
        assert rc == 1, "Con --require-oauth y sin OAuth debe ser exit 1"

    def test_abc_falla_siempre_exit_1(self, tmp_path):
        """[A] falla (venv vacío sin intérprete) → exit 1 siempre, con o sin --require-oauth."""
        bad_venv = tmp_path / "bad_venv"
        bad_venv.mkdir()
        # Venv sin intérprete → [A] y [B] fallarán
        oauth_path = tmp_path / "nonexistent_oauth.json"

        rc_no_flag = doc_mod.run_doctor(
            venv_dir=bad_venv,
            oauth_path=oauth_path,
            skip_network=True,
            require_oauth=False,
        )
        assert rc_no_flag == 1, "[A]/[B] siempre obligatorios incluso sin --require-oauth"


class TestDoctorEProduccionFalloDuro:
    """Refinamiento de seguridad AW-191: [E] es FALLO DURO por defecto (sin --require-oauth)
    si existe un token que apunta a producción o está corrupto; pero si NO hay token es solo
    aviso (la Fase 1 no necesita OAuth)."""

    def _write_oauth(self, tmp_path, api_domain=None, drop_domain=False):
        import json
        p = tmp_path / "zoho_crm_oauth.json"
        data = {"client_id": "x", "client_secret": "x", "refresh_token": "x",
                "accounts_domain": "https://accounts.zoho.eu"}
        if not drop_domain:
            data["api_domain"] = api_domain
        p.write_text(json.dumps(data))
        return p

    def test_token_produccion_falla_sin_require_oauth(self, tmp_path):
        """Token EXISTE y apunta a producción → exit 1 aunque no se pase --require-oauth."""
        venv_dir = _fake_venv(tmp_path)
        oauth = self._write_oauth(tmp_path, "https://www.zohoapis.eu")  # producción EU
        rc = doc_mod.run_doctor(venv_dir=venv_dir, oauth_path=oauth,
                                skip_network=True, require_oauth=False)
        assert rc == 1, "Un token de producción existente debe ser fallo duro por defecto"

    def test_token_corrupto_sin_api_domain_falla(self, tmp_path):
        """Token EXISTE pero sin clave api_domain → fallo duro por defecto (fichero inválido)."""
        venv_dir = _fake_venv(tmp_path)
        oauth = self._write_oauth(tmp_path, drop_domain=True)
        rc = doc_mod.run_doctor(venv_dir=venv_dir, oauth_path=oauth,
                                skip_network=True, require_oauth=False)
        assert rc == 1, "Un token presente pero inválido debe ser fallo duro por defecto"

    def test_token_sandbox_exit_0(self, tmp_path):
        """Token EXISTE y es sandbox → exit 0 por defecto."""
        venv_dir = _fake_venv(tmp_path)
        oauth = self._write_oauth(tmp_path, "https://sandbox.zohoapis.eu")
        rc = doc_mod.run_doctor(venv_dir=venv_dir, oauth_path=oauth,
                                skip_network=True, require_oauth=False)
        assert rc == 0, "Un token sandbox no debe bloquear"


# ---------------------------------------------------------------------------
# AC-4/AC-5 — subproceso: verificar el flag CLI --require-oauth
# ---------------------------------------------------------------------------

class TestDoctorSubprocesoFlags:
    """Tests de integración: doctor.py como subproceso con y sin --require-oauth."""

    def test_sin_flag_sin_oauth_exit_0(self, tmp_path):
        """doctor.py sin flags, venv OK, sin OAuth → exit 0."""
        venv_dir = _fake_venv(tmp_path)
        oauth_path = tmp_path / "no_oauth.json"

        rc, out = _run_doctor(
            venv_dir=venv_dir,
            oauth_path=oauth_path,
        )
        assert rc == 0, f"Esperado exit 0, got {rc}. Output:\n{out}"

    def test_con_require_oauth_sin_oauth_exit_1(self, tmp_path):
        """doctor.py --require-oauth, venv OK, sin OAuth → exit 1."""
        venv_dir = _fake_venv(tmp_path)
        oauth_path = tmp_path / "no_oauth.json"

        rc, out = _run_doctor(
            "--require-oauth",
            venv_dir=venv_dir,
            oauth_path=oauth_path,
        )
        assert rc == 1, f"Esperado exit 1, got {rc}. Output:\n{out}"

    def test_env_require_oauth_sin_oauth_exit_1(self, tmp_path):
        """DOCTOR_REQUIRE_OAUTH=1 activa el mismo gate que --require-oauth."""
        venv_dir = _fake_venv(tmp_path)
        oauth_path = tmp_path / "no_oauth.json"

        rc, out = _run_doctor(
            venv_dir=venv_dir,
            oauth_path=oauth_path,
            env={"DOCTOR_REQUIRE_OAUTH": "1"},
        )
        assert rc == 1, f"Esperado exit 1 con DOCTOR_REQUIRE_OAUTH=1, got {rc}. Output:\n{out}"

    def test_de_exit_0_con_oauth_valido(self, tmp_path):
        """Con venv OK y OAuth sandbox → exit 0 con o sin --require-oauth."""
        import json
        venv_dir = _fake_venv(tmp_path)
        oauth_path = tmp_path / "zoho_crm_oauth.json"
        oauth_path.write_text(json.dumps({
            "client_id": "x", "client_secret": "x", "refresh_token": "x",
            "api_domain": "https://sandbox.zohoapis.eu",
            "accounts_domain": "https://accounts.zoho.eu",
        }))

        rc, out = _run_doctor(
            "--require-oauth",
            venv_dir=venv_dir,
            oauth_path=oauth_path,
        )
        assert rc == 0, f"Con OAuth válido y --require-oauth esperado exit 0. Output:\n{out}"
