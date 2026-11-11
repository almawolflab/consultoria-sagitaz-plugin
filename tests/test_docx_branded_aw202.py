"""AW-202 — DOCX formal con branding de la plantilla 2026.

Fase 1 cubre el **brand-kit** (asset derivado de la plantilla oficial): chrome (header+logo, footer,
fuentes, estilos, tema) + carátula con tokens + región de cuerpo delimitada + firma, SIN el cuerpo de
ejemplo, los 11 comentarios editoriales ni los textos "Instrucciones:"/"Punto fuera del alcance".

Patrón de assert: abrir el .docx como zip, inspeccionar partes OOXML y el texto de `document.xml`.
"""
import html
import importlib
import json
import re
import sys
import xml.dom.minidom as minidom
import zipfile
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1]
BRANDKIT = PLUGIN / "scripts" / "docx" / "assets" / "brandkit_2026.docx"
DOCX_DIR = PLUGIN / "scripts" / "docx"


def _gendocx():
    if str(DOCX_DIR) not in sys.path:
        sys.path.insert(0, str(DOCX_DIR))
    return importlib.reload(importlib.import_module("generar_docx"))


def _docx_names(path):
    with zipfile.ZipFile(str(path)) as z:
        return set(z.namelist())


def _docx_text(path):
    with zipfile.ZipFile(str(path)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    return html.unescape(" ".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml, re.S)))


def _docx_document(path):
    with zipfile.ZipFile(str(path)) as z:
        return z.read("word/document.xml").decode("utf-8", "replace")


def _ders_esquema_vacio():
    return {
        "cliente": "AcmeTest",
        "documento": {"version": "1.0", "autor": "Consultor", "fecha": "2026-11-11", "comentario": ""},
        "especificaciones": [],
        "objetivos_cliente": {"herramientas": [], "puntos": []},
        "solucion_buscada": {"descripcion": "Implantar CRM", "lineas_trabajo": []},
        "requerimientos": [
            {"id": "5.1", "titulo": "Gestión de leads",
             "situacion": "SITUACION_MARCADOR_DERS captura desde formulario web.",
             "requerimientos_funcionales": ["Captura web"]},
        ],
        "fuera_de_alcance": [],
    }


def _names():
    with zipfile.ZipFile(str(BRANDKIT)) as z:
        return set(z.namelist())


def _read(part):
    with zipfile.ZipFile(str(BRANDKIT)) as z:
        return z.read(part).decode("utf-8", "replace")


# ---------------------------------------------------------------- Fase 1: brand-kit

def test_brandkit_existe_y_es_zip():
    assert BRANDKIT.exists(), f"falta el brand-kit: {BRANDKIT}"
    assert zipfile.is_zipfile(str(BRANDKIT))


def test_brandkit_conserva_chrome():
    n = _names()
    assert "word/header1.xml" in n
    assert "word/footer2.xml" in n
    assert "word/styles.xml" in n
    assert "word/theme/theme1.xml" in n
    assert any(x.startswith("word/media/") for x in n), "sin logo/media"
    assert any(x.startswith("word/fonts/") and x.endswith(".ttf") for x in n), "sin fuentes embebidas"


def test_brandkit_sin_comentarios():
    n = _names()
    assert "word/comments.xml" not in n
    assert "word/commentsExtended.xml" not in n
    # y sus rels/overrides eliminados
    assert "comments.xml" not in _read("word/_rels/document.xml.rels")
    assert "comments" not in _read("[Content_Types].xml")


def test_brandkit_sin_cuerpo_ni_textos_editoriales():
    doc = _read("word/document.xml")
    texto = re.sub(r"<[^>]+>", " ", doc)
    assert "Instrucciones:" not in texto
    assert "Punto fuera del alcance" not in texto
    # ninguna sección de ejemplo del cuerpo (se eliminó [13..599])
    assert "Requerimientos Alcances CRM" not in texto
    assert "Tabla de Contenidos" not in texto


def test_brandkit_marcadores_y_tokens_de_caratula():
    doc = _read("word/document.xml")
    assert "AW202:BODY_START" in doc and "AW202:BODY_END" in doc
    # tokens de carátula para rellenar en runtime
    assert "{{AW202_TITULO}}" in doc
    assert "{{AW202_CLIENTE}}" in doc
    assert "{{AW202_VERSION}}" in doc
    assert "{{AW202_FECHA}}" in doc


def test_brandkit_document_xml_bien_formado():
    # debe parsear como XML válido (los comentarios <!-- AW202 --> son válidos)
    minidom.parseString(_read("word/document.xml"))


def test_brandkit_conserva_firma_y_sectpr():
    doc = _read("word/document.xml")
    texto = re.sub(r"<[^>]+>", " ", doc)
    assert "Estado del documento" in texto, "debe conservar el bloque de firma"
    assert "<w:sectPr" in doc and "headerReference" in doc and "footerReference" in doc


# ---------------------------------------------------------------- Fase 2: ensamblado branded

