#!/usr/bin/env python3
"""build_brandkit.py — Deriva el brand-kit del plugin desde la plantilla oficial 2026 (AW-202).

**Dev-only, NO se ejecuta en runtime.** Documenta y hace reproducible la derivación del asset
`scripts/docx/assets/brandkit_2026.docx` a partir del `.docx` fuente facilitado por el usuario
(que NO se commitea por tamaño, ~2.1 MB). El brand-kit es el *chrome* branded (stdlib pura, zipfile):

  - **Conserva verbatim:** header1 (+logo), footer2, `word/media/*`, `word/fonts/*` (+fontTable),
    `styles.xml`, `theme1.xml`, `numbering.xml`, `settings.xml`, `docProps/custom.xml`.
  - **Reescribe `word/document.xml`** a: carátula (título + logos del original) + 3 párrafos de meta
    con tokens `{{AW202_CLIENTE/VERSION/FECHA}}` + salto de página + región de cuerpo vacía delimitada
    por `<!-- AW202:BODY_START -->`/`<!-- AW202:BODY_END -->` + bloque de firma del original + `sectPr`.
  - **Elimina:** `comments.xml`/`commentsExtended.xml` (+ sus rels y Content-Types), el TOC de ejemplo,
    el cuerpo de muestra (secciones 1–14) y los textos editoriales ("Instrucciones:", etc.).

El brand-kit **no** contiene datos de cliente ni instrucciones de la plantilla; es chrome genérico.

Uso (dev):
    python build_brandkit.py /ruta/a/Plantilla-DERS-DERCAS-CRM-2026.docx \
        [salida.docx]   # default: scripts/docx/assets/brandkit_2026.docx

Fuente de referencia (interna del equipo): `Plantilla-DERS-DERCAS-CRM-2026.docx` (no versionada;
se pasa por argumento). El brand-kit reducido resultante sí se commitea como asset del plugin.
"""
import re
import sys
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_DEFAULT_OUT = _HERE / "assets" / "brandkit_2026.docx"

# Fronteras verificadas sobre la plantilla 2026 (hijos top-level de <w:body>):
#   [0..12]   carátula (título+logos; [13] inicia el campo TOC)
#   [13..599] campo TOC + cuerpo de ejemplo (secciones 1–14)  → se eliminan
#   [600..613] bloque de firma ("Estado del documento…")      → se conserva
#   [614]     <w:sectPr> (refs header1/footer2)               → se conserva
_COVER_END = 13        # exclusivo: hijos [0.._COVER_END)
_SIGN_START = 600      # inclusivo: hijos [_SIGN_START..sectPr)

_META_PARAS = (
    '<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>'
    '<w:r><w:t xml:space="preserve">Cliente: {{AW202_CLIENTE}}</w:t></w:r></w:p>'
    '<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>'
    '<w:r><w:t xml:space="preserve">Versión: {{AW202_VERSION}}</w:t></w:r></w:p>'
    '<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>'
    '<w:r><w:t xml:space="preserve">Fecha: {{AW202_FECHA}}</w:t></w:r></w:p>'
)
_PAGE_BREAK = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'
_BODY_REGION = '<!-- AW202:BODY_START --><!-- AW202:BODY_END -->'

_DROP_PARTS = {"word/comments.xml", "word/commentsExtended.xml"}


def _split_body_children(body_inner):
    """Devuelve la lista de hijos top-level de <w:body> (w:p | w:tbl | w:sectPr)."""
    return [m.group(0) for m in re.finditer(
        r'<w:(p|tbl|sectPr)\b(?:[^>]*?/>|.*?</w:\1>)', body_inner, re.S)]


def _tokenize_title(p_xml):
    """Reemplaza el texto del título de portada por el token {{AW202_TITULO}} (conserva el logo y el
    resto del párrafo): el primer run de texto pasa a ser el token, los demás se vacían."""
    runs = list(re.finditer(r'(<w:t\b[^>]*>)(.*?)(</w:t>)', p_xml, re.S))
    if not runs:
        return p_xml
    out, last = [], 0
    for i, m in enumerate(runs):
        out.append(p_xml[last:m.start()])
        out.append(m.group(1) + ("{{AW202_TITULO}}" if i == 0 else "") + m.group(3))
        last = m.end()
    out.append(p_xml[last:])
    return "".join(out)


def _rewrite_document(doc_xml):
    """Reduce el document.xml al chrome: carátula + meta + cuerpo vacío + firma + sectPr."""
    m = re.search(r'(<w:document\b[^>]*>)(.*?)<w:body>(.*)</w:body>\s*(</w:document>)', doc_xml, re.S)
    if not m:
        raise SystemExit("document.xml inesperado: no se encontró <w:body>")
    doc_open, pre_body, body_inner, doc_close = m.groups()
    children = _split_body_children(body_inner)
    if not children or not children[-1].startswith("<w:sectPr"):
        raise SystemExit("document.xml inesperado: el último hijo del body no es <w:sectPr>")
    cover = children[:_COVER_END]
    if cover:
        cover[0] = _tokenize_title(cover[0])      # título de portada → {{AW202_TITULO}}
    sign = children[_SIGN_START:-1]
    sectpr = children[-1]
    new_body = ("".join(cover) + _META_PARAS + _PAGE_BREAK
                + _BODY_REGION + "".join(sign) + sectpr)
    return f"{doc_open}{pre_body}<w:body>{new_body}</w:body>{doc_close}"


def _prune_rels(rels_xml):
    """Elimina las relaciones de comments/commentsExtended."""
    return re.sub(
        r'<Relationship [^>]*Target="comments(Extended)?\.xml"[^>]*/>', "", rels_xml)


def _prune_content_types(ct_xml):
    """Elimina los Override de comments/commentsExtended."""
    return re.sub(
        r'<Override [^>]*PartName="/word/comments(Extended)?\.xml"[^>]*/>', "", ct_xml)


def build_brandkit(src_docx, out_docx=_DEFAULT_OUT):
    src_docx, out_docx = Path(src_docx), Path(out_docx)
    out_docx.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(str(src_docx)) as zin:
        items = [(i.filename, zin.read(i.filename)) for i in zin.infolist()]
    with zipfile.ZipFile(str(out_docx), "w", zipfile.ZIP_DEFLATED) as zout:
        for name, data in items:
            if name in _DROP_PARTS:
                continue
            if name == "word/document.xml":
                data = _rewrite_document(data.decode("utf-8")).encode("utf-8")
            elif name == "word/_rels/document.xml.rels":
                data = _prune_rels(data.decode("utf-8")).encode("utf-8")
            elif name == "[Content_Types].xml":
                data = _prune_content_types(data.decode("utf-8")).encode("utf-8")
            zout.writestr(name, data)
    return out_docx


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    out = build_brandkit(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else _DEFAULT_OUT)
    print(f"brand-kit generado: {out} ({out.stat().st_size} bytes)")
