"""AW-188 Fase 5 — skill `plan`.

Verifica:
- Assets revisor_ir + revisor_correcciones presentes
- revision_ir.py sobre fixture produce revision.json / revision.md
"""
import importlib
import json
import pathlib
import sys

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
PLAN_DIR = SKILLS_DIR / "plan"
FIXTURE_DIR = SCRIPTS_DIR / "tests" / "fixtures"


def test_assets_prompts_plan_presentes():
    """revisor_ir.md.tmpl debe existir en plan/assets/prompts/;
    revisor_correcciones.md.tmpl NO debe existir (AW-193: prompt mal cableado eliminado)."""
    prompts_dir = PLAN_DIR / "assets" / "prompts"
    tmpl_revisor_ir = prompts_dir / "revisor_ir.md.tmpl"
    assert tmpl_revisor_ir.exists(), f"Falta {tmpl_revisor_ir}"
    tmpl_correcciones = prompts_dir / "revisor_correcciones.md.tmpl"
    assert not tmpl_correcciones.exists(), \
        "revisor_correcciones.md.tmpl debe haber sido eliminado (AW-193)"


def test_prompts_plan_tienen_comentario_origen():
    """Los prompts presentes deben tener comentario HTML de origen (AW-188)."""
    prompts_dir = PLAN_DIR / "assets" / "prompts"
    # Solo revisor_ir.md.tmpl (revisor_correcciones eliminado por AW-193)
    for nombre in ["revisor_ir"]:
        tmpl = prompts_dir / f"{nombre}.md.tmpl"
        text = tmpl.read_text(encoding="utf-8")
        assert "<!-- origen:" in text, f"{nombre}.md.tmpl no tiene comentario de origen"
        assert "AW-188" in text, f"{nombre}.md.tmpl no menciona AW-188 en origen"


def test_skill_md_plan_menciona_revisor_ir():
    """SKILL.md de plan debe mencionar revisor_ir y ir.json."""
    text = (PLAN_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "revisor_ir" in text, "SKILL.md plan no menciona revisor_ir"
    assert "ir.json" in text, "SKILL.md plan no menciona ir.json"
    assert "Plan.md" in text, "SKILL.md plan no menciona Plan.md"


def test_skill_md_plan_distingue_criterio_vs_determinismo():
    """SKILL.md de plan debe separar claramente qué es criterio (Claude) vs determinismo (script)."""
    text = (PLAN_DIR / "SKILL.md").read_text(encoding="utf-8")
    # Debe haber alguna mención a "determinista" o "script" vs "Claude"
    assert "Claude" in text, "SKILL.md plan no menciona Claude como motor de criterio"
    assert any(kw in text.lower() for kw in ["determinista", "script", "revision_ir"]), \
        "SKILL.md plan no menciona la parte determinista"


def _get_revision_ir():
    """Importa revision_ir desde skills/plan/scripts/."""
    scripts_skill = PLAN_DIR / "scripts"
    if str(scripts_skill) not in sys.path:
        sys.path.insert(0, str(scripts_skill))
    # Asegurar que parametrizacion está disponible
    if str(SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPTS_DIR))
    if "revision_ir" in sys.modules:
        del sys.modules["revision_ir"]
    return importlib.import_module("revision_ir")


def test_revision_ir_fixture_produce_json(tmp_path):
    """revision_ir.py sobre fixture ir_jaque_r1r3.json produce revision.json."""
    mod = _get_revision_ir()
    fixture = FIXTURE_DIR / "ir_jaque_r1r3.json"
    out_json = tmp_path / "revision.json"

    rc = mod.main([
        "--ir", str(fixture),
        "--out-json", str(out_json),
    ])

    assert rc == 0, f"revision_ir falló con rc={rc}"
    assert out_json.exists(), "No se generó revision.json"
    data = json.loads(out_json.read_text())
    assert isinstance(data, dict), "revision.json no es un objeto"


def test_revision_ir_fixture_produce_md(tmp_path):
    """revision_ir.py sobre fixture produce revision.md."""
    mod = _get_revision_ir()
    fixture = FIXTURE_DIR / "ir_jaque_r1r3.json"
    out_md = tmp_path / "revision.md"

    rc = mod.main([
        "--ir", str(fixture),
        "--out-md", str(out_md),
    ])

    assert rc == 0
    assert out_md.exists(), "No se generó revision.md"
    text = out_md.read_text()
    assert len(text) > 0, "revision.md está vacío"


def test_revision_ir_detecta_id_duplicado(tmp_path):
    """revision_ir.py debe detectar ids duplicados y reflejarlo en la revisión."""
    mod = _get_revision_ir()
    ir_bad = {
        "fields": [
            {"id": "fld-dup", "match": {"module": "Leads", "api_name": "X_Campo"},
             "payload": {"module": "Leads", "field_label": "Campo X", "data_type": "text"}},
            {"id": "fld-dup", "match": {"module": "Leads", "api_name": "Y_Campo"},
             "payload": {"module": "Leads", "field_label": "Campo Y", "data_type": "text"}},
        ]
    }
    ir_file = tmp_path / "ir_dup.json"
    ir_file.write_text(json.dumps(ir_bad))
    out_json = tmp_path / "revision.json"

    rc = mod.main(["--ir", str(ir_file), "--out-json", str(out_json)])
    # Puede que rc!=0 o que el json tenga errores
    if out_json.exists():
        data = json.loads(out_json.read_text())
        # Debe haber algún indicador de error
        errores = data.get("errores") or data.get("errors") or []
        assert errores or rc != 0, "No detectó el id duplicado"
    else:
        assert rc != 0, "Con IR inválido debe fallar"


# ---- AW-193: plan SKILL.md — subagente + sin revisor_correcciones ----

def test_skill_md_plan_instruye_subagente_auditoria():
    """SKILL.md de plan debe instruir el uso de un subagente para auditoría independiente
    (AW-193: juicio de fidelidad en contexto aislado)."""
    text = (PLAN_DIR / "SKILL.md").read_text(encoding="utf-8")
    # Debe mencionar subagente / Agent (la herramienta Claude Code)
    assert any(kw in text for kw in ["subagente", "Agent", "subagent"]), \
        "SKILL.md plan debe mencionar subagente/Agent para el juicio de fidelidad independiente (AW-193)"
    # Debe indicar que es contexto independiente / aislado
    assert any(kw in text.lower() for kw in ["independiente", "contexto", "aislado", "fresco"]), \
        "SKILL.md plan debe explicar que el subagente trabaja en contexto independiente (AW-193)"


def test_skill_md_plan_no_menciona_revisor_correcciones():
    """SKILL.md de plan NO debe mencionar revisor_correcciones (AW-193: prompt mal cableado eliminado)."""
    text = (PLAN_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "revisor_correcciones" not in text, \
        "SKILL.md plan aún menciona revisor_correcciones (AW-193: debe estar eliminado)"
