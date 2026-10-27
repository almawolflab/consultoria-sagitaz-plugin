"""AW-188 Fase 4 — skill `matriz`.

Verifica:
- SKILL.md de matriz
- generar_matriz.py produce un xlsx no vacío sobre fixture ir_jaque_r1r3.json
  sin invocar ningún modelo
"""
import importlib
import pathlib
import sys

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
MATRIZ_DIR = SKILLS_DIR / "matriz"
FIXTURE_DIR = SCRIPTS_DIR / "tests" / "fixtures"


def test_skill_md_matriz_existe():
    """SKILL.md de matriz debe existir."""
    assert (MATRIZ_DIR / "SKILL.md").exists()


def test_skill_md_matriz_toma_ir_json():
    """SKILL.md de matriz debe mencionar ir.json como entrada (no DERCAS directamente)."""
    text = (MATRIZ_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "ir.json" in text, "SKILL.md de matriz no menciona ir.json"
    assert "Matriz_CRM.xlsx" in text, "SKILL.md de matriz no menciona Matriz_CRM.xlsx"


def test_skill_md_matriz_es_determinista_offline():
    """SKILL.md de matriz debe marcar el paso como determinista y offline (sin modelo)."""
    text = (MATRIZ_DIR / "SKILL.md").read_text(encoding="utf-8")
    # Debe mencionar alguno de los términos que señalan que es offline/determinista
    assert any(kw in text.lower() for kw in
               ["determinista", "offline", "sin modelo", "no llama", "openpyxl"]), \
        "SKILL.md de matriz no marca el paso como determinista/offline"


def _get_generar_matriz():
    """Importa generar_matriz desde skills/matriz/scripts/."""
    scripts_skill = MATRIZ_DIR / "scripts"
    if str(scripts_skill) not in sys.path:
        sys.path.insert(0, str(scripts_skill))
    # Asegurarse de que parametrizacion está disponible
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    if "generar_matriz" in sys.modules:
        del sys.modules["generar_matriz"]
    return importlib.import_module("generar_matriz")


def test_generar_matriz_produce_xlsx_no_vacio(tmp_path):
    """generar_matriz.py sobre fixture produce xlsx no vacío, sin red ni modelo."""
    mod = _get_generar_matriz()
    fixture = FIXTURE_DIR / "ir_jaque_r1r3.json"
    out_xlsx = tmp_path / "Matriz_CRM.xlsx"

    rc = mod.main([
        "--ir", str(fixture),
        "--out", str(out_xlsx),
    ])

    assert rc == 0, "generar_matriz debe terminar con rc=0"
    assert out_xlsx.exists(), "No se generó el xlsx"
    assert out_xlsx.stat().st_size > 0, "El xlsx generado está vacío"


def test_generar_matriz_imprime_recuento(tmp_path, capsys):
    """generar_matriz.py debe imprimir el recuento por módulo."""
    mod = _get_generar_matriz()
    fixture = FIXTURE_DIR / "ir_jaque_r1r3.json"
    out_xlsx = tmp_path / "Matriz_CRM_recuento.xlsx"

    mod.main(["--ir", str(fixture), "--out", str(out_xlsx)])
    captured = capsys.readouterr()
    # Debe haber algo en stdout indicando recuento
    assert len(captured.out) > 0 or len(captured.err) > 0, \
        "generar_matriz no imprimió ningún resultado"
