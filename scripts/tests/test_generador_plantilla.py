"""Tests del generador de la Fase 2: IR → propuestas de plantilla + resumen.

Usa el fixture `ir_jaque_r1r3.json` (IR real, sin LLM). Verifica el agrupado por módulo, el round-trip
por la plantilla, la clasificación en 3 cubos del resumen y la neutralidad (no delata IA).
"""
import json
import pathlib
import re

import pytest

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

pytest.importorskip("openpyxl")

from parametrizacion import plantilla_io as P
from parametrizacion import generador_plantilla as G


def _ir():
    return json.loads((FIXTURES / "ir_jaque_r1r3.json").read_text(encoding="utf-8"))


def test_display_y_bucket():
    d = P.cargar_descriptor()
    assert P.display_de_zoho("picklist", d) == "Lista de selección"
    assert P.display_de_zoho("date", d) == "Fecha"
    assert P.bucket_de_zoho("picklist", d) == "v1"
    assert P.bucket_de_zoho("date", d) == "v1"
    assert P.bucket_de_zoho("formula", d) == "mas_adelante"
    assert P.bucket_de_zoho("lookup", d) == "mas_adelante"
    assert P.bucket_de_zoho("imageupload", d) == "manual"


def test_ir_a_propuestas():
    d = P.cargar_descriptor()
    prop = G.ir_a_propuestas(_ir(), d)
    assert set(prop) == {"Leads"}                 # el fixture solo toca Leads
    leads = prop["Leads"]
    assert len(leads) == 4
    origen = next(r for r in leads if "Origen" in r["campo"])
    assert origen["tipo"] == "Lista de selección"
    assert len(origen["valores"]) == 4


def test_roundtrip_por_plantilla(tmp_path):
    d = P.cargar_descriptor()
    prop = G.ir_a_propuestas(_ir(), d)
    out = tmp_path / "pre.xlsx"
    P.escribir_premarcada(d, prop, str(out))
    r = P.leer_plantilla(str(out), d)
    nuevos = r["modulos"]["Leads"]["nuevos"]
    assert len(nuevos) == 4
    assert all(n["origen"] == "DERCAS" and n["amarillo"] for n in nuevos)


def test_resumen_3_cubos_y_neutral():
    d = P.cargar_descriptor()
    res = G.resumen_plantilla(_ir(), d)
    for sec in ("Se puede montar por API", "Automatizable más adelante",
                "Requiere configuración manual", "Recuento por módulo"):
        assert sec in res
    # tablas con roles/perfiles/workflows del IR
    assert "JLT CEO" in res and "JLT Comercial" in res
    # neutralidad: sin frases que delaten automatización/IA (por frase, no subcadena)
    low = res.lower()
    assert "inteligencia artificial" not in low
    assert "ir.json" not in low
    assert "automáticamente" not in low
    assert "generado autom" not in low
    assert not re.search(r"\bIA\b", res)          # 'IA' como palabra suelta


def test_resumen_manual_y_mas_adelante():
    d = P.cargar_descriptor()
    ir = _ir()
    # inyectar un campo 'mas_adelante' (fórmula) y uno manual + un manual_todo
    ir["fields"].append({"from": "9.1", "match": {"module": "Deals", "api_name": "X_Formula"},
                         "payload": {"module": "Deals", "field_label": "X Fórmula", "data_type": "formula"}})
    ir["manual_todo"] = [{"from": "5.14", "item": "Integración WhatsApp", "why": "conector externo"}]
    res = G.resumen_plantilla(ir, d)
    assert "X Fórmula" in res                      # aparece en 'más adelante'
    assert "Integración WhatsApp" in res           # aparece en 'manual'
