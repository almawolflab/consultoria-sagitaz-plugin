"""CLI del aplicador de Parametrización (plugin-claude/scripts/).

Uso:
    # Dry-run (por defecto): solo muestra el plan, NO escribe nada.
    python3 -m parametrizacion.apply_cli --ir tests/fixtures/ir_jaque_r1r3.json

    # Aplicar de verdad (escribe en el sandbox) — pide confirmación salvo --yes:
    python3 -m parametrizacion.apply_cli --ir <ir.json> --apply
"""
import argparse
import sys

from .crm import CrmClient, load_creds
from . import applicator, ir as ir_mod

_MARK = {"create": "＋ crear", "skip": "· omitir (ya existe)", "update": "~ actualizar"}


def _print_plan(actions):
    print(f"\nPlan ({len(actions)} items):")
    for a in actions:
        frm = f"  [{a['from']}]" if a.get("from") else ""
        mod = f" @{a['module']}" if a.get("module") else ""
        print(f"  {_MARK.get(a['op'], a['op']):<26} {a['section']:<10} {a['label']}{mod}{frm}")
    n_create = sum(1 for a in actions if a["op"] == "create")
    n_skip = sum(1 for a in actions if a["op"] == "skip")
    print(f"\nResumen: crear={n_create}  omitir={n_skip}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Aplicador REST v8 de Parametrización (sandbox)")
    ap.add_argument("--ir", required=True, help="ruta al IR (JSON declarativo)")
    ap.add_argument("--apply", action="store_true", help="escribe en el CRM (por defecto solo dry-run)")
    ap.add_argument("--yes", action="store_true", help="no pedir confirmación al escribir")
    ap.add_argument("--creds", default=None, help="ruta a zoho_crm_oauth.json (por defecto raíz de scripts/)")
    args = ap.parse_args(argv)

    ir = ir_mod.load_ir(args.ir)
    creds = load_creds(args.creds) if args.creds else load_creds()
    client = CrmClient(creds=creds)
    print(f"CRM: {client.api}  (org_id={creds.get('org_id')})")

    if not args.apply:
        res = applicator.apply(ir, client, do_write=False)
        _print_plan(res["actions"])
        print("\n(dry-run: no se ha escrito nada)")
        return 0

    # Modo escritura: mostrar plan y confirmar
    maps = applicator.build_discovery(client, ir)
    actions = applicator.plan(ir, maps)
    _print_plan(actions)
    n_create = sum(1 for a in actions if a["op"] == "create")
    if n_create == 0:
        print("\nNada que crear (todo skip). No se escribe.")
        return 0
    if not args.yes:
        resp = input(f"\n¿Aplicar {n_create} creación(es) en {client.api}? [escribe 'si']: ").strip().lower()
        if resp != "si":
            print("Cancelado.")
            return 1
    res = applicator.apply(ir, client, do_write=True)
    print("\nResultados:")
    for r in res["results"]:
        print(f"  {r['status']:<12} {r['section']:<10} {r['label']}"
              + (f"  ERROR: {r['error']}" if r.get("error") else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
