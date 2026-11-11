#!/usr/bin/env python3
"""
generar_docx.py — Generador DOCX **compartido** (ders/dercas/matriz) — .docx EDITABLE (Word / Zoho).

Portado desde `catalyst/appsail-worker/generar_docx.py` (AW-197) y movido a `scripts/docx/` como
módulo compartido (AW-200). Stdlib pura (`zipfile` + XML a mano, sin `python-docx`/`lxml`). El .docx
es una FUNCIÓN PURA del JSON: no completa ni inventa. Dos entradas: `build()` (DERS/DERCAS desde su
JSON) y `build_markdown()` (cualquier resumen/plan en markdown → DOCX, p.ej. el resumen de `matriz`).

El DERS que produce la skill sigue `esquema_vacio` (`requerimientos[].id` numéricos "5.1"). Este
módulo lo **funde** sobre el árbol canónico 2026 (`merge_ders`) para obtener el documento completo
(numeración fija, placeholders en lo no tratado, boilerplate y formación) y luego lo renderiza.
El documento es **round-trip-ready**: cada requerimiento va bajo un Heading `«5.1  Título»` y cada
campo lleva una **etiqueta estable** (Situación, Requerimientos funcionales, Análisis de viabilidad,
Criterios de aceptación, Trazabilidad) — anclas para AW-198. El branding/render formal → AW-202.

Uso CLI:  generar_docx.py <DERS.json> <salida_docx> [--schema plantilla_ders.json]
Uso API:  import generar_docx; generar_docx.build(json_path, out_docx)
"""
import argparse
import json
import os
import re
import sys
import zipfile
from pathlib import Path

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

_HERE = Path(__file__).resolve().parent
# Brand-kit branded (AW-202): chrome (header+logo/footer/fuentes/estilos/tema) + carátula + firma.
_BRANDKIT = _HERE / "assets" / "brandkit_2026.docx"
_BODY_START = "<!-- AW202:BODY_START -->"
_BODY_END = "<!-- AW202:BODY_END -->"
# Módulo compartido (scripts/docx/) → la plantilla canónica vive en skills/ders/assets/schema/.
_DEFAULT_PLANTILLA = _HERE.parents[1] / "skills" / "ders" / "assets" / "schema" / "plantilla_ders.json"


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _run(text, bold=False, italic=False):
    rpr = ""
    if bold or italic:
        rpr = "<w:rPr>%s%s</w:rPr>" % ("<w:b/>" if bold else "", "<w:i/>" if italic else "")
    return '<w:r>%s<w:t xml:space="preserve">%s</w:t></w:r>' % (rpr, _esc(text))


def _p(text="", style=None, bold=False, italic=False, indent=0):
    ppr = []
    if style:
        ppr.append('<w:pStyle w:val="%s"/>' % style)
    if indent:
        ppr.append('<w:ind w:left="%d"/>' % indent)
    ppr_xml = "<w:pPr>%s</w:pPr>" % "".join(ppr) if ppr else ""
    run = _run(text, bold=bold, italic=italic) if text != "" else ""
    return "<w:p>%s%s</w:p>" % (ppr_xml, run)


_INLINE = re.compile(r"\*\*(.+?)\*\*|(?<!\w)_(.+?)_(?!\w)")   # **negrita** | _cursiva_


def _runs(text):
    """Convierte formato inline markdown (**negrita**, _cursiva_) en runs OOXML."""
    out, pos = [], 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            out.append(_run(text[pos:m.start()]))
        if m.group(1) is not None:
            out.append(_run(m.group(1), bold=True))
        else:
            out.append(_run(m.group(2), italic=True))
        pos = m.end()
    if pos < len(text):
        out.append(_run(text[pos:]))
    return "".join(out) or _run(text)


