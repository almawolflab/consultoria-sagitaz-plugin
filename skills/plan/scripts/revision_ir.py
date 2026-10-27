#!/usr/bin/env python3
"""revision_ir.py — Revisión determinista del IR declarativo.

Checks deterministas (sin modelo):
  - parametrizacion.ir.validate: ids únicos, match/payload, deps sin ciclos/colgantes
  - Colisiones de match (mismo api_name/name en dos items distintos de la misma sección)
  - Dependencias hacia ids existentes

Render con parametrizacion.summary → revision.json + revision.md

El JUICIO de fidelidad IR↔DERCAS (invención, faltante, tipo, clasificación, trazabilidad,
idempotencia) lo da Claude con revisor_ir.md.tmpl — no este script.

Uso:
    python revision_ir.py \\
        --ir ~/Sagitaz/clientes/tufisio/ir.json \\
        --out-json ~/Sagitaz/clientes/tufisio/revision.json \\
        --out-md ~/Sagitaz/clientes/tufisio/revision.md

rc=0 incluso si hay observaciones (son para Claude); rc=1 solo si el IR está roto.
"""
import argparse
import json
import pathlib
import sys

# Añadir plugin-claude/scripts/ al path
HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parents[2] / "scripts"  # skills/plan/scripts/ → skills/ → plugin-claude/ → scripts/
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

try:
    from parametrizacion.ir import load_ir, ordered_items, validate, SECTIONS
    from parametrizacion.summary import resumen_md
except ImportError as e:
    print(f"Error: no se puede importar módulos de parametrizacion: {e}", file=sys.stderr)
    print(f"  Buscado en: {SCRIPTS}", file=sys.stderr)
    sys.exit(1)


def _check_colisiones_match(ir):
    """Detecta colisiones de match: mismo api_name/name en dos items de la misma sección."""
    colisiones = []
    for sec in SECTIONS:
        items = ir.get(sec) or []
        vistos = {}  # clave_match → id del primer item
        for it in items:
            m = it.get("match") or {}
            # Clave de match según sección
            if sec == "fields":
                clave = (m.get("module"), m.get("api_name"))
            elif sec in ("roles", "profiles"):
                clave = m.get("name")
            elif sec == "workflows":
                clave = (m.get("module"), m.get("name"))
            else:
                continue
            if clave in vistos:
                colisiones.append({
                    "seccion": sec,
                    "id": it["id"],
                    "colisiona_con": vistos[clave],
                    "match": clave,
                })
            else:
                vistos[clave] = it["id"]
    return colisiones


def revisar(ir):
    """Realiza todos los checks deterministas y devuelve un dict de resultados.

    Returns:
        {
          "valido": bool,
          "errores": [...],       # errores que hacen el IR inválido
          "observaciones": [...], # cosas para revisar (no bloquean)
          "n_items": int,
          "secciones": [str],
        }
    """
    errores = []
    observaciones = []

    # 1. Validación estructural
    try:
        validate(ir)
    except ValueError as e:
        errores.append(str(e))
        return {
            "valido": False,
            "errores": errores,
            "observaciones": [],
            "n_items": 0,
            "secciones": [],
        }

    # 2. Verificar orden topológico (detecta ciclos/deps colgantes)
    try:
        items_ord = list(ordered_items(ir))
    except ValueError as e:
        errores.append(str(e))

    # 3. Colisiones de match
    col = _check_colisiones_match(ir)
    for c in col:
        observaciones.append(
            f"Colisión de match en '{c['seccion']}': "
            f"'{c['id']}' y '{c['colisiona_con']}' tienen el mismo match {c['match']}"
        )

    # 4. Items sin 'from' (trazabilidad — no bloquea, es observación)
    for sec in SECTIONS:
        for it in ir.get(sec) or []:
            if not it.get("from"):
                observaciones.append(
                    f"Item '{it['id']}' ({sec}) no tiene 'from' (sin trazabilidad a requerimiento)")

    n_items = sum(len(ir.get(s) or []) for s in SECTIONS)
    secciones = [s for s in SECTIONS if ir.get(s)]

    return {
        "valido": len(errores) == 0,
        "errores": errores,
        "observaciones": observaciones,
        "n_items": n_items,
        "secciones": secciones,
    }


