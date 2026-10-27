"""Motor plan/apply del aplicador de Parametrización.

- `plan(ir, maps)` resuelve, por cada item del IR, la operación (`create`/`skip`) comparando su `match`
  con el discovery del CRM. Es **dry-run puro**: no escribe.
- `apply(ir, client, do_write=False)` construye el discovery, calcula el plan y —solo si `do_write`—
  ejecuta los aplicadores por tipo en orden de dependencias y verifica cada creación.

Idempotencia: un item cuyo `match` ya existe se resuelve a `skip` y **no** llama a la API. Payloads y
quirks por tipo están tomados del spike §10 (verificados a mano en el sandbox).
"""
from . import discovery, ir as ir_mod


class SkipItem(Exception):
    """El aplicador no puede/ no debe aplicar este item (p. ej. tipo de acción no soportado).
    apply() lo registra como 'omitido' y continúa con el resto (no aborta la corrida)."""


# ---------- PLAN (sin escribir) ----------

def _exists(section, item, maps):
    m = item["match"]
    if section == "fields":
        return m["api_name"] in maps["fields"].get(m["module"], {})
    if section == "roles":
        return m["name"] in maps["roles"]
    if section == "profiles":
        return m["name"] in maps["profiles"]
    if section == "workflows":
        return m["name"] in maps["workflows"].get(m["module"], {})
    raise ValueError(f"sección desconocida: {section}")


def plan(ir, maps):
    """Lista de acciones {section,id,from,op,label} en orden de dependencias."""
    actions = []
    for section, item in ir_mod.ordered_items(ir):
        op = "skip" if _exists(section, item, maps) else "create"
        actions.append({
            "section": section,
            "id": item["id"],
            "from": item.get("from"),
            "op": op,
            "label": item["match"].get("api_name") or item["match"].get("name"),
            "module": item["match"].get("module"),
        })
    return actions


# ---------- DISCOVERY ----------

def build_discovery(client, ir):
    """Construye los mapas de estado actual necesarios para el IR dado."""
    modules = set()
    for it in ir.get("fields", []) or []:
        modules.add(it["match"]["module"])
    for it in ir.get("workflows", []) or []:
        modules.add(it["match"]["module"])

    maps = {"fields": {}, "roles": {}, "profiles": {}, "workflows": {}, "modules": {}}
    for mod in modules:
        maps["fields"][mod] = discovery.get_fields(client, mod)
    if ir.get("roles") or ir.get("profiles"):
        maps["roles"] = discovery.get_roles(client)
    if ir.get("profiles"):
        maps["profiles"] = discovery.get_profiles(client)
    if ir.get("workflows"):
        maps["modules"] = discovery.get_modules(client)
        for mod in modules:
            maps["workflows"][mod] = discovery.get_workflow_rules(client, mod)
    return maps


# ---------- APLICADORES POR TIPO (escriben) ----------

def apply_field(client, item, maps):
    payload = dict(item["payload"])
    module = payload.pop("module", None) or item["match"]["module"]
    client.post("/settings/fields", body={"fields": [payload]}, params={"module": module})
    fields = discovery.get_fields(client, module)          # verify
    maps["fields"][module] = fields
    return item["match"]["api_name"] in fields


def apply_role(client, item, maps):
    payload = dict(item["payload"])
    rep = payload.get("reporting_to")
    if isinstance(rep, dict) and rep.get("name") and not rep.get("id"):
        parent = maps["roles"].get(rep["name"])
        if not parent:
            raise RuntimeError(f"rol padre no encontrado: {rep['name']}")
        payload["reporting_to"] = {"id": parent["id"]}
    client.post("/settings/roles", body={"roles": [payload]})
    maps["roles"] = discovery.get_roles(client)             # verify + refresca ids para hijos
    return item["match"]["name"] in maps["roles"]


def apply_profile(client, item, maps):
    payload = dict(item["payload"])
    src_name = payload.get("clone_from", "Standard")
    src = maps["profiles"].get(src_name)
    if not src:
        raise RuntimeError(f"perfil origen para clonar no encontrado: {src_name}")
    client.post(f"/settings/profiles/{src['id']}/actions/clone",
                body={"profiles": [{"name": payload["name"],
                                    "description": payload.get("description", "")}]})
    maps["profiles"] = discovery.get_profiles(client)       # verify
    # NOTA: el ajuste fino de permisos (PUT /settings/profiles/{id}) se aplica aparte; ver spike §10.3.
    return item["match"]["name"] in maps["profiles"]