def _p_inline(text, style=None, indent=0):
    """Párrafo con runs de formato inline (negrita/cursiva)."""
    ppr = []
    if style:
        ppr.append('<w:pStyle w:val="%s"/>' % style)
    if indent:
        ppr.append('<w:ind w:left="%d"/>' % indent)
    ppr_xml = "<w:pPr>%s</w:pPr>" % "".join(ppr) if ppr else ""
    return "<w:p>%s%s</w:p>" % (ppr_xml, _runs(text))


def _h1(num, title):
    return _p(("%s  %s" % (num, title)).strip(), style="Heading1")


def _h2(title):
    return _p(title, style="Heading2")


def _label(text):
    # etiqueta de campo (negrita) — ancla estable para el round-trip. Usa estilo `Normal` + run bold:
    # existe tanto en la plantilla 2026 (branded) como en los estilos plano (AW-202 fase 3).
    return _p(text, style="Normal", bold=True)


def _para(text, italic=False):
    return _p(text, style="Normal", italic=italic)


def _bullets(items):
    return [_p("•  %s" % it, style="Normal", indent=360) for it in items]


def _placeholder(text):
    return _p(text, style="Normal", italic=True)


def _field(value):
    """Campo DERCAS: analisis_viabilidad (str con saltos) o criterios_aceptacion (lista)."""
    if isinstance(value, list):
        return _bullets(value)
    segs = [l for l in str(value).split("\n") if l.strip()]
    return [_para(seg) for seg in segs]


STYLES_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<w:styles xmlns:w="%s">'
    '<w:docDefaults><w:rPrDefault><w:rPr>'
    '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/><w:sz w:val="22"/></w:rPr></w:rPrDefault>'
    '</w:docDefaults>'
    '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
    '<w:pPr><w:spacing w:after="120"/></w:pPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
    '<w:pPr><w:jc w:val="center"/><w:spacing w:after="240"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="44"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="0"/><w:spacing w:before="240" w:after="120"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="30"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:outlineLvl w:val="1"/><w:spacing w:before="160" w:after="80"/></w:pPr>'
    '<w:rPr><w:b/><w:sz w:val="24"/></w:rPr></w:style>'
    '<w:style w:type="paragraph" w:styleId="FieldLabel"><w:name w:val="Field Label"/>'
    '<w:basedOn w:val="Normal"/><w:pPr><w:spacing w:before="80" w:after="40"/></w:pPr>'
    '<w:rPr><w:b/><w:color w:val="3C3C3C"/></w:rPr></w:style>'
    '</w:styles>'
) % W

CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
    '</Types>'
)

RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
    '</Relationships>'
)

DOC_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    '</Relationships>'
)


def _write_docx(out_docx, body_parts):
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="%s"><w:body>%s<w:sectPr/></w:body></w:document>'
           % (W, "".join(body_parts)))
    with zipfile.ZipFile(str(out_docx), "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", CONTENT_TYPES)
        z.writestr("_rels/.rels", RELS)
        z.writestr("word/_rels/document.xml.rels", DOC_RELS)
        z.writestr("word/styles.xml", STYLES_XML)
        z.writestr("word/document.xml", doc)
    return out_docx


# ------------------------------------------------- Merge: esquema_vacio -> árbol canónico 2026

# Placeholders del esqueleto fijo 2026 (secciones no tratadas en la consultoría).
PH_NUCLEO = "[PENDIENTE — no tratado en consultoría]"
PH_OPCIONAL = "[Solo si está incluido en el proyecto — PENDIENTE DE CONFIRMAR]"


def _iter_slots(secciones):
    """(slot, seccion_numero, seccion_titulo) por cada hoja con numero del árbol 2026."""
    for s in secciones:
        if s.get("hijos"):
            for h in s["hijos"]:
                yield h, s["numero"], s["titulo"]
        elif s.get("id_canon"):        # slot de nivel superior (p.ej. 11 Informes)
            yield s, s["numero"], s["titulo"]


