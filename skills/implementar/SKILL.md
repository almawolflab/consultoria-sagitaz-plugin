---
name: implementar
description: >
  Skill de aplicación del IR al CRM sandbox del consultor. Paso irreversible con dry-run
  por defecto y confirmación explícita obligatoria. Solo CRM sandbox; producción bloqueada
  por guarda dura.
---

# Skill: `implementar`

**Etapa 5 de 5** del pipeline de consultoría Sagitaz.
Aplica `ir.json` al CRM sandbox del consultor mediante REST v8.

> **ATENCIÓN — Paso irreversible:** Esta skill **escribe en el CRM**. El modo por defecto
> es **dry-run** (no escribe nada). La escritura real requiere **confirmación explícita**.
>
> **Solo CRM sandbox:** la guarda dura en `crm.py` lanza `RuntimeError` si `api_domain`
> apunta al dominio de producción. Producción está bloqueada a nivel de código; no hay ninguna
> vía para evitarlo desde esta skill.

---

## Entrada

| Recurso | Descripción |
|---------|-------------|
| `~/Sagitaz/clientes/<cliente>/ir.json` | Salida validada de la skill `dercas` |
| `zoho_crm_oauth.json` | Credenciales del consultor (connected app de AW-186) |
| `--apply` + confirmación `"si"` | Requerido para escritura real |

---

## Flujo

### Paso 1 — Dry-run (modo por defecto, no escribe)

Claude ejecuta:

```bash
python scripts/parametrizacion/apply_cli.py \
  --ir ~/Sagitaz/clientes/<cliente>/ir.json
```

Sin `--apply`, el script muestra el **plan** (creaciones por sección: campos, roles,
perfiles, workflows) pero **no escribe nada** en el CRM. Idempotente: items cuyo `match`
ya existe → `skip`.

Claude resume el plan al consultor:
- Nº de creaciones por sección (`fields`, `roles`, `profiles`, `workflows`).
- Items que serían `skip` (ya existen).
- Cualquier advertencia (dependencias, tope de campos por módulo).

### Paso 2 — Confirmación explícita (obligatoria para escribir)

Claude **no ejecuta la escritura** hasta que el consultor confirme explícitamente.

El script pide confirmación interactiva:

```
¿Aplicar los N cambios al CRM sandbox? [escribe "si" para confirmar]:
```

Solo continúa si el consultor responde `si` (exacto, sin mayúsculas, sin variantes).
Cualquier otra respuesta cancela con rc=1 sin escribir.

### Paso 3 — Aplicación (solo tras confirmación)

```bash
python scripts/parametrizacion/apply_cli.py \
  --ir ~/Sagitaz/clientes/<cliente>/ir.json \
  --apply
```

El script llama `applicator.apply(ir, client, do_write=True)` sobre `CrmClient`
(credenciales de `zoho_crm_oauth.json` del consultor). Flujo:
1. `build_discovery` — estado actual del CRM.
2. `plan` — lista de acciones (create/skip).
3. Si `do_write=True` → ejecuta creaciones en orden topológico (`depends_on`).
4. Verifica cada creación.

Idempotencia: segunda corrida → todo `skip`.

### Paso 4 — Resumen

Claude genera `resumen_implementacion.md` con:
- Resultado por sección (creados / skip / errores).
- Enlace al sandbox para verificar.

---

## Reparto criterio ↔ determinismo

| Quién | Qué hace |
|-------|---------|
| **Claude** | Presenta el plan dry-run al consultor; pide confirmación |
| **Script** (`apply_cli.py`) | Dry-run o apply vía REST v8; idempotente |
| **Claude** | Genera `resumen_implementacion.md` |

**La escritura SOLO ocurre vía `apply_cli.py` con `--apply` tras confirmación.**
Claude no tiene ninguna otra vía para escribir en el CRM.

---

## Guardas de seguridad

1. **Dry-run por defecto:** sin `--apply`, el script nunca escribe.
2. **Confirmación explícita:** con `--apply`, el script pide `"si"` interactivo
   (patrón `apply_cli.py`; `--yes` solo para automatización CI aprobada).
3. **Sandbox-only (guarda dura en `crm.py`):**
   Si el `api_domain` del fichero de credenciales apunta al dominio de producción,
   `CrmClient` lanza `RuntimeError` antes de cualquier llamada a la API.
   Este error se lanza en el constructor, antes de cualquier llamada.
   No hay ninguna vía de bypassarlo desde esta skill.

---

## Salida

| Fichero | Ruta convención (§4.3) |
|---------|----------------------|
| `resumen_implementacion.md` | `~/Sagitaz/clientes/<cliente>/resumen_implementacion.md` |

---

## Assets de esta skill

```
skills/implementar/
└── SKILL.md            (este fichero)
```

Esta skill reutiliza `scripts/parametrizacion/apply_cli.py` sin modificaciones
(AW-187). No se crea ningún otro aplicador.

---

## Fin de la cadena

Esta es la última skill. El ciclo completo queda documentado en los ficheros locales
del cliente (`~/Sagitaz/clientes/<cliente>/`). Para un nuevo ciclo (cambios adicionales),
actualiza `ir.json` y repite desde `dercas` o directamente desde `implementar`.
