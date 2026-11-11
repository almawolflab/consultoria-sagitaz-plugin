"""AW-197 — Tests del validador real de DERS contra la plantilla canónica 2026.

El validador comprueba que el DERS *producido* por la skill (esquema `esquema_vacio`:
`requerimientos[]` con `id`/`numero` numéricos) tiene numeración que pertenece al árbol
canónico de `plantilla_ders.json`, sin numeración inventada ni duplicados.
"""
import importlib
import json
import pathlib
import sys

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"
DERS_SCRIPTS = SKILLS_DIR / "ders" / "scripts"
PLANTILLA = SKILLS_DIR / "ders" / "assets" / "schema" / "plantilla_ders.json"


def _import_validar():
    if str(DERS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(DERS_SCRIPTS))
    mod = importlib.import_module("validar_ders")
    return importlib.reload(mod)


def _plantilla():
    return json.loads(PLANTILLA.read_text(encoding="utf-8"))


def _ders_valido():
    """DERS mínimo válido (esquema_vacio) con numeración dentro del árbol canónico."""
    return {
        "cliente": "AcmeTest",
        "documento": {"version": "", "autor": "", "fecha": "", "comentario": ""},
        "requerimientos": [
            {"id": "5.1", "titulo": "Leads", "situacion": "x",
             "requerimientos_funcionales": [], "analisis_viabilidad": None,
             "criterios_aceptacion": None, "evidencia": [], "confianza": "alta"},
            {"id": "5.2", "titulo": "Oportunidades", "situacion": "y",
             "requerimientos_funcionales": [], "analisis_viabilidad": None,
             "criterios_aceptacion": None, "evidencia": [], "confianza": "media"},
            {"id": "10.1", "titulo": "Config empresa", "situacion": "z",
             "requerimientos_funcionales": [], "analisis_viabilidad": None,
             "criterios_aceptacion": None, "evidencia": [], "confianza": "alta"},
        ],
        "fuera_de_alcance": [],
    }


def test_numeros_canonicos_incluye_hojas_y_grupos():
    v = _import_validar()
    nums = v.numeros_canonicos(_plantilla())
    assert "5.1" in nums and "5.3" in nums and "11" in nums
    assert "5" in nums and "13" in nums
    assert "5.99" not in nums and "16.2" not in nums


def test_ders_valido_sin_errores():
    v = _import_validar()
    errores = v.validar_estructura(_ders_valido(), _plantilla())
    assert errores == [], f"esperaba DERS válido, errores: {errores}"


def test_numero_fuera_de_plantilla():
    v = _import_validar()
    ders = _ders_valido()
    ders["requerimientos"][0]["id"] = "5.99"
    errores = v.validar_estructura(ders, _plantilla())
    assert any("5.99" in e for e in errores), errores


def test_req_sin_id_ni_numero():
    v = _import_validar()
    ders = _ders_valido()
    ders["requerimientos"].append({"titulo": "huerfano"})
    errores = v.validar_estructura(ders, _plantilla())
    assert any("id" in e.lower() or "numero" in e.lower() for e in errores), errores


def test_requerimientos_no_es_lista():
    v = _import_validar()
    ders = _ders_valido()
    ders["requerimientos"] = {"5.1": "mal"}
    errores = v.validar_estructura(ders, _plantilla())
    assert any("requerimientos" in e for e in errores), errores


def test_ders_no_es_dict():
    v = _import_validar()
    errores = v.validar_estructura([], _plantilla())
    assert errores, "una lista no es un DERS válido"


def test_numero_duplicado():
    v = _import_validar()
    ders = _ders_valido()
    ders["requerimientos"].append(
        {"id": "5.1", "titulo": "dup", "situacion": "", "requerimientos_funcionales": [],
         "analisis_viabilidad": None, "criterios_aceptacion": None, "evidencia": [],
         "confianza": ""})
    errores = v.validar_estructura(ders, _plantilla())
    assert any("5.1" in e and ("duplic" in e.lower()) for e in errores), errores


def test_subapartado_fuera_de_su_requerimiento():
    v = _import_validar()
    ders = _ders_valido()
    ders["requerimientos"][0]["subapartados"] = [{"id": "6.1.1", "titulo": "mal ubicado"}]
    errores = v.validar_estructura(ders, _plantilla())
    assert any("6.1.1" in e for e in errores), errores


def test_cli_rc0_para_ders_valido(tmp_path):
    v = _import_validar()
    ders_path = tmp_path / "DERS.json"
    ders_path.write_text(json.dumps(_ders_valido()), encoding="utf-8")
    rc = v.main([str(ders_path), "--schema", str(PLANTILLA)])
    assert rc == 0


def test_cli_rc1_para_numero_invalido(tmp_path):
    v = _import_validar()
    ders = _ders_valido()
    ders["requerimientos"][0]["id"] = "99.9"
    ders_path = tmp_path / "DERS.json"
    ders_path.write_text(json.dumps(ders), encoding="utf-8")
    rc = v.main([str(ders_path), "--schema", str(PLANTILLA)])
    assert rc == 1
