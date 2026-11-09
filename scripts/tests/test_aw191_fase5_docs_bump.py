"""AW-191 Fase 5 — Docs + bump (AC-8, AC-9, AC-10).

AC-8: Sin menciones "gemini" (case-insensitive) en la superficie del consultor:
      skills/*/SKILL.md, README.md, docs/setup_crm_consultor.md.
AC-9: Sin refs AW-18x en skills/*/SKILL.md, README.md, docs/setup_crm_consultor.md.
      (Excluidas: assets/prompts/*.tmpl, CONVENCION.md, skills_paths.py — dev-facing).
AC-10: Versión 0.1.2 en .claude-plugin/plugin.json y .claude-plugin/marketplace.json.
"""
import json
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent.parent
SKILLS_DIR = PLUGIN_ROOT / "skills"
README = PLUGIN_ROOT / "README.md"
SETUP_CRM = PLUGIN_ROOT / "docs" / "setup_crm_consultor.md"
PLUGIN_JSON = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = PLUGIN_ROOT / ".claude-plugin" / "marketplace.json"


def _surface_files():
    """Ficheros de la superficie del consultor (excluye templates de prompts y dev-facing)."""
    files = []
    # skills/*/SKILL.md
    for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
        files.append(skill_md)
    if README.exists():
        files.append(README)
    if SETUP_CRM.exists():
        files.append(SETUP_CRM)
    return files


class TestAusenciaGemini:
    """AC-8: Sin menciones a Gemini en la superficie del consultor."""

    def test_sin_gemini_en_skill_mds(self):
        """skills/*/SKILL.md no deben mencionar 'gemini'."""
        for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
            content = skill_md.read_text()
            matches = re.findall(r"gemini", content, re.IGNORECASE)
            assert not matches, (
                f"{skill_md.relative_to(PLUGIN_ROOT)} contiene 'Gemini': {matches}"
            )

    def test_sin_gemini_en_readme(self):
        """README.md no debe mencionar 'gemini'."""
        if not README.exists():
            return
        content = README.read_text()
        matches = re.findall(r"gemini", content, re.IGNORECASE)
        assert not matches, f"README.md contiene 'Gemini': {matches}"

    def test_sin_gemini_en_setup_crm(self):
        """docs/setup_crm_consultor.md no debe mencionar 'gemini'."""
        if not SETUP_CRM.exists():
            return
        content = SETUP_CRM.read_text()
        matches = re.findall(r"gemini", content, re.IGNORECASE)
        assert not matches, f"setup_crm_consultor.md contiene 'Gemini': {matches}"


class TestAusenciaAW18x:
    """AC-9: Sin refs AW-18x en la superficie del consultor.

    Excluidos (dev-facing): assets/prompts/*.tmpl, CONVENCION.md, skills_paths.py.
    """

    # Regex robusto: cualquier AW-18x del Epic del plugin (185..189), no solo refs concretas.
    _AW_REF = re.compile(r"AW-18[0-9]")

    def test_sin_aw18x_en_todos_los_skill_md(self):
        """Ningún skills/*/SKILL.md debe contener AW-18[0-9] (superficie del consultor)."""
        for skill_md in SKILLS_DIR.glob("*/SKILL.md"):
            matches = self._AW_REF.findall(skill_md.read_text())
            assert not matches, (
                f"{skill_md.relative_to(SKILLS_DIR.parent)} contiene refs internas {set(matches)}"
            )

    def test_sin_aw18x_en_readme(self):
        """README.md no debe contener AW-18[0-9]."""
        if not README.exists():
            return
        matches = self._AW_REF.findall(README.read_text())
        assert not matches, f"README.md contiene refs internas {set(matches)}"

    def test_sin_aw18x_en_setup_crm(self):
        """docs/setup_crm_consultor.md no debe contener AW-18[0-9]."""
        if not SETUP_CRM.exists():
            return
        matches = self._AW_REF.findall(SETUP_CRM.read_text())
        assert not matches, f"setup_crm_consultor.md contiene refs internas {set(matches)}"


class TestVersionBump:
    """AC-10: Versión 0.1.4 en plugin.json y marketplace.json (bumpeada por AW-192/193)."""

    def test_plugin_json_version(self):
        """plugin.json debe tener version 0.1.4."""
        assert PLUGIN_JSON.exists(), f"No existe: {PLUGIN_JSON}"
        data = json.loads(PLUGIN_JSON.read_text())
        assert data.get("version") == "0.1.4", (
            f"plugin.json version={data.get('version')!r}, esperado '0.1.4'"
        )

    def test_marketplace_json_version(self):
        """marketplace.json debe tener version 0.1.4 en el plugin consultoria-sagitaz."""
        assert MARKETPLACE_JSON.exists(), f"No existe: {MARKETPLACE_JSON}"
        data = json.loads(MARKETPLACE_JSON.read_text())
        # La versión puede estar en data["version"] (raíz) o en data["plugins"][0]["version"]
        version = data.get("version")
        if version is None:
            plugins = data.get("plugins", [])
            if plugins:
                version = plugins[0].get("version")
        assert version == "0.1.4", (
            f"marketplace.json version={version!r}, esperado '0.1.4'"
        )