def _ph(slot):
    return PH_OPCIONAL if slot.get("tipo") == "opcional" else PH_NUCLEO


def _req_base(titulo):
    return {"numero": "", "titulo": titulo, "seccion": "", "seccion_titulo": "",
            "situacion": "", "requerimientos_funcionales": [],
            "analisis_viabilidad": None, "criterios_aceptacion": None,
            "adjuntos": [], "evidencia": [], "confianza": ""}


def _num_req(r):
    val = r.get("numero") or r.get("id")
    return str(val).strip() if val is not None else ""


def merge_ders(ders, plantilla):
    """Funde un DERS `esquema_vacio` sobre el árbol FIJO 2026 (match por número de requerimiento).

    Determinista: recorre el árbol, rellena por número lo que aportó el modelo y deja placeholder
    en el resto. Numeración FIJA (no se renumera). Viabilidad/Criterios = null (los rellena DERCAS).
    Devuelve el DERS en el esquema que consume `_body_ders` (con numero/seccion/boilerplate/formación).
    """
    cliente = (ders.get("cliente") or "").strip()
    by_num = {_num_req(r): r for r in ders.get("requerimientos", []) if _num_req(r)}

    reqs = []
    for slot, sec_num, sec_tit in _iter_slots(plantilla["secciones"]):
        m = by_num.get(str(slot["numero"]))
        r = _req_base(slot["titulo"])
        r["numero"] = slot["numero"]
        r["seccion"] = sec_num
        r["seccion_titulo"] = sec_tit
        if m:
            r["titulo"] = m.get("titulo") or slot["titulo"]
            r["situacion"] = m.get("situacion", "") or _ph(slot)
            r["requerimientos_funcionales"] = m.get("requerimientos_funcionales", []) or []
            r["evidencia"] = m.get("evidencia", []) or []
            r["confianza"] = m.get("confianza", "")
            r["adjuntos"] = m.get("adjuntos", []) or []
            # DERCAS (AW-200 #8): si el requerimiento origen trae viabilidad/criterios (fase DERCAS
            # sobre un DERS en esquema_vacio), conservarlos; si no, quedan en null (los rellena DERCAS).
            if m.get("analisis_viabilidad") is not None:
                r["analisis_viabilidad"] = m["analisis_viabilidad"]
            if m.get("criterios_aceptacion") is not None:
                r["criterios_aceptacion"] = m["criterios_aceptacion"]
        else:
            r["situacion"] = _ph(slot)   # esqueleto completo con placeholder
        reqs.append(r)

    ep = plantilla["especificaciones_plantilla"]
    espec = [ep["definicion"]] + ep["items"]
    espec = [s.replace("[CLIENTE]", cliente or "[CLIENTE]") for s in espec]
    # si el modelo aportó especificaciones, se añaden tras las de plantilla
    espec += [s for s in (ders.get("especificaciones") or []) if s]

    docb = plantilla.get("documento_boilerplate", {})

    def _cli(s):
        return (s or "").replace("[CLIENTE]", cliente or "[CLIENTE]")

    sol = ders.get("solucion_buscada", {}) or {}
    fmt = next((s for s in plantilla["secciones"] if s.get("tipo") == "formacion"), {})
    return {
        "cliente": cliente,
        "documento": ders.get("documento", {"version": "", "autor": "", "fecha": "", "comentario": ""}),
        "control_documentos": plantilla.get("control_documentos", {}),
        "objetivo_documento": _cli(docb.get("objetivo_documento", "")),
        "especificaciones": espec,
        "objetivos_cliente": ders.get("objetivos_cliente", {"herramientas": [], "puntos": []}),
        "solucion_buscada": {"descripcion": sol.get("descripcion", ""),
                             "lineas_trabajo": plantilla["lineas_trabajo_estandar"]},
        "requerimientos": reqs,
        "formacion": fmt,
        "fuera_de_alcance": ders.get("fuera_de_alcance", []),
        "nota_final": _cli(docb.get("nota_final", "")),
        "estado_documento": _cli(docb.get("estado_documento", "")),
    }


