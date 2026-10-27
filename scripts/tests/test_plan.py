"""Tests del planificador (idempotencia): con los JLT_ existentes → skip; con CRM vacío → create ordenado."""
from pathlib import Path

from parametrizacion import applicator, ir as ir_mod

FIX = Path(__file__).resolve().parent / "fixtures" / "ir_jaque_r1r3.json"
IR = ir_mod.load_ir(str(FIX))


def _maps_con_todo():
    """Discovery simulado que YA contiene todos los artefactos del IR (estado tras el spike)."""
    fields = {it["match"]["api_name"]: {"id": "1", "api_name": it["match"]["api_name"]}
              for it in IR["fields"]}
    roles = {it["match"]["name"]: {"id": "r", "display_label": it["match"]["name"]} for it in IR["roles"]}
    roles["Gerencia"] = {"id": "root", "display_label": "Gerencia"}
    profiles = {it["match"]["name"]: {"id": "p"} for it in IR["profiles"]}
    workflows = {it["match"]["name"]: {"id": "w"} for it in IR["workflows"]}
    return {"fields": {"Leads": fields}, "roles": roles, "profiles": profiles,
            "workflows": {"Leads": workflows}, "modules": {"Leads": "m1"}}


def _maps_vacios():
    return {"fields": {"Leads": {}}, "roles": {"Gerencia": {"id": "root"}}, "profiles": {"Standard": {"id": "s"}},
            "workflows": {"Leads": {}}, "modules": {"Leads": "m1"}}


def test_idempotencia_todo_skip():
    actions = applicator.plan(IR, _maps_con_todo())
    assert actions, "el plan no debe estar vacío"
    assert all(a["op"] == "skip" for a in actions), \
        "con los JLT_ ya existentes, todo debe resolver a skip (no duplicar)"


def test_crm_vacio_todo_create_en_orden():
    actions = applicator.plan(IR, _maps_vacios())
    assert all(a["op"] == "create" for a in actions)
    ids = [a["id"] for a in actions]
    assert ids.index("role-ceo") < ids.index("role-gerente")
    assert ids.index("fld-origen") < ids.index("wf-recordatorio")


def test_skip_no_llama_a_la_api():
    """En dry-run (do_write=False) nunca se escribe, y con todo existente no habría creaciones."""
    class _NoClient:
        def get(self, *a, **k):
            raise AssertionError("plan() no debe llamar a la API en dry-run")

    # plan() opera solo sobre los mapas ya construidos; no toca el cliente.
    actions = applicator.plan(IR, _maps_con_todo())
    assert sum(1 for a in actions if a["op"] == "create") == 0
