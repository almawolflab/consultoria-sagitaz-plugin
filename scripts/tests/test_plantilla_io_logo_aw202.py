"""AW-202 Fase 6 — la matriz conserva el logo.

`escribir_premarcada` usa openpyxl (`load_workbook`+`save`), que **sin Pillow descarta las imágenes
embebidas** (media, drawings, rels de hoja y el `<drawing>` del sheet). El fix re-inyecta esos parts
por zip tras el save, para que el `.xlsx` de salida conserve el logo de la plantilla base.
"""
import warnings
import zipfile
from pathlib import Path

from parametrizacion.plantilla_io import cargar_descriptor, escribir_premarcada
from parametrizacion.generador_plantilla import ir_a_propuestas
from parametrizacion.ir import load_ir

FIX = Path(__file__).resolve().parent / "fixtures" / "ir_jaque_r1r3.json"


def _matriz(tmp_path):
    warnings.simplefilter("ignore")
    desc = cargar_descriptor(None)
    ir = load_ir(str(FIX))
    out = tmp_path / "Matriz_CRM.xlsx"
    escribir_premarcada(desc, ir_a_propuestas(ir, desc), str(out))
    return out


def test_matriz_conserva_media_y_drawings(tmp_path):
    out = _matriz(tmp_path)
    names = zipfile.ZipFile(str(out)).namelist()
    assert any(n.startswith("xl/media/") for n in names), "xl/media/ vacío: se perdió el logo"
    assert any(n.startswith("xl/drawings/drawing") for n in names), "faltan los drawings"


def test_matriz_sheet_referencia_drawing(tmp_path):
    out = _matriz(tmp_path)
    z = zipfile.ZipFile(str(out))
    assert "xl/worksheets/_rels/sheet1.xml.rels" in z.namelist()
    assert "<drawing" in z.read("xl/worksheets/sheet1.xml").decode("utf-8", "replace")


def test_matriz_content_types_validos(tmp_path):
    out = _matriz(tmp_path)
    ct = zipfile.ZipFile(str(out)).read("[Content_Types].xml").decode("utf-8")
    assert 'Extension="png"' in ct
    assert "drawing+xml" in ct


def test_matriz_sigue_abriendo_con_openpyxl(tmp_path):
    out = _matriz(tmp_path)
    from openpyxl import load_workbook
    warnings.simplefilter("ignore")
    wb = load_workbook(str(out))
    assert wb.sheetnames
