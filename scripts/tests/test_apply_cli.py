"""Tests del CLI local apply_cli (AW-187 §6 Fase 3): dry-run por defecto y confirmación en --apply.

100% offline: CrmClient/load_creds/applicator mockeados; no abre red ni lee credenciales reales.
"""
import pathlib

import pytest

from parametrizacion import apply_cli

IR_FIX = str(pathlib.Path(__file__).resolve().parent / "fixtures" / "ir_jaque_r1r3.json")

CREDS = {"api_domain": "https://sandbox.zohoapis.com", "accounts_domain": "https://accounts.zoho.com",
         "client_id": "cid", "client_secret": "csec", "refresh_token": "rt", "org_id": "693026068"}


class _FakeClient:
    api = "https://sandbox.zohoapis.com"

    def __init__(self, *a, **k):
        pass


@pytest.fixture
def entorno(monkeypatch):
    """Mockea credenciales, cliente y aplicador; registra las llamadas a apply()."""
    calls = {"apply": []}

    def fake_apply(ir, client, do_write=False):
        calls["apply"].append({"do_write": do_write})
        return {"actions": [{"section": "fields", "id": "f1", "op": "create",
                             "label": "X", "module": "Leads", "from": "5.1"}],
                "results": []}

    monkeypatch.setattr(apply_cli, "load_creds", lambda *a, **k: dict(CREDS))
    monkeypatch.setattr(apply_cli, "CrmClient", lambda *a, **k: _FakeClient())
    monkeypatch.setattr(apply_cli.applicator, "apply", fake_apply)
    monkeypatch.setattr(apply_cli.applicator, "build_discovery", lambda client, ir: {})
    monkeypatch.setattr(apply_cli.applicator, "plan",
                        lambda ir, maps: [{"section": "fields", "id": "f1", "op": "create",
                                           "label": "X", "module": "Leads", "from": "5.1"}])
    return calls


def test_dry_run_por_defecto_no_escribe(entorno, monkeypatch):
    """Sin --apply: corre el plan con do_write=False y NUNCA con do_write=True."""
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("dry-run no debe pedir confirmación"))
    rc = apply_cli.main(["--ir", IR_FIX])
    assert rc == 0
    assert entorno["apply"] == [{"do_write": False}], "dry-run debe llamar a apply con do_write=False"


def test_apply_pide_confirmacion_y_cancela(entorno, monkeypatch):
    """Con --apply sin --yes: pide confirmación; si no se responde 'si', cancela sin escribir."""
    preguntas = []

    def fake_input(prompt=""):
        preguntas.append(prompt)
        return "no"

    monkeypatch.setattr("builtins.input", fake_input)
    rc = apply_cli.main(["--ir", IR_FIX, "--apply"])
    assert rc == 1, "cancelar debe devolver 1"
    assert preguntas, "con --apply (sin --yes) debe pedir confirmación"
    assert not any(c["do_write"] for c in entorno["apply"]), "cancelado: no debe escribir"


def test_apply_confirmado_escribe(entorno, monkeypatch):
    """Con --apply y confirmación 'si': escribe (do_write=True)."""
    monkeypatch.setattr("builtins.input", lambda *a: "si")
    rc = apply_cli.main(["--ir", IR_FIX, "--apply"])
    assert rc == 0
    assert {"do_write": True} in entorno["apply"]


def test_apply_yes_no_pregunta(entorno, monkeypatch):
    """Con --apply --yes: no pide confirmación y escribe."""
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("--yes no debe pedir confirmación"))
    rc = apply_cli.main(["--ir", IR_FIX, "--apply", "--yes"])
    assert rc == 0
    assert {"do_write": True} in entorno["apply"]
