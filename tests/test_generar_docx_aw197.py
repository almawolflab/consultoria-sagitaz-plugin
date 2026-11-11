"""AW-197 — Tests del generador de DOCX portado a la skill `ders`.

El DERS producido por la skill sigue `esquema_vacio` (`requerimientos[].id` numéricos). El
generador funde ese DERS sobre el árbol canónico 2026 (`merge_ders`) y emite un `.docx` editable
(stdlib pura). Estos son tests de humo: el documento se genera, no está vacío y es un OOXML válido
con las secciones esperadas. El branding/render formal se trata en AW-202.
"""
import importlib
import json
import pathlib
import sys
import zipfile

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"
# AW-200: generar_docx movido a scripts/docx/ (módulo compartido ders/dercas/matriz).
DOCX_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "docx"
PLANTILLA = SKILLS_DIR / "ders" / "assets" / "schema" / "plantilla_ders.json"


def _import_gendocx():
    if str(DOCX_DIR) not in sys.path:
        sys.path.insert(0, str(DOCX_DIR))
    mod = importlib.import_module("generar_docx")
    return importlib.reload(mod)


def _plantilla():
    return json.loads(PLANTILLA.read_text(encoding="utf-8"))


def _ders_esquema_vacio():
    return {
        "cliente": "AcmeTest",
        "documento": {"version": "", "autor": "", "fecha": "", "comentario": ""},
        "especificaciones": [],
        "objetivos_cliente": {"herramientas": ["Zoho One"], "puntos": ["Centralizar leads"]},
        "solucion_buscada": {"descripcion": "Implantar CRM", "lineas_trabajo": []},
        "requerimientos": [
            {"id": "5.1", "titulo": "Gestión de leads",
             "situacion": "Hoy los leads llegan por email sin control.",
             "requerimientos_funcionales": ["Captura desde formulario web"],
             "analisis_viabilidad": None, "criterios_aceptacion": None,
             "adjuntos": [], "evidencia": [{"reunion": "m01", "minuto": "05:12"}],
             "confianza": "alta"},
            {"id": "10.1", "titulo": "Configuración de la empresa",
             "situacion": "Falta definir moneda y zona horaria.",
             "requerimientos_funcionales": [],
             "analisis_viabilidad": None, "criterios_aceptacion": None,
             "adjuntos": [], "evidencia": [], "confianza": "media"},
        ],
        "fuera_de_alcance": [],
    }


def test_merge_asigna_numero_y_seccion():
    g = _import_gendocx()
    merged = g.merge_ders(_ders_esquema_vacio(), _plantilla())
    by_num = {r["numero"]: r for r in merged["requerimientos"]}
    # El slot 5.1 recibe la situación aportada por el modelo
    assert "5.1" in by_num
    assert "leads llegan por email" in by_num["5.1"]["situacion"]
    assert by_num["5.1"]["seccion"] == "5"
    assert by_num["5.1"]["seccion_titulo"]
    # Un slot no tratado (p.ej. 7.1) queda con placeholder, no se pierde del árbol
    assert "7.1" in by_num
    assert "[" in by_num["7.1"]["situacion"]  # placeholder entre corchetes


def test_merge_incluye_boilerplate_y_formacion():
    g = _import_gendocx()
    merged = g.merge_ders(_ders_esquema_vacio(), _plantilla())
    assert merged["cliente"] == "AcmeTest"
    assert merged.get("objetivo_documento")      # boilerplate de la plantilla
    assert merged.get("nota_final")
    assert merged.get("estado_documento")
    assert merged.get("formacion")               # sección 12


def test_build_genera_docx_valido(tmp_path):
    g = _import_gendocx()
    ders_path = tmp_path / "DERS.json"
    ders_path.write_text(json.dumps(_ders_esquema_vacio()), encoding="utf-8")
    out = tmp_path / "DERS.docx"
    g.build(str(ders_path), str(out))
    assert out.exists() and out.stat().st_size > 0
    # Es un OOXML válido (zip con word/document.xml) y contiene contenido del DERS
    with zipfile.ZipFile(str(out)) as z:
        nombres = z.namelist()
        assert "word/document.xml" in nombres
        doc = z.read("word/document.xml").decode("utf-8")
    assert "AcmeTest" in doc
    assert "Gestión de leads" in doc
    assert "Situación" in doc


def test_build_docx_desde_ders_ya_merged(tmp_path):
    """Si el DERS ya trae numero/seccion (formato merged), build no re-funde y genera igual."""
    g = _import_gendocx()
    merged = g.merge_ders(_ders_esquema_vacio(), _plantilla())
    ders_path = tmp_path / "DERS_merged.json"
    ders_path.write_text(json.dumps(merged), encoding="utf-8")
    out = tmp_path / "DERS.docx"
    g.build(str(ders_path), str(out))
    assert out.exists() and out.stat().st_size > 0
