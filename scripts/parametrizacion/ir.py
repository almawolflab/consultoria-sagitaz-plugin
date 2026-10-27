"""Carga y validación ligera del IR (spec de parametrización declarativa, esquema del spike §1).

El IR es un JSON con secciones por tipo (`fields`, `roles`, `profiles`, `workflows`); cada item lleva
como mínimo `id` (slug estable), `match` (clave de idempotencia) y `payload`. Opcional `depends_on`
(lista de ids que deben aplicarse antes) y `from` (requerimiento origen, trazabilidad).

La validación NO es exhaustiva; comprueba lo mínimo para **fallar pronto** ante un IR roto — importa
porque a futuro el consultor editará este JSON a mano. `ordered_items` devuelve los items en orden de
dependencias (topológico), para que roles-padre precedan a hijos y los campos precedan al workflow que
los referencia.
"""
import json

SECTIONS = ("fields", "roles", "profiles", "workflows")


def load_ir(path):
    with open(path) as f:
        ir = json.load(f)
    validate(ir)
    return ir


def validate(ir):
    if not isinstance(ir, dict):
        raise ValueError("IR: la raíz debe ser un objeto JSON")
    seen = set()
    present = [s for s in SECTIONS if s in ir]
    if not present:
        raise ValueError(f"IR: no hay ninguna sección conocida ({', '.join(SECTIONS)})")
    for sec in present:
        items = ir[sec]
        if not isinstance(items, list):
            raise ValueError(f"IR: la sección '{sec}' debe ser una lista")
        for i, it in enumerate(items):
            loc = f"{sec}[{i}]"
            if not isinstance(it, dict):
                raise ValueError(f"IR: {loc} debe ser un objeto")
            for req in ("id", "match", "payload"):
                if req not in it:
                    raise ValueError(f"IR: {loc} sin campo obligatorio '{req}'")
            if it["id"] in seen:
                raise ValueError(f"IR: id duplicado '{it['id']}' en {loc}")
            seen.add(it["id"])
            if not isinstance(it.get("match"), dict):
                raise ValueError(f"IR: {loc}.match debe ser un objeto")
            dep = it.get("depends_on", [])
            if not isinstance(dep, list):
                raise ValueError(f"IR: {loc}.depends_on debe ser una lista")
    return True


def ordered_items(ir):
    """Devuelve [(section, item), ...] en orden topológico por `depends_on`.

    Orden estable: respeta el orden de secciones (SECTIONS) y el orden dentro de cada sección como
    desempate; solo adelanta un item cuando otro depende de él.
    """
    items = []          # (section, item) en orden natural
    by_id = {}
    for sec in SECTIONS:
        for it in ir.get(sec, []) or []:
            items.append((sec, it))
            by_id[it["id"]] = (sec, it)

    resolved, out = set(), []

    def visit(node, stack):
        sec, it = node
        iid = it["id"]
        if iid in resolved:
            return
        if iid in stack:
            raise ValueError(f"IR: ciclo de dependencias en '{iid}'")
        stack.add(iid)
        for dep in it.get("depends_on", []) or []:
            if dep not in by_id:
                raise ValueError(f"IR: '{iid}' depende de id inexistente '{dep}'")
            visit(by_id[dep], stack)
        stack.discard(iid)
        resolved.add(iid)
        out.append(node)

    for node in items:
        visit(node, set())
    return out
