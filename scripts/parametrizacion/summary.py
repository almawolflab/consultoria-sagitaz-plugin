"""Resumen legible del IR para el consultor (Markdown, determinista, sin modelo).

Convierte el IR ejecutable en un documento que el consultor lee y valida ANTES de aplicar. Es una vista
FIEL del `ir.json` (el JSON sigue siendo la fuente ejecutable); no vuelve a "generar" nada, solo renderiza.
Opcionalmente incluye los caveats del revisor (paso 4). Mira `issues/parametrizacion-fase-v1.md` §11.6.
"""


def _tabla(headers, filas):
    """Devuelve líneas de una tabla Markdown; [] si no hay filas."""
    if not filas:
        return []
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for f in filas:
        out.append("| " + " | ".join((str(c) if c is not None else "").replace("\n", " ") for c in f) + " |")
    return out


def _picklist_str(payload):
    vals = payload.get("pick_list_values") or []
    nombres = [v.get("display_value", "") for v in vals]
    return ", ".join(n for n in nombres if n)


def _reporta_a(payload):
    rep = payload.get("reporting_to")
    if isinstance(rep, dict):
        return rep.get("name") or rep.get("id") or ""
    return rep or "—"


def _criterio(payload):
    return payload.get("criteria_message") or payload.get("criteria") or "—"


_OP = {"create": "crear", "skip": "omitir (ya existe)", "update": "actualizar"}


def plan_md(actions):
    """Render legible del plan dry-run del aplicador (lista de acciones de applicator.plan)."""
    n_c = sum(1 for a in actions if a["op"] == "create")
    n_s = sum(1 for a in actions if a["op"] == "skip")
    L = ["# Plan de aplicación (dry-run — no se ha escrito nada)", "",
         f"Contra el CRM: crear={n_c} · omitir={n_s} · total={len(actions)}.", ""]
    L += _tabla(["Op", "Tipo", "Item", "Módulo", "Req."],
                [[_OP.get(a["op"], a["op"]), a["section"], a.get("label", ""),
                  a.get("module", "") or "", a.get("from", "") or ""] for a in actions])
    L += ["", "> Este plan es solo lectura. La aplicación real se hace con el CLI local, con aprobación."]
    return "\n".join(L) + "\n"


def resumen_md(ir, revision=None):
    meta = ir.get("meta", {}) or {}
    L = [f"# Parametrización — resumen para revisión ({meta.get('cliente', '')})", ""]
    ctx = [f"org: `{meta.get('org_id', '?')}` (sandbox)", f"fecha: {meta.get('generated_at', '?')}",
           f"prefijo: `{meta.get('prefix', '?')}`"]
    L.append(" · ".join(ctx))
    L += ["",
          "> Esto es lo que se aplicará al CRM. El fichero `ir.json` es la **fuente ejecutable**; "
          "si algo no encaja, edítalo antes de aplicar. Este resumen es un borrador para validar.", ""]

    # --- Revisión automática (opcional) ---
    if revision:
        punt = revision.get("puntuacion", "?")
        L += [f"## Revisión automática — {punt}/100", "", revision.get("resumen", ""), ""]
        graves = [d for d in revision.get("defectos", []) if d.get("severidad") in ("alta", "media")]
        if graves:
            L += _tabla(["Severidad", "Regla", "Item", "Req.", "Detalle"],
                        [[d.get("severidad", ""), d.get("regla", ""), d.get("item", ""),
                          d.get("from", ""), d.get("detalle", "")] for d in graves])
            L.append("")

    # --- Se creará automáticamente ---
    L += ["## Se creará automáticamente (vía API)", ""]

    fields = ir.get("fields", []) or []
    if fields:
        L += ["### Campos", ""]
        filas = []
        for f in fields:
            p = f.get("payload", {})
            filas.append([f["match"].get("module", ""), p.get("field_label", f["match"].get("api_name", "")),
                          p.get("data_type", ""), _picklist_str(p), f.get("from", "")])
        L += _tabla(["Módulo", "Campo", "Tipo", "Valores (picklist)", "Req."], filas)
        L.append("")

    roles = ir.get("roles", []) or []
    if roles:
        L += ["### Roles", ""]
        L += _tabla(["Rol", "Reporta a", "Req."],
                    [[r["match"].get("name", ""), _reporta_a(r.get("payload", {})), r.get("from", "")]
                     for r in roles])
        L.append("")

    profiles = ir.get("profiles", []) or []
    if profiles:
        L += ["### Perfiles", ""]
        L += _tabla(["Perfil", "Clonado de", "Nota", "Req."],
                    [[p["match"].get("name", ""), p.get("payload", {}).get("clone_from", ""),
                      p.get("payload", {}).get("description", ""), p.get("from", "")] for p in profiles])
        L.append("")

    workflows = ir.get("workflows", []) or []
    if workflows:
        L += ["### Workflows (reglas de automatización)", ""]
        L += _tabla(["Nombre", "Módulo", "Qué hace (criterio)", "Req."],
                    [[w["match"].get("name", ""), w["match"].get("module", ""),
                      _criterio(w.get("payload", {})), w.get("from", "")] for w in workflows])
        L.append("")

    # --- Tareas manuales ---
    manual = ir.get("manual_todo", []) or []
    L += ["## Tareas manuales (fuera del alcance de la API)", ""]
    if manual:
        L.append("_Blueprints, integraciones externas, DNS, sharing/validación/asignación, scoring… se "
                 "configuran a mano._")
        L.append("")
        for m in manual:
            req = f" (Req. {m.get('from')})" if m.get("from") else ""
            porque = f" — _{m.get('why')}_" if m.get("why") else ""
            spec = f" · configurar: {m.get('spec')}" if m.get("spec") else ""
            L.append(f"- [ ] **{m.get('item', '')}**{porque}{spec}{req}")
        L.append("")
    else:
        L += ["Ninguna.", ""]

    # --- Cierre ---
    L += ["---",
          f"**Recuento:** campos={len(fields)} · roles={len(roles)} · perfiles={len(profiles)} · "
          f"workflows={len(workflows)} · tareas manuales={len(manual)}.",
          "",
          "Borrador para validar. Al aplicar solo se crea lo de la sección automática; las tareas "
          "manuales quedan para el consultor."]
    return "\n".join(L) + "\n"
