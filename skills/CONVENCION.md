# Convención de ficheros locales por cliente (AW-188 §4.3)

El handoff entre skills se realiza mediante ficheros locales en una ruta predecible por cliente.
No hay estado durable compartido ni tabla `procesos`; la convención de rutas permite reanudar
el trabajo en otra sesión.

## Raíz configurable

```
~/Sagitaz/clientes/<cliente>/      ← por defecto
```

Override (para tests o entornos distintos):
- Variable de entorno: `SAGITAZ_CLIENTES_ROOT=/ruta/a/clientes`
- Argumento `root=` en `skills_paths.cliente_path(...)`

## Ficheros estándar por etapa

```
~/Sagitaz/clientes/<cliente>/
├── transcripciones.txt          ← (ders) texto traído del endpoint vía fetch_transcripciones.py
├── DERS.json                    ← (ders) DERS validado contra plantilla_ders.json
├── DERS.docx                    ← (ders) render opcional para el cliente
├── DERCAS.json                  ← (dercas) DERS + analisis_viabilidad + criterios_aceptacion
├── ir.json                      ← (dercas) IR declarativo → entrada de matriz / plan / implementar
├── Matriz_CRM.xlsx              ← (matriz) plantilla pre-marcada (openpyxl, offline)
├── Plan.md                      ← (plan) plan de implementación legible
├── revision.json                ← (plan) veredicto mecánico de fidelidad IR↔DERCAS
├── revision.md                  ← (plan) veredicto en Markdown (para el consultor)
└── resumen_implementacion.md    ← (implementar) resultado de la aplicación REST v8
```

## Cadena de dependencias

```
fetch_transcripciones.py
  → transcripciones.txt
    → Claude (extractor/enriquecedor/juez/patcher) → DERS.json
      → validar_ders.py (check esquema)
        → Claude (patcher_dercas) → DERCAS.json
          → Claude (mapper_ir) → ir.json
            → validar_ir.py (check estructural)
              ├─ generar_matriz.py → Matriz_CRM.xlsx
              ├─ revision_ir.py + Claude (revisor_ir) → revision.* + Plan.md
              └─ apply_cli.py (dry-run → confirm → apply) → resumen_implementacion.md
```

## Helper de rutas

Todas las skills importan `skills_paths.cliente_path(cliente, fichero)` para resolver rutas:

```python
from skills_paths import cliente_path

ders_json = cliente_path("tufisio", "DERS.json")
ir_json   = cliente_path("tufisio", "ir.json")
```

Esto garantiza que la salida de cada skill es exactamente la entrada de la siguiente.

## Nota sobre producción

La raíz `~/Sagitaz/clientes/` es local al consultor. Los ficheros **no** se suben automáticamente
a WorkDrive en esta versión (gap conocido, docs/24). El CRM que se modifica es siempre el
**sandbox del consultor** (guarda dura en `crm.py`; ver skill `implementar`).
