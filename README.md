# Plugin Consultoría Sagitaz — Guía de Setup y Distribución

Plugin de Claude Teams que expone el pipeline completo de consultoría de Sagitaz como skills:
DERS → DERCAS → IR → Matriz CRM → Plan → Implementación (solo sandbox Zoho CRM).

---

## Para el consultor — Setup inicial

### 1. Requisitos previos (macOS)

**Lo único que instalas a mano es Python 3.10 o superior.** El resto (entorno virtual,
dependencias, verificación) lo prepara el plugin **automáticamente** al abrir sesión.

| Requisito | Versión mínima | Instalación |
|-----------|---------------|-------------|
| Python | 3.10+ | [python.org/downloads](https://www.python.org/downloads/) (universal) · o, si ya tienes Homebrew: `brew install python@3.12` |
| Claude Desktop (pestaña Code) / Claude Code | última | Incluido en tu plan |

> No necesitas saber la ruta exacta de Python: el plugin **autodescubre** cualquier `python3.1x` ≥ 3.10
> de tu sistema. (Alcance actual: macOS.)

### 2. Instalar el plugin desde el marketplace

1. En **Customize → Plugins → + Add → Add marketplace**, introduce el repositorio del plugin:
   `almawolflab/consultoria-sagitaz-plugin` (o la URL git
   `https://github.com/almawolflab/consultoria-sagitaz-plugin.git`) y pulsa **Sync**.
   (En Claude Code por terminal: `/plugin` → añade el mismo marketplace.)
2. Instala (o actualiza) **consultoria-sagitaz** desde el marketplace añadido.
3. Al instalarlo, rellena los valores de `userConfig`:

   | Campo | Qué introducir |
   |-------|---------------|
   | `transcripciones_endpoint` | URL base del endpoint `/transcripciones` (la da el owner) — *solo Fase 2* |
   | `transcripciones_team_token` | Token de equipo (lo reparte el owner; se guarda de forma segura) — *solo Fase 2* |
   | `crm_client_id` | Client ID de la connected app de Zoho CRM sandbox (lo reparte el owner) — *solo `/implementar`* |
   | `crm_client_secret` | Client Secret de la connected app (se guarda de forma segura) — *solo `/implementar`* |
   | `python_bin` | **Déjalo vacío** (el plugin autodescubre Python). Solo fíjalo si la autodetección falla. |

   > Los campos sensibles (`transcripciones_team_token`, `crm_client_secret`) se almacenan en
   > el almacén seguro de la plataforma, **nunca** en `settings.json` ni en el repo.
   >
   > **Materialización (AW-196):** al abrir sesión, el hook SessionStart escribe estos valores
   > en `data_dir()` (`~/.local/share/consultoria-sagitaz/`) como `transcripciones.json` y
   > `crm_connected_app.json` (permisos `0600`). Así las skills `ders`/`implementar` los usan
   > **sin exportar variables de entorno ni tocar ficheros a mano**.

### 3. Preparación automática del entorno (hook SessionStart)

**No tienes que hacer nada manual.** Al abrir una sesión en la pestaña Code, un hook `SessionStart`
del plugin:
1. **autodescubre** un Python ≥ 3.10 (o usa `python_bin` si lo fijaste);
2. **crea el venv** e instala las dependencias (`openpyxl`) la **primera vez** (verás un aviso
   "Preparando el entorno… ~15-30s"); las siguientes sesiones son instantáneas (idempotente);
3. **informa a Claude** del estado del entorno; si **falta Python ≥ 3.10**, muestra un aviso con el
   enlace de instalación ([python.org/downloads](https://www.python.org/downloads/)).

El venv vive en un directorio fijo (`~/.local/share/consultoria-sagitaz/venv`, salvo override con
`CONSULTORIA_SAGITAZ_DATA` / `XDG_DATA_HOME`).

> **Fallback manual (opcional):** si lo necesitas, puedes forzar la preparación con
> `python3 scripts/bootstrap.py` (o `--force` para recrearlo).

### 4. Verificar el entorno con doctor.py (diagnóstico opcional)

El onboarding ya es automático (paso 3). Si quieres diagnosticar a mano:

```bash
python3 scripts/doctor.py
```

> **No necesitas pasar flags**: doctor autodescubre el venv y la ruta del token OAuth.

Checks que realiza:

| Check | Descripción | Obligatorio |
|-------|-------------|-------------|
| [A] Python >= 3.10 | Versión del intérprete en el venv | Sí |
| [B] openpyxl importa | Dependencia de la matriz CRM | Sí |
| [C] Sin imageio-ffmpeg | No debe estar en el venv del plugin | Sí |
| [D] Fichero OAuth existe | `zoho_crm_oauth.json` del consultor | Solo para `/implementar` (aviso sin `--require-oauth`) |
| [E] api_domain sandbox | `sandbox.zohoapis.<dc>`, nunca producción | Solo para `/implementar` (aviso sin `--require-oauth`) |
| [F] Endpoint alcanzable | `TRANSCRIPCIONES_ENDPOINT` responde | Aviso |

Devuelve **exit 0** si [A][B][C] pasan (sin importar [D]/[E], que son avisos por defecto).
Para `/implementar`, usa `doctor --require-oauth` para verificar también [D]/[E].
Las skills `/matriz`, `/plan` y `/dercas` funcionan sin OAuth ([D]/[E] no son obligatorios para Fase 1).

### 5. Autorización Zoho (una vez por consultor)

Lanza el flujo OAuth de la connected app de Zoho que te da el owner para generar tu fichero de credenciales local:

```bash
python3 scripts/authorize_crm.py
```

Esto abre el navegador con el consentimiento OAuth de tu cuenta Zoho y guarda el fichero
`zoho_crm_oauth.json` (gitignored) con tu `refresh_token` y el `api_domain` del sandbox.

> **Importante:** el fichero siempre apunta al **sandbox** (`sandbox.zohoapis.com`).
> El plugin bloquea cualquier operación contra producción (`www.zohoapis.com`) a nivel de código
> (`scripts/parametrizacion/crm.py:56-59`).

### 6. Prueba E2E

Para confirmar que todo funciona de extremo a extremo:

1. Abre una sesión con el plugin activo.
2. Invoca `ders` para un cliente de prueba.
3. Sigue el ciclo hasta `implementar` sobre tu CRM sandbox.
4. Verifica en el sandbox que los campos aparecen correctamente.

---

## Mapeo userConfig → ficheros materializados (AW-196)

Los valores de `userConfig` solo llegan a procesos de **hook** como `CLAUDE_PLUGIN_OPTION_*`
(no a los scripts que una skill ejecuta por Bash). Por eso el hook SessionStart los
**materializa** en `data_dir()` (`~/.local/share/consultoria-sagitaz/`, override
`CONSULTORIA_SAGITAZ_DATA`), con permisos `0600`, y los scripts los leen de ahí:

| `userConfig` | Fichero en `data_dir()` | Clave | Usado en |
|-------------|------------------------|-------|---------:|
| `transcripciones_endpoint` | `transcripciones.json` | `endpoint` | `skills/ders/scripts/fetch_transcripciones.py` |
| `transcripciones_team_token` | `transcripciones.json` | `token` | `skills/ders/scripts/fetch_transcripciones.py` |
| `crm_client_id` | `crm_connected_app.json` | `client_id` | `scripts/authorize_crm.py` |
| `crm_client_secret` | `crm_connected_app.json` | `client_secret` | `scripts/authorize_crm.py` |
| `python_bin` | _(no se materializa)_ | — | hook SessionStart (autodescubre el intérprete) |

> Precedencia en los consumidores: argumentos CLI > variables de entorno
> (`TRANSCRIPCIONES_ENDPOINT`/`TEAM_API_TOKEN`, `ZCRM_APP_*`) > fichero materializado.

---

## Dependencias del plugin

| Paquete | Versión | Naturaleza | Para qué |
|---------|---------|-----------|---------|
| `openpyxl` | 3.1.5 | Puro Python, cross-platform | Generar/leer la plantilla CRM (xlsx) |
| `et-xmlfile` | 2.0.0 | Puro Python, cross-platform | Dependencia de openpyxl |
| `Pillow` | >=10,<12 | Binario por-plataforma (opcional) | Conservar el logo del xlsx; sin él el xls se genera igual |

> `imageio-ffmpeg` (transcripción de audio) **no está** en este plugin: pertenece al worker
> de Zoho Catalyst en el servidor. El plugin no transcribe; recibe el texto ya procesado.

---

## Para el primary owner — Publicación y distribución

### Estructura del marketplace

El `marketplace.json` y el plugin se distribuyen desde el repositorio público de GitHub.
El `marketplace.json` vive en la raíz del repo (`.claude-plugin/marketplace.json`):

```json
{
  "plugins": [{
    "name": "consultoria-sagitaz",
    "source": {
      "type": "git",
      "url": "https://github.com/almawolflab/consultoria-sagitaz-plugin.git"
    },
    "autoUpdate": false
  }]
}
```

> **Añadir el marketplace:** en **Customize → Plugins → + Add → Add marketplace**, con el repo
> `almawolflab/consultoria-sagitaz-plugin` (o su URL git). El conector de GitHub de la app
> no admite el GitLab self-hosted; por eso la distribución va por este GitHub público.

### Managed settings (admin console de claude.ai, rol Owner)

Publicar en la consola de administración del Team:

```json
{
  "extraKnownMarketplaces": {
    "sagitaz-aiops": {
      "source": {
        "type": "git",
        "url": "https://github.com/almawolflab/consultoria-sagitaz-plugin.git"
      }
    }
  },
  "enabledPlugins": {
    "consultoria-sagitaz@sagitaz-aiops": true
  }
}
```

Con esto, todos los consultores del Team verán el plugin en `/plugin` y podrán instalarlo.

### Versionado y actualizaciones

1. Editar `version` en `.claude-plugin/plugin.json` (p.ej. `"0.1.0"` → `"0.2.0"`).
2. Commitear y hacer push al repositorio del marketplace.
3. Los consultores reciben la actualización en el próximo `/plugin update`
   (o automáticamente si `autoUpdate: true` en el marketplace).

### Secretos — qué va y qué no va en el plugin

| Qué | Dónde vive | En el repo |
|-----|-----------|-----------|
| `transcripciones_team_token` | Almacén seguro de Claude Code (userConfig sensitive) | **NO** |
| `zoho_crm_oauth.json` del consultor | Local del consultor (gitignored) | **NO** |
| `~/.local/share/consultoria-sagitaz/venv` | Local del consultor (dir fijo, fuera del plugin) | **NO** |
| `plugin.json`, skills, scripts | Repo del plugin | Sí (sin secretos) |
