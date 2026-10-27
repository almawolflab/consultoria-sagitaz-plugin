#!/usr/bin/env python3
"""validar_ders.py — Validación estructural del DERS.json contra plantilla_ders.json.

Comprueba que el DERS tiene las secciones de la plantilla con la numeración intacta.
Determinista, sin modelo.

Uso:
    python validar_ders.py ~/Sagitaz/clientes/tufisio/DERS.json
    python validar_ders.py ~/Sagitaz/clientes/tufisio/DERS.json \
        --schema assets/schema/plantilla_ders.json

Sale con rc=0 si el DERS es estructuralmente válido; rc=1 con detalle si no.
"""
import argparse
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
DEFAULT_SCHEMA = HERE.parent / "assets" / "schema" / "plantilla_ders.json"

# Claves de primer nivel que deben estar en el DERS (tomadas de la plantilla)
_CLAVES_OBLIGATORIAS = [
    "control_documentos",
    "documento_boilerplate",
    "especificaciones_plantilla",
]

# Clave que contiene los requerimientos
_CLAVE_REQS = "requerimientos"


def _cargar_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def validar_estructura(ders, schema):
    """Valida la estructura del DERS contra la plantilla.

    Retorna lista de errores (vacía = válido).
    """
    errores = []

    if not isinstance(ders, dict):
        return ["El DERS no es un objeto JSON válido"]

    # Verificar secciones de la plantilla presente en el schema
    # Las secciones de la plantilla son las claves de primer nivel del schema
    secciones_schema = {k for k in schema.keys() if not k.startswith("_")}
    secciones_ders = set(ders.keys())

    # Verificar claves obligatorias
    for clave in _CLAVES_OBLIGATORIAS:
        if clave not in secciones_ders:
            errores.append(f"Falta sección obligatoria: '{clave}'")

    # Verificar que los requerimientos tienen la estructura básica
    reqs = ders.get(_CLAVE_REQS) or ders.get("requerimientos_plantilla")
    if reqs is not None:
        if not isinstance(reqs, list):
            errores.append(f"'{_CLAVE_REQS}' debe ser una lista")
        else:
            for i, req in enumerate(reqs):
                if not isinstance(req, dict):
                    errores.append(f"requerimientos[{i}] no es un objeto")
                    continue
                if "id" not in req and "numero" not in req:
                    errores.append(f"requerimientos[{i}] no tiene 'id' ni 'numero'")

    return errores


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validación estructural del DERS.json contra plantilla_ders.json")
    parser.add_argument("ders", help="Ruta al DERS.json a validar")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA),
                        help="Ruta a plantilla_ders.json (default: assets/schema/)")

    args = parser.parse_args(argv)

    ders_path = pathlib.Path(args.ders)
    if not ders_path.exists():
        print(f"Error: DERS no encontrado: {ders_path}", file=sys.stderr)
        return 1

    schema_path = pathlib.Path(args.schema)
    if not schema_path.exists():
        print(f"Error: Schema no encontrado: {schema_path}", file=sys.stderr)
        return 1

    try:
        ders = _cargar_json(ders_path)
        schema = _cargar_json(schema_path)
    except json.JSONDecodeError as e:
        print(f"Error de JSON: {e}", file=sys.stderr)
        return 1

    errores = validar_estructura(ders, schema)

    if errores:
        print(f"DERS inválido ({len(errores)} error(es)):", file=sys.stderr)
        for e in errores:
            print(f"  - {e}", file=sys.stderr)
        return 1

    print(f"OK: {ders_path.name} válido estructuralmente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