def _created_id(resp, key):
    """Extrae el id creado de una respuesta de settings ({key:[{code,details:{id}}]})."""
    try:
        return resp[key][0]["details"]["id"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"respuesta sin id creado: {str(resp)[:300]}")


def apply_workflow(client, item, maps):
    """Crea una regla de workflow según el spike §10.6 / doc v8:
    1) por cada acción field_update → POST /settings/automation/field_updates (module id + field id) → id
    2) POST /settings/automation/workflow_rules con execute_when + conditions + instant_actions (id+type).
    Tipos de acción no soportados (task/email) → SkipItem (workflow omitido, no aborta la corrida).
    """
    payload = item["payload"]
    module_api = payload.get("module") or item["match"]["module"]
    module_id = maps.get("modules", {}).get(module_api)
    if not module_id:
        raise RuntimeError(f"módulo no encontrado en discovery: {module_api}")

    # 1) acciones → objetos + refs (id, type)
    action_refs = []
    for a in payload.get("actions", []):
        if a.get("type") != "field_update":
            raise SkipItem(f"tipo de acción no soportado aún: {a.get('type')!r} "
                           f"(tareas/alertas/correo → manual_todo)")
        fld = maps["fields"].get(module_api, {}).get(a["field"])
        if not fld or not fld.get("id"):
            raise RuntimeError(f"campo del field_update no encontrado: {module_api}.{a['field']}")
        body = {"field_updates": [{
            "module": {"api_name": module_api, "id": module_id},
            "type": "static", "feature_type": "workflow",
            "field": {"api_name": a["field"], "id": fld["id"]},
            "name": a.get("name") or f"{payload['name']} · {a['field']}",
            "value": a["value"],
        }]}
        resp = client.post("/settings/automation/field_updates", body=body)
        action_refs.append({"id": _created_id(resp, "field_updates"), "type": "field_updates"})

    # 2) execute_when (repeat + trigger_module obligatorios para edit/create_or_edit)
    trig = (payload.get("trigger") or {}).get("on", "create_or_edit")
    execute_when = {"type": trig}
    if trig in ("edit", "create_or_edit"):
        execute_when["details"] = {"repeat": True,
                                   "trigger_module": {"api_name": module_api, "id": module_id}}

    crit = payload.get("criteria")
    criteria = None
    if crit:
        criteria = {"comparator": crit.get("operator", "equal"),
                    "field": {"api_name": crit["field"]}, "value": crit["value"]}
    rule = {
        "execute_when": execute_when,
        "module": {"api_name": module_api},
        "name": payload["name"],
        "conditions": [{
            "sequence_number": 1,
            "criteria_details": {"criteria": criteria},
            "instant_actions": {"actions": action_refs},
        }],
    }
    client.post("/settings/automation/workflow_rules", body={"workflow_rules": [rule]})
    maps["workflows"][module_api] = discovery.get_workflow_rules(client, module_api)   # verify
    return item["match"]["name"] in maps["workflows"][module_api]


_APPLIERS = {
    "fields": apply_field,
    "roles": apply_role,
    "profiles": apply_profile,
    "workflows": apply_workflow,
}


# ---------- APPLY ----------

def apply(ir, client, do_write=False):
    """Calcula el plan y, si do_write, ejecuta las creaciones en orden y verifica cada una."""
    maps = build_discovery(client, ir)
    actions = plan(ir, maps)
    result = {"actions": actions, "wrote": False, "results": []}
    if not do_write:
        return result

    result["wrote"] = True
    by_id = {(sec, it["id"]): it for sec, it in ir_mod.ordered_items(ir)}
    for act in actions:
        if act["op"] != "create":
            result["results"].append({**act, "status": "skipped"})
            continue
        item = by_id[(act["section"], act["id"])]
        try:
            ok = _APPLIERS[act["section"]](client, item, maps)
            result["results"].append({**act, "status": "created" if ok else "unverified"})
        except SkipItem as ex:
            result["results"].append({**act, "status": "omitido", "error": str(ex)})
        except Exception as ex:  # noqa: BLE001 — robusto: registra y sigue (no aborta la corrida)
            result["results"].append({**act, "status": "error", "error": repr(ex)})
    return result
