#!/usr/bin/env python3
"""validar_ders.py — Validación estructural del DERS.json contra la plantilla canónica 2026.

Valida el DERS *producido* por la skill (esquema `esquema_vacio.json`: `requerimientos[]` con
`id`/`numero` numéricos del tipo "5.1") contra el árbol FIJO de secciones de `plantilla_ders.json`
(`Plantilla-DERS-DERCAS-CRM-2026`). Comprueba:

  - La numeración de cada requerimiento pertenece al árbol canónico (sin numeración inventada).
  - No hay números de requerimiento duplicados (numeración intacta).
  - Los subapartados de un requerimiento cuelgan de su propio número (`5.1` → `5.1.x`).

Determinista, sin modelo. Nota: un DERS pre-2026 (p.ej. tufisio, formato plano sin esta numeración)
NO conformará — es lo esperado.

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

# Clave que contiene los requerimientos (con fallback al nombre legacy)
_CLAVE_REQS = "requerimientos"
_CLAVE_REQS_LEGACY = "requerimientos_plantilla"


def _cargar_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def numeros_canonicos(schema):
    """Conjunto de números de sección/subsección válidos del árbol 2026.

    Recorre `secciones` y recoge: número de cada grupo (p.ej. "5"), de cada hijo/hoja
    (p.ej. "5.1"), de cada slot de nivel superior (p.ej. "11", "13") y de los subapartados
    de formación (p.ej. "12.1.1").
    """
    nums = set()
    for s in schema.get("secciones", []):
        if s.get("numero"):
            nums.add(str(s["numero"]))
        for h in s.get("hijos", []):
            if h.get("numero"):
                nums.add(str(h["numero"]))
        for sa in s.get("subapartados", []):
            if sa.get("numero"):
                nums.add(str(sa["numero"]))
    return nums


def _numero_req(req):
    """Número de un requerimiento: `numero` si existe, si no `id` (ambos numéricos "5.1")."""
    val = req.get("numero") or req.get("id")
    return str(val).strip() if val is not None else ""


def validar_estructura(ders, schema):
    """Valida el DERS producido contra el árbol canónico de la plantilla.

    Retorna lista de errores (vacía = válido).
    """
    errores = []

    if not isinstance(ders, dict):
        return ["El DERS no es un objeto JSON válido (se esperaba un objeto)."]

    canon = numeros_canonicos(schema)
    if not canon:
        errores.append("La plantilla no define secciones canónicas ('secciones' vacío).")

    reqs = ders.get(_CLAVE_REQS)
    if reqs is None:
        reqs = ders.get(_CLAVE_REQS_LEGACY)
    if reqs is None:
        errores.append(f"Falta la clave '{_CLAVE_REQS}' (lista de requerimientos).")
        return errores
    if not isinstance(reqs, list):
        errores.append(f"'{_CLAVE_REQS}' debe ser una lista.")
        return errores

    vistos = {}
    for i, req in enumerate(reqs):
        if not isinstance(req, dict):
            errores.append(f"requerimientos[{i}] no es un objeto.")
            continue
        num = _numero_req(req)
        if not num:
            errores.append(f"requerimientos[{i}] no tiene 'id' ni 'numero'.")
            continue
        if num not in canon:
            errores.append(
                f"requerimientos[{i}] numero '{num}' está fuera del árbol de la plantilla "
                f"(numeración no canónica).")
        if num in vistos:
            errores.append(
                f"requerimientos[{i}] numero '{num}' duplicado "
                f"(ya usado en requerimientos[{vistos[num]}]).")
        else:
            vistos[num] = i

        # Subapartados (si los hay): su número debe colgar del número del requerimiento.
        for j, sa in enumerate(req.get("subapartados", []) or []):
            if not isinstance(sa, dict):
                continue
            sub = str(sa.get("numero") or sa.get("id") or "").strip()
            if sub and not sub.startswith(num + "."):
                errores.append(
                    f"requerimientos[{i}].subapartados[{j}] numero '{sub}' no cuelga de "
                    f"'{num}' (subapartado mal ubicado).")

    return errores


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validación estructural del DERS.json contra la plantilla canónica 2026.")
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
