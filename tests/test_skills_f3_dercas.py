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


# ---- AW-192: guard {{PREFIX}} en validar_ir.py ----

def test_validar_ir_rechaza_placeholder_en_api_name(tmp_path, capsys):
    """Un IR con {{PREFIX}}Tipo en api_name debe ser rechazado (placeholder sin sustituir)."""
    mod = _get_validar_ir()
    ir_bad = {
        "fields": [
            {"id": "fld-tipo", "match": {"module": "Leads", "api_name": "{{PREFIX}}Tipo"},
             "payload": {"module": "Leads", "field_label": "{{PREFIX}} Tipo", "data_type": "picklist",
                         "pick_list_values": [{"display_value": "A", "actual_value": "A"}]}},
        ]
    }
    ir_file = tmp_path / "ir_placeholder.json"
    ir_file.write_text(json.dumps(ir_bad))
    rc = mod.main([str(ir_file)])
    assert rc != 0, "IR con placeholder {{PREFIX}} debe ser rechazado"
    captured = capsys.readouterr()
    assert "placeholder" in (captured.out + captured.err).lower() or \
           "PREFIX" in (captured.out + captured.err), \
        "El mensaje de error debe mencionar 'placeholder' o 'PREFIX'"


def test_validar_ir_rechaza_placeholder_en_nombre_role(tmp_path, capsys):
    """Un IR con {{PREFIX}} en name de un role debe ser rechazado."""
    mod = _get_validar_ir()
    ir_bad = {
        "roles": [
            {"id": "role-ceo", "match": {"name": "{{PREFIX}} CEO"},
             "payload": {"name": "{{PREFIX}} CEO", "display_label": "{{PREFIX}} CEO"}},
        ]
    }
    ir_file = tmp_path / "ir_placeholder_role.json"
    ir_file.write_text(json.dumps(ir_bad))
    rc = mod.main([str(ir_file)])
    assert rc != 0, "IR con placeholder {{PREFIX}} en role.name debe ser rechazado"


def test_validar_ir_rechaza_placeholder_en_workflow_fields(tmp_path):
    """Un IR con {{PREFIX}} en criteria.field o actions[].field de un workflow debe ser rechazado
    (AW-192: es justo donde la convención vieja ponía {{PREFIX}}Tipo/{{PREFIX}}Prioridad)."""
    mod = _get_validar_ir()
    # criteria.field con placeholder
    ir_criteria = {
        "workflows": [
            {"id": "wf-prio", "match": {"module": "Leads", "name": "Asignar prioridad"},
             "payload": {"module": "Leads", "name": "Asignar prioridad",
                         "criteria": {"field": "{{PREFIX}}Tipo", "operator": "equal", "value": "Clinica"},
                         "actions": [{"type": "field_update", "field": "Prioridad", "value": "Alta"}]}},
        ]
    }
    f1 = tmp_path / "ir_wf_criteria.json"
    f1.write_text(json.dumps(ir_criteria))
    assert mod.main([str(f1)]) != 0, "placeholder en criteria.field debe rechazarse"
    # actions[].field con placeholder
    ir_action = {
        "workflows": [
            {"id": "wf-prio", "match": {"module": "Leads", "name": "Asignar prioridad"},
             "payload": {"module": "Leads", "name": "Asignar prioridad",
                         "criteria": {"field": "Tipo", "operator": "equal", "value": "Clinica"},
                         "actions": [{"type": "field_update", "field": "{{PREFIX}}Prioridad", "value": "Alta"}]}},
        ]
    }
    f2 = tmp_path / "ir_wf_action.json"
    f2.write_text(json.dumps(ir_action))
    assert mod.main([str(f2)]) != 0, "placeholder en actions[].field debe rechazarse"


def test_validar_ir_acepta_nombres_planos(tmp_path):
    """Un IR con nombres planos (sin {{PREFIX}}) debe pasar validación."""
    mod = _get_validar_ir()
    ir_ok = {
        "fields": [
            {"id": "fld-origen", "match": {"module": "Leads", "api_name": "Origen"},
             "payload": {"module": "Leads", "field_label": "Origen", "data_type": "picklist",
                         "pick_list_values": [{"display_value": "Meta Ads", "actual_value": "Meta Ads"}]}},
        ],
        "roles": [
            {"id": "role-ceo", "match": {"name": "CEO"},
             "payload": {"name": "CEO", "display_label": "CEO"}},
        ]
    }
    ir_file = tmp_path / "ir_plano.json"
    ir_file.write_text(json.dumps(ir_ok))
    rc = mod.main([str(ir_file)])
    assert rc == 0, "IR con nombres planos debe ser válido"


# ---- AW-192: mapper_ir.md.tmpl y SKILL.md sin {{PREFIX}} ----

def test_mapper_ir_no_tiene_prefix():
    """mapper_ir.md.tmpl NO debe contener {{PREFIX}} (AW-192: nombres planos)."""
    mapper = DERCAS_DIR / "assets" / "prompts" / "mapper_ir.md.tmpl"
    text = mapper.read_text(encoding="utf-8")
    assert "{{PREFIX}}" not in text, \
        "mapper_ir.md.tmpl aún contiene {{PREFIX}} — debe usar nombres planos (AW-192)"


def test_skill_md_dercas_no_tiene_prefix():
    """SKILL.md de dercas NO debe mencionar {{PREFIX}}."""
    text = (DERCAS_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "{{PREFIX}}" not in text, \
        "SKILL.md de dercas aún contiene {{PREFIX}} (AW-192)"


def test_skill_md_ders_no_tiene_prefix():
    """SKILL.md de ders NO debe mencionar {{PREFIX}} en instrucciones al consultor."""
    ders_dir = SKILLS_DIR / "ders"
    text = (ders_dir / "SKILL.md").read_text(encoding="utf-8")
    assert "{{PREFIX}}" not in text, \
        "SKILL.md de ders aún contiene {{PREFIX}} (AW-192)"
