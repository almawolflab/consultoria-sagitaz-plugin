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
| `zoho_crm_oauth.json` | Credenciales del consultor (la connected app de Zoho que te da el owner) |
| Confirmación en el chat | Requerida para escritura real (Claude pregunta antes de aplicar) |

---

## Flujo

### Paso 1 — Dry-run (no escribe nada)

Claude ejecuta el dry-run (sin `--apply`):

```bash
python scripts/parametrizacion/apply_cli.py \
  --ir ~/Sagitaz/clientes/<cliente>/ir.json
```

El script muestra el **plan** (creaciones por sección: campos, roles,
perfiles, workflows) pero **no escribe nada** en el CRM. Idempotente: items cuyo `match`
ya existe → `skip`.

Claude resume el plan al consultor en el chat:
- Nº de creaciones por sección (`fields`, `roles`, `profiles`, `workflows`).
- Items que serían `skip` (ya existen).
- Cualquier advertencia (dependencias, tope de campos por módulo).

### Paso 2 — Confirmación en el chat (obligatoria para escribir)

Claude **pregunta en el chat** al consultor si desea aplicar los cambios.
Claude **no ejecuta la escritura** hasta recibir confirmación explícita en el chat.

Ejemplo de pregunta que Claude formula:
> "El dry-run planifica N creaciones (X campos, Y roles…). ¿Confirmas que quieres aplicarlos al CRM sandbox?"

Claude espera la respuesta del consultor antes de continuar.

> **Nota:** `apply_cli.py` incluye un `input()` interactivo para uso manual desde la
> terminal (CLI directo). Cuando se usa desde esta skill, la confirmación se gestiona
> en el chat y se pasa el flag `--yes` al script para saltarse el `input()`.

### Paso 3 — Aplicación (solo tras confirmación en el chat)

Tras confirmación del consultor, Claude ejecuta:

```bash
python scripts/parametrizacion/apply_cli.py \
  --ir ~/Sagitaz/clientes/<cliente>/ir.json \
  --apply --yes
```

El flag `--yes` evita que el script pida `input()` interactivo (que se colgaría en la
Bash tool de Claude Code). El script llama `applicator.apply(ir, client, do_write=True)` sobre `CrmClient`
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
2. **Confirmación en el chat:** Claude pregunta en el chat antes de ejecutar `--apply --yes`.
   Para uso manual en terminal, `apply_cli.py` conserva `input()` interactivo (no usar desde skill).
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
(el aplicador del plugin). No se crea ningún otro aplicador.

---

## Fin de la cadena

Esta es la última skill. El ciclo completo queda documentado en los ficheros locales
del cliente (`~/Sagitaz/clientes/<cliente>/`). Para un nuevo ciclo (cambios adicionales),
actualiza `ir.json` y repite desde `dercas` o directamente desde `implementar`.
