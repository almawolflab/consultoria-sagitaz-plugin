# Revisión del IR (checks deterministas)

**Estado:** VÁLIDO
**Items:** 11 en sección(es): fields, roles, profiles, workflows

Sin errores ni observaciones deterministas. El juicio de fidelidad IR↔DERCAS lo da Claude con `revisor_ir.md.tmpl`.

---

# Parametrización — resumen para revisión (Jaque Legal)

org: `693026068` (sandbox) · fecha: ? · prefijo: `?`

> Esto es lo que se aplicará al CRM. El fichero `ir.json` es la **fuente ejecutable**; si algo no encaja, edítalo antes de aplicar. Este resumen es un borrador para validar.

## Se creará automáticamente (vía API)

### Campos

| Módulo | Campo | Tipo | Valores (picklist) | Req. |
|---|---|---|---|---|
| Leads | JLT Origen/Referido | picklist | Jaque Legal (JL), Hipotecasos (MTP), Legaltech (BDT), Particular (COL1) | 5.4/5.1 |
| Leads | JLT Servicio (Campana) | picklist | Complemento/Brecha, Revolving/Transpar., Cartel de coches, Hipotecas, LSO, Consultas, Lesiones, Defensa del monitorio | 5.1 |
| Leads | JLT Motivo de perdida | picklist | No contesta, No viable, No quiere, Repetido | 5.1 |
| Leads | JLT Fecha Recordatorio | date |  | 5.10 |

### Roles

| Rol | Reporta a | Req. |
|---|---|---|
| JLT CEO | Gerencia | 5.3 |
| JLT Gerente comercial | JLT CEO | 5.3 |
| JLT Comerciales | JLT Gerente comercial | 5.3 |
| JLT Administracion | JLT CEO | 5.3 |
| JLT Cobranza | JLT Administracion | 5.3 |

### Perfiles

| Perfil | Clonado de | Nota | Req. |
|---|---|---|---|
| JLT Comercial | Standard | Comercial: sin acceso a Oportunidades (Deals) | 5.3 |

### Workflows (reglas de automatización)

| Nombre | Módulo | Qué hace (criterio) | Req. |
|---|---|---|---|
| JLT Recordatorio firma Hoja de encargo | Leads | JLT_Origen_Referido = 'Jaque Legal (JL)' | 5.10/5.1 |

## Tareas manuales (fuera del alcance de la API)

Ninguna.

---
**Recuento:** campos=4 · roles=5 · perfiles=1 · workflows=1 · tareas manuales=0.

Borrador para validar. Al aplicar solo se crea lo de la sección automática; las tareas manuales quedan para el consultor.
