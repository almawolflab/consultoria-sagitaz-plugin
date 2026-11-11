---
name: ders
description: >
  Skill de extracción del DERS (Documento de Especificaciones y Requerimientos de Software)
  a partir de transcripciones de reuniones con el cliente. Claude redacta el DERS guiado por
  los prompts del pipeline Sagitaz; los scripts hacen lo determinista (fetch + validación).
---

# Skill: `ders`

**Etapa 1 de 5** del pipeline de consultoría Sagitaz.
Convierte transcripciones de reuniones en un `DERS.json` al estándar Sagitaz.

> **Principio rector (§4.1):** Claude aporta el criterio (extracción y redacción);
> los scripts hacen lo determinista (fetch de transcripciones y validación de esquema).
> **No se invocan orquestadores de pipeline** ni modelos externos; el razonamiento lo hace Claude.

---

## Entrada

| Recurso | Descripción |
|---------|-------------|
| `<cliente>` | Nombre del cliente (slug, p.ej. `tufisio`) |
| Endpoint `/transcripciones` | El servicio de transcripciones del servidor — no necesitas acceso directo |
| `assets/schema/plantilla_ders.json` | Árbol de secciones FIJO (numeración no se renumera) |
| `assets/schema/esquema_vacio.json` | Esqueleto JSON vacío para rellenar |

---

## Flujo

### Paso 1 — Obtener transcripciones (script determinista)

```bash
python skills/ders/scripts/fetch_transcripciones.py \
  --cliente <cliente> \
  --out ~/Sagitaz/clientes/<cliente>/transcripciones.txt
```

El script usa stdlib pura (`urllib`) y **autorresuelve** endpoint y token: si el consultor
los configuró en los ajustes del plugin (*Endpoint de transcripciones* / *Token de equipo*),
el hook SessionStart los materializa en `data_dir()/transcripciones.json` (AW-196) y el
script los lee de ahí automáticamente — **no hace falta exportar variables de entorno**.
Precedencia: `--endpoint`/`--token` (CLI) > env `TRANSCRIPCIONES_ENDPOINT`/`TEAM_API_TOKEN`
> `data_dir()/transcripciones.json`.
**Nunca imprime el token.** Sale con rc≠0 en errores 401/503/404 con mensaje claro
(y si no hay endpoint/token configurados, indica que se fijen en los ajustes del plugin).

### Paso 2 — Claude redacta y audita el DERS (criterio del modelo)

El Paso 2 tiene tres subpasos: **2a** (borrador), **2b** (juicio por subagente independiente)
y **2c** (aplicar el veredicto). La estructura destino es la de
`assets/schema/plantilla_ders.json` (árbol de secciones FIJO).

#### Paso 2a — Borrador (extractor → enriquecedor)

Claude (principal) sigue estos prompts como instrucciones, en orden, y escribe el borrador
`DERS.json`:

1. **`assets/prompts/extractor.md.tmpl`** — extrae requerimientos SOLO del corpus de transcripciones.
   Sin conocimiento previo. Sin inventar nada que no esté en el texto.
2. **`assets/prompts/enriquecedor.md.tmpl`** — enriquece con contexto de Zoho CRM,
   sin modificar lo acordado con el cliente.

#### Paso 2b — Juicio del DERS (subagente Claude con contexto independiente)

Igual que en la skill `plan`, el **juicio no es auto-auditoría**: Claude lanza un **subagente**
mediante la herramienta `Agent` de Claude Code. El subagente recibe en **contexto fresco**
(sin memoria del Claude que redactó el borrador):

- el **borrador `DERS.json`** a juzgar
- las **transcripciones íntegras** (`transcripciones.txt`) — el corpus de referencia
- `assets/prompts/juez.md.tmpl` — la rúbrica Sagitaz (auditor independiente)

La independencia viene del contexto aislado: al no compartir sesión con el Claude que generó
el borrador, el juicio es genuinamente externo (no un auto-juicio). El subagente devuelve un
veredicto JSON `{ puntuacion, defectos[], resumen }` que Claude principal escribe en
`revision_ders_juez.json`.

> Si el subagente cae o no devuelve JSON válido, el flujo **no bloquea** el borrador: se avisa y
> se continúa (el DERS queda sin veredicto automático, revisable por el consultor).

#### Paso 2c — Aplicar el veredicto (patcher)

Claude principal aplica las correcciones **reparables** del veredicto siguiendo
**`assets/prompts/patcher.md.tmpl`**, que recibe el borrador + `revision_ders_juez.json`.
El consultor **revisa y edita conversando** hasta cerrar el DERS.

### Paso 3 — Validar + generar DOCX (scripts deterministas)

```bash
python skills/ders/scripts/validar_ders.py \
  ~/Sagitaz/clientes/<cliente>/DERS.json \
  --schema assets/schema/plantilla_ders.json
```

