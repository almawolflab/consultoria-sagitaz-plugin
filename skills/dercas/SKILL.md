---
name: dercas
description: >
  Skill de análisis de viabilidad + criterios de aceptación (DERCAS) y generación del IR
  (Implementation Record) declarativo. Claude trabaja en 2 fases guiado por prompts Sagitaz;
  el script valida el IR resultante.
---

# Skill: `dercas`

**Etapa 2 de 5** del pipeline de consultoría Sagitaz.
Convierte `DERS.json` + criterios dictados por el consultor en `DERCAS.json` + `ir.json`.

> **Principio rector (§4.1):** Claude aporta el criterio en 2 fases (DERCAS + IR);
> el script hace la validación determinista del IR resultante.
> **No se ejecuta `mapper.py`** ni modelos externos; el razonamiento lo hace Claude.

---

## Entrada

| Recurso | Descripción |
|---------|-------------|
| `~/Sagitaz/clientes/<cliente>/DERS.json` | Salida de la skill `ders` |
| Dictado del consultor | Criterios y análisis de viabilidad por requerimiento (texto o voz) |
| `assets/prompts/patcher_dercas.md.tmpl` | Instrucciones para la fase DERCAS |
| `assets/prompts/mapper_ir.md.tmpl` | Instrucciones para la fase IR |

---

## Flujo — 2 fases de Claude + validación

### Fase 1 — DERCAS (Claude con criterio)

Claude aplica `assets/prompts/patcher_dercas.md.tmpl` sobre el `DERS.json` cerrado:

- Rellena `analisis_viabilidad` (prosa, según el dictado del consultor) y
  `criterios_aceptacion` (fórmula _"Se verifica que [condición] → [resultado esperado]"_)
  **por cada requerimiento**.
- **No modifica** el resto del DERS (requerimientos, especificaciones, texto ya acordado).
- Marca `[PENDIENTE — sin dictado del consultor]` donde no haya dictado aún.
- La estructura destino es la de `scripts/assets/dercas_con_plantilla.json`
  (claves `requerimientos[].{analisis_viabilidad, criterios_aceptacion, ...}`).

El consultor revisa y corrige conversando hasta cerrar el DERCAS.

### Fase 2 — IR declarativo (Claude con criterio)

Una vez cerrado el DERCAS, Claude aplica `assets/prompts/mapper_ir.md.tmpl`:

- Produce `ir.json` con secciones `fields`, `roles`, `profiles`, `workflows`
  + `manual_todo` + `_changelog`.
- Respeta las **reglas duras** del prompt:
  - Solo tipos automatizables (p.ej. `picklist`, `text`; no `fileupload`).
  - Nombres planos en `api_name` y nombres custom (sin prefijo).
  - `match` por idempotencia (lookup del item existente).
  - `from` por trazabilidad (id del requerimiento origen).
  - `depends_on` para orden de aplicación.

### Validación del IR (script determinista)

```bash
python skills/dercas/scripts/validar_ir.py \
  ~/Sagitaz/clientes/<cliente>/ir.json
```

Usa `parametrizacion.ir` (`load_ir` + `validate` + `ordered_items` + `validar_semantico`) vía sys.path
a `plugin-claude/scripts/`. Comprueba:

- `id` único por sección.
- `match`, `payload` presentes.
- `depends_on` sin ciclos ni referencias colgantes.
- **Semántico (AW-200):** `data_type` válido contra el descriptor, `match.module == payload.module`,
  que el módulo exista en el descriptor y la coherencia de picklists. Los *avisos* (rol raíz
  duplicable, campo manual sin `manual_todo`) se imprimen pero **no** bloquean.

Sale con rc≠0 y detalle si el IR no es válido.

### Emisión del DERCAS.docx (script determinista, AW-200 #8 + AW-202)

Una vez cerrado el DERCAS, Claude genera el **DOCX formal branded** (entregable de cliente) junto al JSON:

```bash
python scripts/docx/generar_docx.py \
  ~/Sagitaz/clientes/<cliente>/DERCAS.json \
  ~/Sagitaz/clientes/<cliente>/DERCAS.docx \
  --dercas --formal
```

Reusa el generador compartido (`build(..., dercas=True)`): renderiza `analisis_viabilidad` y
`criterios_aceptacion` por requerimiento con anclas estables. Es función pura del JSON (stdlib pura).
`--formal` (AW-202) parte del brand-kit 2026 (logo/portada/firma) y filtra marcadores/trazabilidad
internos. (Omite `--formal` para el borrador interno; `--plano` para salida sin branding.)

---

## Reparto criterio ↔ determinismo

| Quién | Qué hace |
|-------|---------|
| **Claude** (fase 1) | Aplica `patcher_dercas.md.tmpl` → `DERCAS.json` con viabilidad + criterios |
| **Claude** (fase 2) | Aplica `mapper_ir.md.tmpl` → `ir.json` con reglas duras |
| **Script** (`validar_ir.py`) | Validación estructural **y semántica** del IR (ids, match, deps, data_type/módulo/picklist) — sin modelo |
| **Script** (`scripts/docx/generar_docx.py`) | Emite `DERCAS.docx` **formal branded** (`build(dercas=True, formal=True)`) — generador compartido |

---

## Salida

| Fichero | Ruta convención (§4.3) |
|---------|----------------------|
| `DERCAS.json` | `~/Sagitaz/clientes/<cliente>/DERCAS.json` |
| `DERCAS.docx` | `~/Sagitaz/clientes/<cliente>/DERCAS.docx` (formal branded: logo/portada/firma, limpio — AW-202) |
| `ir.json` | `~/Sagitaz/clientes/<cliente>/ir.json` ← entrada de `matriz`, `plan`, `implementar` |

---

## Assets de esta skill

```
skills/dercas/
├── SKILL.md                            (este fichero)
├── assets/
│   └── prompts/
│       ├── patcher_dercas.md.tmpl      (instrucciones fase DERCAS: viabilidad + criterios)
│       └── mapper_ir.md.tmpl           (instrucciones fase IR declarativo)
└── scripts/
    └── validar_ir.py                   (validación IR via parametrizacion.ir.validate)
```

Los esquemas de referencia (`dercas_con_plantilla.json`) están en `plugin-claude/scripts/assets/`.

---

## Siguiente skill

Una vez validado `ir.json`, el consultor puede ejecutar (en cualquier orden):
- **`matriz`** → `Matriz_CRM.xlsx` para validar con el cliente
- **`plan`** → `Plan.md` + `revision.*` para revisar la fidelidad del IR
- **`implementar`** → aplicación al CRM sandbox (después de validar matriz y plan)
