"""Tests para AW-190 — authorize_crm.py escribe donde crm.py lee (AC-4).

Migrados en AW-196: la ruta base ya NO es $CLAUDE_PLUGIN_DATA sino bootstrap.data_dir()
(configurable con $CONSULTORIA_SAGITAZ_DATA). Todos offline: exchange_code y verify_org
mockeados.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# conftest.py ya añade scripts/ al sys.path para import authorize_crm


DUMMY_CLIENT_ID = "test-cid-190"
DUMMY_CLIENT_SECRET = "test-csec-190"
DUMMY_REFRESH_TOKEN = "1000.dummy-refresh-190.abc"
DUMMY_ACCESS_TOKEN = "1000.dummy-access-190.xyz"
DUMMY_API_DOMAIN = "https://sandbox.zohoapis.eu"
DUMMY_ACCOUNTS = "https://accounts.zoho.eu"
DUMMY_SCOPE = "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.org.READ"
DUMMY_ORG_ID = "190190190"

FAKE_TOKEN_RESPONSE = {
    "access_token": DUMMY_ACCESS_TOKEN,
    "refresh_token": DUMMY_REFRESH_TOKEN,
    "api_domain": DUMMY_API_DOMAIN,
    "accounts-server": DUMMY_ACCOUNTS,
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": DUMMY_SCOPE,
}

FAKE_ORG_SANDBOX = {
    "org": [{"zgid": DUMMY_ORG_ID, "type": "sandbox", "company_name": "Test Corp"}]
}


def _make_urlopen_mock(token_resp=None, org_resp=None):
    """Mock para urllib.request.urlopen que sirve respuestas fake."""
    class FakeResponse:
        def __init__(self, data):
            self._data = data
        def read(self):
            return self._data
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    def _urlopen(req, timeout=60):
        url = req.full_url if hasattr(req, "full_url") else req
        if "/oauth/v2/token" in url:
            return FakeResponse(json.dumps(token_resp or FAKE_TOKEN_RESPONSE).encode())
        if "/crm/v8/org" in url:
            return FakeResponse(json.dumps(org_resp or FAKE_ORG_SANDBOX).encode())
        raise AssertionError(f"URL inesperada en test: {url}")

    return _urlopen


# ---------------------------------------------------------------------------
# AC-4: DEFAULT_OUT resuelto desde resolve_oauth_path(for_write=True)
# ---------------------------------------------------------------------------

class TestDefaultOutResolve:
    """DEFAULT_OUT de authorize_crm debe provenir de crm.resolve_oauth_path(for_write=True)."""

    def test_resolve_for_write_apunta_a_data_dir(self, monkeypatch, tmp_path):
        """resolve_oauth_path(for_write=True) apunta a data_dir()/zoho_crm_oauth.json (AW-196)."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        from parametrizacion.crm import resolve_oauth_path
        expected = resolve_oauth_path(for_write=True)
        assert expected == str(tmp_path / "zoho_crm_oauth.json")

    def test_resolve_for_write_no_es_default_creds(self, monkeypatch, tmp_path):
        """for_write ya no cae en DEFAULT_CREDS (scripts/): la ruta canónica es data_dir()."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        from parametrizacion.crm import DEFAULT_CREDS, resolve_oauth_path
        expected = resolve_oauth_path(for_write=True)
        assert expected != DEFAULT_CREDS
        assert str(tmp_path) in expected


# ---------------------------------------------------------------------------
# AC-4: run_authorization_flow escribe en la ruta resuelta y crm.load_creds la lee
# ---------------------------------------------------------------------------

class TestRunAuthFlowWritesResolved:
    """run_authorization_flow escribe en resolve_oauth_path(for_write=True)."""

    def test_escribe_en_data_dir_y_load_creds_la_lee(self, monkeypatch, tmp_path):
        """Con CONSULTORIA_SAGITAZ_DATA=tmp, el token cae en tmp/ y crm.load_creds() lo encuentra."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        import authorize_crm as ac
        import importlib
        importlib.reload(ac)  # recalcula DEFAULT_OUT con la nueva env
        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", _make_urlopen_mock())

        # Ejecutamos el flujo completo con exchange_code/verify_org mockeados
        expected_out = str(tmp_path / "zoho_crm_oauth.json")
        ac.run_authorization_flow(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            code="1000.test-code-190",
            redirect_uri="http://127.0.0.1:19190/callback",
            accounts_url=DUMMY_ACCOUNTS,
            out_path=expected_out,
        )

        assert Path(expected_out).exists(), "El fichero debe estar en plugin_data"

        # crm.load_creds() sin path explícito debe encontrarlo (via resolve_oauth_path)
        from parametrizacion import crm
        creds = crm.load_creds(path=None)
        assert creds["client_id"] == DUMMY_CLIENT_ID
        assert creds["refresh_token"] == DUMMY_REFRESH_TOKEN

    def test_makedirs_crea_directorio_si_no_existe(self, monkeypatch, tmp_path):
        """authorize_crm hace makedirs antes de escribir (directorio puede no existir)."""
        sub = tmp_path / "deep" / "nested"
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(sub))
        import authorize_crm as ac
        import importlib
        importlib.reload(ac)
        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", _make_urlopen_mock())

        out_path = str(sub / "zoho_crm_oauth.json")
        # El directorio sub no existe aún — debe crearse
        ac.run_authorization_flow(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            code="1000.test-makedirs",
            redirect_uri="http://127.0.0.1:19191/callback",
            accounts_url=DUMMY_ACCOUNTS,
            out_path=out_path,
        )
        assert Path(out_path).exists()


# ---------------------------------------------------------------------------
# AC-4: DEFAULT_APP_CREDS también se busca en $CLAUDE_PLUGIN_DATA
# ---------------------------------------------------------------------------

class TestDefaultAppCreds:
    """resolve_app_creds_path: con data_dir() se busca ahí primero, luego en scripts/ (AW-196)."""

    def test_resolve_app_creds_sin_fichero_en_data_dir(self, monkeypatch, tmp_path):
        """Sin el fichero en data_dir(), la ruta de app creds cae en scripts/."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path / "empty"))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        import authorize_crm as ac
        result = ac.resolve_app_creds_path()
        assert "crm_connected_app.json" in result
        assert "scripts" in result or os.path.dirname(ac.__file__) in result

    def test_resolve_app_creds_con_fichero_en_data_dir(self, monkeypatch, tmp_path):
        """Con el fichero en data_dir(), devuelve esa ruta."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        app_creds = tmp_path / "crm_connected_app.json"
        app_creds.write_text('{"client_id":"x","client_secret":"y"}')
        import authorize_crm as ac
        result = ac.resolve_app_creds_path()
        assert result == str(app_creds)

    def test_resolve_app_creds_ignora_claude_plugin_data(self, monkeypatch, tmp_path):
        """CLAUDE_PLUGIN_DATA ya no influye: sin fichero en data_dir() cae a scripts/."""
        monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path / "empty"))
        monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "ignorar"))
        (tmp_path / "ignorar").mkdir(parents=True)
        (tmp_path / "ignorar" / "crm_connected_app.json").write_text("{}")
        import authorize_crm as ac
        result = ac.resolve_app_creds_path()
        assert str(tmp_path / "ignorar") not in result
        assert "crm_connected_app.json" in result
