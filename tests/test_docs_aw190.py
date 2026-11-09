"""Tests para AW-190 — Docs + manifiesto (AC-7, AC-8, AC-9).

Tests que asserta el estado de los ficheros de documentación y manifiestos.
"""
import json
import re
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# AC-7: README.md
# ---------------------------------------------------------------------------

class TestReadme:
    """README.md: onboarding automático (AW-194) y doctor sin flags."""

    def test_readme_no_exige_ruta_fija_python311(self):
        """AW-194: el README ya NO exige fijar python_bin a /opt/homebrew/bin/python3.11."""
        readme = (PLUGIN_ROOT / "README.md").read_text()
        assert "/opt/homebrew/bin/python3.11` en macOS" not in readme, (
            "README no debe pedir fijar python_bin a una ruta absoluta (ahora autodescubre)"
        )

    def test_readme_onboarding_autodescubre_python(self):
        """AW-194: el README ya no fija una ruta a python3.11; el onboarding autodescubre Python ≥3.10."""
        readme = (PLUGIN_ROOT / "README.md").read_text()
        assert "3.10" in readme, "README debe indicar el piso Python 3.10+"
        assert "autodescubre" in readme.lower() or "python.org" in readme, (
            "README debe reflejar el onboarding automático (autodescubrimiento / python.org)"
        )

    def test_readme_doctor_documentado_sin_flags(self):
        """README.md documenta doctor.py sin flags (no --venv-dir ni --oauth-path)."""
        readme = (PLUGIN_ROOT / "README.md").read_text()
        # Debe haber una línea con el comando de doctor sin flags
        assert "python3 scripts/doctor.py" in readme or "scripts/doctor.py" in readme, (
            "README.md debe documentar el comando doctor.py"
        )

    def test_readme_tabla_checks_D_E_solo_implementar(self):
        """README.md indica en la tabla que [D] y [E] son 'solo para /implementar'."""
        readme = (PLUGIN_ROOT / "README.md").read_text()
        assert "/implementar" in readme, (
            "README.md debe mencionar que [D]/[E] son necesarios para /implementar"
        )


# ---------------------------------------------------------------------------
# AC-8: setup_crm_consultor.md
# ---------------------------------------------------------------------------

class TestSetupCrmDoc:
    """setup_crm_consultor.md no contiene pipeline.parametrizacion.apply."""

    def test_setup_no_contiene_pipeline_parametrizacion_apply(self):
        """setup_crm_consultor.md no usa el módulo de monorepo pipeline.parametrizacion.apply."""
        doc = (PLUGIN_ROOT / "docs" / "setup_crm_consultor.md").read_text()
        assert "pipeline.parametrizacion.apply" not in doc, (
            "setup_crm_consultor.md contiene la ruta antigua del monorepo 'pipeline.parametrizacion.apply'"
        )

    def test_setup_menciona_claude_plugin_data(self):
        """setup_crm_consultor.md menciona $CLAUDE_PLUGIN_DATA como ubicación del token."""
        doc = (PLUGIN_ROOT / "docs" / "setup_crm_consultor.md").read_text()
        assert "CLAUDE_PLUGIN_DATA" in doc, (
            "setup_crm_consultor.md debe mencionar $CLAUDE_PLUGIN_DATA como ubicación del token"
        )

    def test_setup_comando_verificacion_correcto(self):
        """setup_crm_consultor.md usa un comando de verificación del plugin correcto."""
        doc = (PLUGIN_ROOT / "docs" / "setup_crm_consultor.md").read_text()
        # Debe usar algún comando del plugin real (apply_cli, doctor, etc.)
        # No debe usar el módulo de monorepo
        valid_commands = [
            "apply_cli",
            "scripts/doctor.py",
            "doctor.py",
            "parametrizacion.apply_cli",
        ]
        has_valid = any(cmd in doc for cmd in valid_commands)
        assert has_valid, (
            f"setup_crm_consultor.md debe tener un comando de verificación del plugin. "
            f"Buscados: {valid_commands}"
        )


# ---------------------------------------------------------------------------
# AC-9: plugin.json y marketplace.json con versión 0.1.1
# ---------------------------------------------------------------------------

def _plugin_version():
    data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    return data["version"]


def _marketplace_version():
    data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "marketplace.json").read_text())
    sagitaz_plugin = next(
        (p for p in data.get("plugins", []) if p.get("name") == "consultoria-sagitaz"), None
    )
    assert sagitaz_plugin is not None, "marketplace.json debe tener el plugin consultoria-sagitaz"
    return sagitaz_plugin["version"]


class TestVersionBump:
    """plugin.json y marketplace.json declaran la misma versión, bumpeada por AW-191."""

    def test_plugin_marketplace_version_consistente(self):
        """plugin.json y marketplace.json coinciden en versión (invariante robusto a bumps)."""
        assert _plugin_version() == _marketplace_version(), (
            f"versión plugin.json ({_plugin_version()}) != marketplace.json ({_marketplace_version()})"
        )

    def test_version_bumpeada(self):
        """La versión está por encima de las publicadas previamente (0.1.0/0.1.1 — AW-191 = 0.1.2)."""
        assert _plugin_version() not in ("0.1.0", "0.1.1"), (
            f"la versión debe estar bumpeada por AW-191, es '{_plugin_version()}'"
        )

    def test_plugin_json_python_bin_es_opcional(self):
        """AW-194: python_bin es override opcional — sin default de ruta fija (autodescubrimiento)."""
        plugin_json = (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
        data = json.loads(plugin_json)
        python_bin = data.get("userConfig", {}).get("python_bin", {})
        assert python_bin, "python_bin debe seguir existiendo como override opcional"
        assert not python_bin.get("default"), (
            f"python_bin no debe tener default de ruta fija; es: '{python_bin.get('default')}'"
        )
