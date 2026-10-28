"""Tests para AW-190 — doctor.py autodescubrimiento venv + texto [D]/[E] (AC-1, AC-5).

Todos offline. Se monkeypatchean CLAUDE_PLUGIN_DATA y se crean venvs fake.
"""
import os
import sys
import json
from pathlib import Path
from io import StringIO

import pytest

# conftest.py añade scripts/ al path, pero doctor.py se importa con sys.path desde scripts/
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_venv(base: Path) -> Path:
    """Crea un venv fake mínimo (estructura de directorios sin intérprete real)."""
    venv_dir = base / "venv"
    # Crear la estructura básica del venv
    (venv_dir / "bin").mkdir(parents=True, exist_ok=True)
    # Crear un fake python binary (ejecutable) que reporte Python 3.11.0
    fake_python = venv_dir / "bin" / "python"
    fake_python.write_text(
        '#!/bin/sh\n'
        'if echo "$*" | grep -q "version_info"; then\n'
        '  echo "3.11.0"\n'
        'elif echo "$*" | grep -q "openpyxl"; then\n'
        '  echo "3.1.5"\n'
        '  exit 0\n'
        'else\n'
        '  exit 0\n'
        'fi\n'
    )
    fake_python.chmod(0o755)
    return venv_dir


def _add_scripts_to_path():
    """Ensure scripts/ is in sys.path for doctor.py imports."""
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))


# ---------------------------------------------------------------------------
# AC-1: sin --venv-dir, doctor resuelve bootstrap.plugin_data_dir()/venv
# ---------------------------------------------------------------------------

class TestDoctorVenvAutodescubrimiento:
    """Sin --venv-dir ni DOCTOR_VENV_DIR, doctor usa bootstrap.plugin_data_dir()/venv."""

    def test_venv_resuelto_desde_bootstrap_cuando_existe(self, monkeypatch, tmp_path, capsys):
        """Con venv fake en plugin_data/venv, doctor lo usa (no python del sistema)."""
        _add_scripts_to_path()
        import doctor
        import bootstrap

        # Crear venv fake
        venv_dir = _make_fake_venv(tmp_path)

        # Monkeypatch bootstrap.plugin_data_dir para devolver tmp_path
        monkeypatch.setattr(bootstrap, "plugin_data_dir", lambda: tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))

        # Sin --venv-dir ni DOCTOR_VENV_DIR, resolve_venv_dir debe dar tmp_path/venv
        resolved = doctor.resolve_venv_dir(venv_dir_arg=None)
        assert resolved is not None
        assert str(tmp_path) in str(resolved)
        assert "venv" in str(resolved)

    def test_venv_no_existe_devuelve_none(self, monkeypatch, tmp_path):
        """Si el venv de bootstrap no existe, devuelve None (python del sistema)."""
        _add_scripts_to_path()
        import doctor
        import bootstrap

        # Monkeypatch bootstrap.plugin_data_dir para devolver tmp_path (sin venv)
        monkeypatch.setattr(bootstrap, "plugin_data_dir", lambda: tmp_path)
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
        # No creamos venv en tmp_path

        resolved = doctor.resolve_venv_dir(venv_dir_arg=None)
        assert resolved is None

    def test_venv_arg_explicito_tiene_prioridad(self, monkeypatch, tmp_path):
        """--venv-dir explícito siempre tiene prioridad sobre autodescubrimiento."""
        _add_scripts_to_path()
        import doctor

        explicit_dir = tmp_path / "explicit_venv"
        explicit_dir.mkdir()
        resolved = doctor.resolve_venv_dir(venv_dir_arg=str(explicit_dir))
        assert resolved == explicit_dir

    def test_doctor_venv_dir_env_tiene_prioridad(self, monkeypatch, tmp_path):
        """DOCTOR_VENV_DIR env var tiene prioridad sobre autodescubrimiento."""
        _add_scripts_to_path()
        import doctor

        env_dir = tmp_path / "env_venv"
        env_dir.mkdir()
        monkeypatch.setenv("DOCTOR_VENV_DIR", str(env_dir))
        resolved = doctor.resolve_venv_dir(venv_dir_arg=None)
        assert resolved == env_dir


