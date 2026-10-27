# Plugin Consultoría Sagitaz — Guía de Setup y Distribución

Plugin de Claude Teams que expone el pipeline completo de consultoría de Sagitaz como skills:
DERS → DERCAS → IR → Matriz CRM → Plan → Implementación (solo sandbox Zoho CRM).

---

## Para el consultor — Setup inicial

### 1. Requisitos previos

| Requisito | Versión mínima | Instalación |
|-----------|---------------|-------------|
| Python | 3.11+ | macOS: `brew install python@3.11` o [python.org](https://www.python.org/downloads/); Windows: instalador oficial con **"Add to PATH"** |
| Claude Code / Claude Teams | última | Incluido en la sesión de Teams |

> **Windows:** usa `py -3` como intérprete. Al configurar `userConfig.python_bin`, introduce `py -3`.

### 2. Instalar el plugin desde el marketplace del owner

1. Abre Claude Code y escribe `/plugin`.
2. En la pestaña del marketplace, busca **consultoria-sagitaz**.
3. Pulsa **Instalar**. Claude Code pedirá los valores de `userConfig`:

   | Campo | Qué introducir |
   |-------|---------------|
   | `transcripciones_endpoint` | URL base del endpoint `/transcripciones` (la da el owner) |
   | `transcripciones_team_token` | Token de equipo (lo reparte el owner; se guarda de forma segura) |
   | `python_bin` | `python3` en macOS · `py -3` en Windows |

   > El `transcripciones_team_token` se almacena en el almacén seguro de la plataforma,
   > **nunca** en `settings.json` ni en el repo.

### 3. Bootstrap del runtime Python

La primera vez que uses una skill que ejecuta scripts, se lanza `bootstrap.py` automáticamente.
También puedes ejecutarlo a mano desde la raíz del plugin:

```bash
python3 scripts/bootstrap.py
```

Esto crea un venv en `$CLAUDE_PLUGIN_DATA/venv` e instala las dependencias del plugin
(`openpyxl`, `et-xmlfile`). Es **idempotente**: re-ejecutar no reinstala si ya está OK.

Para recrear el venv desde cero:

```bash
python3 scripts/bootstrap.py --force
```

### 4. Verificar el entorno con doctor.py

```bash
python3 scripts/doctor.py
```

Checks que realiza:

| Check | Descripción | Obligatorio |
|-------|-------------|-------------|
| [A] Python >= 3.11 | Versión del intérprete en el venv | Sí |
| [B] openpyxl importa | Dependencia de la matriz CRM | Sí |
| [C] Sin imageio-ffmpeg | No debe estar en el venv del plugin | Sí |
| [D] Fichero OAuth existe | `zoho_crm_oauth.json` del consultor | Sí |
| [E] api_domain no productivo | `sandbox.zohoapis.com`, nunca `www.zohoapis.com` | Sí |
| [F] Endpoint alcanzable | `TRANSCRIPCIONES_ENDPOINT` responde | Aviso |

Devuelve **exit 0** solo si todos los checks obligatorios pasan.

### 5. Autorización Zoho (una vez por consultor)

Lanza el flujo OAuth de la connected app (AW-186) para generar tu fichero de credenciales local:

```bash
python3 scripts/authorize_crm.py
```

Esto abre el navegador con el consentimiento OAuth de tu cuenta Zoho y guarda el fichero
`zoho_crm_oauth.json` (gitignored) con tu `refresh_token` y el `api_domain` del sandbox.

> **Importante:** el fichero siempre apunta al **sandbox** (`sandbox.zohoapis.com`).
> El plugin bloquea cualquier operación contra producción (`www.zohoapis.com`) a nivel de código
> (`scripts/parametrizacion/crm.py:56-59`).

### 6. Prueba E2E con cliente Tufisio

Para confirmar que todo funciona de extremo a extremo:

1. Abre una sesión de Claude Teams con el plugin activo.
2. Invoca `/ders` con una transcripción de Tufisio.
3. Sigue el ciclo hasta `/implementar` sobre tu CRM sandbox.
4. Verifica en el sandbox que los campos aparecen correctamente.

---

## Mapeo userConfig → variables de entorno

Las skills del plugin pasan los valores de `userConfig` a los scripts como variables de entorno:

| `userConfig` | Variable de entorno | Usado en |
|-------------|--------------------|---------:|
| `transcripciones_endpoint` | `TRANSCRIPCIONES_ENDPOINT` | `skills/ders/scripts/fetch_transcripciones.py` |
| `transcripciones_team_token` | `TEAM_API_TOKEN` | `skills/ders/scripts/fetch_transcripciones.py` |
| `python_bin` | _(se usa para invocar el intérprete del venv)_ | hooks de skills |

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

El owner mantiene un repositorio en el GitLab self-hosted con el catálogo del marketplace.
Ver el fichero de ejemplo en `.claude-plugin/marketplace.json.example`:

```json
{
  "plugins": [{
    "name": "consultoria-sagitaz",
    "source": {
      "type": "git",
      "url": "https://gitlab.192.168.0.29.nip.io/aiops/<repo-marketplace>.git",
      "directory": "plugin-claude"
    },
    "autoUpdate": false
  }]
}
```

> **Fuente `git` (no `github`):** el host es GitLab self-hosted. Cada consultor necesita
> acceso de lectura al repositorio.

> **Certificado autofirmado:** si Claude Code no puede clonar por el cert autofirmado del
> GitLab, la alternativa es usar `CLAUDE_CODE_PLUGIN_SEED_DIR` con una copia local
> pre-clonada del plugin, o alojar un `marketplace.json` en una URL HTTPS pública/interna.

### Managed settings (admin console de claude.ai, rol Owner)

Publicar en la consola de administración del Team:

```json
{
  "extraKnownMarketplaces": {
    "sagitaz-aiops": {
      "source": {
        "type": "git",
        "url": "https://gitlab.192.168.0.29.nip.io/aiops/<repo-marketplace>.git"
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
| `CLAUDE_PLUGIN_DATA/venv` | Local del consultor (fuera del plugin) | **NO** |
| `plugin.json`, skills, scripts | Repo del plugin | Sí (sin secretos) |
