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
