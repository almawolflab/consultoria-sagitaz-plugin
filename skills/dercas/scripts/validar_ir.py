#!/usr/bin/env python3
"""validar_ir.py — Validación del IR declarativo.

Usa parametrizacion.ir (load_ir + validate + ordered_items) desde plugin-claude/scripts/.
Comprueba: ids únicos, match/payload presentes, depends_on sin ciclos ni referencias colgantes.

Uso:
    python validar_ir.py ~/Sagitaz/clientes/tufisio/ir.json

Sale con rc=0 si el IR es válido; rc=1 con detalle si no.
"""
import argparse
import pathlib
import sys

# Añadir plugin-claude/scripts/ al path para importar parametrizacion
HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parents[2] / "scripts"  # skills/dercas/scripts/ → skills/ → plugin-claude/ → scripts/
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:
    # load_ir llama internamente a ir.validate (contrato de la spec §4.5.2:
    # "validación del IR contra parametrizacion/ir.py::validate"); ordered_items
    # añade la detección de ciclos y referencias colgantes en depends_on.
    from parametrizacion.ir import load_ir, ordered_items
except ImportError as e:
    print(f"Error: no se puede importar parametrizacion.ir: {e}", file=sys.stderr)
    print(f"  Buscado en: {SCRIPTS}", file=sys.stderr)
    sys.exit(1)


import re as _re

_PLACEHOLDER_RE = _re.compile(r"\{\{[A-Z_]+\}\}")


def _check_placeholders(ir: dict) -> list[str]:
    """Devuelve lista de errores si algún api_name/field_label/name contiene placeholder {{...}}.

    AW-192: la convención {{PREFIX}} fue eliminada; nombres custom son planos.
    """
    errors = []
    # fields: api_name y field_label
    for item in ir.get("fields") or []:
        item_id = item.get("id", "?")
        for key_path, value in [
            ("match.api_name", (item.get("match") or {}).get("api_name", "")),
            ("payload.field_label", (item.get("payload") or {}).get("field_label", "")),
        ]:
            if _PLACEHOLDER_RE.search(str(value)):
                errors.append(
                    f"Item '{item_id}' tiene placeholder sin sustituir en {key_path}: {value!r}"
                )
    # roles, profiles, workflows: name
    for seccion in ("roles", "profiles", "workflows"):
        for item in ir.get(seccion) or []:
            item_id = item.get("id", "?")
            for key_path, value in [
                ("match.name", (item.get("match") or {}).get("name", "")),
                ("payload.name", (item.get("payload") or {}).get("name", "")),
            ]:
                if _PLACEHOLDER_RE.search(str(value)):
                    errors.append(
                        f"Item '{item_id}' ({seccion}) tiene placeholder sin sustituir "
                        f"en {key_path}: {value!r}"
                    )
    # workflows: criteria.field y actions[].field (donde la convención vieja ponía {{PREFIX}}Tipo/{{PREFIX}}Prioridad)
    for item in ir.get("workflows") or []:
        item_id = item.get("id", "?")
        payload = item.get("payload") or {}
        criteria_field = (payload.get("criteria") or {}).get("field", "")
        if _PLACEHOLDER_RE.search(str(criteria_field)):
            errors.append(
                f"Item '{item_id}' (workflows) tiene placeholder sin sustituir "
                f"en payload.criteria.field: {criteria_field!r}"
            )
        for i, action in enumerate(payload.get("actions") or []):
            action_field = (action or {}).get("field", "")
            if _PLACEHOLDER_RE.search(str(action_field)):
                errors.append(
                    f"Item '{item_id}' (workflows) tiene placeholder sin sustituir "
                    f"en payload.actions[{i}].field: {action_field!r}"
                )
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Validación del IR declarativo (ir.json)")
    parser.add_argument("ir", help="Ruta al ir.json a validar")

    args = parser.parse_args(argv)

    ir_path = pathlib.Path(args.ir)
    if not ir_path.exists():
        print(f"Error: IR no encontrado: {ir_path}", file=sys.stderr)
        return 1

    try:
        ir = load_ir(str(ir_path))
    except ValueError as e:
        print(f"IR inválido: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Error al leer el IR: {e}", file=sys.stderr)
        return 1

    # Guard AW-192: rechazar placeholders {{...}} sin sustituir
    placeholder_errors = _check_placeholders(ir)
    if placeholder_errors:
        for err in placeholder_errors:
            print(f"IR inválido (placeholder sin sustituir): {err}", file=sys.stderr)
        return 1

    # Verificar también el orden topológico (detecta ciclos y deps colgantes)
    try:
        items = list(ordered_items(ir))
    except ValueError as e:
        print(f"IR inválido (dependencias): {e}", file=sys.stderr)
        return 1

    n = sum(len(ir.get(s, []) or []) for s in ("fields", "roles", "profiles", "workflows"))
    secciones = [s for s in ("fields", "roles", "profiles", "workflows") if ir.get(s)]

    print(f"OK: {ir_path.name} válido — {n} item(s) en sección(es): {', '.join(secciones)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
