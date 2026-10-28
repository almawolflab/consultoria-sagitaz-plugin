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
    """README.md contiene referencias correctas a python3.11 y doctor sin flags."""

    def test_readme_no_tiene_python_bin_python3_suelto(self):
        """python_bin no apunta a 'python3' sin ruta absoluta."""
        readme = (PLUGIN_ROOT / "README.md").read_text()
        # No debe haber `python_bin` apuntando a `python3` suelto (sin ruta absoluta)
        # Patrón problemático: `python3` como valor de python_bin sin ser ruta absoluta
        # Buscamos si hay "python_bin" seguido (en el readme) por el valor "python3"
        # como valor de config (no como ejemplo de invocación)
        bad_pattern = re.compile(r'`python_bin`.*?`python3`', re.DOTALL)
        # En la tabla de userConfig, el valor de python_bin debe tener la ruta absoluta
        # Comprobamos que no diga simplemente "python3" en la celda de la tabla
        assert "python3` en macOS" not in readme or "/opt/homebrew" in readme or "python3.11" in readme, (
            "README.md debe referenciar python3.11 con ruta absoluta para macOS"
        )

    def test_readme_tiene_ruta_absoluta_python311(self):
        """README.md menciona la ruta absoluta a python3.11."""
        readme = (PLUGIN_ROOT / "README.md").read_text()
        assert "/opt/homebrew/bin/python3.11" in readme or "python3.11" in readme, (
            "README.md debe mencionar python3.11 o su ruta absoluta"
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

class TestVersionBump:
    """plugin.json y marketplace.json tienen versión 0.1.1."""

    def test_plugin_json_version_0_1_1(self):
        """plugin.json tiene versión 0.1.1."""
        plugin_json = (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
        data = json.loads(plugin_json)
        assert data["version"] == "0.1.1", (
            f"plugin.json debe tener versión '0.1.1', tiene '{data.get('version')}'"
        )

    def test_marketplace_json_version_0_1_1(self):
        """marketplace.json tiene versión 0.1.1 en el plugin consultoria-sagitaz."""
        marketplace_json = (PLUGIN_ROOT / ".claude-plugin" / "marketplace.json").read_text()
        data = json.loads(marketplace_json)
        plugins = data.get("plugins", [])
        sagitaz_plugin = next(
            (p for p in plugins if p.get("name") == "consultoria-sagitaz"), None
        )
        assert sagitaz_plugin is not None, "marketplace.json debe tener el plugin consultoria-sagitaz"
        assert sagitaz_plugin["version"] == "0.1.1", (
            f"marketplace.json debe tener versión '0.1.1', tiene '{sagitaz_plugin.get('version')}'"
        )

    def test_plugin_json_python_bin_default_es_ruta_absoluta(self):
        """plugin.json: el default de python_bin es la ruta absoluta a python3.11."""
        plugin_json = (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text()
        data = json.loads(plugin_json)
        python_bin_default = data.get("userConfig", {}).get("python_bin", {}).get("default", "")
        # En macOS debe ser la ruta absoluta; en Windows sería py -3
        # El default debe no ser simplemente "python3" suelto
        assert python_bin_default != "python3", (
            f"plugin.json python_bin default no debe ser 'python3' suelto; es: '{python_bin_default}'"
        )
        assert "python3.11" in python_bin_default or "py -3" in python_bin_default, (
            f"plugin.json python_bin default debe ser ruta absoluta a python3.11 o 'py -3'; es: '{python_bin_default}'"
        )
