"""Cliente REST v8 de Zoho CRM (stdlib urllib, sin dependencias externas).

Canjea el refresh token por un access token (válido ~1 h) y llama a la API con
`Authorization: Zoho-oauthtoken <at>`. Mejora clave: **refresh-on-401 con 1 reintento** (recomendado en el
spike §9.4), para no fallar cuando el access token caduca a mitad de una tanda.

Credenciales desde `zoho_crm_oauth.json` (creado por `scripts/gen_crm_refresh_token.py`), con override por
env `ZCRM_*`. **Siempre** se usa el `api_domain` del fichero (el sandbox `sandbox.zohoapis.com`); usar
`www.zohoapis.com` está prohibido (regla de seguridad del spike §10.4) y se rechaza explícitamente.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CREDS = os.path.join(HERE, "zoho_crm_oauth.json")


_ENV = (("client_id", "ZCRM_CLIENT_ID"), ("client_secret", "ZCRM_CLIENT_SECRET"),
        ("refresh_token", "ZCRM_REFRESH_TOKEN"), ("api_domain", "ZCRM_API_DOMAIN"),
        ("accounts_domain", "ZCRM_ACCOUNTS_DOMAIN"))


def load_creds(path=DEFAULT_CREDS):
    """Carga las credenciales de CRM.

    Prioridad: **env vars `ZCRM_*`** (worker de Catalyst, sin fichero) → luego el JSON local
    `zoho_crm_oauth.json` si existe. `accounts_domain` cae a accounts.zoho.com por defecto.
    """
    c = {}
    if os.path.exists(path):
        with open(path) as f:
            c = json.load(f)
    for key, env in _ENV:            # env pisa el fichero (worker)
        v = os.environ.get(env)
        if v:
            c[key] = v
    c.setdefault("accounts_domain", "https://accounts.zoho.com")
    for req in ("client_id", "client_secret", "refresh_token", "api_domain"):
        if not c.get(req):
            raise RuntimeError(f"Faltan credenciales CRM: {req} (env ZCRM_* o zoho_crm_oauth.json)")
    return c


class CrmClient:
    """Cliente ligero para `{api_domain}/crm/v8{path}` con refresh-on-401."""

    def __init__(self, creds=None, creds_path=DEFAULT_CREDS, timeout=60):
        self.c = creds or load_creds(creds_path)
        self.api = self.c["api_domain"].rstrip("/")
        self.accounts = self.c["accounts_domain"].rstrip("/")
        self.timeout = timeout
        self._at = None
        if "www.zohoapis.com" in self.api:
            raise RuntimeError(
                "api_domain apunta a producción (www.zohoapis.com); usa el sandbox "
                "(sandbox.zohoapis.com). Prohibido por seguridad (spike §10.4).")

    # --- OAuth ---
    def _refresh(self):
        data = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "client_id": self.c["client_id"],
            "client_secret": self.c["client_secret"],
            "refresh_token": self.c["refresh_token"],
        }).encode()
        req = urllib.request.Request(
            f"{self.accounts}/oauth/v2/token", data=data, method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            tok = json.loads(r.read())
        if "access_token" not in tok:
            raise RuntimeError(f"No se obtuvo access_token: {json.dumps(tok)[:300]}")
        self._at = tok["access_token"]
        return self._at

    def _token(self):
        return self._at or self._refresh()

    # --- HTTP ---
    def request(self, method, path, params=None, body=None):
        """Llama a `/crm/v8{path}`. Devuelve dict (JSON) o {} si la respuesta viene vacía.

        En un 401 (INVALID_TOKEN) refresca el access token y reintenta **una** vez.
        """
        url = f"{self.api}/crm/v8{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        data = json.dumps(body).encode() if body is not None else None
        for attempt in (1, 2):
            headers = {"Authorization": f"Zoho-oauthtoken {self._token()}"}
            if data is not None:
                headers["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=data, headers=headers, method=method)
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    raw = r.read()
                    return json.loads(raw) if raw else {}
            except urllib.error.HTTPError as e:
                raw = e.read().decode("utf-8", "ignore")
                if e.code == 401 and attempt == 1:
                    self._refresh()  # token caducado → refresca y reintenta una vez
                    continue
                raise RuntimeError(f"CRM HTTP {e.code} {method} {path}: {raw[:600]}") from None

    def get(self, path, params=None):
        return self.request("GET", path, params=params)

    def post(self, path, body, params=None):
        return self.request("POST", path, params=params, body=body)

    def put(self, path, body, params=None):
        return self.request("PUT", path, params=params, body=body)