def test_branded_build_chrome_caratula_y_cuerpo(tmp_path):
    g = _gendocx()
    src = tmp_path / "DERS.json"
    src.write_text(json.dumps(_ders_esquema_vacio()), encoding="utf-8")
    out = tmp_path / "DERS.docx"
    g.build(str(src), str(out), branded=True, meta={"cliente": "AcmeTest", "version": "1.0",
                                                    "fecha": "2026-11-11"})
    names = _docx_names(out)
    assert any(n.startswith("word/media/") for n in names), "branded debe conservar el logo"
    assert "word/header1.xml" in names and "word/styles.xml" in names
    doc = _docx_document(out)
    # carátula rellenada; sin tokens residuales
    assert "AcmeTest" in _docx_text(out)
    assert "{{AW202_" not in doc
    # cuerpo insertado; sin marcadores residuales
    assert "SITUACION_MARCADOR_DERS" in _docx_text(out)
    assert "AW202:BODY_START" not in doc and "AW202:BODY_END" not in doc
    minidom.parseString(doc)                      # XML bien formado


def test_branded_degrada_sin_brandkit(tmp_path, monkeypatch):
    g = _gendocx()
    monkeypatch.setattr(g, "_BRANDKIT", tmp_path / "no_existe.docx")
    src = tmp_path / "DERS.json"
    src.write_text(json.dumps(_ders_esquema_vacio()), encoding="utf-8")
    out = tmp_path / "DERS.docx"
    g.build(str(src), str(out), branded=True)     # no debe lanzar
    assert out.exists()
    names = _docx_names(out)
    assert "word/document.xml" in names and "word/styles.xml" in names
    assert not any(n.startswith("word/media/") for n in names)   # degradó a plano
    assert "SITUACION_MARCADOR_DERS" in _docx_text(out)


def test_branded_false_sigue_siendo_plano(tmp_path):
    g = _gendocx()
    src = tmp_path / "DERS.json"
    src.write_text(json.dumps(_ders_esquema_vacio()), encoding="utf-8")
    out = tmp_path / "DERS.docx"
    g.build(str(src), str(out), branded=False)
    names = _docx_names(out)
    assert not any(n.startswith("word/media/") for n in names)


# ---------------------------------------------------------------- Fase 3: estilos de plantilla

def test_cuerpo_usa_estilos_de_plantilla(tmp_path):
    g = _gendocx()
    src = tmp_path / "DERS.json"
    src.write_text(json.dumps(_ders_esquema_vacio()), encoding="utf-8")
    out = tmp_path / "DERS.docx"
    g.build(str(src), str(out), branded=True, meta={"cliente": "AcmeTest"})
    doc = _docx_document(out)
    assert 'w:pStyle w:val="Heading1"' in doc        # secciones con estilo de la plantilla
    # no referencias a estilos custom ausentes de la plantilla (dangling en branded)
    assert "FieldLabel" not in doc


def test_labels_siguen_siendo_ancla_bold(tmp_path):
    g = _gendocx()
    src = tmp_path / "DERS.json"
    src.write_text(json.dumps(_ders_esquema_vacio()), encoding="utf-8")
    out = tmp_path / "DERS.docx"
    g.build(str(src), str(out), branded=True)
    assert "Situación" in _docx_text(out)            # la label estable persiste (round-trip AW-198)


def test_tabla_markdown_usa_estilo_branded(tmp_path):
    g = _gendocx()
    out = tmp_path / "t.docx"
    md = "| Módulo | Campo |\n|---|---|\n| Leads | Origen |"
    g.build_markdown(md, str(out))
    with zipfile.ZipFile(str(out)) as z:
        doc = z.read("word/document.xml").decode("utf-8")
    assert 'w:tblStyle w:val="3257188"' in doc       # estilo de tabla del kit 2026


# ---------------------------------------------------------------- Fase 4: modo formal

def _ders_con_marcadores():
    return {
        "cliente": "AcmeTest",
        "documento": {"version": "1.0", "autor": "", "fecha": "2026-11-11", "comentario": ""},
        "especificaciones": [],
        "objetivos_cliente": {"herramientas": [], "puntos": []},
        "solucion_buscada": {"descripcion": "", "lineas_trabajo": []},
        "requerimientos": [
            {"id": "5.1", "titulo": "Gestión de leads",
             "situacion": "[DECISIÓN CONSULTOR] Captura web automatizada.",
             "requerimientos_funcionales": [],
             "analisis_viabilidad": "[PENDIENTE DE CONFIRMAR] Viable con picklist.",
             "criterios_aceptacion": ["Se verifica que entra un lead."],
             "evidencia": [{"reunion": "m01", "minuto": "12:30"}],
             "confianza": "alta"},
        ],
        "fuera_de_alcance": [],
    }


