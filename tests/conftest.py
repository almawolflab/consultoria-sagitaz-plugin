import sys
from pathlib import Path

# plugin-claude/ lleva guion (no es paquete importable): se añade scripts/ al path
# para que los tests hagan `import authorize_crm`.
# parents[1] = plugin-claude/ ; parents[2] = <root del repo>
SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))  # para `import pipeline.parametrizacion.crm` en los tests de compatibilidad
