"""AW-188 Fase 1 — Esqueleto + convención de ficheros.

Verifica:
- Que existen los 5 SKILL.md bajo plugin-claude/skills/{ders,dercas,matriz,plan,implementar}/
- Que existe la convención centralizada CONVENCION.md
- Que el helper de rutas (skills_paths) resuelve correctamente las rutas por cliente según §4.3
"""
import pathlib
import os

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"

SKILLS = ["ders", "dercas", "matriz", "plan", "implementar"]


def test_existen_5_skill_md():
    """Fase 1 RED→GREEN: los 5 SKILL.md deben existir."""
    for skill in SKILLS:
        skill_md = SKILLS_DIR / skill / "SKILL.md"
        assert skill_md.exists(), f"Falta {skill_md}"


def test_existe_convencion_md():
    """El fichero CONVENCION.md debe existir en plugin-claude/skills/."""
    conv = SKILLS_DIR / "CONVENCION.md"
    assert conv.exists(), f"Falta {conv}"


def test_convencion_contiene_rutas_clave():
    """CONVENCION.md debe documentar las rutas estándar del §4.3."""
    conv = SKILLS_DIR / "CONVENCION.md"
    text = conv.read_text(encoding="utf-8")
    for fname in ["transcripciones.txt", "DERS.json", "DERCAS.json", "ir.json",
                  "Matriz_CRM.xlsx", "Plan.md", "revision.json", "resumen_implementacion.md"]:
        assert fname in text, f"CONVENCION.md no menciona {fname}"


def test_helper_rutas_cliente(tmp_path):
    """El helper de rutas deve resolver ~/Sagitaz/clientes/<cliente>/<fichero> respetando override."""
    import sys
    sys.path.insert(0, str(SKILLS_DIR))
    from skills_paths import cliente_path

    # Con override de raíz via env o parámetro
    raiz = tmp_path / "clientes"
    p = cliente_path("tufisio", "DERS.json", root=raiz)
    assert p == raiz / "tufisio" / "DERS.json"


def test_helper_rutas_default():
    """Sin override, la raíz debe ser ~/Sagitaz/clientes (o SAGITAZ_CLIENTES_ROOT)."""
    import sys
    sys.path.insert(0, str(SKILLS_DIR))
    from skills_paths import cliente_path

    # Sobrescribir con env vacío para verificar comportamiento default seguro
    old = os.environ.pop("SAGITAZ_CLIENTES_ROOT", None)
    try:
        p = cliente_path("test_cliente", "ir.json")
        expected_default = pathlib.Path.home() / "Sagitaz" / "clientes" / "test_cliente" / "ir.json"
        assert p == expected_default
    finally:
        if old is not None:
            os.environ["SAGITAZ_CLIENTES_ROOT"] = old


def test_helper_rutas_env_override(tmp_path):
    """SAGITAZ_CLIENTES_ROOT env var debe sobrescribir la raíz para tests offline."""
    import sys
    sys.path.insert(0, str(SKILLS_DIR))
    from skills_paths import cliente_path

    os.environ["SAGITAZ_CLIENTES_ROOT"] = str(tmp_path / "clientes")
    try:
        p = cliente_path("acme", "DERCAS.json")
        assert p == tmp_path / "clientes" / "acme" / "DERCAS.json"
    finally:
        del os.environ["SAGITAZ_CLIENTES_ROOT"]


def test_skill_md_tienen_frontmatter_yaml():
    """Cada SKILL.md debe tener frontmatter YAML con name y description."""
    for skill in SKILLS:
        skill_md = SKILLS_DIR / skill / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        assert text.startswith("---"), f"{skill}/SKILL.md no empieza con frontmatter YAML (---)"
        assert "name:" in text, f"{skill}/SKILL.md no tiene 'name:' en frontmatter"
        assert "description:" in text, f"{skill}/SKILL.md no tiene 'description:' en frontmatter"