def _esta_merged(ders):
    """Un DERS ya fundido trae numero/seccion en sus requerimientos."""
    reqs = ders.get("requerimientos") or []
    return bool(reqs) and all(isinstance(r, dict) and "seccion" in r for r in reqs)


# ------------------------------------------------- Render del cuerpo

# Marcadores internos a ocultar en modo formal. Se ciñe a los marcadores EXACTOS esperados para no
# erradicar texto de negocio legítimo (p.ej. "[Sistema A - Tarea pendiente]"):
#   - [DECISIÓN CONSULTOR …]      (anotación del consultor)
#   - [… PENDIENTE DE CONFIRMAR]  (consultor + placeholder opcional "[Solo si… PENDIENTE DE CONFIRMAR]")
#   - [PENDIENTE — …] / [PENDIENTE - …]  (placeholder de sección no tratada, PH_NUCLEO)
_MARCADOR_RE = re.compile(
    r"\[[^\]]*DECISI[ÓO]N CONSULTOR[^\]]*\]\s*"
    r"|\[[^\]]*PENDIENTE DE CONFIRMAR[^\]]*\]\s*"
    r"|\[PENDIENTE\s*[—-][^\]]*\]\s*", re.I)


def _strip_marcadores(text):
    """Quita los marcadores internos del texto (modo formal). Devuelve el resto, recortado."""
    return _MARCADOR_RE.sub("", str(text)).strip()


