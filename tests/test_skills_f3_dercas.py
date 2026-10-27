"""AW-188 Fase 3 — skill `dercas` (+IR).

Verifica:
- Assets patcher_dercas + mapper_ir presentes
- validar_ir.py: IR válido pasa, id duplicado falla, dep colgante falla
"""
import importlib
import pathlib
import sys
import json

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
DERCAS_DIR = SKILLS_DIR / "dercas"
FIXTURE_DIR = SCRIPTS_DIR / "tests" / "fixtures"


def test_assets_prompts_dercas_presentes():
    """patcher_dercas.md.tmpl y mapper_ir.md.tmpl deben existir en dercas/assets/prompts/."""
    prompts_dir = DERCAS_DIR / "assets" / "prompts"
    for nombre in ["patcher_dercas", "mapper_ir"]:
        tmpl = prompts_dir / f"{nombre}.md.tmpl"
        assert tmpl.exists(), f"Falta {tmpl}"


def test_prompts_dercas_tienen_comentario_origen():
    """Los prompts copiados deben tener comentario HTML de origen (AW-188)."""
    prompts_dir = DERCAS_DIR / "assets" / "prompts"
    for nombre in ["patcher_dercas", "mapper_ir"]:
        tmpl = prompts_dir / f"{nombre}.md.tmpl"
        text = tmpl.read_text(encoding="utf-8")
        assert "<!-- origen:" in text, f"{nombre}.md.tmpl no tiene comentario de origen"
        assert "AW-188" in text, f"{nombre}.md.tmpl no menciona AW-188 en origen"


def test_skill_md_dercas_menciona_2_fases():
    """SKILL.md de dercas debe documentar las 2 fases de Claude (DERCAS + IR)."""
    text = (DERCAS_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "patcher_dercas" in text, "SKILL.md dercas no menciona patcher_dercas"
    assert "mapper_ir" in text, "SKILL.md dercas no menciona mapper_ir"
    assert "ir.json" in text, "SKILL.md dercas no menciona ir.json"
    assert "DERCAS.json" in text, "SKILL.md dercas no menciona DERCAS.json"


def _get_validar_ir():
    """Importa validar_ir desde skills/dercas/scripts/."""
    scripts_skill = DERCAS_DIR / "scripts"
    if str(scripts_skill) not in sys.path:
        sys.path.insert(0, str(scripts_skill))
    if "validar_ir" in sys.modules:
        del sys.modules["validar_ir"]
    return importlib.import_module("validar_ir")


def test_validar_ir_fixture_valido_pasa(tmp_path):
    """El fixture ir_jaque_r1r3.json debe pasar validación de validar_ir."""
    mod = _get_validar_ir()
    fixture = FIXTURE_DIR / "ir_jaque_r1r3.json"
    rc = mod.main([str(fixture)])
    assert rc == 0, "El IR fixture válido debe pasar"


def test_validar_ir_id_duplicado_falla(tmp_path):
    """Un IR con id duplicado debe fallar con rc!=0 y mensaje claro."""
    mod = _get_validar_ir()
    # Crear IR con id duplicado
    ir_bad = {
        "fields": [
            {"id": "fld-dup", "match": {"module": "Leads", "api_name": "X_Campo"},
             "payload": {"module": "Leads", "field_label": "Campo X", "data_type": "text"}},
            {"id": "fld-dup", "match": {"module": "Leads", "api_name": "Y_Campo"},
             "payload": {"module": "Leads", "field_label": "Campo Y", "data_type": "text"}},
        ]
    }
    ir_file = tmp_path / "ir_bad_dup.json"
    ir_file.write_text(json.dumps(ir_bad))
    rc = mod.main([str(ir_file)])
    assert rc != 0, "IR con id duplicado debe fallar"


def test_validar_ir_dep_colgante_falla(tmp_path):
    """Un IR con depends_on a id inexistente debe fallar."""
    mod = _get_validar_ir()
    ir_bad = {
        "fields": [
            {"id": "fld-real", "match": {"module": "Leads", "api_name": "X_Campo"},
             "payload": {"module": "Leads", "field_label": "Campo X", "data_type": "text"},
             "depends_on": ["fld-inexistente"]},
        ]
    }
    ir_file = tmp_path / "ir_bad_dep.json"
    ir_file.write_text(json.dumps(ir_bad))
    rc = mod.main([str(ir_file)])
    assert rc != 0, "IR con dependencia colgante debe fallar"


def test_validar_ir_ir_probe_workflow_pasa():
    """El fixture ir_probe_workflow.json debe pasar validación."""
    mod = _get_validar_ir()
    fixture = FIXTURE_DIR / "ir_probe_workflow.json"
    if not fixture.exists():
        import pytest; pytest.skip("Fixture ir_probe_workflow.json no disponible")
    rc = mod.main([str(fixture)])
    assert rc == 0, "ir_probe_workflow.json debe ser válido"