def test_formal_elimina_intro_marcadores_y_trazabilidad(tmp_path):
    g = _gendocx()
    src = tmp_path / "d.json"
    src.write_text(json.dumps(_ders_con_marcadores()), encoding="utf-8")
    out = tmp_path / "f.docx"
    g.build(str(src), str(out), formal=True, branded=False, modelo="gpt-x")
    txt = _docx_text(out)
    assert "BORRADOR EDITABLE" not in txt
    assert "Modelo generador" not in txt
    # marcadores del consultor filtrados (el placeholder de licencias de la plantilla no es uno)
    assert "DECISIÓN CONSULTOR" not in txt
    assert "PENDIENTE DE CONFIRMAR" not in txt
    assert "Trazabilidad" not in txt and "m01" not in txt
    # el contenido real (tras quitar el marcador) permanece
    assert "Captura web automatizada." in txt
    assert "Viable con picklist." in txt


def test_formal_no_erradica_texto_de_negocio_con_pendiente(tmp_path):
    """Regex ceñida: texto legítimo con la palabra 'pendiente' NO debe borrarse en formal."""
    g = _gendocx()
    d = _ders_con_marcadores()
    d["requerimientos"][0]["situacion"] = ("Integrar [Sistema A - Tarea pendiente] con el CRM. "
                                           "[DECISIÓN CONSULTOR] vía API.")
    src = tmp_path / "d.json"
    src.write_text(json.dumps(d), encoding="utf-8")
    out = tmp_path / "f.docx"
    g.build(str(src), str(out), formal=True, branded=False)
    txt = _docx_text(out)
    assert "[Sistema A - Tarea pendiente]" in txt      # texto de negocio conservado
    assert "DECISIÓN CONSULTOR" not in txt             # marcador interno sí filtrado


def test_borrador_conserva_marcadores_y_trazabilidad(tmp_path):
    g = _gendocx()
    src = tmp_path / "d.json"
    src.write_text(json.dumps(_ders_con_marcadores()), encoding="utf-8")
    out = tmp_path / "b.docx"
    g.build(str(src), str(out), formal=False, branded=False)
    txt = _docx_text(out)
    assert "BORRADOR EDITABLE" in txt
    assert "DECISIÓN CONSULTOR" in txt and "PENDIENTE DE CONFIRMAR" in txt
    assert "Trazabilidad" in txt and "m01" in txt


def test_formal_solo_secciones_canonicas(tmp_path):
    g = _gendocx()
    d = _ders_esquema_vacio()
    d["requerimientos"].append({"id": "99.9", "titulo": "SECCION_INVENTADA", "situacion": "x"})
    src = tmp_path / "d.json"
    src.write_text(json.dumps(d), encoding="utf-8")
    out = tmp_path / "f.docx"
    g.build(str(src), str(out), formal=True, branded=False)
    assert "SECCION_INVENTADA" not in _docx_text(out)


# ---------------------------------------------------------------- Fase 5: CLI / integración skills

def test_cli_formal_produce_entregable_branded(tmp_path):
    g = _gendocx()
    src = tmp_path / "DERS.json"
    src.write_text(json.dumps(_ders_con_marcadores()), encoding="utf-8")
    out = tmp_path / "DERS.docx"
    g.main([str(src), str(out), "--formal"])
    assert any(n.startswith("word/media/") for n in _docx_names(out)), "entregable debe ir branded"
    txt = _docx_text(out)
    assert "AcmeTest" in txt                       # carátula rellenada desde el JSON
    assert "DECISIÓN CONSULTOR" not in txt         # formal
    assert "BORRADOR EDITABLE" not in txt


def test_cli_plano_desactiva_branding(tmp_path):
    g = _gendocx()
    src = tmp_path / "DERS.json"
    src.write_text(json.dumps(_ders_esquema_vacio()), encoding="utf-8")
    out = tmp_path / "DERS.docx"
    g.main([str(src), str(out), "--plano"])
    assert not any(n.startswith("word/media/") for n in _docx_names(out))


# ---------------------------------------------------------------- Fase 7: Plan → DOCX branded

def test_plan_markdown_branded(tmp_path):
    g = _gendocx()
    out = tmp_path / "Plan.docx"
    md = ("# Plan de implementación — AcmeTest\n\n## Fase 1\n\n- Configuración inicial\n\n"
          "| Hito | Fecha |\n|---|---|\n| Kickoff | S1 |")
    g.build_markdown(md, str(out), title="Plan de implementación", branded=True,
                     meta={"cliente": "AcmeTest", "titulo": "Plan de implementación — AcmeTest"})
    assert any(n.startswith("word/media/") for n in _docx_names(out)), "Plan branded debe traer logo"
    txt = _docx_text(out)
    assert "Plan de implementación" in txt and "Kickoff" in txt and "AcmeTest" in txt
    doc = _docx_document(out)
    assert "{{AW202_" not in doc
    minidom.parseString(doc)


def test_plan_markdown_plano_sin_branding(tmp_path):
    g = _gendocx()
    out = tmp_path / "Plan.docx"
    g.build_markdown("# Plan\n\ntexto", str(out), branded=False)
    assert not any(n.startswith("word/media/") for n in _docx_names(out))
