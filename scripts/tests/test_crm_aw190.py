"""Tests para AW-190 — resolución única del path OAuth en crm.py (AC-2, AC-3, AC-6).

Migrados en AW-196: la ruta base ya NO es $CLAUDE_PLUGIN_DATA (que no llega a los scripts
de skills) sino bootstrap.data_dir(), configurable con $CONSULTORIA_SAGITAZ_DATA.
Todos los tests son offline (monkeypatch de CONSULTORIA_SAGITAZ_DATA y tmp_path).
La guarda de dominio productivo y los tests existentes deben seguir verdes.
"""
import os
import json
import pytest
from pathlib import Path

# conftest.py ya añade scripts/ al sys.path
from parametrizacion import crm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_oauth(path, api_domain="https://sandbox.zohoapis.eu"):
    """Escribe un zoho_crm_oauth.json mínimo en la ruta indicada."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "client_id": "cid",
        "client_secret": "csec",
        "refresh_token": "rt",
        "api_domain": api_domain,
        "accounts_domain": "https://accounts.zoho.eu",
    }
    path.write_text(json.dumps(data))
    return path


# ---------------------------------------------------------------------------
# AC-2: plugin_data_oauth_path()  — migrado a data_dir() (AW-196)
# ---------------------------------------------------------------------------

class TestPluginDataOauthPath:
    """plugin_data_oauth_path() devuelve data_dir()/zoho_crm_oauth.json (nunca None)."""

    def test_usa_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert crm.plugin_data_oauth_path() == str(tmp_path / "zoho_crm_oauth.json")

    def test_ignora_claude_plugin_data(self, monkeypatch, tmp_path):
        """CLAUDE_PLUGIN_DATA ya no influye (no llega a scripts Bash)."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "ignorar"))
        result = crm.plugin_data_oauth_path()
        assert result == str(tmp_path / "zoho_crm_oauth.json")

    def test_ruta_contiene_nombre_correcto(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        result = crm.plugin_data_oauth_path()
        assert os.path.basename(result) == "zoho_crm_oauth.json"


# ---------------------------------------------------------------------------
# AC-2: resolve_oauth_path(for_write=True)  — siempre data_dir() (AW-196)
# ---------------------------------------------------------------------------

class TestResolveOauthPathForWrite:
    """resolve_oauth_path(for_write=True) escribe siempre en data_dir()."""

    def test_devuelve_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        result = crm.resolve_oauth_path(for_write=True)
        assert result == str(tmp_path / "zoho_crm_oauth.json")

    def test_no_cae_a_default_creds(self, monkeypatch, tmp_path):
        """for_write nunca usa DEFAULT_CREDS: la ruta canónica es data_dir()."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        result = crm.resolve_oauth_path(for_write=True)
        assert result != crm.DEFAULT_CREDS
        assert str(tmp_path) in result


# ---------------------------------------------------------------------------
# AC-3: resolve_oauth_path(for_write=False)  — data_dir() con fallback a DEFAULT_CREDS
# ---------------------------------------------------------------------------

class TestResolveOauthPathForRead:
    """resolve_oauth_path(for_write=False) prioriza data_dir() si el fichero existe."""

    def test_prefiere_data_dir_si_existe(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        oauth = tmp_path / "zoho_crm_oauth.json"
        _write_oauth(oauth)
        result = crm.resolve_oauth_path(for_write=False)
        assert result == str(oauth)

    def test_cae_a_default_si_data_dir_no_existe(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path / "empty"))
        monkeypatch.setattr(crm, "DEFAULT_CREDS", str(tmp_path / "scripts" / "zoho_crm_oauth.json"))
        scripts_oauth = tmp_path / "scripts" / "zoho_crm_oauth.json"
        _write_oauth(scripts_oauth)
        result = crm.resolve_oauth_path(for_write=False)
        assert result == str(scripts_oauth)

    def test_devuelve_preferida_si_ninguno_existe(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        monkeypatch.setattr(crm, "DEFAULT_CREDS", str(tmp_path / "scripts" / "zoho_crm_oauth.json"))
        # Ninguno de los dos ficheros existe → devuelve la ruta de data_dir (la preferida)
        result = crm.resolve_oauth_path(for_write=False)
        assert result == str(tmp_path / "zoho_crm_oauth.json")

    def test_sin_data_dir_file_y_default_existe(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path / "empty"))
        monkeypatch.setattr(crm, "DEFAULT_CREDS", str(tmp_path / "zoho_crm_oauth.json"))
        _write_oauth(tmp_path / "zoho_crm_oauth.json")
        result = crm.resolve_oauth_path(for_write=False)
        assert result == str(tmp_path / "zoho_crm_oauth.json")

    def test_sin_data_dir_file_y_default_no_existe(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path / "empty"))
        monkeypatch.setattr(crm, "DEFAULT_CREDS", str(tmp_path / "scripts" / "zoho_crm_oauth.json"))
        # Nada existe → devuelve la preferida (data_dir())
        result = crm.resolve_oauth_path(for_write=False)
        assert result == str(tmp_path / "empty" / "zoho_crm_oauth.json")


# ---------------------------------------------------------------------------
# AC-3: load_creds(path=None) usa resolve_oauth_path
# ---------------------------------------------------------------------------

class TestLoadCredsResolve:
    """load_creds(path=None) resuelve automáticamente la ruta del token."""

    def test_load_creds_sin_path_usa_data_dir(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        oauth = tmp_path / "zoho_crm_oauth.json"
        _write_oauth(oauth)
        # No lanzamos excepción → lo leyó de data_dir()
        creds = crm.load_creds(path=None)
        assert creds["client_id"] == "cid"

    def test_load_creds_sin_path_cae_a_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path / "empty"))
        monkeypatch.setattr(crm, "DEFAULT_CREDS", str(tmp_path / "zoho_crm_oauth.json"))
        _write_oauth(tmp_path / "zoho_crm_oauth.json")
        creds = crm.load_creds(path=None)
        assert creds["refresh_token"] == "rt"

    def test_load_creds_con_path_explicito_lo_usa(self, monkeypatch, tmp_path):
        """path explícito sigue teniendo prioridad sobre resolve_oauth_path."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path / "data"))
        explicit = tmp_path / "explicit" / "zoho_crm_oauth.json"
        _write_oauth(explicit, api_domain="https://sandbox.zohoapis.com")
        creds = crm.load_creds(path=str(explicit))
        assert creds["api_domain"] == "https://sandbox.zohoapis.com"


# ---------------------------------------------------------------------------
# AC-6: Guarda de dominio productivo sigue intacta
# ---------------------------------------------------------------------------

class TestGuardaDominioCrmAW190:
    """Regresión: la guarda RuntimeError para www.zohoapis.com sigue activa."""

    def test_rechaza_produccion(self):
        bad_creds = {
            "api_domain": "https://www.zohoapis.com",
            "accounts_domain": "https://accounts.zoho.com",
            "client_id": "x", "client_secret": "x", "refresh_token": "x",
        }
        with pytest.raises(RuntimeError, match="www.zohoapis.com"):
            crm.CrmClient(creds=bad_creds)

    def test_acepta_sandbox(self):
        ok_creds = {
            "api_domain": "https://sandbox.zohoapis.eu",
            "accounts_domain": "https://accounts.zoho.eu",
            "client_id": "x", "client_secret": "x", "refresh_token": "x",
        }
        client = crm.CrmClient(creds=ok_creds)
        assert client is not None
