"""Tests del loader/validador del IR y del orden topológico por depends_on."""
import json
from pathlib import Path

import pytest

from parametrizacion import ir as ir_mod

FIX = Path(__file__).resolve().parent / "fixtures" / "ir_jaque_r1r3.json"


def test_ordered_pone_dependencias_antes():
    ir = ir_mod.load_ir(str(FIX))
    order = [it["id"] for _, it in ir_mod.ordered_items(ir)]
    # roles: el padre antes que los hijos
    assert order.index("role-ceo") < order.index("role-gerente")
    assert order.index("role-gerente") < order.index("role-comerciales")
    assert order.index("role-admin") < order.index("role-cobranza")
    # workflow después de los campos que referencia
    assert order.index("fld-origen") < order.index("wf-recordatorio")
    assert order.index("fld-fecha-recordatorio") < order.index("wf-recordatorio")


def test_validate_rechaza_item_sin_payload():
    with pytest.raises(ValueError):
        ir_mod.validate({"fields": [{"id": "x", "match": {"module": "Leads", "api_name": "A"}}]})


def test_validate_rechaza_seccion_no_lista():
    with pytest.raises(ValueError):
        ir_mod.validate({"fields": {"id": "x", "match": {}, "payload": {}}})


def test_validate_rechaza_id_duplicado():
    with pytest.raises(ValueError):
        ir_mod.validate({"fields": [
            {"id": "dup", "match": {"module": "Leads", "api_name": "A"}, "payload": {}},
            {"id": "dup", "match": {"module": "Leads", "api_name": "B"}, "payload": {}},
        ]})


def test_ordered_detecta_dependencia_inexistente():
    with pytest.raises(ValueError):
        ir_mod.ordered_items({"roles": [
            {"id": "r", "match": {"name": "R"}, "payload": {}, "depends_on": ["no-existe"]},
        ]})


def test_ordered_detecta_ciclo():
    with pytest.raises(ValueError):
        ir_mod.ordered_items({"roles": [
            {"id": "a", "match": {"name": "A"}, "payload": {}, "depends_on": ["b"]},
            {"id": "b", "match": {"name": "B"}, "payload": {}, "depends_on": ["a"]},
        ]})
