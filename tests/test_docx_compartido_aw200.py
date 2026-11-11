"""AW-200 — Generador DOCX compartido (scripts/docx/generar_docx.py).

Cubre lo que AW-200 añade sobre AW-197:
- `build_markdown()` portado desde catalyst (markdown → DOCX: encabezados, tablas, viñetas, checkbox).
- `build(..., dercas=True)` emite DERCAS.docx con anclas estables (#8).
- `matriz_resumen`: `resumen_plantilla` → `build_markdown` → DOCX con `manual_todo` y recuento (#3).

Patrón de assert: abrir el .docx como zip, leer `word/document.xml`, extraer texto con regex.
"""
import html
import importlib
import json
import re
import sys
import zipfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
DOCX_DIR = PLUGIN / "scripts" / "docx"
FIXTURES = PLUGIN / "scripts" / "tests" / "fixtures"


def _gendocx():
    if str(DOCX_DIR) not in sys.path:
        sys.path.insert(0, str(DOCX_DIR))
    mod = importlib.import_module("generar_docx")
    return importlib.reload(mod)


def _texto(docx_path):
    with zipfile.ZipFile(str(docx_path)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    return html.unescape(" ".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S)))


def _es_ooxml_valido(docx_path):
    with zipfile.ZipFile(str(docx_path)) as z:
        names = set(z.namelist())
    return {"[Content_Types].xml", "word/document.xml", "word/styles.xml"} <= names


# ---------------------------------------------------------------- build_markdown (Fase 4)

def test_build_markdown_encabezados_y_parrafos(tmp_path):
    g = _gendocx()
    out = tmp_path / "md.docx"
    md = "# Título principal\n\n## Subapartado\n\nUn párrafo normal."
    g.build_markdown(md, str(out), title="Doc")
    assert _es_ooxml_valido(out)
    txt = _texto(out)
    assert "Título principal" in txt and "Subapartado" in txt and "Un párrafo normal." in txt


def test_build_markdown_tabla(tmp_path):
    g = _gendocx()
    out = tmp_path / "tabla.docx"
    md = "| Módulo | Campo |\n|---|---|\n| Leads | Origen |\n| Deals | Fase |"
    g.build_markdown(md, str(out))
    with zipfile.ZipFile(str(out)) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "<w:tbl>" in xml                                   # se generó una tabla OOXML
    txt = _texto(out)
    assert "Leads" in txt and "Origen" in txt and "Fase" in txt


def test_build_markdown_checkbox(tmp_path):
    g = _gendocx()
    out = tmp_path / "chk.docx"
    md = "- [ ] Tarea pendiente\n- [x] Tarea hecha\n- Item normal"
    g.build_markdown(md, str(out))
    txt = _texto(out)
    assert "Tarea pendiente" in txt and "Tarea hecha" in txt and "Item normal" in txt
    assert "☐" in txt and "☑" in txt                          # casillas de verificación


# ---------------------------------------------------------------- DERCAS.docx (#8, Fase 5)

_DERCAS_SAMPLE = PLUGIN / "scripts" / "assets" / "dercas_con_plantilla.json"


def test_dercas_docx_anclas_estables(tmp_path):
    g = _gendocx()
    out = tmp_path / "DERCAS.docx"
    g.build(str(_DERCAS_SAMPLE), str(out), dercas=True)
    assert _es_ooxml_valido(out)
    txt = _texto(out)
    assert "Análisis de viabilidad" in txt and "Criterios de aceptación" in txt


def test_dercas_docx_incluye_contenido_viabilidad(tmp_path):
    g = _gendocx()
    out = tmp_path / "DERCAS.docx"
    g.build(str(_DERCAS_SAMPLE), str(out), dercas=True)
    txt = _texto(out)
    assert "captación automática" in txt           # contenido real de analisis_viabilidad del sample


def test_dercas_docx_desde_esquema_vacio_conserva_viabilidad(tmp_path):
    """Guard: un DERCAS en esquema_vacio (reqs con `id`, sin `seccion`) se funde SIN perder la
    viabilidad/criterios que aportó la fase DERCAS (merge_ders debe copiarlos)."""
    g = _gendocx()
    dercas_ev = {
        "cliente": "AcmeTest",
        "requerimientos": [{
            "id": "5.1", "titulo": "Gestión de leads",
            "situacion": "Hoy sin control.",
            "analisis_viabilidad": "Viable con campos personalizados en Leads.",
            "criterios_aceptacion": ["Se verifica que un lead entra y queda registrado."],
        }],
    }
    src = tmp_path / "DERCAS.json"
    src.write_text(json.dumps(dercas_ev), encoding="utf-8")
    out = tmp_path / "DERCAS.docx"
    g.build(str(src), str(out), dercas=True)
    txt = _texto(out)
    assert "Viable con campos personalizados en Leads." in txt
    assert "un lead entra y queda registrado" in txt


# ---------------------------------------------------------------- matriz_resumen.docx (#3, Fase 6)

def _get_generar_matriz():
    scripts_skill = PLUGIN / "skills" / "matriz" / "scripts"
    if str(scripts_skill) not in sys.path:
        sys.path.insert(0, str(scripts_skill))
    sys.modules.pop("generar_matriz", None)
    return importlib.import_module("generar_matriz")


def test_matriz_resumen_se_genera_junto_al_xlsx(tmp_path):
    gm = _get_generar_matriz()
    gold = FIXTURES / "ir_jaque_r1r3.json"
    out_xlsx = tmp_path / "Matriz_CRM.xlsx"
    rc = gm.main(["--ir", str(gold), "--out", str(out_xlsx)])
    assert rc == 0
    resumen = tmp_path / "matriz_resumen.docx"
    assert resumen.exists(), "matriz debe emitir matriz_resumen.docx junto al xlsx"
    assert _es_ooxml_valido(resumen)
    txt = _texto(resumen)
    assert "Leads" in txt                              # recuento por módulo / campos del IR gold


def test_matriz_resumen_muestra_manual_todo(tmp_path):
    """El resumen debe incluir las tareas manuales (lo que NO se automatiza) — núcleo del #3."""
    from parametrizacion.generador_plantilla import resumen_plantilla
    from parametrizacion.plantilla_io import cargar_descriptor
    g = _gendocx()
    ir = {
        "meta": {"cliente": "AcmeTest"},
        "fields": [{
            "id": "fld-a", "from": "R1",
            "match": {"module": "Leads", "api_name": "Origen"},
            "payload": {"module": "Leads", "field_label": "Origen", "data_type": "picklist",
                        "pick_list_values": [{"display_value": "Web", "actual_value": "Web"}]},
        }],
        "manual_todo": [{"item": "Configurar blueprint de ventas", "why": "requiere ajuste manual",
                         "from": "R5"}],
    }
    md = resumen_plantilla(ir, cargar_descriptor(None))
    out = tmp_path / "matriz_resumen.docx"
    g.build_markdown(md, str(out), title="Matriz — AcmeTest")
    txt = _texto(out)
    assert "Configurar blueprint de ventas" in txt
    assert "☐" in txt                                  # el manual_todo va como checkbox
