---
name: plan
description: >
  Skill de revisión del IR y generación del plan de implementación legible.
  Claude realiza el juicio de fidelidad IR↔DERCAS mediante un subagente independiente;
  el script hace las comprobaciones deterministas (validación de esquema, colisiones de
  match, dependencias).
---

# Skill: `plan`

**Etapa 4 de 5** del pipeline de consultoría Sagitaz.
Revisa `ir.json` y produce `Plan.md` + `revision.json`/`revision.md`.

> **Principio rector (§4.1):** El **juicio de fidelidad** lo da un **subagente independiente** con
> `revisor_ir.md.tmpl` en contexto aislado; las **comprobaciones mecánicas** (validación de
> esquema, colisiones, deps) las hace el script determinista `revision_ir.py`. Sin modelos externos;
> el razonamiento lo hace Claude.

---

## Entrada

| Recurso | Descripción |
|---------|-------------|
| `~/Sagitaz/clientes/<cliente>/ir.json` | Salida de la skill `dercas` |
| `~/Sagitaz/clientes/<cliente>/DERCAS.json` | Para verificar fidelidad IR↔DERCAS |
| `assets/prompts/revisor_ir.md.tmpl` | Rúbrica de fidelidad (6 ejes) |

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
idempotencia) **no** lo hace el script — lo hace un subagente Claude en el Paso 2.

### Paso 2 — Juicio de fidelidad IR↔DERCAS (subagente Claude con contexto independiente)

Claude lanza un **subagente** mediante la herramienta `Agent` de Claude Code. El subagente
recibe en **contexto fresco** (sin memoria del Claude que generó el IR):

- `ir.json` — el IR a auditar
- `DERCAS.json` — la fuente de verdad del consultor
- `assets/prompts/revisor_ir.md.tmpl` — la rúbrica de los 6 ejes

La independencia viene del contexto aislado del subagente: al no compartir la sesión con
el Claude que generó el IR, el juicio es genuinamente externo (no un auto-juicio).

El subagente devuelve un veredicto JSON con puntuación y defectos por los 6 ejes:

1. **Invención** — ¿hay items sin `from` o cuyo `from` no existe en el DERCAS?
2. **Faltante** — ¿hay requerimientos del DERCAS sin items en el IR?
3. **Tipo** — ¿los `data_type` son los adecuados para cada requerimiento?
4. **Clasificación** — ¿fields/roles/profiles/workflows correctamente clasificados?
5. **Trazabilidad** — ¿cada item tiene `from` con el id del requerimiento origen?
6. **Idempotencia** — ¿los `match` son suficientemente selectivos?

Claude principal escribe los resultados del subagente en `revision_fidelidad.json`.

Si la auditoría detecta defectos **reparables** (errores claros, no decisiones del
consultor), Claude corrige el `ir.json` guiándose por el veredicto recibido del
subagente — sin prompt aparte, aplicando directamente lo que indica el veredicto.

### Paso 3 — Plan de implementación (Claude)

Claude genera `Plan.md` con:
- Resumen del IR (creaciones por sección, tope de campos por módulo).
- Veredicto de la revisión (aprobado / observaciones / bloqueante).
- Orden de aplicación recomendado (topológico por `depends_on`).

### Paso 4 — Plan.docx branded (script determinista, AW-202)

Tras aprobar `Plan.md`, Claude emite el **DOCX branded** (chrome 2026: logo/cabecera/footer/estilos):

```bash
python -c "import sys; sys.path.insert(0,'scripts'); from docx import generar_docx; \
  generar_docx.build_markdown(open('~/Sagitaz/clientes/<cliente>/Plan.md').read(), \
  '~/Sagitaz/clientes/<cliente>/Plan.docx', branded=True, \
  meta={'titulo':'Plan de implementación — <cliente>','cliente':'<cliente>'})"
```

Reusa el generador DOCX compartido (`build_markdown(..., branded=True)`): portada simple + cuerpo del
markdown (encabezados, tablas, listas) con los estilos de la plantilla. Degrada a `.docx` plano si el
brand-kit falta.

---

## Reparto criterio ↔ determinismo

| Quién | Qué hace |
|-------|---------|
| **Script** (`revision_ir.py`) | Validación, colisiones de match, deps, render — determinista |
| **Subagente Claude** | Juicio de fidelidad IR↔DERCAS con `revisor_ir.md.tmpl` en contexto independiente |
| **Claude** (principal) | Correcciones reparables al IR según veredicto; redacción de `Plan.md` |

---

## Salida

| Fichero | Ruta convención (§4.3) |
|---------|----------------------|
| `revision.json` | `~/Sagitaz/clientes/<cliente>/revision.json` |
| `revision.md` | `~/Sagitaz/clientes/<cliente>/revision.md` |
| `revision_fidelidad.json` | `~/Sagitaz/clientes/<cliente>/revision_fidelidad.json` |
| `Plan.md` | `~/Sagitaz/clientes/<cliente>/Plan.md` |
| `Plan.docx` | `~/Sagitaz/clientes/<cliente>/Plan.docx` (branded: logo/cabecera/estilos — AW-202) |

---

## Assets de esta skill

```
skills/plan/
├── SKILL.md                              (este fichero)
├── assets/
│   └── prompts/
│       └── revisor_ir.md.tmpl            (rúbrica de fidelidad IR↔DERCAS — para el subagente)
└── scripts/
    └── revision_ir.py                    (checks deterministas + render summary)
```

---

## Siguiente skill

Con `Plan.md` aprobado (y `ir.json` corregido si procede), el consultor pasa a
**`implementar`** para aplicar el IR al CRM sandbox.
