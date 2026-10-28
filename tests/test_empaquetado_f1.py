"""AW-189 — Fase 1 TDD: manifiesto plugin.json + ausencia de bin/ toplevel."""
import json
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"


def test_manifest_valido():
    """plugin.json existe, tiene los campos obligatorios y userConfig correcto."""
    assert MANIFEST.exists(), f"No existe {MANIFEST}"
    data = json.loads(MANIFEST.read_text())
    # name en kebab-case, sin palabras reservadas (claude / anthropic)
    name = data.get("name", "")
    assert name == "consultoria-sagitaz", f"name incorrecto: {name!r}"
    assert "claude" not in name.lower(), "name contiene 'claude' (reservado)"
    assert "anthropic" not in name.lower(), "name contiene 'anthropic' (reservado)"
    # userConfig con los tres campos obligatorios
    uc = data.get("userConfig", {})
    assert "transcripciones_endpoint" in uc, "falta userConfig.transcripciones_endpoint"
    assert "transcripciones_team_token" in uc, "falta userConfig.transcripciones_team_token"
    assert "python_bin" in uc, "falta userConfig.python_bin"
    # sensitive en transcripciones_team_token
    assert uc["transcripciones_team_token"].get("sensitive") is True, \
        "transcripciones_team_token debe tener sensitive: true"
    # python_bin tiene default (ruta absoluta a python3.11, no "python3" suelto — AW-190 AC-7)
    python_bin_default = uc["python_bin"].get("default", "")
    assert python_bin_default != "python3", \
        "python_bin default no debe ser 'python3' suelto (AW-190: usar ruta absoluta)"
    assert "python3.11" in python_bin_default or "py -3" in python_bin_default, \
        f"python_bin default debe contener 'python3.11' o 'py -3'; tiene: {python_bin_default!r}"
    # version presente (0.1.1 tras el bump de AW-190 AC-9)
    assert data.get("version") == "0.1.1", f"version incorrecto: {data.get('version')!r}"
    # displayName presente
    assert "displayName" in data, "falta displayName"
    # $schema presente
    assert "$schema" in data, "falta $schema"


def test_sin_bin_toplevel():
    """El plugin NO tiene carpeta bin/ en su raíz (incompatible con claude.ai/Cowork)."""
    bin_dir = PLUGIN_ROOT / "bin"
    assert not bin_dir.exists(), f"Se encontró {bin_dir} — prohíbida por contrato de plugin"
