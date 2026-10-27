---
name: plan
description: >
  Skill de revisión del IR y generación del plan de implementación legible.
  Claude realiza el juicio de fidelidad IR↔DERCAS; el script hace las comprobaciones
  deterministas (validación de esquema, colisiones de match, dependencias).
---

# Skill: `plan`

**Etapa 4 de 5** del pipeline de consultoría Sagitaz.
Revisa `ir.json` y produce `Plan.md` + `revision.json`/`revision.md`.

> **Principio rector (§4.1):** El **juicio de fidelidad** lo da Claude con `revisor_ir.md.tmpl`;
> las **comprobaciones mecánicas** (validación de esquema, colisiones, deps) las hace el script
> determinista `revision_ir.py`. Sin llamadas a Gemini.

---

## Entrada

| Recurso | Descripción |
|---------|-------------|
| `~/Sagitaz/clientes/<cliente>/ir.json` | Salida de la skill `dercas` |
| `~/Sagitaz/clientes/<cliente>/DERCAS.json` | Para verificar fidelidad IR↔DERCAS |
| `assets/prompts/revisor_ir.md.tmpl` | Rúbrica de fidelidad (6 ejes) |
| `assets/prompts/revisor_correcciones.md.tmpl` | Instrucciones de corrección post-revisión |

---

## Flujo

### Paso 1 — Revisión determinista del IR (script)

```bash
python skills/plan/scripts/revision_ir.py \
  --ir ~/Sagitaz/clientes/<cliente>/ir.json \
  --out-json ~/Sagitaz/clientes/<cliente>/revision.json \
  --out-md ~/Sagitaz/clientes/<cliente>/revision.md
```

El script realiza comprobaciones **deterministas** (sin modelo):
- `parametrizacion.ir.validate` — ids únicos, `match`/`payload` presentes, deps sin ciclos.
- Colisiones de `match` (mismo `api_name`/`name` en dos items distintos).
- Referencias `depends_on` a ids existentes.
- Render con `parametrizacion.summary` → `revision.json` + `revision.md` estructurados.

El **juicio de fidelidad** (invención, faltante, tipo, clasificación, trazabilidad,
idempotencia) **no** lo hace el script — lo hace Claude en el Paso 2.

### Paso 2 — Juicio de fidelidad IR↔DERCAS (Claude con criterio)

Claude lee `revision.md` (salida del script) y aplica `assets/prompts/revisor_ir.md.tmpl`:

Rúbrica de 6 ejes:
1. **Invención** — ¿hay items sin `from` o cuyo `from` no existe en el DERCAS?
2. **Faltante** — ¿hay requerimientos del DERCAS sin items en el IR?
3. **Tipo** — ¿los `data_type` son los adecuados para cada requerimiento?
4. **Clasificación** — ¿fields/roles/profiles/workflows correctamente clasificados?
5. **Trazabilidad** — ¿cada item tiene `from` con el id del requerimiento origen?
6. **Idempotencia** — ¿los `match` son suficientemente selectivos?

Si hay correcciones, Claude aplica `assets/prompts/revisor_correcciones.md.tmpl` y propone
el `ir.json` corregido para que el consultor lo revise.

### Paso 3 — Plan de implementación (Claude)

Claude genera `Plan.md` con:
- Resumen del IR (creaciones por sección, tope de campos por módulo).
- Veredicto de la revisión (aprobado / observaciones / bloqueante).
- Orden de aplicación recomendado (topológico por `depends_on`).

---

## Reparto criterio ↔ determinismo

| Quién | Qué hace |
|-------|---------|
| **Script** (`revision_ir.py`) | Validación, colisiones de match, deps, render — determinista |
| **Claude** | Juicio de fidelidad IR↔DERCAS con `revisor_ir.md.tmpl` |
| **Claude** | Propuesta de correcciones con `revisor_correcciones.md.tmpl` |
| **Claude** | Redacción del `Plan.md` legible |

---

## Salida

| Fichero | Ruta convención (§4.3) |
|---------|----------------------|
| `revision.json` | `~/Sagitaz/clientes/<cliente>/revision.json` |
| `revision.md` | `~/Sagitaz/clientes/<cliente>/revision.md` |
| `Plan.md` | `~/Sagitaz/clientes/<cliente>/Plan.md` |

---

## Assets de esta skill

```
skills/plan/
├── SKILL.md                              (este fichero)
├── assets/
│   └── prompts/
│       ├── revisor_ir.md.tmpl            (copiado de pipeline/prompts/, AW-188)
│       └── revisor_correcciones.md.tmpl  (copiado de pipeline/prompts/, AW-188)
└── scripts/
    └── revision_ir.py                    (checks deterministas + render summary)
```

---

## Siguiente skill

Con `Plan.md` aprobado (y `ir.json` corregido si procede), el consultor pasa a
**`implementar`** para aplicar el IR al CRM sandbox.
