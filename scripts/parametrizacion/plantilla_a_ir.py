#!/usr/bin/env python3
"""
plantilla_a_ir.py — Fase 3 de la parametrización (AW-161): plantilla definitiva → IR ejecutable.

Transforma la plantilla que el consultor confirmó (parseada con `plantilla_io.leer_plantilla`) en el IR
ejecutable: los campos personalizados **v1** se vuelven `fields` del IR; los tipos `mas_adelante`/`manual`
van a `manual_todo`. Los `roles`/`perfiles`/`workflows` se **heredan del IR del DERCAS** (la plantilla no
los cubre). Determinista (sin modelo). NO aplica en el CRM (eso es Fase 4).

Ver contrato `docs/27_contrato_plantilla_parametrizacion.md`.
"""
import re
import unicodedata

from . import plantilla_io
from . import ir as ir_mod


def _slug(txt):
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")
    return t or "campo"


def _pick(valores):
    return [{"display_value": v, "actual_value": v} for v in (valores or [])]


def _sin_deps(items):
    """Copia items del DERCAS quitando `depends_on` (sus deps referencian ids de campos del DERCAS que
    aquí se sustituyen por los de la plantilla; el orden por secciones ya pone campos antes de workflows)."""
    out = []
    for it in items or []:
        c = dict(it)
        c.pop("depends_on", None)
        out.append(c)
    return out


def plantilla_a_ir(parsed, dercas_ir, descriptor, prefix="CFG_", cliente=""):
    """Construye el IR final desde la plantilla parseada + el IR del DERCAS. Valida antes de devolver."""
    dercas_ir = dercas_ir or {}
    fields, manual = [], []
    ids = set()
    for api, mod in (parsed.get("modulos") or {}).items():
        vistos_api = set()
        for nuevo in mod.get("nuevos") or []:
            campo = (nuevo.get("campo") or "").strip()
            if not campo:
                continue
            zoho, bucket = plantilla_io.clasificar_tipo(nuevo.get("tipo"), descriptor)
            if bucket == "v1" and zoho:
                api_name = prefix + _slug(campo)
                while api_name in vistos_api:          # unicidad por módulo
                    api_name += "_2"
                vistos_api.add(api_name)
                fid = "fld-" + _slug(campo).lower(); base = fid; k = 1
                while fid in ids:
                    fid = f"{base}-{k}"; k += 1
                ids.add(fid)
                payload = {"module": api, "field_label": campo, "data_type": zoho}
                if zoho in ("picklist", "multiselectpicklist") and nuevo.get("valores"):
                    payload["pick_list_values"] = _pick(nuevo["valores"])
                fields.append({"id": fid, "from": "plantilla",
                               "match": {"module": api, "api_name": api_name}, "payload": payload})
            else:
                manual.append({"from": "plantilla", "item": f"{campo} ({api})",
                               "why": f"tipo «{nuevo.get('tipo')}» no automatizable ({bucket})"})

    ir_final = {
        "meta": {"cliente": cliente or (dercas_ir.get("meta", {}) or {}).get("cliente", ""),
                 "prefix": prefix, "source": "plantilla"},
        "fields": fields,
        "roles": dercas_ir.get("roles", []) or [],                 # roles: conservan sus deps (rol→rol)
        "profiles": _sin_deps(dercas_ir.get("profiles", [])),
        "workflows": _sin_deps(dercas_ir.get("workflows", [])),
        "manual_todo": (dercas_ir.get("manual_todo", []) or []) + manual,
    }
    ir_mod.validate(ir_final)
    ir_mod.ordered_items(ir_final)     # falla pronto ante ciclos/deps rotas
    return ir_final