Validación estructural contra la plantilla canónica 2026: la numeración de cada requerimiento
pertenece al árbol FIJO de secciones, sin numeración inventada ni duplicados. Determinista, sin
modelo. Sale con rc≠0 y detalle si el DERS no pasa. (Un DERS pre-2026, p.ej. tufisio plano, no
conformará: es lo esperado.)

Tras validar, Claude genera el **DOCX formal branded** (entregable de cliente) junto al JSON:

```bash
python scripts/docx/generar_docx.py \
  ~/Sagitaz/clientes/<cliente>/DERS.json \
  ~/Sagitaz/clientes/<cliente>/DERS.docx \
  --formal
```

`scripts/docx/generar_docx.py` es el **generador DOCX compartido** (AW-200) que usan `ders`, `dercas`
y `matriz`. Es una **función pura** del JSON (stdlib pura, sin dependencias): funde el DERS sobre el
árbol 2026 y emite OOXML con *labels* estables (anclas para el round-trip futuro, AW-198).

`--formal` (AW-202) parte del **brand-kit 2026** (logo/cabecera/portada/firma) y produce una salida
**limpia de cliente**: sin intro de proceso ni anotaciones `[DECISIÓN CONSULTOR]`/`[PENDIENTE…]` ni
trazabilidad de audios. (Omite `--formal` para el borrador interno con anotaciones; `--plano` para
salida sin branding.)

---

## Reparto criterio ↔ determinismo

| Quién | Qué hace |
|-------|---------|
| **Script** (`fetch_transcripciones.py`) | GET `/transcripciones?cliente=X` → `transcripciones.txt` |
| **Claude (principal)** | Lee transcripciones, sigue extractor → enriquecedor → borrador `DERS.json` (2a); aplica el veredicto con patcher (2c) |
| **Subagente Claude** | Juzga el borrador con `juez.md.tmpl` en contexto independiente → `revision_ders_juez.json` (2b) |
| **Script** (`validar_ders.py`) | Valida `DERS.json` contra la plantilla canónica 2026 (numeración) |
| **Script** (`scripts/docx/generar_docx.py`) | Generador DOCX compartido: emite `DERS.docx` **formal branded** (brand-kit 2026) desde el JSON |

---

## Salida

| Fichero | Ruta convención (§4.3) |
|---------|----------------------|
| `transcripciones.txt` | `~/Sagitaz/clientes/<cliente>/transcripciones.txt` |
| `DERS.json` | `~/Sagitaz/clientes/<cliente>/DERS.json` ← fuente de verdad |
| `revision_ders_juez.json` | `~/Sagitaz/clientes/<cliente>/revision_ders_juez.json` (veredicto del subagente) |
| `DERS.docx` | `~/Sagitaz/clientes/<cliente>/DERS.docx` (formal branded: logo/portada/firma, limpio — AW-202) |

La ruta se resuelve con `skills_paths.cliente_path(cliente, "DERS.json")`.

---

## Assets de esta skill

```
skills/ders/
├── SKILL.md                            (este fichero)
├── assets/
│   ├── prompts/
│   │   ├── extractor.md.tmpl           (prompt de extracción de requerimientos)
│   │   ├── enriquecedor.md.tmpl        (prompt de enriquecimiento con contexto CRM)
│   │   ├── juez.md.tmpl                (rúbrica Sagitaz — para el subagente auditor independiente, 2b)
│   │   └── patcher.md.tmpl             (aplica el veredicto del juez sobre el borrador, 2c)
│   └── schema/
│       ├── plantilla_ders.json         (árbol de secciones FIJO — fuente de verdad)
│       └── esquema_vacio.json          (esqueleto JSON vacío para Claude)
└── scripts/
    ├── fetch_transcripciones.py        (stdlib urllib; sin dependencias externas)
    └── validar_ders.py                 (validación de numeración contra plantilla 2026)
```

> El generador DOCX vive ahora en `plugin-claude/scripts/docx/generar_docx.py` (módulo **compartido**
> por `ders`/`dercas`/`matriz`, AW-200), no bajo `skills/ders/scripts/`.

Los esquemas de `assets/schema/` son **copias** de `plugin-claude/scripts/assets/` (layout exigido por
la spec §4.2: el conocimiento de dominio viaja con la skill). ⚠️ Riesgo de deriva: si
`scripts/assets/plantilla_ders.json` o `esquema_vacio.json` cambian, re-sincronizar estas copias
(candidato a check automático, análogo a `scripts/sync_catalyst_assets.py`).

---

## Siguiente skill

Una vez cerrado y validado `DERS.json`, la siguiente skill es **`dercas`**:
lee `DERS.json` y produce `DERCAS.json` + `ir.json`.
