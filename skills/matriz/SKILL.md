---
name: matriz
description: >
  Skill de generación de la Matriz CRM (Excel pre-marcada) a partir del IR declarativo.
  Paso completamente determinista y offline: no llama a ningún modelo.
---

# Skill: `matriz`

**Etapa 3 de 5** del pipeline de consultoría Sagitaz.
Convierte `ir.json` en `Matriz_CRM.xlsx` (plantilla pre-marcada con los campos propuestos).

> **Principio rector (§4.1):** Este paso es **completamente determinista y offline**.
> Claude dispara el script y resume el resultado; no razona sobre el contenido.
> No se llama a ningún modelo para generar la matriz.

---

## Entrada

| Recurso | Descripción |
|---------|-------------|
| `~/Sagitaz/clientes/<cliente>/ir.json` | Salida de la skill `dercas` |
| `scripts/assets/plantilla_crm.json` | Descriptor de módulos, tipos y planes |
| `scripts/assets/plantilla_crm_base.xlsx` | Plantilla base con estilo Sagitaz |

> La skill toma `ir.json` directamente, **no el DERCAS**. La cadena corregida es:
> `dercas` produce el IR → `matriz` lo consume.

---

## Flujo

### Paso único — Generar xlsx (script determinista, offline, sin modelo)

```bash
python skills/matriz/scripts/generar_matriz.py \
  --ir ~/Sagitaz/clientes/<cliente>/ir.json \
  --out ~/Sagitaz/clientes/<cliente>/Matriz_CRM.xlsx
```

El script:
1. Carga `ir.json` y valida con `ir.validate`.
2. Llama `generador_plantilla.ir_a_propuestas(ir, descriptor)` — agrupa campos por módulo.
3. Llama `plantilla_io.escribir_premarcada(descriptor, propuestas, out_xlsx)` — inyecta
   los campos en la plantilla base (en amarillo, `Origen=DERCAS`).
4. Imprime el recuento por módulo (y excedidos de tope si los hay).

Dependencias: `openpyxl` (Python puro). No requiere red ni credenciales.

---

## Reparto criterio ↔ determinismo

| Quién | Qué hace |
|-------|---------|
| **Script** (`generar_matriz.py`) | `ir_a_propuestas` + `escribir_premarcada` → xlsx |
| **Claude** | Recibe el xlsx, resume el recuento por módulo para el consultor |

Claude **no toma decisiones** sobre el contenido de la matriz; esas decisiones ya están
en el `ir.json` cerrado.

---

## Salida

| Fichero | Ruta convención (§4.3) |
|---------|----------------------|
| `Matriz_CRM.xlsx` | `~/Sagitaz/clientes/<cliente>/Matriz_CRM.xlsx` |

---

## Assets de esta skill

```
skills/matriz/
├── SKILL.md                (este fichero)
└── scripts/
    └── generar_matriz.py   (ir_a_propuestas + escribir_premarcada; openpyxl; sin modelo)
```

Los assets de la plantilla (`plantilla_crm_base.xlsx`, `plantilla_crm.json`) están en
`plugin-claude/scripts/assets/` (no se duplican).

---

## Siguiente skill

Con la `Matriz_CRM.xlsx` validada con el cliente, el consultor pasa a **`plan`** para
revisar la fidelidad del IR y generar el plan de implementación.
