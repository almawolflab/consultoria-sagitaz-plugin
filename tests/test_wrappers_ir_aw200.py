"""AW-200 #5 — Los wrappers del IR invocan `validar_semantico`.

- `skills/dercas/scripts/validar_ir.py`: un IR estructuralmente válido pero semánticamente roto
  (data_type inexistente, módulo desalineado, picklist vacía) sale con rc=1.
- `skills/plan/scripts/revision_ir.py`: los errores semánticos van al bloque **bloqueante**
  (`errores`) y los avisos a **observaciones**.
"""
import importlib
import json
import sys
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
DERCAS_SCRIPTS = PLUGIN / "skills" / "dercas" / "scripts"
PLAN_SCRIPTS = PLUGIN / "skills" / "plan" / "scripts"


def _get_validar_ir():
    if str(DERCAS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(DERCAS_SCRIPTS))
    sys.modules.pop("validar_ir", None)
    return importlib.import_module("validar_ir")


def _get_revision_ir():
    if str(PLAN_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(PLAN_SCRIPTS))
    sys.modules.pop("revision_ir", None)
    return importlib.import_module("revision_ir")


def _ir_dt_malo():
    return {"fields": [{
        "id": "fld-x", "from": "R1",
        "match": {"module": "Leads", "api_name": "X_Campo"},
        "payload": {"module": "Leads", "field_label": "Campo X", "data_type": "noexiste"},
    }]}


def _ir_modulo_desalineado():
    return {"fields": [{
        "id": "fld-y", "from": "R1",
        "match": {"module": "Leads", "api_name": "Y_Campo"},
        "payload": {"module": "Deals", "field_label": "Campo Y", "data_type": "text"},
    }]}


# ---------------------------------------------------------------- validar_ir (dercas)

def test_validar_ir_data_type_invalido_falla(tmp_path):
    mod = _get_validar_ir()
    f = tmp_path / "ir.json"
    f.write_text(json.dumps(_ir_dt_malo()))
    assert mod.main([str(f)]) == 1


def test_validar_ir_modulo_desalineado_falla(tmp_path):
    mod = _get_validar_ir()
    f = tmp_path / "ir.json"
    f.write_text(json.dumps(_ir_modulo_desalineado()))
    assert mod.main([str(f)]) == 1


def test_validar_ir_gold_sigue_pasando(tmp_path):
    mod = _get_validar_ir()
    fixture = PLUGIN / "scripts" / "tests" / "fixtures" / "ir_jaque_r1r3.json"
    assert mod.main([str(fixture)]) == 0


# ---------------------------------------------------------------- revision_ir (plan)

def test_revision_ir_error_semantico_en_errores():
    mod = _get_revision_ir()
    res = mod.revisar(_ir_dt_malo())
    assert res["valido"] is False
    assert any("noexiste" in e for e in res["errores"])


def test_revision_ir_aviso_raiz_en_observaciones():
    mod = _get_revision_ir()
    ir = {"roles": [{"id": "r1", "from": "R1", "match": {"name": "CEO"}, "payload": {}}]}
    res = mod.revisar(ir)
    assert res["valido"] is True                      # avisos no bloquean
    assert not any("CEO" in e for e in res["errores"])
    assert any("CEO" in o or "raíz" in o.lower() or "raiz" in o.lower()
               for o in res["observaciones"])


def test_revision_ir_gold_valido():
    mod = _get_revision_ir()
    gold = json.loads((PLUGIN / "scripts" / "tests" / "fixtures" / "ir_jaque_r1r3.json").read_text())
    res = mod.revisar(gold)
    assert res["valido"] is True
    assert res["errores"] == []