# ---------------------------------------------------------------------------
# AC-1: oauth_path default usa crm.resolve_oauth_path
# ---------------------------------------------------------------------------

class TestDoctorOauthPathResolve:
    """oauth_path por defecto usa crm.resolve_oauth_path(for_write=False)."""

    def test_oauth_path_default_usa_resolve(self, monkeypatch, tmp_path):
        _add_scripts_to_path()
        import doctor
        from parametrizacion import crm

        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path))
        oauth = tmp_path / "zoho_crm_oauth.json"
        oauth.write_text('{}')

        resolved = doctor.resolve_oauth_path(oauth_path_arg=None)
        # Debe coincidir con lo que dice crm.resolve_oauth_path
        expected = crm.resolve_oauth_path(for_write=False)
        assert str(resolved) == expected

    def test_oauth_path_arg_explicito_tiene_prioridad(self, monkeypatch, tmp_path):
        _add_scripts_to_path()
        import doctor

        explicit = tmp_path / "custom_oauth.json"
        explicit.write_text('{}')
        resolved = doctor.resolve_oauth_path(oauth_path_arg=str(explicit))
        assert resolved == explicit


# ---------------------------------------------------------------------------
# AC-5: [D] y [E] contienen el texto "solo necesario para /implementar"
# ---------------------------------------------------------------------------

class TestDoctorLabelsImplementar:
    """[D] y [E] incluyen el texto 'solo necesario para /implementar'."""

    def test_label_D_contiene_texto_implementar(self):
        _add_scripts_to_path()
        import doctor
        import importlib
        importlib.reload(doctor)

        TEXTO = "solo necesario para /implementar"
        # run_doctor debe incluir ese texto en los labels o mensajes de [D] y [E]
        # Lo verificamos chequeando que el texto aparece en run_doctor's output
        from io import StringIO
        import sys

        # Crear un oauth path que no existe (para que [D] falle y muestre su label)
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            non_existent = Path(tmpdir) / "no_existe.json"
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                doctor.run_doctor(
                    venv_dir=None,
                    oauth_path=non_existent,
                    skip_network=True,
                )
            except SystemExit:
                pass
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        assert TEXTO in output, (
            f"El texto '{TEXTO}' debe aparecer en la salida de run_doctor para [D] o [E]"
        )

    def test_label_E_contiene_texto_implementar(self):
        _add_scripts_to_path()
        import doctor
        import importlib
        importlib.reload(doctor)

        TEXTO = "solo necesario para /implementar"

        # Crear un oauth con api_domain producción para que [E] falle con su label
        import tempfile, json
        with tempfile.TemporaryDirectory() as tmpdir:
            oauth_path = Path(tmpdir) / "zoho_crm_oauth.json"
            oauth_path.write_text(json.dumps({
                "api_domain": "https://www.zohoapis.com",
                "client_id": "x",
            }))
            old_stdout = sys.stdout
            sys.stdout = StringIO()
            try:
                doctor.run_doctor(
                    venv_dir=None,
                    oauth_path=oauth_path,
                    skip_network=True,
                )
            except SystemExit:
                pass
            output = sys.stdout.getvalue()
            sys.stdout = old_stdout

        assert TEXTO in output, (
            f"El texto '{TEXTO}' debe aparecer en la salida de run_doctor para [E]"
        )

    def test_fallo_D_sigue_dando_exit_1(self):
        """[D] falla → exit != 0 (no cambió el comportamiento)."""
        _add_scripts_to_path()
        import doctor

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            non_existent = Path(tmpdir) / "no_existe.json"
            result = doctor.run_doctor(
                venv_dir=None,
                oauth_path=non_existent,
                skip_network=True,
            )
        assert result != 0
