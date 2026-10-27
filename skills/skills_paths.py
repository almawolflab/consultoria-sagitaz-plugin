"""skills_paths.py — Convención de ficheros locales por cliente (AW-188 §4.3).

Raíz configurable:
  1. Argumento `root` explícito (para tests y CLI)
  2. Env SAGITAZ_CLIENTES_ROOT
  3. Por defecto: ~/Sagitaz/clientes/

Uso:
    from skills_paths import cliente_path
    ders_json = cliente_path("tufisio", "DERS.json")
"""
import os
import pathlib


_DEFAULT_ROOT = pathlib.Path.home() / "Sagitaz" / "clientes"


def clientes_root(root=None):
    """Devuelve la raíz de clientes: argumento > env > default."""
    if root is not None:
        return pathlib.Path(root)
    env = os.environ.get("SAGITAZ_CLIENTES_ROOT")
    if env:
        return pathlib.Path(env)
    return _DEFAULT_ROOT


def cliente_path(cliente, fichero, root=None):
    """Devuelve la ruta absoluta de un fichero de cliente según §4.3.

    Args:
        cliente: nombre del cliente (slug, p.ej. "tufisio")
        fichero: nombre del fichero (p.ej. "DERS.json", "ir.json")
        root: raíz opcional; si None, se usa clientes_root()

    Returns:
        pathlib.Path con la ruta absoluta (no crea el directorio)
    """
    return clientes_root(root) / cliente / fichero


# Ficheros estándar por etapa (§4.3)
FICHEROS = {
    "transcripciones": "transcripciones.txt",    # ders — fetch_transcripciones
    "ders":            "DERS.json",               # ders — validado contra plantilla_ders.json
    "ders_docx":       "DERS.docx",              # ders — render opcional
    "dercas":          "DERCAS.json",             # dercas — DERS + viabilidad + criterios
    "ir":              "ir.json",                 # dercas — IR declarativo
    "matriz":          "Matriz_CRM.xlsx",         # matriz — plantilla pre-marcada
    "plan":            "Plan.md",                 # plan — plan legible
    "revision_json":   "revision.json",           # plan — veredicto de revisión
    "revision_md":     "revision.md",             # plan — veredicto de revisión (Markdown)
    "resumen_impl":    "resumen_implementacion.md",  # implementar — resultado
}


def cliente_ficheros(cliente, root=None):
    """Devuelve un dict {clave: Path} con todas las rutas estándar de un cliente."""
    return {k: cliente_path(cliente, v, root=root) for k, v in FICHEROS.items()}
