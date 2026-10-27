#!/usr/bin/env python3
"""generar_matriz.py — Genera la Matriz CRM (xlsx pre-marcada) desde ir.json.

Sin red, sin modelo. Usa:
  generador_plantilla.ir_a_propuestas(ir, descriptor)
  plantilla_io.escribir_premarcada(descriptor, propuestas, out_xlsx)

Uso:
    python generar_matriz.py \\
        --ir ~/Sagitaz/clientes/tufisio/ir.json \\
        --out ~/Sagitaz/clientes/tufisio/Matriz_CRM.xlsx

Imprime recuento de campos propuestos por módulo.
"""
import argparse
import json
import os
import pathlib
import sys

# Añadir plugin-claude/scripts/ al path
HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parents[2] / "scripts"  # skills/matriz/scripts/ → skills/ → plugin-claude/ → scripts/
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:
    from parametrizacion.ir import load_ir
    from parametrizacion.generador_plantilla import ir_a_propuestas
    from parametrizacion.plantilla_io import cargar_descriptor, escribir_premarcada
except ImportError as e:
    print(f"Error: no se puede importar módulos de parametrizacion: {e}", file=sys.stderr)
    print(f"  Buscado en: {SCRIPTS}", file=sys.stderr)
    sys.exit(1)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Genera Matriz_CRM.xlsx desde ir.json (sin red ni modelo)")
    parser.add_argument("--ir", required=True, help="Ruta al ir.json")
    parser.add_argument("--out", default=None,
                        help="Ruta de salida del xlsx (default: ~/Sagitaz/clientes/<cliente>/Matriz_CRM.xlsx)")
    parser.add_argument("--descriptor", default=None,
                        help="Ruta a plantilla_crm.json (default: scripts/assets/plantilla_crm.json)")

    args = parser.parse_args(argv)

    ir_path = pathlib.Path(args.ir)
    if not ir_path.exists():
        print(f"Error: IR no encontrado: {ir_path}", file=sys.stderr)
        return 1

    # Cargar IR
    try:
        ir = load_ir(str(ir_path))
    except (ValueError, Exception) as e:
        print(f"Error al cargar el IR: {e}", file=sys.stderr)
        return 1

    # Cargar descriptor
    try:
        descriptor = cargar_descriptor(args.descriptor)
    except Exception as e:
        print(f"Error al cargar el descriptor de plantilla: {e}", file=sys.stderr)
        return 1

    # Ruta de salida
    if args.out:
        out_path = pathlib.Path(args.out)
    else:
        # Intentar inferir desde la ruta del IR
        cliente_dir = ir_path.parent
        out_path = cliente_dir / "Matriz_CRM.xlsx"

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Generar propuestas
    propuestas = ir_a_propuestas(ir, descriptor)

    # Escribir xlsx
    try:
        escribir_premarcada(descriptor, propuestas, str(out_path))
    except Exception as e:
        print(f"Error al generar el xlsx: {e}", file=sys.stderr)
        return 1

    # Imprimir recuento por módulo
    total = 0
    lineas = []
    for modulo, campos in sorted(propuestas.items()):
        n = len(campos)
        total += n
        lineas.append(f"  {modulo}: {n} campo(s)")

    meta = ir.get("meta", {}) or {}
    cliente = meta.get("cliente", ir_path.parent.name)
    print(f"Matriz CRM generada: {out_path}")
    print(f"Cliente: {cliente} | Total propuestas: {total} campo(s)")
    if lineas:
        print("Por módulo:")
        for l in lineas:
            print(l)
    else:
        print("  (sin campos en el IR)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
