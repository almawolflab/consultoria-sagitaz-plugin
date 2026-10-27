"""Tests del cliente CRM: rechazo de producción y refresh-on-401 con 1 reintento (sin red)."""
import io
import json
import urllib.error
import urllib.request

import pytest

from parametrizacion.crm import CrmClient

CREDS = {
    "api_domain": "https://sandbox.zohoapis.com",
    "accounts_domain": "https://accounts.zoho.com",
    "client_id": "cid", "client_secret": "csec", "refresh_token": "rt", "org_id": "693026068",
}


class _Resp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_rechaza_produccion():
    bad = dict(CREDS, api_domain="https://www.zohoapis.com")
    with pytest.raises(RuntimeError):
        CrmClient(creds=bad)


def test_refresh_on_401_reintenta_una_vez(monkeypatch):
    state = {"tokens": 0, "crm": 0}

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if "oauth/v2/token" in url:
            state["tokens"] += 1
            return _Resp({"access_token": f"AT{state['tokens']}"})
        state["crm"] += 1
        if state["crm"] == 1:
            raise urllib.error.HTTPError(
                url, 401, "Unauthorized", {}, io.BytesIO(b'{"code":"INVALID_TOKEN"}'))
        return _Resp({"roles": [{"id": "r1", "display_label": "JLT CEO"}]})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = CrmClient(creds=CREDS)
    out = client.get("/settings/roles")

    assert out == {"roles": [{"id": "r1", "display_label": "JLT CEO"}]}
    assert state["crm"] == 2, "debe reintentar la llamada CRM exactamente una vez"
    assert state["tokens"] == 2, "debe refrescar el token (inicial + tras el 401)"


def test_error_no_401_no_reintenta(monkeypatch):
    state = {"crm": 0}

    def fake_urlopen(req, timeout=None):
        url = req.full_url
        if "oauth/v2/token" in url:
            return _Resp({"access_token": "AT"})
        state["crm"] += 1
        raise urllib.error.HTTPError(url, 400, "Bad Request", {}, io.BytesIO(b'{"code":"INVALID_DATA"}'))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    client = CrmClient(creds=CREDS)
    with pytest.raises(RuntimeError):
        client.get("/settings/fields", params={"module": "Leads"})
    assert state["crm"] == 1, "un 400 no debe reintentarse"
