"""AW-196 — Fase 2: hook SessionStart materializa userConfig → data_dir().

Cubre:
- plugin.json: userConfig crm_client_id / crm_client_secret (sensitive).
- onboard.materialize_userconfig: escribe transcripciones.json y crm_connected_app.json
  (0600, idempotente, merge sin pisar con vacíos, sin loguear secretos).
- fetch_transcripciones: resuelve endpoint/token desde data_dir()/transcripciones.json
  (precedencia CLI > env > fichero); _data_dir() coincide con bootstrap.data_dir().
- crm.resolve_oauth_path / authorize_crm.resolve_app_creds_path → data_dir().
"""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

# conftest de scripts/tests añade scripts/ al sys.path
import bootstrap as bootstrap_mod  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HOOKS = PLUGIN_ROOT / "hooks"
DERS_SCRIPTS = PLUGIN_ROOT / "skills" / "ders" / "scripts"


# ---------------------------------------------------------------------------
# Fase 1 — plugin.json: userConfig crm_client_id / crm_client_secret
# ---------------------------------------------------------------------------

def test_plugin_json_tiene_crm_client_id_y_secret():
    data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    uc = data["userConfig"]
    assert "crm_client_id" in uc, "falta userConfig.crm_client_id"
    assert "crm_client_secret" in uc, "falta userConfig.crm_client_secret"


def test_plugin_json_crm_secret_es_sensitive():
    data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    uc = data["userConfig"]
    assert uc["crm_client_secret"].get("sensitive") is True, (
        "crm_client_secret debe ser sensitive"
    )
    # client_id no es secreto, no debe marcarse sensitive (evita ocultarlo sin motivo)
    assert uc["crm_client_id"].get("sensitive") is not True


# ---------------------------------------------------------------------------
# Fase 2 — onboard.materialize_userconfig
# ---------------------------------------------------------------------------

def _import_onboard():
    if str(HOOKS) not in sys.path:
        sys.path.insert(0, str(HOOKS))
    import onboard  # noqa: E402
    return onboard


def _mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


def test_materialize_transcripciones_crea_json_0600(monkeypatch, tmp_path):
    ob = _import_onboard()
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_ENDPOINT", "https://ep.example")
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_TEAM_TOKEN", "TKN123")
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_CRM_CLIENT_ID", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_CRM_CLIENT_SECRET", raising=False)

    written = ob.materialize_userconfig(tmp_path)

    f = tmp_path / "transcripciones.json"
    assert f.exists()
    assert json.loads(f.read_text()) == {"endpoint": "https://ep.example", "token": "TKN123"}
    assert _mode(f) == 0o600
    assert "transcripciones.json" in written
    assert "crm_connected_app.json" not in written


def test_materialize_crm_crea_json_0600(monkeypatch, tmp_path):
    ob = _import_onboard()
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_ENDPOINT", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_TEAM_TOKEN", raising=False)
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_CRM_CLIENT_ID", "1000.ABC")
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_CRM_CLIENT_SECRET", "sek")

    ob.materialize_userconfig(tmp_path)

    f = tmp_path / "crm_connected_app.json"
    assert f.exists()
    assert json.loads(f.read_text()) == {"client_id": "1000.ABC", "client_secret": "sek"}
    assert _mode(f) == 0o600


def test_materialize_sin_valores_no_crea_ficheros(monkeypatch, tmp_path):
    ob = _import_onboard()
    for k in ("TRANSCRIPCIONES_ENDPOINT", "TRANSCRIPCIONES_TEAM_TOKEN",
              "CRM_CLIENT_ID", "CRM_CLIENT_SECRET"):
        monkeypatch.delenv(f"CLAUDE_PLUGIN_OPTION_{k}", raising=False)

    written = ob.materialize_userconfig(tmp_path)

    assert written == []
    assert not (tmp_path / "transcripciones.json").exists()
    assert not (tmp_path / "crm_connected_app.json").exists()


def test_materialize_idempotente(monkeypatch, tmp_path):
    ob = _import_onboard()
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_ENDPOINT", "https://ep")
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_TEAM_TOKEN", "T")
    ob.materialize_userconfig(tmp_path)
    content1 = (tmp_path / "transcripciones.json").read_text()
    ob.materialize_userconfig(tmp_path)
    content2 = (tmp_path / "transcripciones.json").read_text()
    assert content1 == content2
    assert _mode(tmp_path / "transcripciones.json") == 0o600


