"""AW-189 — Fase 1 TDD: manifiesto plugin.json + ausencia de bin/ toplevel."""
import json
import zipfile
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
BRANDKIT = PLUGIN_ROOT / "scripts" / "docx" / "assets" / "brandkit_2026.docx"


def test_brandkit_empaquetado_valido():
    """AW-202: el brand-kit se empaqueta con el plugin, es un .docx válido con chrome y sin
    comentarios editoriales ni datos de cliente."""
    assert BRANDKIT.exists(), f"falta el brand-kit: {BRANDKIT}"
    assert zipfile.is_zipfile(str(BRANDKIT)), "el brand-kit no es un zip/.docx válido"
    with zipfile.ZipFile(str(BRANDKIT)) as z:
        names = set(z.namelist())
        doc = z.read("word/document.xml").decode("utf-8", "replace")
    assert "word/header1.xml" in names and "word/styles.xml" in names
    assert any(n.startswith("word/media/") for n in names), "brand-kit sin logo"
    assert "word/comments.xml" not in names, "brand-kit con comentarios editoriales"
    assert "Instrucciones:" not in doc, "brand-kit con textos editoriales de la plantilla"


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
    # python_bin es OPCIONAL (override) — sin ruta fija por defecto (AW-194: autodescubrimiento)
    assert "python_bin" in uc, "python_bin debe seguir existiendo como override opcional"
    assert not uc["python_bin"].get("default"), \
        "python_bin no debe tener default de ruta fija (AW-194: el plugin autodescubre Python)"
    # version presente (0.1.8 tras el bump de AW-202)
    assert data.get("version") == "0.1.8", f"version incorrecto: {data.get('version')!r}"
    # displayName presente
    assert "displayName" in data, "falta displayName"
    # $schema presente
    assert "$schema" in data, "falta $schema"


def test_sin_bin_toplevel():
    """El plugin NO tiene carpeta bin/ en su raíz (incompatible con claude.ai/Cowork)."""
    bin_dir = PLUGIN_ROOT / "bin"
    assert not bin_dir.exists(), f"Se encontró {bin_dir} — prohíbida por contrato de plugin"
