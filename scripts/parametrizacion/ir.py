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


# ---------------------------------------------------------------- validación semántica (AW-200 #5)

# El descriptor no lista roles raíz estándar → constante mínima documentada (normalizada a minúsculas).
_ROLES_RAIZ = {"ceo", "gerencia", "dirección general", "direccion general"}

_BUCKETS_NO_API = ("mas_adelante", "manual")


def tipos_validos(descriptor):
    """data_types Zoho reconocidos: propiedad 'zoho' de cada tipo (NO las claves, que van en español)."""
    return {info.get("zoho") for info in (descriptor or {}).get("tipos", {}).values() if info.get("zoho")}


def modulos_validos(descriptor):
    """api_names válidos: descriptor['modulos'] es una lista de dicts con 'api_name'."""
    return {m.get("api_name") for m in (descriptor or {}).get("modulos", []) if m.get("api_name")}


def _bucket_de_zoho(zoho, descriptor):
    """data_type Zoho → bucket (v1|mas_adelante|manual). Desconocido → 'manual'. Sin descriptor → None."""
    for info in (descriptor or {}).get("tipos", {}).values():
        if info.get("zoho") == zoho:
            return info.get("bucket", "manual")
    return None if not (descriptor or {}).get("tipos") else "manual"


def _check_picklist(item):
    """pick_list_values: lista no vacía, cada valor con display_value+actual_value, sin display duplicado."""
    errs = []
    iid = item.get("id", "?")
    plv = item.get("payload", {}).get("pick_list_values")
    if not plv or not isinstance(plv, list):
        errs.append(f"{iid}: picklist sin 'pick_list_values' (lista no vacía)")
        return errs
    vistos = set()
    for v in plv:
        if not isinstance(v, dict) or not v.get("display_value") or not v.get("actual_value"):
            errs.append(f"{iid}: picklist con valor sin 'display_value'/'actual_value'")
            continue
        dv = v["display_value"]
        if dv in vistos:
            errs.append(f"{iid}: picklist con 'display_value' duplicado '{dv}'")
        vistos.add(dv)
    return errs


def _avisos_roles_raiz(ir):
    out = []
    for r in ir.get("roles", []) or []:
        nombre = (r.get("match", {}) or {}).get("name", "")
        if nombre and nombre.strip().lower() in _ROLES_RAIZ:
            out.append(f"{r.get('id', '?')}: rol '{nombre}' coincide con un rol raíz estándar "
                       f"(posible duplicado)")
    return out


def _avisos_manual_todo(ir, descriptor):
    out = []
    manual_ids = {m.get("item") for m in (ir.get("manual_todo", []) or [])}
    for item in ir.get("fields", []) or []:
        payload = item.get("payload", {}) or {}
        bucket = _bucket_de_zoho(payload.get("data_type"), descriptor)
        if bucket in _BUCKETS_NO_API:
            label = payload.get("field_label") or item.get("id", "?")
            if label not in manual_ids and item.get("id") not in manual_ids:
                out.append(f"{item.get('id', '?')}: campo '{label}' en bucket '{bucket}' "
                           f"sin entrada en manual_todo (trazabilidad)")
    return out


def validar_semantico(ir, descriptor):
    """Checks semánticos sobre un IR ya estructuralmente válido.

    Devuelve `(errores, avisos)`: `errores` bloquean (rc=1); `avisos` son observaciones de
    trazabilidad. NO lanza. Degrada sin falsos positivos si el descriptor viene incompleto
    (sets vacíos → se omite ese check).
    """
    errores, avisos = [], []
    tvalid = tipos_validos(descriptor)
    mvalid = modulos_validos(descriptor)
    for item in ir.get("fields", []) or []:
        iid = item.get("id", "?")
        payload, match = item.get("payload", {}) or {}, item.get("match", {}) or {}
        dt = payload.get("data_type")
        if tvalid and dt not in tvalid:
            errores.append(f"{iid}: data_type '{dt}' no es válido")
        if match.get("module") != payload.get("module"):
            errores.append(f"{iid}: match.module ({match.get('module')!r}) != "
                           f"payload.module ({payload.get('module')!r})")
        if mvalid and match.get("module") not in mvalid:
            errores.append(f"{iid}: módulo '{match.get('module')}' no existe en el descriptor")
        if dt in ("picklist", "multiselectpicklist"):
            errores += _check_picklist(item)
    avisos += _avisos_roles_raiz(ir)
    avisos += _avisos_manual_todo(ir, descriptor)
    return errores, avisos


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