def test_materialize_no_pisa_con_vacios(monkeypatch, tmp_path):
    """Un valor ausente en env NO borra el valor previo del fichero (merge)."""
    ob = _import_onboard()
    f = tmp_path / "transcripciones.json"
    f.write_text(json.dumps({"endpoint": "https://previo", "token": "PREVIO"}))
    # Solo llega el endpoint nuevo; el token no está en env → se conserva el previo.
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_ENDPOINT", "https://nuevo")
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_TEAM_TOKEN", raising=False)

    ob.materialize_userconfig(tmp_path)

    data = json.loads(f.read_text())
    assert data["endpoint"] == "https://nuevo"
    assert data["token"] == "PREVIO", "no debe pisar el token previo con vacío"


def test_materialize_env_vacio_no_pisa(monkeypatch, tmp_path):
    """Env presente pero vacío se trata como ausente (no pisa)."""
    ob = _import_onboard()
    f = tmp_path / "crm_connected_app.json"
    f.write_text(json.dumps({"client_id": "ID", "client_secret": "SEC"}))
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_CRM_CLIENT_ID", "")
    monkeypatch.setenv("CLAUDE_PLUGIN_OPTION_CRM_CLIENT_SECRET", "   ")

    ob.materialize_userconfig(tmp_path)

    data = json.loads(f.read_text())
    assert data == {"client_id": "ID", "client_secret": "SEC"}


def test_onboard_integration_materializa_y_no_filtra_secretos(tmp_path):
    """onboard.py (subproceso) materializa transcripciones.json sin filtrar el token."""
    # venv fake que pasa venv_is_ok (import openpyxl → exit 0) para no instalar nada
    venv_bin = tmp_path / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    fake_py = venv_bin / "python"
    fake_py.write_text("#!/bin/sh\nexit 0\n")
    fake_py.chmod(fake_py.stat().st_mode | stat.S_IEXEC)

    SECRET = "SUPER_SECRET_TOKEN_999"
    env = dict(os.environ)
    env["CONSULTORIA_SAGITAZ_DATA"] = str(tmp_path)
    env["CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_ENDPOINT"] = "https://ep.example"
    env["CLAUDE_PLUGIN_OPTION_TRANSCRIPCIONES_TEAM_TOKEN"] = SECRET

    res = subprocess.run(
        [sys.executable, str(HOOKS / "onboard.py")],
        env=env, capture_output=True, text=True,
    )
    assert res.returncode == 0
    f = tmp_path / "transcripciones.json"
    assert f.exists()
    assert json.loads(f.read_text())["token"] == SECRET
    assert SECRET not in res.stdout, "el token no debe aparecer en stdout"
    assert SECRET not in res.stderr, "el token no debe aparecer en stderr"


# ---------------------------------------------------------------------------
# Fase 3 — fetch_transcripciones lee de data_dir()/transcripciones.json
# ---------------------------------------------------------------------------

def _import_fetch():
    if str(DERS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(DERS_SCRIPTS))
    if "fetch_transcripciones" in sys.modules:
        del sys.modules["fetch_transcripciones"]
    import importlib
    return importlib.import_module("fetch_transcripciones")


class _RecordingUrlopen:
    """Mock de urlopen que registra la Request y devuelve un cuerpo fijo."""

    def __init__(self, body):
        self.body = json.dumps(body).encode()
        self.captured = None

    def __call__(self, req, *a, **k):
        self.captured = req
        import unittest.mock as mock
        cm = mock.MagicMock()
        cm.__enter__ = mock.Mock(return_value=cm)
        cm.__exit__ = mock.Mock(return_value=False)
        cm.read = mock.Mock(return_value=self.body)
        return cm


def test_fetch_usa_bootstrap_data_dir(monkeypatch, tmp_path):
    """fetch reutiliza bootstrap.data_dir() (DRY): el fichero se busca en esa ruta."""
    fetch = _import_fetch()
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    # fetch comparte el mismo módulo bootstrap que el resto del plugin
    assert fetch.bootstrap.data_dir() == bootstrap_mod.data_dir()


def test_fetch_lee_endpoint_y_token_de_json(monkeypatch, tmp_path):
    """Sin env ni CLI, fetch resuelve endpoint/token desde data_dir()/transcripciones.json."""
    fetch = _import_fetch()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "transcripciones.json").write_text(
        json.dumps({"endpoint": "https://fromjson", "token": "JSONTOKEN"}))
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(data_dir))
    monkeypatch.delenv("TRANSCRIPCIONES_ENDPOINT", raising=False)
    monkeypatch.delenv("TEAM_API_TOKEN", raising=False)

    out = tmp_path / "out.txt"
    rec = _RecordingUrlopen({"status": "ok", "reuniones": [], "n": 0})
    monkeypatch.setattr("urllib.request.urlopen", rec)

    rc = fetch.main(["--cliente", "tufisio", "--out", str(out)])

    assert rc == 0
    assert "https://fromjson/transcripciones" in rec.captured.full_url
    assert rec.captured.headers.get("X-team-token") == "JSONTOKEN"


