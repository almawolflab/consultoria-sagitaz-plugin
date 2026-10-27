# Setup CRM por consultor — OAuth Authorization Code

> **Alcance:** Este flujo opera **exclusivamente en el sandbox de Zoho CRM**.
> Cualquier intento de autorizar una org de producción es bloqueado con error.
> Ver docs/32 §9.

---

## Para el owner: registrar la connected app (una vez)

Sigue estos pasos una sola vez. Después distribuye `client_id` y `client_secret` a
cada consultor por un canal fuera de banda (no por email sin cifrar, no por Git).

### 1. Crear la connected app en `api-console.zoho.com`

1. Ve a [https://api-console.zoho.com](https://api-console.zoho.com) y selecciona tu
   organización sandbox.
2. Pulsa **"Add Client"** → tipo **"Server-based Applications"**.
3. Rellena los campos:
   - **Client Name:** `AIOps Plugin Claude` (o similar descriptivo)
   - **Homepage URL:** `http://localhost`
   - **Authorized Redirect URIs:** añade las siguientes líneas (una por línea):
     ```
     http://127.0.0.1/callback
     http://localhost/callback
     ```
     Zoho acepta estas URIs con cualquier puerto efímero; el script elige el puerto
     automáticamente (RFC 8252). Si Zoho exige puerto fijo, usa `http://127.0.0.1:8080/callback`
     y lanza el script con `--port 8080`.
4. Pulsa **"Create"**. Zoho muestra `Client ID` y `Client Secret`.

### 2. Scopes que debe conceder la app

El script solicita automáticamente los scopes:

```
ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.org.READ
```

Asegúrate de que la app tiene permiso para esos scopes en tu organización sandbox.

### 3. Distribuir las credenciales a cada consultor

Crea un fichero `crm_connected_app.json` con el contenido siguiente y compártelo con
cada consultor por un canal seguro (p. ej. mensaje directo cifrado, gestor de contraseñas
compartido, o entrega en persona):

```json
{
  "client_id": "1000.XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
  "client_secret": "YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY"
}
```

**Nunca lo compartas por correo sin cifrar ni lo subas a ningún repositorio.**

---

## Para el consultor: autorizar tu cuenta Zoho (una vez por máquina)

### Prerequisitos

- Tener acceso a la organización sandbox "Prueba Salto" de Zoho CRM con **tu propia cuenta**.
- Haber recibido `crm_connected_app.json` del owner y colocarlo en la **raíz del repositorio**:
  ```
  transcriber/crm_connected_app.json   ← este fichero, nunca commiteado
  ```
  Alternativamente, exporta las variables de entorno:
  ```bash
  export ZCRM_APP_CLIENT_ID="1000.xxx"
  export ZCRM_APP_CLIENT_SECRET="yyy"
  ```

### Pasos de autorización

1. Desde la raíz del repositorio, ejecuta:

   ```bash
   python plugin-claude/scripts/authorize_crm.py
   ```

   Opciones útiles:
   ```
   --accounts https://accounts.zoho.eu   # DC europeo (por defecto)
   --port 8080                           # puerto fijo si Zoho rechaza el efímero
   --out /ruta/personalizada/token.json  # ruta de salida alternativa
   ```

2. El script abrirá tu navegador con la **pantalla de consentimiento de Zoho**.
   Si el navegador no abre, copia la URL que imprime el script y pégala manualmente.

3. En el navegador:
   - Inicia sesión con **tu propia cuenta Zoho** (no la del owner).
   - Acepta los permisos solicitados.
   - La página del navegador mostrará "Authorization successful. You can close this tab."

4. El script imprimirá algo como:
   ```
   OK — credentials written to zoho_crm_oauth.json
   Scopes granted: ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.org.READ
   Org verified: zgid=693026068 type=sandbox api_domain=https://sandbox.zohoapis.eu
   ```

5. El fichero `zoho_crm_oauth.json` (permisos `0600`) contiene tu refresh token y está
   listo para que `crm.py` / `applicator.py` lo consuman.

### Dónde cae el token

| Fichero | Ubicación | ¿Commiteado? |
|---------|-----------|--------------|
| `zoho_crm_oauth.json` | raíz del repo (o `--out`) | **NO** — está en `.gitignore` |
| `crm_connected_app.json` | raíz del repo | **NO** — está en `.gitignore` |

> **NUNCA hagas `git add zoho_crm_oauth.json` ni `git add crm_connected_app.json`.**
> Si accidentalmente lo commiteas, **revoca el token en Zoho inmediatamente** (ver sección
> "Revocar / re-autorizar" más abajo) y rota el `client_secret` con el owner.

### Verificar que funciona

```bash
python3 -m pipeline.parametrizacion.apply --ir pipeline/tests/fixtures/ir_jaque_r1r3.json --dry-run
```

Si no hay errores de credenciales, el token está correctamente configurado.

---

## Revocar / re-autorizar

### Revocar el token de un consultor

En [https://api-console.zoho.com](https://api-console.zoho.com) → selecciona la connected
app → "Authorized Apps" (o desde la cuenta del consultor en Zoho: Perfil → Connected
Apps → revocar `AIOps Plugin Claude`).

Tras revocar, el `zoho_crm_oauth.json` local deja de funcionar. Bórralo y ejecuta de
nuevo el flujo de autorización.

### Re-autorizar (token caducado o revocado)

```bash
rm zoho_crm_oauth.json   # elimina el token antiguo
python plugin-claude/scripts/authorize_crm.py
```

El script pide `prompt=consent` siempre, de modo que el nuevo refresh token sustituye
al anterior aunque la app ya estuviera previamente autorizada.

### Rotar el `client_secret` de la app

Si el `client_secret` se ve comprometido:
1. El owner lo rota en `api-console.zoho.com` → selecciona la app → "Regenerate Secret".
2. El owner distribuye el nuevo secret a todos los consultores.
3. Cada consultor actualiza su `crm_connected_app.json` y re-ejecuta el flujo.

---

## Errores frecuentes

| Mensaje | Causa | Solución |
|---------|-------|----------|
| `crm_connected_app.json not found` | El fichero no está en la raíz | Colócalo en la raíz del repo o exporta `ZCRM_APP_*` |
| `ERROR: Org type is 'production'` | Iniciaste sesión con una cuenta de producción | Usa tu cuenta del sandbox "Prueba Salto" |
| `ERROR: No authorization code received (timeout?)` | Cerraste el navegador o tardaste >120 s | Vuelve a ejecutar y completa el flujo rápidamente |
| `error=access_denied` | Cancelaste el consentimiento | Ejecuta de nuevo y acepta los permisos |
| `Faltan credenciales CRM: refresh_token` | Token corrompido o vacío | Borra `zoho_crm_oauth.json` y re-autoriza |

---

## Referencia de scopes

| Scope | Para qué |
|-------|----------|
| `ZohoCRM.modules.ALL` | Leer/escribir campos en módulos del CRM (AW-187 applicator) |
| `ZohoCRM.settings.ALL` | Leer configuración de módulos, layouts, campos |
| `ZohoCRM.org.READ` | Verificar binding de la org (tipo sandbox, zgid) |
