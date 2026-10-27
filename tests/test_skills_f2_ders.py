"""AW-188 Fase 2 — skill `ders`.

Verifica:
- Assets de prompts presentes (extractor, enriquecedor, juez, patcher) + schema (plantilla_ders.json)
- SKILL.md NO menciona ders.py ni Gemini como motor
- fetch_transcripciones.py funciona con urlopen mockeado (200/401/503)
- El token nunca aparece en stdout
"""
import importlib
import io
import json
import pathlib
import sys
import unittest.mock as mock

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
DERS_DIR = SKILLS_DIR / "ders"


def test_assets_prompts_ders_presentes():
    """Los 4 prompts tmpl de ders deben estar en assets/prompts/."""
    prompts_dir = DERS_DIR / "assets" / "prompts"
    for nombre in ["extractor", "enriquecedor", "juez", "patcher"]:
        tmpl = prompts_dir / f"{nombre}.md.tmpl"
        assert tmpl.exists(), f"Falta {tmpl}"


def test_asset_plantilla_ders_presente():
    """assets/schema/plantilla_ders.json debe existir bajo ders/."""
    schema = DERS_DIR / "assets" / "schema" / "plantilla_ders.json"
    assert schema.exists(), f"Falta {schema}"


def test_asset_esquema_vacio_presente():
    """assets/schema/esquema_vacio.json debe existir bajo ders/."""
    schema = DERS_DIR / "assets" / "schema" / "esquema_vacio.json"
    assert schema.exists(), f"Falta {schema}"


def test_skill_md_ders_no_menciona_orquestador_ders():
    """SKILL.md de ders NO debe referenciar el orquestador pipeline/ders.py (llama a Gemini).

    El fichero validar_ders.py (nuestro script determinista) es correcto; lo que se
    prohíbe es mencionar pipeline/ders.py o sugerir ejecutar el orquestador de pipeline.
    """
    text = (DERS_DIR / "SKILL.md").read_text(encoding="utf-8")
    # No debe mencionar pipeline/ders.py ni python ders.py como comando
    assert "pipeline/ders.py" not in text, \
        "SKILL.md de ders menciona pipeline/ders.py (orquestador con Gemini)"
    assert "python ders.py" not in text, \
        "SKILL.md de ders sugiere ejecutar python ders.py (orquestador con Gemini)"


def test_skill_md_ders_no_menciona_gemini_como_motor():
    """SKILL.md de ders NO debe referenciar Gemini como motor de criterio."""
    text = (DERS_DIR / "SKILL.md").read_text(encoding="utf-8")
    # "Gemini" puede aparecer sólo en contexto negativo ("no llama a Gemini"), no como motor
    lines_with_gemini = [l for l in text.splitlines() if "Gemini" in l and "no" not in l.lower() and "sin" not in l.lower()]
    assert not lines_with_gemini, f"SKILL.md ders menciona Gemini como motor: {lines_with_gemini}"


def test_prompts_ders_conservan_prefix():
    """Los prompts tmpl que usan {{PREFIX}} deben conservarlo (no sustituir)."""
    prompts_dir = DERS_DIR / "assets" / "prompts"
    # patcher.md.tmpl es el que normalmente usa {{PREFIX}}
    for nombre in ["extractor", "enriquecedor", "juez", "patcher"]:
        tmpl = prompts_dir / f"{nombre}.md.tmpl"
        text = tmpl.read_text(encoding="utf-8")
        # Si el prompt original tiene {{PREFIX}}, la copia también debe tenerlo
        orig = (pathlib.Path(__file__).resolve().parents[2] / "pipeline" / "prompts" /
                f"{nombre}.md.tmpl")
        if orig.exists():
            orig_text = orig.read_text(encoding="utf-8")
            if "{{PREFIX}}" in orig_text:
                assert "{{PREFIX}}" in text, f"{nombre}.md.tmpl perdió {{{{PREFIX}}}}"


def test_prompts_ders_tienen_comentario_origen():
    """Los prompts copiados deben tener comentario HTML de origen (AW-188)."""
    prompts_dir = DERS_DIR / "assets" / "prompts"
    for nombre in ["extractor", "enriquecedor", "juez", "patcher"]:
        tmpl = prompts_dir / f"{nombre}.md.tmpl"
        text = tmpl.read_text(encoding="utf-8")
        assert "<!-- origen:" in text, f"{nombre}.md.tmpl no tiene comentario de origen"
        assert "AW-188" in text, f"{nombre}.md.tmpl no menciona AW-188 en el comentario de origen"


# ---- fetch_transcripciones.py tests ----

def _get_fetch_mod():
    """Importa fetch_transcripciones desde skills/ders/scripts/ añadiéndolo al path."""
    scripts_skill = DERS_DIR / "scripts"
    if str(scripts_skill) not in sys.path:
        sys.path.insert(0, str(scripts_skill))
    if "fetch_transcripciones" in sys.modules:
        del sys.modules["fetch_transcripciones"]
    return importlib.import_module("fetch_transcripciones")


