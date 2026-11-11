"""AW-200 #5 — Tests del validador IR *semántico* (`ir.validar_semantico`).

`validate()` (estructural) ya existe y no cambia. `validar_semantico(ir, descriptor)` es aditivo:
devuelve una tupla `(errores, avisos)` — `errores` bloquean (rc=1), `avisos` son observaciones de
trazabilidad. Comprueba data_type ∈ tipos del descriptor, `match.module == payload.module`, que el
módulo exista en el descriptor y la coherencia de picklists. Degrada sin falsos positivos si el
descriptor viene incompleto.
"""
import copy
import json
from pathlib import Path

from parametrizacion import ir as ir_mod
from parametrizacion.plantilla_io import cargar_descriptor

FIX = Path(__file__).resolve().parent / "fixtures" / "ir_jaque_r1r3.json"


def _gold():
    return json.loads(FIX.read_text(encoding="utf-8"))


def _desc():
    return cargar_descriptor(None)


# ---------------------------------------------------------------- helpers de derivación

def test_tipos_validos_extrae_zoho_no_claves():
    """Crítico #1: el set válido son los nombres Zoho (propiedad .zoho), NO las claves español."""
    tv = ir_mod.tipos_validos(_desc())
    assert "picklist" in tv and "date" in tv and "text" in tv      # nombres Zoho
    assert "texto" not in tv and "lista de seleccion" not in tv    # claves español NO


def test_modulos_validos_desde_lista_api_name():
    mv = ir_mod.modulos_validos(_desc())
    assert "Leads" in mv and "Deals" in mv
    assert len(mv) >= 10


# ---------------------------------------------------------------- gold: sin falsos positivos

def test_gold_sin_errores():
    errores, _avisos = ir_mod.validar_semantico(_gold(), _desc())
    assert errores == [], errores


def test_gold_picklist_y_date_pasan():
    """Guard contra Crítico #1: data_types Zoho reales (picklist, date) no se rechazan."""
    errores, _ = ir_mod.validar_semantico(_gold(), _desc())
    assert not any("data_type" in e for e in errores)


# ---------------------------------------------------------------- un fallo por check

def test_data_type_inexistente_bloquea():
    ir = _gold()
    ir["fields"][0]["payload"]["data_type"] = "noexiste"
    errores, _ = ir_mod.validar_semantico(ir, _desc())
    assert any("noexiste" in e and ir["fields"][0]["id"] in e for e in errores)


def test_match_module_distinto_de_payload_module_bloquea():
    ir = _gold()
    ir["fields"][0]["payload"]["module"] = "Deals"   # match sigue en Leads
    errores, _ = ir_mod.validar_semantico(ir, _desc())
    assert any("module" in e and ir["fields"][0]["id"] in e for e in errores)


def test_modulo_inventado_bloquea():
    ir = _gold()
    ir["fields"][0]["match"]["module"] = "ModuloInventado"
    ir["fields"][0]["payload"]["module"] = "ModuloInventado"
    errores, _ = ir_mod.validar_semantico(ir, _desc())
    assert any("ModuloInventado" in e for e in errores)


def test_picklist_vacia_bloquea():
    ir = _gold()
    ir["fields"][0]["payload"]["pick_list_values"] = []
    errores, _ = ir_mod.validar_semantico(ir, _desc())
    assert any(ir["fields"][0]["id"] in e for e in errores)


def test_picklist_display_duplicado_bloquea():
    ir = _gold()
    plv = ir["fields"][0]["payload"]["pick_list_values"]
    plv.append({"display_value": plv[0]["display_value"], "actual_value": "x"})
    errores, _ = ir_mod.validar_semantico(ir, _desc())
    assert any(ir["fields"][0]["id"] in e for e in errores)


def test_picklist_sin_actual_value_bloquea():
    ir = _gold()
    ir["fields"][0]["payload"]["pick_list_values"] = [{"display_value": "A"}]
    errores, _ = ir_mod.validar_semantico(ir, _desc())
    assert any(ir["fields"][0]["id"] in e for e in errores)


# ---------------------------------------------------------------- degradación (sin descriptor)

def test_descriptor_vacio_degrada_sin_falsos_positivos():
    ir = _gold()
    ir["fields"][0]["payload"]["data_type"] = "cualquier_cosa"
    errores, _ = ir_mod.validar_semantico(ir, {})
    # sin tipos/modulos en el descriptor, los checks que dependen de ellos se omiten
    assert not any("data_type" in e for e in errores)
    assert not any("no existe en el descriptor" in e for e in errores)


def test_validar_semantico_no_lanza_con_ir_minimo():
    # No debe petar si faltan secciones
    errores, avisos = ir_mod.validar_semantico({"fields": []}, _desc())
    assert errores == [] and avisos == []


# ---------------------------------------------------------------- avisos (no bloquean)

def test_rol_raiz_es_aviso_no_error():
    ir = {"roles": [{"id": "r1", "match": {"name": "CEO"}, "payload": {}}]}
    errores, avisos = ir_mod.validar_semantico(ir, _desc())
    assert errores == []
    assert any("CEO" in a or "raíz" in a.lower() or "raiz" in a.lower() for a in avisos)


def test_campo_manual_sin_manual_todo_es_aviso():
    ir = {
        "fields": [{
            "id": "fld-formula", "from": "R9",
            "match": {"module": "Leads", "api_name": "Calc"},
            "payload": {"module": "Leads", "field_label": "Calc", "data_type": "formula"},
        }],
        "manual_todo": [],
    }
    errores, avisos = ir_mod.validar_semantico(ir, _desc())
    assert errores == []
    assert any("fld-formula" in a or "Calc" in a for a in avisos)


def test_retorno_es_tupla_errores_avisos():
    res = ir_mod.validar_semantico(_gold(), _desc())
    assert isinstance(res, tuple) and len(res) == 2
    errores, avisos = res
    assert isinstance(errores, list) and isinstance(avisos, list)
