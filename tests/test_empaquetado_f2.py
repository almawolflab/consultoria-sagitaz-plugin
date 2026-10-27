"""AW-189 — Fase 2 TDD: requirements-plugin.txt multiplataforma, sin wheel Linux-only."""
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
REQS = PLUGIN_ROOT / "requirements-plugin.txt"

# Dependencias prohibidas: Linux-only o por-plataforma no opcional
_PROHIBITED = [
    "imageio-ffmpeg",
    "imageio_ffmpeg",
    "google-generativeai",
    "google_generativeai",
    "genai",
]

# Dependencias permitidas (puro Python, cross-platform)
_REQUIRED = ["openpyxl", "et-xmlfile"]


def _active_lines(text: str) -> list[str]:
    """Devuelve las líneas no-comentario, no vacías, en minúscula."""
    result = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            result.append(stripped.lower())
    return result


def test_requirements_sin_linux_only():
    """requirements-plugin.txt NO debe contener imageio-ffmpeg ni google-generativeai/genai."""
    assert REQS.exists(), f"No existe {REQS}"
    active = _active_lines(REQS.read_text())
    for line in active:
        for prohibited in _PROHIBITED:
            assert prohibited.lower() not in line, (
                f"Dependencia prohibida en requirements-plugin.txt: {line!r} "
                f"(contiene {prohibited!r})"
            )


def test_requirements_solo_puro_python():
    """requirements-plugin.txt debe incluir openpyxl y et-xmlfile; Pillow solo como comentario."""
    assert REQS.exists(), f"No existe {REQS}"
    text = REQS.read_text()
    active = _active_lines(text)

    # Las requeridas deben estar activas
    for dep in _REQUIRED:
        found = any(dep.lower() in line for line in active)
        assert found, f"Falta dependencia obligatoria en requirements-plugin.txt: {dep!r}"

    # Pillow NO debe estar como línea activa (debe ser comentario opcional)
    for line in active:
        assert "pillow" not in line.lower(), (
            f"Pillow debe ser línea comentada (opcional), no activa: {line!r}"
        )
