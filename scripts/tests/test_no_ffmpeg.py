"""Regresión: ningún import del paquete portado arrastra imageio_ffmpeg, google.generativeai ni genai."""
import sys
import importlib

import pytest

# modules to check
MODULES_TO_IMPORT = [
    "parametrizacion",
    "parametrizacion.crm",
    "parametrizacion.discovery",
    "parametrizacion.applicator",
    "parametrizacion.ir",
    "parametrizacion.summary",
    "parametrizacion.generador_plantilla",
    "parametrizacion.plantilla_a_ir",
]

FORBIDDEN = ["imageio_ffmpeg", "imageio", "google.generativeai", "genai", "moviepy", "pydub"]


@pytest.mark.parametrize("mod_name", MODULES_TO_IMPORT)
def test_import_no_arrastra_ffmpeg_ni_gemini(mod_name):
    """Importar el módulo no carga imageio_ffmpeg ni google.generativeai en sys.modules."""
    # clean state before
    before = set(sys.modules.keys())
    importlib.import_module(mod_name)
    after = set(sys.modules.keys())
    nuevos = after - before
    for forbidden in FORBIDDEN:
        contaminados = [m for m in nuevos if m == forbidden or m.startswith(forbidden + ".")]
        assert not contaminados, (
            f"Importar '{mod_name}' cargó módulos prohibidos: {contaminados}"
        )
