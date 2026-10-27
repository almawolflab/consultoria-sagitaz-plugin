"""Tests del aplicador de workflows endurecido (CRM mockeado, sin red)."""
import pytest

from parametrizacion import applicator


class _FakeClient:
    """Registra las llamadas POST y devuelve ids sintéticos."""
    def __init__(self):
        self.posts = []

    def post(self, path, body=None, params=None):
        self.posts.append((path, body))
        if path.endswith("/field_updates"):
            return {"field_updates": [{"code": "SUCCESS", "details": {"id": "FU1"}}]}
        if path.endswith("/workflow_rules"):
            return {"workflow_rules": [{"code": "SUCCESS", "details": {"id": "WF1"}}]}
        return {}

    def get(self, path, params=None):
        # verify → get_workflow_rules devuelve la regla creada
        if path.endswith("/workflow_rules"):
            return {"workflow_rules": [{"name": "T_ Asignar prioridad", "id": "WF1"}]}
        return {}


def _maps():
    return {"modules": {"Leads": "MOD_LEADS"},
            "fields": {"Leads": {"T_Prioridad": {"id": "FLD_PRIO", "api_name": "T_Prioridad"}}},
            "roles": {}, "profiles": {}, "workflows": {"Leads": {}}}


def _wf_item(action_type="field_update"):
    return {"id": "wf-x", "from": "5.1", "match": {"module": "Leads", "name": "T_ Asignar prioridad"},
            "payload": {"name": "T_ Asignar prioridad", "module": "Leads",
                        "trigger": {"on": "create_or_edit"},
                        "criteria": {"field": "T_Prioridad", "operator": "equal", "value": "Alta"},
                        "actions": [{"type": action_type, "field": "T_Prioridad", "value": "Alta"}]}}


def test_field_update_se_crea_antes_que_la_regla():
    client = _FakeClient()
    ok = applicator.apply_workflow(client, _wf_item(), _maps())
    assert ok is True
    paths = [p for p, _ in client.posts]
    assert paths == ["/settings/automation/field_updates", "/settings/automation/workflow_rules"], \
        "debe crear la acción field_update ANTES que la regla"
    # la regla referencia la acción por id + type
    _, rule_body = client.posts[1]
    acts = rule_body["workflow_rules"][0]["conditions"][0]["instant_actions"]["actions"]
    assert acts == [{"id": "FU1", "type": "field_updates"}]
    # execute_when create_or_edit lleva repeat + trigger_module
    ew = rule_body["workflow_rules"][0]["execute_when"]
    assert ew["type"] == "create_or_edit" and ew["details"]["repeat"] is True
    assert ew["details"]["trigger_module"]["id"] == "MOD_LEADS"


def test_field_update_usa_module_id_y_field_id():
    client = _FakeClient()
    applicator.apply_workflow(client, _wf_item(), _maps())
    _, fu_body = client.posts[0]
    fu = fu_body["field_updates"][0]
    assert fu["module"]["id"] == "MOD_LEADS"
    assert fu["field"]["id"] == "FLD_PRIO"
    assert fu["value"] == "Alta"


def test_tipo_de_accion_no_soportado_lanza_skipitem():
    client = _FakeClient()
    with pytest.raises(applicator.SkipItem):
        applicator.apply_workflow(client, _wf_item(action_type="task"), _maps())
    assert client.posts == [], "no debe escribir nada si la acción no está soportada"


def test_apply_registra_omitido_y_no_aborta(monkeypatch):
    # IR con un workflow de acción no soportada → omitido; el resto del plan sigue.
    ir = {"workflows": [_wf_item(action_type="task")]}
    maps = _maps()
    monkeypatch.setattr(applicator, "build_discovery", lambda client, ir: maps)
    res = applicator.apply(ir, _FakeClient(), do_write=True)
    estados = [r["status"] for r in res["results"]]
    assert "omitido" in estados
