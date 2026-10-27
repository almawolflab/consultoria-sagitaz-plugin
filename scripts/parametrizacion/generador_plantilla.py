#!/usr/bin/env python3
"""
generador_plantilla.py — Fase 2 de la parametrización reorientada (AW-161).

Transforma el IR (salida del mapper DERCAS→IR) en:
  1. `propuestas` para pre-marcar la plantilla Excel (campos por módulo) → `plantilla_io.escribir_premarcada`.
  2. el **resumen** consultor-facing (entregable estrella) que clasifica todo en 3 cubos:
     API-ya · automatizable-más-adelante · manual.

Lenguaje neutro (no delata automatización/IA). Determinista (no llama a ningún modelo): el IR ya viene
del mapper. Ver contrato `docs/27_contrato_plantilla_parametrizacion.md`.
"""
from . import plantilla_io


# ---------------------------------------------------------------- IR → propuestas de plantilla

def ir_a_propuestas(ir, descriptor):
    """Agrupa los campos del IR por módulo, en el formato de `plantilla_io.escribir_premarcada`:
    `{api_name: [{campo, tipo(display ES), seccion, valores}]}`."""
    prop = {}
    for f in ir.get("fields", []) or []:
        p = f.get("payload", {}) or {}
        api = f.get("match", {}).get("module") or p.get("module")
        if not api:
            continue
        valores = [v.get("display_value", "") for v in (p.get("pick_list_values") or [])]
        prop.setdefault(api, []).append({
            "campo": p.get("field_label") or f.get("match", {}).get("api_name", ""),
            "tipo": plantilla_io.display_de_zoho(p.get("data_type"), descriptor),
            "seccion": p.get("section") or "",
            "valores": [v for v in valores if v],
        })
    return prop


# ---------------------------------------------------------------- resumen (3 cubos)

def _tabla(headers, filas):
    if not filas:
        return []
    out = ["| " + " | ".join(headers) + " |",
           "|" + "|".join(["---"] * len(headers)) + "|"]
    for f in filas:
        out.append("| " + " | ".join((str(c) if c is not None else "").replace("\n", " ") for c in f) + " |")
    return out


def _picklist(p):
    return ", ".join(v.get("display_value", "") for v in (p.get("pick_list_values") or []) if v.get("display_value"))


def _split_fields(ir, descriptor):
    """Reparte los campos del IR en v1 / mas_adelante / manual según su data_type."""
    cubos = {"v1": [], "mas_adelante": [], "manual": []}
    for f in ir.get("fields", []) or []:
        p = f.get("payload", {}) or {}
        b = plantilla_io.bucket_de_zoho(p.get("data_type"), descriptor)  # siempre v1|mas_adelante|manual
        cubos[b].append(f)
    return cubos


