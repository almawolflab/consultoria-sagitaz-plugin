"""Tests de la Fase 3: plantilla definitiva → IR ejecutable."""
import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

pytest.importorskip("openpyxl")

from parametrizacion import plantilla_io as P
from parametrizacion import plantilla_a_ir as A
from parametrizacion import ir as ir_mod


def _parsed(tmp_path, prop):
    d = P.cargar_descriptor()
    out = tmp_path / "def.xlsx"
    P.escribir_premarcada(d, prop, str(out))
    return d, P.leer_plantilla(str(out), d)


def test_slug():
    assert A._slug("Fecha de firma") == "Fecha_de_firma"
    assert A._slug("Nº de hijos") == "No_de_hijos"   # º (ordinal) → 'o' por NFKD
    assert A._slug("  ") == "campo"


def test_plantilla_a_ir_v1_y_manual(tmp_path):
    prop = {"Leads": [
        {"campo": "Origen", "tipo": "Lista de selección", "valores": ["Web", "Referido"]},
        {"campo": "Codigo interno", "tipo": "Fórmula"},          # mas_adelante → manual_todo
    ]}
    d, parsed = _parsed(tmp_path, prop)
    dercas_ir = json.loads((FIXTURES / "ir_jaque_r1r3.json").read_text(encoding="utf-8"))
    ir_final = A.plantilla_a_ir(parsed, dercas_ir, d, prefix="JL_", cliente="Jaque Legal")

    # campo v1 → fields
    f = next(x for x in ir_final["fields"] if x["payload"]["field_label"] == "Origen")
    assert f["match"]["module"] == "Leads"
    assert f["match"]["api_name"] == "JL_Origen"
    assert f["payload"]["data_type"] == "picklist"
    assert [v["display_value"] for v in f["payload"]["pick_list_values"]] == ["Web", "Referido"]
    # campo fórmula → manual_todo (no en fields)
    assert not any(x["payload"]["field_label"] == "Codigo interno" for x in ir_final["fields"])
    assert any("Codigo interno" in m["item"] for m in ir_final["manual_todo"])
    # roles/perfiles heredados del DERCAS
    assert len(ir_final["roles"]) == len(dercas_ir["roles"])
    assert len(ir_final["profiles"]) == len(dercas_ir["profiles"])
    assert ir_final["meta"]["source"] == "plantilla"


def test_ir_final_valida_y_ordena(tmp_path):
    prop = {"Leads": [{"campo": "Origen", "tipo": "Lista de selección", "valores": ["A"]}]}
    d, parsed = _parsed(tmp_path, prop)
    dercas_ir = json.loads((FIXTURES / "ir_jaque_r1r3.json").read_text(encoding="utf-8"))
    ir_final = A.plantilla_a_ir(parsed, dercas_ir, d, prefix="JL_")
    # no lanza (validate + ordered_items se ejecutan dentro); reconfirmamos
    assert ir_mod.validate(ir_final) is True
    orden = ir_mod.ordered_items(ir_final)
    assert len(orden) >= len(ir_final["fields"]) + len(ir_final["roles"])
