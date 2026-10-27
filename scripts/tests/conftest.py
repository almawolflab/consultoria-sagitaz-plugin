"""Añade plugin-claude/scripts/ al sys.path para que los tests importen el paquete directamente."""
import sys
from pathlib import Path

# Add plugin-claude/scripts/ to sys.path so `import parametrizacion` works
SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