def resumen_plantilla(ir, descriptor, plan_cliente=None):
    """Markdown consultor-facing con la clasificación API-ya / más-adelante / manual de la config.
    `plan_cliente`: nº de campos custom permitidos por módulo (si None, usa el tope estándar del descriptor)."""
    meta = ir.get("meta", {}) or {}
    cli = meta.get("cliente", "")
    cubos = _split_fields(ir, descriptor)
    roles = ir.get("roles", []) or []
    profiles = ir.get("profiles", []) or []
    workflows = ir.get("workflows", []) or []
    manual_todo = ir.get("manual_todo", []) or []

    L = [f"# Parametrización — mapa de configuración ({cli})", "",
         "Qué de la configuración acordada se puede montar por API y qué queda para hacer a mano. "
         "Los campos propuestos vienen ya marcados en la plantilla adjunta.", ""]

    # --- Se creará por API (ahora) ---
    L += ["## Se puede montar por API (ahora)", ""]
    if cubos["v1"]:
        L += ["### Campos", ""]
        L += _tabla(["Módulo", "Campo", "Tipo", "Valores (lista)", "Req."],
                    [[f["match"].get("module", ""), f["payload"].get("field_label", ""),
                      plantilla_io.display_de_zoho(f["payload"].get("data_type"), descriptor),
                      _picklist(f["payload"]), f.get("from", "")] for f in cubos["v1"]])
        L.append("")
    if roles:
        L += ["### Roles", ""]
        L += _tabla(["Rol", "Reporta a", "Req."],
                    [[r["match"].get("name", ""),
                      (r.get("payload", {}).get("reporting_to") or {}).get("name", "—") if isinstance(
                          r.get("payload", {}).get("reporting_to"), dict) else "—", r.get("from", "")]
                     for r in roles])
        L.append("")
    if profiles:
        L += ["### Perfiles", ""]
        L += _tabla(["Perfil", "Clonado de", "Nota", "Req."],
                    [[p["match"].get("name", ""), p.get("payload", {}).get("clone_from", ""),
                      p.get("payload", {}).get("description", ""), p.get("from", "")] for p in profiles])
        L.append("")
    if workflows:
        L += ["### Workflows", ""]
        L += _tabla(["Nombre", "Módulo", "Req."],
                    [[w["match"].get("name", ""), w["match"].get("module", ""), w.get("from", "")]
                     for w in workflows])
        L.append("")
    if not (cubos["v1"] or roles or profiles or workflows):
        L += ["_Nada en este bloque._", ""]

    # --- Automatizable más adelante ---
    L += ["## Automatizable más adelante", ""]
    if cubos["mas_adelante"]:
        L += _tabla(["Módulo", "Campo", "Tipo", "Req."],
                    [[f["match"].get("module", ""), f["payload"].get("field_label", ""),
                      plantilla_io.display_de_zoho(f["payload"].get("data_type"), descriptor),
                      f.get("from", "")] for f in cubos["mas_adelante"]])
        L.append("")
    L += ["_Tipos avanzados (fórmula, autonumérico, lookup), módulos personalizados y ubicación en "
          "secciones/layout se incorporarán en una tanda posterior._", ""]

    # --- Manual ---
    L += ["## Requiere configuración manual", ""]
    items = []
    for f in cubos["manual"]:
        items.append(f"**{f['payload'].get('field_label','')}** ({f['match'].get('module','')}) — tipo no "
                     f"automatizable")
    for m in manual_todo:
        req = f" (Req. {m.get('from')})" if m.get("from") else ""
        porque = f" — _{m.get('why')}_" if m.get("why") else ""
        items.append(f"**{m.get('item','')}**{porque}{req}")
    if items:
        for it in items:
            L.append(f"- [ ] {it}")
        L.append("")
    L += ["_Reglas de validación, dependencias de campo, notificaciones (Email/WhatsApp) y blueprints se "
          "configuran a mano._", ""]

    # --- Límite de campos por plan ---
    cap = plan_cliente if plan_cliente else (descriptor.get("planes", {}) or {}).get("estandar", 10)
    por_modulo = {}
    for f in (cubos["v1"] + cubos["mas_adelante"]):
        por_modulo[f["match"].get("module", "?")] = por_modulo.get(f["match"].get("module", "?"), 0) + 1
    excedidos = [f"{m} ({n})" for m, n in por_modulo.items() if n > cap]
    L += ["## Recuento por módulo (campos personalizados)", ""]
    L += _tabla(["Módulo", "Campos propuestos"], [[m, n] for m, n in sorted(por_modulo.items())])
    nota_plan = "" if plan_cliente else " (referencia: plan estándar; **confirmar el plan del cliente**)"
    L += ["", f"Tope por módulo: **{cap}**{nota_plan}."]
    if excedidos:
        L.append(f"> ⚠️ Superan el tope: {', '.join(excedidos)}.")
    L.append("")

    # --- cierre ---
    L += ["---",
          f"**Recuento:** campos={len(ir.get('fields', []) or [])} · roles={len(roles)} · "
          f"perfiles={len(profiles)} · workflows={len(workflows)} · manuales={len(items)}."]
    return "\n".join(L) + "\n"
