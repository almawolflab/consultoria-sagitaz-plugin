"""Tests del resumen legible del IR + plan_md (determinista, sin red).

Combina test_param_summary.py y test_param_plan_md.py del pipeline.
"""
import json
from pathlib import Path

from parametrizacion import summary

FIX = Path(__file__).resolve().parent / "fixtures"
IR = json.loads((FIX / "ir_jaque_r1r3.json").read_text(encoding="utf-8"))
V_BAJA = json.loads((FIX / "revision_baja.json").read_text(encoding="utf-8"))


def test_resumen_incluye_todos_los_items_ejecutables():
    md = summary.resumen_md(IR)
    # fidelidad: cada campo/rol/perfil/workflow del IR aparece por su nombre/label
    for f in IR["fields"]:
        assert f["payload"]["field_label"] in md
    for r in IR["roles"]:
        assert r["match"]["name"] in md
    for p in IR["profiles"]:
        assert p["match"]["name"] in md
    for w in IR["workflows"]:
        assert w["match"]["name"] in md
    # trazabilidad: algún req. de origen presente
    assert "5.1" in md and "5.3" in md


def test_resumen_lista_manual_todo():
    ir = dict(IR)
    ir["manual_todo"] = [{"from": "5.14", "item": "Integración WhatsApp", "why": "conector externo",
                          "spec": "configurar Woztell"}]
    md = summary.resumen_md(ir)
    assert "Integración WhatsApp" in md
    assert "conector externo" in md
    assert "- [ ]" in md          # checklist


def test_resumen_con_revision_incluye_puntuacion_y_defectos_graves():
    md = summary.resumen_md(IR, revision=V_BAJA)
    assert "55/100" in md
    assert "Revisión automática" in md
    # defecto de severidad alta del fixture
    assert "wf-blueprint-op" in md


def test_resumen_sin_revision_omite_ese_bloque():
    md = summary.resumen_md(IR, revision=None)
    assert "Revisión automática" not in md


def test_recuento_final():
    md = summary.resumen_md(IR)
    assert f"campos={len(IR['fields'])}" in md
    assert f"roles={len(IR['roles'])}" in md


# --- plan_md ---

ACTIONS = [
    {"section": "fields", "id": "f1", "op": "create", "label": "T_Prioridad", "module": "Leads", "from": "5.1"},
    {"section": "roles", "id": "r1", "op": "skip", "label": "T_ CEO", "module": None, "from": "10.2"},
]


def test_plan_md_incluye_ops_y_recuento():
    md = summary.plan_md(ACTIONS)
    assert "crear=1" in md and "omitir=1" in md
    assert "T_Prioridad" in md and "T_ CEO" in md
    assert "dry-run" in md