def _body_ders(data, modelo, dercas, formal=False):
    """Construye el cuerpo del .docx a partir del JSON del DERS (merged).

    `formal=True` (AW-202) produce salida limpia de cliente (implementado en Fase 4)."""
    b = []
    tipo = "DERCAS" if dercas else "DERS"
    cli = (data.get("cliente") or "(cliente no extraído)").strip()
    b.append(_p("%s — %s" % (tipo, cli), style="Title"))
    # Intro de proceso y byline: solo en el borrador interno (formal=False).
    if not formal:
        b.append(_placeholder("Documento generado automáticamente — BORRADOR EDITABLE. "
                              "Ajusta el contenido directamente en este documento; el pipeline releerá tus cambios."))
        if modelo:
            b.append(_p("Modelo generador: %s" % modelo, style="Normal", italic=True))

    def _c(text):
        return _strip_marcadores(text) if formal else text

    # 1 Control de documentos
    b.append(_h1("1", "Control de documentos"))
    doc = data.get("documento", {})
    if any(doc.values()):
        for k in ("version", "autor", "fecha", "comentario"):
            if doc.get(k):
                b.append(_label(k.capitalize() + ":"))
                b.append(_para(str(doc[k])))
    else:
        b.append(_placeholder("[Control de versiones del documento — a completar (versión, autor, "
                              "fecha, revisiones y aprobaciones).]"))

    # 2 Objetivo del documento
    b.append(_h1("2", "Objetivo del documento"))
    b.append(_para(data["objetivo_documento"]) if data.get("objetivo_documento")
             else _placeholder("[Sección de texto fijo de la plantilla estándar del DERS.]"))

    # 3 Especificaciones
    b.append(_h1("3", "Especificaciones"))
    esp = data.get("especificaciones", [])
    b.extend(_bullets(esp) if esp else [_placeholder("(no extraído por el modelo)")])

    # 4 Fuerza de ventas
    b.append(_h1("4", "Fuerza de ventas"))
    oc = data.get("objetivos_cliente", {})
    b.append(_h2("4.1  Objetivos del cliente"))
    if oc.get("herramientas"):
        b.append(_label("Herramientas:")); b.extend(_bullets(oc["herramientas"]))
    if oc.get("puntos"):
        b.append(_label("Objetivos:")); b.extend(_bullets(oc["puntos"]))
    if not (oc.get("herramientas") or oc.get("puntos")):
        b.append(_placeholder("(no extraído por el modelo)"))
    sb = data.get("solucion_buscada", {})
    b.append(_h2("4.2  Solución buscada"))
    if sb.get("descripcion"):
        b.append(_para(sb["descripcion"]))
    if sb.get("lineas_trabajo"):
        b.append(_label("Líneas de trabajo:")); b.extend(_bullets(sb["lineas_trabajo"]))
    if not (sb.get("descripcion") or sb.get("lineas_trabajo")):
        b.append(_placeholder("(no extraído por el modelo)"))

    # 5–11 Requerimientos (agrupados por sección temática)
    sec_actual = None
    for r in data.get("requerimientos", []):
        top_level = (r["numero"] == r["seccion"])
        if not top_level and r["seccion"] != sec_actual:
            b.append(_h1(r["seccion"], r["seccion_titulo"])); sec_actual = r["seccion"]
        if top_level:
            b.append(_h1(r["numero"], r["titulo"])); sec_actual = r["seccion"]
        else:
            b.append(_h2("%s  %s" % (r["numero"], r["titulo"])))
        sit = _c(r.get("situacion", ""))
        if sit:
            b.append(_label("Situación")); b.append(_para(sit))
        elif not formal:
            b.append(_label("Situación")); b.append(_para(r.get("situacion", "")))
        rf = [_c(x) for x in (r.get("requerimientos_funcionales") or [])]
        rf = [x for x in rf if x]
        if rf:
            b.append(_label("Requerimientos funcionales")); b.extend(_bullets(rf))

        def _campo(valor):
            """Render de analisis/criterios con marcadores filtrados (formal); quita vacíos."""
            if isinstance(valor, list):
                items = [x for x in (_c(v) for v in valor) if x]
                return _bullets(items)
            segs = [l for l in str(_c(valor)).split("\n") if l.strip()]
            return [_para(s) for s in segs]

        for label, val in (("Análisis de viabilidad", r.get("analisis_viabilidad")),
                           ("Criterios de aceptación", r.get("criterios_aceptacion"))):
            partes = _campo(val) if val is not None else []
            if partes:
                b.append(_label(label)); b.extend(partes)
            elif not formal:
                b.append(_label(label)); b.append(_placeholder("(A desarrollar en documento DERCAS)"))

        # Trazabilidad (confianza + evidencia de audios): material interno, solo en borrador.
        ev = r.get("evidencia", [])
        if (ev or r.get("confianza")) and not formal:
            refs = ", ".join("%s [%s]" % (e.get("reunion"), e.get("minuto")) for e in ev if e.get("reunion"))
            b.append(_p("Trazabilidad (metadato del modelo) — confianza: %s; evidencia: %s"
                        % (r.get("confianza") or "n/d", refs or "n/d"), style="Normal", italic=True))

    # 12 Formación
    b.append(_h1("12", "Formación"))
    fmt = data.get("formacion", {})
    if fmt.get("intro"):
        b.append(_para(fmt["intro"]))
    for sa in fmt.get("subapartados", []):
        b.append(_h2("%s  %s" % (sa.get("numero", ""), sa.get("titulo", ""))))
        if sa.get("contenidos"):
            b.extend(_bullets(sa["contenidos"]))
    if not fmt:
        b.append(_placeholder("[Sección de texto fijo de la plantilla estándar del DERS (formación).]"))

    # 13 Fuera del alcance
    b.append(_h1("13", "Fuera del alcance"))
    fa = data.get("fuera_de_alcance", [])
    if fa:
        for i, f in enumerate(fa, 1):
            b.append(_h2("13.%d  %s" % (i, f.get("titulo", ""))))
            if f.get("situacion"):
                b.append(_label("Situación")); b.append(_para(f["situacion"]))
            if f.get("objetivos"):
                b.append(_label("Objetivos")); b.append(_para(f["objetivos"]))
            if f.get("descripcion"):
                b.append(_para(f["descripcion"]))
            if f.get("tratamiento"):
                b.append(_label("Tratamiento")); b.append(_para(f["tratamiento"]))
    else:
        b.append(_placeholder("(no se detectaron puntos fuera del alcance en la consultoría)"))

    # 14 Nota final
    b.append(_h1("14", "Nota final"))
    b.append(_para(data["nota_final"]) if data.get("nota_final")
             else _placeholder("[Sección de texto fijo de la plantilla estándar del DERS.]"))

    # 15 Estado y firma
    b.append(_h1("15", "Estado del documento y firma"))
    b.append(_para(data["estado_documento"]) if data.get("estado_documento")
             else _placeholder("[Sección de texto fijo de la plantilla estándar del DERS (firma).]"))
    return b