def test_fetch_cli_gana_sobre_json(monkeypatch, tmp_path):
    fetch = _import_fetch()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "transcripciones.json").write_text(
        json.dumps({"endpoint": "https://fromjson", "token": "JSONTOKEN"}))
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(data_dir))
    monkeypatch.delenv("TRANSCRIPCIONES_ENDPOINT", raising=False)
    monkeypatch.delenv("TEAM_API_TOKEN", raising=False)

    out = tmp_path / "out.txt"
    rec = _RecordingUrlopen({"status": "ok", "reuniones": [], "n": 0})
    monkeypatch.setattr("urllib.request.urlopen", rec)

    rc = fetch.main(["--cliente", "x", "--out", str(out),
                     "--endpoint", "https://cli", "--token", "CLITOKEN"])
    assert rc == 0
    assert "https://cli/transcripciones" in rec.captured.full_url
    assert rec.captured.headers.get("X-team-token") == "CLITOKEN"


def test_fetch_env_gana_sobre_json(monkeypatch, tmp_path):
    fetch = _import_fetch()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "transcripciones.json").write_text(
        json.dumps({"endpoint": "https://fromjson", "token": "JSONTOKEN"}))
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(data_dir))
    monkeypatch.setenv("TRANSCRIPCIONES_ENDPOINT", "https://fromenv")
    monkeypatch.setenv("TEAM_API_TOKEN", "ENVTOKEN")

    out = tmp_path / "out.txt"
    rec = _RecordingUrlopen({"status": "ok", "reuniones": [], "n": 0})
    monkeypatch.setattr("urllib.request.urlopen", rec)

    rc = fetch.main(["--cliente", "x", "--out", str(out)])
    assert rc == 0
    assert "https://fromenv/transcripciones" in rec.captured.full_url
    assert rec.captured.headers.get("X-team-token") == "ENVTOKEN"


# ---------------------------------------------------------------------------
# Fase 4 — rutas OAuth / app-creds basadas en data_dir() (cierra parcado AW-191)
# ---------------------------------------------------------------------------

def test_crm_plugin_data_oauth_path_usa_data_dir(monkeypatch, tmp_path):
    from parametrizacion import crm
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    assert crm.plugin_data_oauth_path() == str(tmp_path / "zoho_crm_oauth.json")


def test_crm_resolve_oauth_for_write_en_data_dir(monkeypatch, tmp_path):
    from parametrizacion import crm
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    assert crm.resolve_oauth_path(for_write=True) == str(tmp_path / "zoho_crm_oauth.json")


def test_crm_resolve_oauth_ignora_claude_plugin_data(monkeypatch, tmp_path):
    """CLAUDE_PLUGIN_DATA ya NO influye (no llega a Bash de skills; AW-196)."""
    from parametrizacion import crm
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "otro"))
    assert crm.resolve_oauth_path(for_write=True) == str(tmp_path / "zoho_crm_oauth.json")


def test_crm_resolve_oauth_for_read_prefiere_data_dir_si_existe(monkeypatch, tmp_path):
    from parametrizacion import crm
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    token = tmp_path / "zoho_crm_oauth.json"
    token.write_text("{}")
    assert crm.resolve_oauth_path(for_write=False) == str(token)


def test_authorize_resolve_app_creds_en_data_dir(monkeypatch, tmp_path):
    import authorize_crm as ac
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    creds = tmp_path / "crm_connected_app.json"
    creds.write_text(json.dumps({"client_id": "x", "client_secret": "y"}))
    assert ac.resolve_app_creds_path() == str(creds)


def test_authorize_resolve_app_creds_cae_a_scripts_si_no_en_data_dir(monkeypatch, tmp_path):
    import authorize_crm as ac
    monkeypatch.setenv("CONSULTORIA_SAGITAZ_DATA", str(tmp_path))
    monkeypatch.delenv("CLAUDE_PLUGIN_DATA", raising=False)
    # Sin fichero en data_dir → cae a scripts/
    result = ac.resolve_app_creds_path()
    assert result.endswith("scripts/crm_connected_app.json") or "scripts" in result
    assert str(tmp_path) not in result


def test_guarda_sandbox_crm_intacta(monkeypatch):
    """La guarda de dominio productivo en CrmClient sigue activa (AW-191)."""
    from parametrizacion import crm
    with pytest.raises(RuntimeError, match="sandbox"):
        crm.CrmClient(creds={
            "api_domain": "https://www.zohoapis.com",
            "accounts_domain": "https://accounts.zoho.com",
            "client_id": "x", "client_secret": "y", "refresh_token": "z",
        })
