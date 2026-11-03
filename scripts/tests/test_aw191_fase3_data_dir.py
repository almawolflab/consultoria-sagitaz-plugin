"""AW-191 Fase 3 — data_dir() determinista (AC-6, AC-7).

AC-6: doctor sin flags autodescubre data_dir()/venv → [B] verde.
AC-7: bootstrap crea el venv en data_dir()/venv; respeta CONSULTORIA_SAGITAZ_DATA / XDG_DATA_HOME.
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

# conftest.py añade scripts/ al sys.path
import bootstrap as bootstrap_mod
import doctor as doc_mod


# ---------------------------------------------------------------------------
# AC-7 — data_dir() resolución
# ---------------------------------------------------------------------------

class TestDataDir:
    """bootstrap.data_dir() resuelve la ruta determinista."""

    def test_override_consultoria_sagitaz_data(self, monkeypatch, tmp_path):
        """CONSULTORIA_SAGITAZ_DATA → esa ruta exacta."""
        override = tmp_path / "mi-data"
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(override))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = bootstrap_mod.data_dir()
        assert result == override

    def test_xdg_data_home_appends_consultoria(self, monkeypatch, tmp_path):
        """XDG_DATA_HOME → XDG_DATA_HOME/consultoria-sagitaz."""
        monkeypatch.delenv("CONSULTORIA_SAGITAZ_DATA", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        result = bootstrap_mod.data_dir()
        assert result == tmp_path / "consultoria-sagitaz"

    def test_default_sin_env(self, monkeypatch):
        """Sin vars → ~/.local/share/consultoria-sagitaz."""
        monkeypatch.delenv("CONSULTORIA_SAGITAZ_DATA", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = bootstrap_mod.data_dir()
        assert result == Path.home() / ".local" / "share" / "consultoria-sagitaz"

    def test_consultoria_data_tiene_prioridad_sobre_xdg(self, monkeypatch, tmp_path):
        """CONSULTORIA_SAGITAZ_DATA tiene prioridad sobre XDG_DATA_HOME."""
        override = tmp_path / "explicit-override"
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(override))
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        result = bootstrap_mod.data_dir()
        assert result == override

    def test_ignora_claude_plugin_data(self, monkeypatch, tmp_path):
        """CLAUDE_PLUGIN_DATA no afecta a data_dir() (no está en la cadena)."""
        monkeypatch.delenv("CONSULTORIA_SAGITAZ_DATA", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "plugin-data"))
        result = bootstrap_mod.data_dir()
        # Default: debe ser ~/.local/share/consultoria-sagitaz, NO el CLAUDE_PLUGIN_DATA
        assert result == Path.home() / ".local" / "share" / "consultoria-sagitaz"


# ---------------------------------------------------------------------------
# AC-7 — plugin_data_dir() delega a data_dir()
# ---------------------------------------------------------------------------

class TestPluginDataDirDelegates:
    """bootstrap.plugin_data_dir() devuelve lo mismo que data_dir()."""

    def test_plugin_data_dir_equals_data_dir(self, monkeypatch):
        monkeypatch.delenv("CONSULTORIA_SAGITAZ_DATA", raising=False)
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert bootstrap_mod.plugin_data_dir() == bootstrap_mod.data_dir()

    def test_plugin_data_dir_con_override(self, monkeypatch, tmp_path):
        override = tmp_path / "override"
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(override))
        assert bootstrap_mod.plugin_data_dir() == override


# ---------------------------------------------------------------------------
# AC-6 — doctor autodescubre data_dir()/venv (sin CLAUDE_PLUGIN_DATA)
# ---------------------------------------------------------------------------

class TestDoctorAutodescubreVenv:
    """doctor usa data_dir()/venv sin necesitar CLAUDE_PLUGIN_DATA."""

    def test_autodescubre_venv_en_data_dir(self, monkeypatch, tmp_path):
        """Con venv en data_dir()/venv → [B] verde (sin --venv-dir explícito)."""
        import venv as venv_mod

        # Poner data_dir() en tmp_path
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
        monkeypatch.delenv("DOCTOR_VENV_DIR", raising=False)

        # Crear venv real con openpyxl en data_dir()/venv
        venv_path = tmp_path / "venv"
        venv_mod.create(str(venv_path), with_pip=True)
        python = venv_path / "bin" / "python"
        subprocess.run(
            [str(python), "-m", "pip", "install", "--quiet", "openpyxl"],
            check=True, capture_output=True,
        )

        # resolve_venv_dir sin argumento debe encontrar data_dir()/venv
        # (porque bootstrap.plugin_data_dir() devuelve tmp_path y el venv existe)
        resolved = doc_mod.resolve_venv_dir(venv_dir_arg=None)
        assert resolved is not None
        assert resolved == venv_path

    def test_sin_venv_en_data_dir_devuelve_none(self, monkeypatch, tmp_path):
        """Sin venv en data_dir() → resolve_venv_dir devuelve None (usa python del sistema)."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
        monkeypatch.delenv("DOCTOR_VENV_DIR", raising=False)
        # No creamos el venv en tmp_path
        resolved = doc_mod.resolve_venv_dir(venv_dir_arg=None)
        assert resolved is None