# ------------------------------------------------- Ensamblado branded (AW-202)

def _meta_de(data):
    """Deriva {cliente, version, fecha} del JSON para rellenar la carátula del brand-kit."""
    doc = data.get("documento", {}) or {}
    return {"cliente": (data.get("cliente") or "").strip(),
            "version": doc.get("version", "") or "",
            "fecha": doc.get("fecha", "") or ""}


def _rellenar_caratula(doc_xml, meta):
    """Sustituye los tokens {{AW202_*}} de la carátula del brand-kit por los valores de meta."""
    repl = {"{{AW202_TITULO}}": meta.get("titulo") or "(documento)",
            "{{AW202_CLIENTE}}": meta.get("cliente") or "(cliente)",
            "{{AW202_VERSION}}": meta.get("version") or "",
            "{{AW202_FECHA}}": meta.get("fecha") or ""}
    for tok, val in repl.items():
        doc_xml = doc_xml.replace(tok, _esc(val))
    return doc_xml


def _ensamblar_branded(brandkit_path, cuerpo, meta, out_docx):
    """Ensambla el DOCX branded: copia el chrome del brand-kit verbatim, rellena la carátula e
    inserta `cuerpo` (list[<w:p>…]) entre los marcadores AW202:BODY_*. Conserva sectPr + firma."""
    cuerpo_xml = "".join(cuerpo)
    with zipfile.ZipFile(str(brandkit_path)) as zin:
        parts = [(i.filename, zin.read(i.filename)) for i in zin.infolist()]
    with zipfile.ZipFile(str(out_docx), "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in parts:
            if name == "word/document.xml":
                doc = _rellenar_caratula(data.decode("utf-8"), meta)
                doc = re.sub(re.escape(_BODY_START) + r".*?" + re.escape(_BODY_END),
                             lambda _m: cuerpo_xml, doc, count=1, flags=re.S)
                data = doc.encode("utf-8")
            zout.writestr(name, data)
    return out_docx


def build(json_path, out_docx, modelo="", dercas=False, schema_path=None,
          formal=False, branded=True, meta=None):
    """Genera un .docx desde el DERS/DERCAS.json.

    - `branded=True` (por defecto): parte del brand-kit 2026 (chrome + carátula + firma). Si el
      brand-kit falta o está corrupto, degrada a un .docx plano (stdlib) con aviso en stderr.
    - `formal=True`: salida limpia de cliente (sin intro/anotaciones; ver `_body_ders`).
    - `meta`: {cliente, version, fecha} para la carátula; si None se deriva del JSON.
    Si el DERS sigue `esquema_vacio` (requerimientos sin `seccion`), se funde antes sobre la
    plantilla canónica 2026. Devuelve la ruta de salida."""
    data = json.loads(Path(json_path).read_text(encoding="utf-8"))
    if not _esta_merged(data):
        plantilla = json.loads(Path(schema_path or _DEFAULT_PLANTILLA).read_text(encoding="utf-8"))
        data = merge_ders(data, plantilla)
    cuerpo = _body_ders(data, modelo, dercas, formal=formal)
    if branded:
        m = dict(meta or _meta_de(data))
        m.setdefault("titulo", "Documento de Especificaciones, Requerimientos y Criterios de "
                     "Aceptación (DERCAS)" if dercas
                     else "Documento de Especificaciones y Requerimientos de Software (DERS)")
        try:
            return _ensamblar_branded(_BRANDKIT, cuerpo, m, out_docx)
        except Exception as e:  # noqa: BLE001 — degradar a plano con aviso, no romper el pipeline
            print("AW-202: brand-kit no disponible (%s); se genera DOCX plano" % e, file=sys.stderr)
    return _write_docx(out_docx, cuerpo)


# ------------------------------------------------- Markdown → DOCX (portado de catalyst, AW-200)
# Usado por `matriz` (resumen auto-vs-manual) y disponible para cualquier resumen/plan markdown.

_ANCHO_TABLA = 9000   # twips (~ancho útil de la página con márgenes de 1")


def _peso_col(h):
    """Peso relativo de una columna por su cabecera (Valores ancha; Campo/Nombre medias)."""
    h = h.lower()
    if "valor" in h:
        return 3
    if "campo" in h or "nombre" in h or "qué hace" in h or "nota" in h:
        return 2
    return 1


def _tc(text, ancho, bold=False, fill=None):
    """Celda de tabla OOXML (`<w:tc>`) con ancho fijo (twips)."""
    tcw = '<w:tcW w:w="%d" w:type="dxa"/>' % ancho
    shd = '<w:shd w:val="clear" w:color="auto" w:fill="%s"/>' % fill if fill else ""
    return "<w:tc><w:tcPr>%s%s</w:tcPr><w:p>%s</w:p></w:tc>" % (tcw, shd, _run(text, bold=bold))


def _tabla_md(header, rows):
    """Tabla OOXML (`<w:tbl>`) con anchos de columna fijos y layout fijo (para que Writer no colapse)."""
    n = len(header)
    pesos = [_peso_col(h) for h in header]
    sp = sum(pesos) or n
    anchos = [max(700, _ANCHO_TABLA * p // sp) for p in pesos]
    bordes = "<w:tblBorders>" + "".join(
        '<w:%s w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>' % s
        for s in ("top", "left", "bottom", "right", "insideH", "insideV")) + "</w:tblBorders>"
    # Estilo de tabla de la plantilla 2026 (branded); en modo plano el estilo no existe y Word
    # cae a los bordes explícitos de abajo (degradación limpia).
    tblpr = ('<w:tblPr><w:tblStyle w:val="3257188"/><w:tblW w:w="%d" w:type="dxa"/>'
             '<w:tblLayout w:type="fixed"/>%s</w:tblPr>'
             % (sum(anchos), bordes))
    grid = "<w:tblGrid>%s</w:tblGrid>" % "".join('<w:gridCol w:w="%d"/>' % a for a in anchos)
    trs = ["<w:tr>%s</w:tr>" % "".join(_tc(h, anchos[j], bold=True, fill="D9D9D9")
                                       for j, h in enumerate(header))]
    for r in rows:
        cells = (list(r) + [""] * n)[:n]
        trs.append("<w:tr>%s</w:tr>" % "".join(_tc(c, anchos[j]) for j, c in enumerate(cells)))
    return "<w:tbl>%s%s%s</w:tbl>" % (tblpr, grid, "".join(trs))


def _es_fila_tabla(s):
    return s.startswith("|") and s.endswith("|") and s.count("|") >= 2


def _es_separador(s):
    cuerpo = s.replace("|", "").replace(":", "").replace(" ", "")
    return bool(cuerpo) and set(cuerpo) <= {"-"}


def _celdas(s):
    return [c.strip() for c in s.strip().strip("|").split("|")]


def build_markdown(md_text, out_docx, title=None, branded=False, meta=None):
    """Genera un .docx desde un texto markdown (resumen/plan de parametrización).
    Soporta encabezados `#`/`##`/`###`, viñetas `-`/`*`, **tablas** `| a | b |` y párrafos.

    `branded=True` (AW-202) parte del brand-kit (chrome + carátula); `meta` rellena la portada
    (`titulo`/`cliente`/`version`/`fecha`). Degrada a .docx plano si el brand-kit falta."""
    b = []
    if title and not branded:        # en branded el título va en la carátula, no en el cuerpo
        b.append(_p(title, style="Title"))
    lines = md_text.split("\n")
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1
            continue
        # tabla markdown: fila `| … |` seguida de separador `|---|---|`
        if _es_fila_tabla(s) and i + 1 < len(lines) and _es_separador(lines[i + 1].strip()):
            header = _celdas(s)
            i += 2
            rows = []
            while i < len(lines) and _es_fila_tabla(lines[i].strip()):
                rows.append(_celdas(lines[i].strip()))
                i += 1
            b.append(_tabla_md(header, rows))
            b.append(_p(""))            # párrafo de separación tras la tabla (Word lo requiere)
            continue
        if s.startswith("### "):
            b.append(_h2(s[4:].strip()))
        elif s.startswith("## "):
            b.append(_h2(s[3:].strip()))
        elif s.startswith("# "):
            b.append(_h1("", s[2:].strip()))
        elif s.startswith("- ") or s.startswith("* "):
            cont = s[2:].strip()
            pre = "•  "
            if cont.startswith("[ ]"):
                pre, cont = "☐  ", cont[3:].strip()      # casilla vacía
            elif cont[:3].lower() == "[x]":
                pre, cont = "☑  ", cont[3:].strip()      # casilla marcada
            b.append(_p_inline(pre + cont, style="Normal", indent=360))
        else:
            b.append(_p_inline(s, style="Normal"))
        i += 1
    if branded:
        m = dict(meta or {})
        m.setdefault("titulo", title or "Documento")
        try:
            return _ensamblar_branded(_BRANDKIT, b, m, out_docx)
        except Exception as e:  # noqa: BLE001 — degradar a plano con aviso
            print("AW-202: brand-kit no disponible (%s); se genera DOCX plano" % e, file=sys.stderr)
    return _write_docx(out_docx, b)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Genera DERS/DERCAS.docx branded desde el JSON")
    parser.add_argument("json", help="Ruta al DERS/DERCAS.json")
    parser.add_argument("out", help="Ruta de salida .docx")
    parser.add_argument("--schema", default=str(_DEFAULT_PLANTILLA),
                        help="Ruta a plantilla_ders.json (default: assets/schema/)")
    parser.add_argument("--modelo", default="", help="Etiqueta del modelo generador (opcional)")
    parser.add_argument("--formal", action="store_true",
                        help="Salida limpia de cliente (sin intro/anotaciones/trazabilidad)")
    parser.add_argument("--plano", action="store_true",
                        help="Sin branding (stdlib plano, sin brand-kit)")
    parser.add_argument("--dercas", action="store_true", help="Render de DERCAS (o env DERCAS=1)")
    parser.add_argument("--cliente", default=None, help="Carátula: nombre del cliente")
    parser.add_argument("--version", default=None, help="Carátula: versión del documento")
    parser.add_argument("--fecha", default=None, help="Carátula: fecha del documento")
    args = parser.parse_args(argv)
    meta = None
    if args.cliente or args.version or args.fecha:
        meta = {"cliente": args.cliente or "", "version": args.version or "", "fecha": args.fecha or ""}
    build(args.json, args.out, modelo=args.modelo,
          dercas=(args.dercas or os.environ.get("DERCAS") == "1"), schema_path=args.schema,
          formal=args.formal, branded=not args.plano, meta=meta)
    print("DOCX generado: %s" % args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
