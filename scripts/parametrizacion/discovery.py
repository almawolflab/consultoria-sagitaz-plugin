"""Discovery read-only del estado actual del CRM, para resolver idempotencia (create/skip/update).

Cada función devuelve un mapa `clave -> objeto` con el que el aplicador decide si un item del IR ya existe.
No escribe nada. Protocolo "discovery-first" del spike §3.
"""


def get_modules(client):
    """api_name -> id (str) de los módulos del CRM."""
    data = client.get("/settings/modules").get("modules", []) or []
    return {m.get("api_name"): m.get("id") for m in data if m.get("api_name")}


def get_fields(client, module):
    """api_name -> field (dict) de los campos de un módulo."""
    data = client.get("/settings/fields", params={"module": module}).get("fields", []) or []
    return {f.get("api_name"): f for f in data if f.get("api_name")}


def get_roles(client):
    """name -> role (dict)."""
    data = client.get("/settings/roles").get("roles", []) or []
    return {r.get("display_label") or r.get("name"): r for r in data if (r.get("display_label") or r.get("name"))}


def get_profiles(client):
    """name -> profile (dict)."""
    data = client.get("/settings/profiles").get("profiles", []) or []
    return {p.get("name"): p for p in data if p.get("name")}


def get_workflow_rules(client, module):
    """name -> rule (dict). El endpoint devuelve `workflow_rules` (o `rules` en algunas versiones)."""
    resp = client.get("/settings/automation/workflow_rules", params={"module": module})
    data = resp.get("workflow_rules") or resp.get("rules") or []
    return {r.get("name"): r for r in data if r.get("name")}