def _render_md(ir, resultado):
    """Render Markdown de la revisión determinista."""
    lineas = ["# Revisión del IR (checks deterministas)", ""]
    lineas.append(f"**Estado:** {'VÁLIDO' if resultado['valido'] else 'INVÁLIDO'}")
    lineas.append(f"**Items:** {resultado['n_items']} en sección(es): "
                  f"{', '.join(resultado['secciones']) or '(ninguna)'}")
    lineas.append("")

    if resultado["errores"]:
        lineas.append("## Errores (bloquean aplicación)")
        for e in resultado["errores"]:
            lineas.append(f"- {e}")
        lineas.append("")

    if resultado["observaciones"]:
        lineas.append("## Observaciones (para revisar con Claude)")
        for o in resultado["observaciones"]:
            lineas.append(f"- {o}")
        lineas.append("")

    if not resultado["errores"] and not resultado["observaciones"]:
        lineas.append("Sin errores ni observaciones deterministas. "
                      "El juicio de fidelidad IR↔DERCAS lo da Claude con `revisor_ir.md.tmpl`.")
        lineas.append("")

    lineas.append("---")
    lineas.append("")
    # Incluir resumen del IR (via summary)
    try:
        lineas.append(resumen_md(ir))
    except Exception:  # noqa: BLE001
        pass

    return "\n".join(lineas)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Revisión determinista del IR (ir.json)")
    parser.add_argument("--ir", required=True, help="Ruta al ir.json")
    parser.add_argument("--out-json", default=None,
                        help="Ruta de salida revision.json")
    parser.add_argument("--out-md", default=None,
                        help="Ruta de salida revision.md")

    args = parser.parse_args(argv)

    ir_path = pathlib.Path(args.ir)
    if not ir_path.exists():
        print(f"Error: IR no encontrado: {ir_path}", file=sys.stderr)
        return 1

    try:
        ir = load_ir(str(ir_path))
    except ValueError as e:
        # IR roto: guardar revision con error
        resultado = {
            "valido": False,
            "errores": [str(e)],
            "observaciones": [],
            "n_items": 0,
            "secciones": [],
        }
        _guardar(ir_path, {}, resultado, args.out_json, args.out_md)
        print(f"IR inválido: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Error al leer el IR: {e}", file=sys.stderr)
        return 1

    resultado = revisar(ir)
    _guardar(ir_path, ir, resultado, args.out_json, args.out_md)

    if resultado["errores"]:
        print(f"IR inválido ({len(resultado['errores'])} error(es)):", file=sys.stderr)
        for e in resultado["errores"]:
            print(f"  - {e}", file=sys.stderr)
        return 1

    if resultado["observaciones"]:
        print(f"OK (con {len(resultado['observaciones'])} observación(es) para Claude):")
        for o in resultado["observaciones"]:
            print(f"  - {o}")
    else:
        print(f"OK: IR válido — {resultado['n_items']} item(s), "
              f"sin observaciones deterministas")

    return 0


def _guardar(ir_path, ir, resultado, out_json_path, out_md_path):
    """Guarda revision.json y revision.md en las rutas indicadas."""
    # Inferir directorio del IR si no se especifica salida
    base_dir = ir_path.parent

    if out_json_path:
        json_path = pathlib.Path(out_json_path)
    else:
        json_path = base_dir / "revision.json"

    if out_md_path:
        md_path = pathlib.Path(out_md_path)
    else:
        md_path = base_dir / "revision.md"

    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    # Guardar JSON
    json_path.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # Guardar Markdown
    md_path.write_text(
        _render_md(ir, resultado),
        encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(main())