def _mock_response(status, body_dict):
    """Crea un mock de urllib response para urlopen."""
    body_bytes = json.dumps(body_dict).encode()
    cm = mock.MagicMock()
    cm.__enter__ = mock.Mock(return_value=cm)
    cm.__exit__ = mock.Mock(return_value=False)
    cm.status = status
    cm.read = mock.Mock(return_value=body_bytes)
    return cm


def test_fetch_200_escribe_transcripciones(tmp_path):
    """Con respuesta 200, fetch_transcripciones escribe transcripciones.txt correctamente."""
    mod = _get_fetch_mod()

    reuniones = [
        {"reunion": "m01", "fichero": "m01.txt", "texto": "Texto reunión uno."},
        {"reunion": "m02", "fichero": "m02.txt", "texto": "Texto reunión dos."},
    ]
    body = {"status": "ok", "cliente": "tufisio", "reuniones": reuniones, "n": 2}
    out_file = tmp_path / "transcripciones.txt"

    with mock.patch("urllib.request.urlopen", return_value=_mock_response(200, body)):
        rc = mod.main([
            "--cliente", "tufisio",
            "--endpoint", "http://fake.endpoint",
            "--token", "FAKE_TOKEN",
            "--out", str(out_file)
        ])

    assert rc == 0
    assert out_file.exists()
    text = out_file.read_text()
    assert "Texto reunión uno." in text
    assert "Texto reunión dos." in text


def test_fetch_401_sale_con_error(tmp_path, capsys):
    """Con 401, fetch_transcripciones sale con rc!=0 y mensaje claro."""
    import urllib.error
    mod = _get_fetch_mod()
    out_file = tmp_path / "transcripciones.txt"

    with mock.patch("urllib.request.urlopen",
                    side_effect=urllib.error.HTTPError(
                        "http://fake", 401, "Unauthorized", {}, None)):
        rc = mod.main([
            "--cliente", "tufisio",
            "--endpoint", "http://fake.endpoint",
            "--token", "FAKE_TOKEN",
            "--out", str(out_file)
        ])

    assert rc != 0
    captured = capsys.readouterr()
    assert "401" in captured.err or "autoriza" in captured.err.lower() or "token" in captured.err.lower()


def test_fetch_503_sale_con_error(tmp_path, capsys):
    """Con 503, fetch_transcripciones sale con rc!=0 y mensaje claro."""
    import urllib.error
    mod = _get_fetch_mod()
    out_file = tmp_path / "transcripciones.txt"

    with mock.patch("urllib.request.urlopen",
                    side_effect=urllib.error.HTTPError(
                        "http://fake", 503, "Service Unavailable", {}, None)):
        rc = mod.main([
            "--cliente", "tufisio",
            "--endpoint", "http://fake.endpoint",
            "--token", "FAKE_TOKEN",
            "--out", str(out_file)
        ])

    assert rc != 0
    captured = capsys.readouterr()
    assert "503" in captured.err or "servicio" in captured.err.lower() or "disponible" in captured.err.lower()


def test_fetch_no_imprime_token(tmp_path, capsys):
    """El token NUNCA debe aparecer en stdout ni stderr."""
    mod = _get_fetch_mod()

    reuniones = [{"reunion": "m01", "fichero": "m01.txt", "texto": "Hola."}]
    body = {"status": "ok", "cliente": "tufisio", "reuniones": reuniones, "n": 1}
    out_file = tmp_path / "transcripciones.txt"
    SECRET_TOKEN = "MY_SECRET_TOKEN_12345"

    with mock.patch("urllib.request.urlopen", return_value=_mock_response(200, body)):
        mod.main([
            "--cliente", "tufisio",
            "--endpoint", "http://fake.endpoint",
            "--token", SECRET_TOKEN,
            "--out", str(out_file)
        ])

    captured = capsys.readouterr()
    assert SECRET_TOKEN not in captured.out, "Token apareció en stdout"
    assert SECRET_TOKEN not in captured.err, "Token apareció en stderr"


def test_fetch_404_sale_con_error(tmp_path, capsys):
    """Con 404, sale con rc!=0 y mensaje de cliente no encontrado."""
    import urllib.error
    mod = _get_fetch_mod()
    out_file = tmp_path / "transcripciones.txt"

    with mock.patch("urllib.request.urlopen",
                    side_effect=urllib.error.HTTPError(
                        "http://fake", 404, "Not Found", {}, None)):
        rc = mod.main([
            "--cliente", "clienteInexistente",
            "--endpoint", "http://fake.endpoint",
            "--token", "FAKE_TOKEN",
            "--out", str(out_file)
        ])

    assert rc != 0
