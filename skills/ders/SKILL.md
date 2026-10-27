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
> **No se invocan orquestadores de pipeline** ni motores externos como Gemini.

---

## Entrada

| Recurso | Descripción |
|---------|-------------|
| `<cliente>` | Nombre del cliente (slug, p.ej. `tufisio`) |
| Endpoint `/transcripciones` | Servicio AW-185 — no necesitas acceso directo |
| `assets/schema/plantilla_ders.json` | Árbol de secciones FIJO (numeración no se renumera) |
| `assets/schema/esquema_vacio.json` | Esqueleto JSON vacío para rellenar |

---

## Flujo

### Paso 1 — Obtener transcripciones (script determinista)

```bash
python skills/ders/scripts/fetch_transcripciones.py \
  --cliente <cliente> \
  --endpoint $TRANSCRIPCIONES_ENDPOINT \
  --token $TEAM_API_TOKEN \
  --out ~/Sagitaz/clientes/<cliente>/transcripciones.txt
```

El script usa stdlib pura (`urllib`). Lee endpoint y token de env
(`TRANSCRIPCIONES_ENDPOINT`, `TEAM_API_TOKEN`) o argumentos CLI.
**Nunca imprime el token.** Sale con rc≠0 en errores 401/503/404 con mensaje claro.

### Paso 2 — Claude redacta el DERS (criterio del modelo)

Claude sigue los 4 prompts del pipeline como instrucciones, en orden:

1. **`assets/prompts/extractor.md.tmpl`** — extrae requerimientos SOLO del corpus de transcripciones.
   Sin conocimiento previo. Sin inventar nada que no esté en el texto.
2. **`assets/prompts/enriquecedor.md.tmpl`** — enriquece con contexto de Zoho CRM,
   sin modificar lo acordado con el cliente.
3. **`assets/prompts/juez.md.tmpl`** — auto-auditoría con rúbrica Sagitaz (fidelidad,
   completitud, no-invención, formato).
4. **`assets/prompts/patcher.md.tmpl`** — aplica las correcciones del juez.
   Usa `{{PREFIX}}` del cliente para nombrar campos personalizados.

La estructura destino es la de `assets/schema/plantilla_ders.json` (árbol de secciones FIJO).
El consultor **revisa y edita conversando** hasta cerrar el DERS.

> Render `.docx` (DERS.docx): pendiente/opcional en v1 (`generar_docx.py` de AW-187).

### Paso 3 — Validar el DERS (script determinista)

```bash
python skills/ders/scripts/validar_ders.py \
  ~/Sagitaz/clientes/<cliente>/DERS.json \
  --schema assets/schema/plantilla_ders.json
```

Validación estructural del árbol de secciones (secciones fijas, numeración intacta).
Determinista, sin modelo. Sale con rc≠0 y detalle si el DERS no pasa.

---

## Reparto criterio ↔ determinismo

| Quién | Qué hace |
|-------|---------|
| **Script** (`fetch_transcripciones.py`) | GET `/transcripciones?cliente=X` → `transcripciones.txt` |
| **Claude** | Lee transcripciones, sigue extractor → enriquecedor → juez → patcher → `DERS.json` |
| **Script** (`validar_ders.py`) | Valida `DERS.json` contra esquema estructural |

---

## Salida

| Fichero | Ruta convención (§4.3) |
|---------|----------------------|
| `transcripciones.txt` | `~/Sagitaz/clientes/<cliente>/transcripciones.txt` |
| `DERS.json` | `~/Sagitaz/clientes/<cliente>/DERS.json` ← fuente de verdad |
| `DERS.docx` | `~/Sagitaz/clientes/<cliente>/DERS.docx` (opcional) |

La ruta se resuelve con `skills_paths.cliente_path(cliente, "DERS.json")`.

---

## Assets de esta skill

```
skills/ders/
├── SKILL.md                            (este fichero)
├── assets/
│   ├── prompts/
│   │   ├── extractor.md.tmpl           (copiado de pipeline/prompts/, AW-188)
│   │   ├── enriquecedor.md.tmpl        (copiado de pipeline/prompts/, AW-188)
│   │   ├── juez.md.tmpl                (copiado de pipeline/prompts/, AW-188)
│   │   └── patcher.md.tmpl             (copiado de pipeline/prompts/, AW-188)
│   └── schema/
│       ├── plantilla_ders.json         (árbol de secciones FIJO — fuente de verdad)
│       └── esquema_vacio.json          (esqueleto JSON vacío para Claude)
└── scripts/
    ├── fetch_transcripciones.py        (stdlib urllib; sin Gemini, sin dependencias externas)
    └── validar_ders.py                 (validación estructural determinista)
```

Los esquemas de `assets/schema/` son **copias** de `plugin-claude/scripts/assets/` (layout exigido por
la spec §4.2: el conocimiento de dominio viaja con la skill). ⚠️ Riesgo de deriva: si
`scripts/assets/plantilla_ders.json` o `esquema_vacio.json` cambian, re-sincronizar estas copias
(candidato a check automático, análogo a `scripts/sync_catalyst_assets.py`).

---

## Siguiente skill

Una vez cerrado y validado `DERS.json`, la siguiente skill es **`dercas`**:
lee `DERS.json` y produce `DERCAS.json` + `ir.json`.
