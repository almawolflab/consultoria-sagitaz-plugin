#!/usr/bin/env python3
"""OAuth Authorization Code flow with loopback redirect for Zoho CRM (per-consultant).

Each consultant runs this script once to authorize their own Zoho account and obtain
a refresh token compatible with crm.py / applicator.py (same zoho_crm_oauth.json format).

Usage:
    python plugin-claude/scripts/authorize_crm.py
    # Reads client_id/secret from crm_connected_app.json (not committed) or
    # ZCRM_APP_CLIENT_ID / ZCRM_APP_CLIENT_SECRET env vars.

Implements RFC 8252 (OAuth for native/CLI apps) with loopback redirect.
Only stdlib: http.server, urllib, webbrowser, secrets, json, os, sys.

SECURITY INVARIANTS:
- Never prints client_secret, refresh_token, or access_token.
- Writes zoho_crm_oauth.json with permissions 0600.
- Aborts with sys.exit(1) if org type != 'sandbox' or domain is www.zohoapis.com.
"""
import http.server
import json
import os
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SCRIPTS = Path(__file__).resolve().parent  # scripts/ directory
import sys as _sys
if str(_SCRIPTS) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS))

from parametrizacion.crm import resolve_oauth_path as _resolve_oauth_path


def resolve_app_creds_path() -> str:
    """Ruta al fichero crm_connected_app.json.

    Prioridad: $CLAUDE_PLUGIN_DATA si el fichero existe ahí; si no, scripts/.
    """
    import os
    data = os.environ.get("CLAUDE_PLUGIN_DATA", "").strip()
    if data:
        plugin_data_path = str(Path(data) / "crm_connected_app.json")
        if Path(plugin_data_path).exists():
            return plugin_data_path
    return str(_SCRIPTS / "crm_connected_app.json")


DEFAULT_OUT = _resolve_oauth_path(for_write=True)
DEFAULT_APP_CREDS = resolve_app_creds_path()

# Scopes required by the applicator (AW-187 / applicator.py / apply.py)
SCOPES = ",".join([
    "ZohoCRM.modules.ALL",
    "ZohoCRM.settings.ALL",
    "ZohoCRM.org.READ",
])


# ---------------------------------------------------------------------------
# Credentials loader
# ---------------------------------------------------------------------------

def load_app_creds(app_creds_path: str = DEFAULT_APP_CREDS):
    """Load client_id/secret from crm_connected_app.json or env vars.

    Priority: env vars ZCRM_APP_CLIENT_ID / ZCRM_APP_CLIENT_SECRET override the file.
    The file is never committed (gitignored). The env path is for CI/testing.
    """
    client_id = os.environ.get("ZCRM_APP_CLIENT_ID")
    client_secret = os.environ.get("ZCRM_APP_CLIENT_SECRET")

    if not (client_id and client_secret):
        if not os.path.exists(app_creds_path):
            print(
                f"ERROR: {app_creds_path} not found and ZCRM_APP_CLIENT_ID/SECRET not set.",
                file=sys.stderr,
            )
            print(
                "Create crm_connected_app.json with {\"client_id\": ..., \"client_secret\": ...}",
                file=sys.stderr,
            )
            sys.exit(1)
        with open(app_creds_path) as f:
            data = json.load(f)
        client_id = client_id or data["client_id"]
        client_secret = client_secret or data["client_secret"]

    if not client_id or not client_secret:
        print("ERROR: client_id or client_secret is empty.", file=sys.stderr)
        sys.exit(1)

    return client_id, client_secret


# ---------------------------------------------------------------------------
# OAuth: exchange authorization code for tokens
# ---------------------------------------------------------------------------

def exchange_code(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    accounts_url: str = "https://accounts.zoho.eu",
) -> dict:
    """Exchange an authorization code for a token dict.

    Returns a dict with all keys required by crm.load_creds:
        client_id, client_secret, refresh_token, api_domain,
        accounts_domain, org_id (None until verify_org), scopes.

    Raises RuntimeError if Zoho does not return a refresh_token.
    """
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }).encode()
    req = urllib.request.Request(
        f"{accounts_url}/oauth/v2/token",
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        tok = json.loads(r.read())

    if "refresh_token" not in tok:
        # Never print access_token; only print safe fields for diagnosis
        safe = {k: tok[k] for k in tok if k not in ("access_token", "refresh_token")}
        print("ERROR: Zoho did not return a refresh_token.", file=sys.stderr)
        print(f"Response (safe fields): {json.dumps(safe)}", file=sys.stderr)
        print(
            "Typical causes: code expired (>10 min), already used, wrong scopes/DC, "
            "or app not configured with access_type=offline.",
            file=sys.stderr,
        )
        raise RuntimeError("No refresh_token in token response")

    # Use api_domain from the response (correct DC for the user)
    api_domain = tok.get("api_domain", "https://sandbox.zohoapis.eu")
    # accounts-server from response supersedes the default
    accounts_domain = tok.get("accounts-server", accounts_url)

    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": tok["refresh_token"],
        "api_domain": api_domain,
        "accounts_domain": accounts_domain,
        "org_id": None,   # filled in after verify_org
        "scopes": tok.get("scope", SCOPES),
        # Store access_token only in memory for the org check; never persisted
        "_access_token": tok.get("access_token"),
    }


# ---------------------------------------------------------------------------
# Sandbox guard
# ---------------------------------------------------------------------------

def assert_sandbox(org_info: dict, api_domain: str) -> None:
    """Hard guard: exit(1) if org is not sandbox or domain is production.

    Hardens what gen_crm_refresh_token.py:99-105 only warns about.
    """
    if "www.zohoapis.com" in api_domain:
        print(
            f"ERROR: api_domain '{api_domain}' points to production (www.zohoapis.com). "
            "This script only works with sandbox orgs.",
            file=sys.stderr,
        )
        sys.exit(1)

    zoho_type = org_info.get("type", "")
    if zoho_type != "sandbox":
        zgid = org_info.get("zgid", "unknown")
        print(
            f"ERROR: Org type is '{zoho_type}' (zgid={zgid}), not 'sandbox'. "
            "This script only writes credentials for sandbox orgs. "
            "If you only have a production org, this is by design (see docs/setup_crm_consultor.md).",
            file=sys.stderr,
        )
        sys.exit(1)


def verify_org(api_domain: str, access_token: str) -> dict:
    """Call GET /crm/v8/org and return org_info dict.

    Exits with code 1 if org is not a sandbox or domain is production.
    Returns the org info dict on success.
    """
    # Domain check: reject www.zohoapis.com before even making the request
    if "www.zohoapis.com" in api_domain:
        print(
            f"ERROR: api_domain '{api_domain}' points to production (www.zohoapis.com). "
            "This script only works with sandbox orgs.",
            file=sys.stderr,
        )
        sys.exit(1)

    url = f"{api_domain.rstrip('/')}/crm/v8/org"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Zoho-oauthtoken {access_token}"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        data = json.loads(r.read())

    org_list = data.get("org") or [{}]
    org_info = org_list[0]

    assert_sandbox(org_info, api_domain)
    return org_info


# ---------------------------------------------------------------------------
# Credentials writer
# ---------------------------------------------------------------------------

def write_creds(creds: dict, out_path: str) -> None:
    """Atomically write zoho_crm_oauth.json with 0600 permissions.

    Never writes the in-memory _access_token key.
    Creates parent directories if they don't exist.
    """
    safe = {k: v for k, v in creds.items() if not k.startswith("_")}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    tmp = out_path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(safe, f, indent=2)
    os.chmod(tmp, 0o600)
    os.replace(tmp, out_path)
    os.chmod(out_path, 0o600)


# ---------------------------------------------------------------------------
# run_authorization_flow — core (no browser/server: takes pre-captured code)
# ---------------------------------------------------------------------------

def run_authorization_flow(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    accounts_url: str = "https://accounts.zoho.eu",
    out_path: str = DEFAULT_OUT,
) -> None:
    """Exchange code, verify sandbox, write credentials.

    This function is the testable core; it does NOT open a browser or loopback server
    (those are in main() / start_loopback_server_and_wait()).
    Exits with code 1 if org is not sandbox. Does not write the file in that case.
    """
    creds = exchange_code(
        code=code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        accounts_url=accounts_url,
    )

    access_token = creds.pop("_access_token", None)
    if not access_token:
        print("ERROR: no access_token in token response.", file=sys.stderr)
        sys.exit(1)

    # Verify sandbox — exits(1) if not sandbox
    org_info = verify_org(api_domain=creds["api_domain"], access_token=access_token)
    creds["org_id"] = org_info.get("zgid")

    write_creds(creds, out_path)

    # Safe output: only non-secret fields
    zgid = org_info.get("zgid", "unknown")
    zoho_type = org_info.get("type", "unknown")
    print(f"OK — credentials written to {os.path.relpath(out_path)}")
    print(f"Scopes granted: {creds.get('scopes', '(none)')}")
    print(f"Org verified: zgid={zgid} type={zoho_type} api_domain={creds['api_domain']}")


# ---------------------------------------------------------------------------
# Loopback HTTP server
# ---------------------------------------------------------------------------

def _find_free_port() -> int:
    """Find a free ephemeral TCP port on 127.0.0.1."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Minimal HTTP handler that captures the OAuth callback code."""

    captured_code = None
    captured_error = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "error" in params:
            type(self).captured_error = params["error"][0]
            body = b"<html><body>Authorization failed. You can close this tab.</body></html>"
        elif "code" in params:
            type(self).captured_code = params["code"][0]
            body = b"<html><body>Authorization successful. You can close this tab.</body></html>"
        else:
            body = b"<html><body>Unexpected request. You can close this tab.</body></html>"

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # Suppress default access log


def start_loopback_server_and_wait(
    port: int = 0,
    timeout: int = 120,
    inject_request_after_start: tuple = None,
) -> str:
    """Start loopback HTTP server on an ephemeral port and wait for the OAuth callback.

    Returns the captured authorization code.
    Exits with code 1 if the callback contains an error or times out.

    Args:
        port: port to listen on (0 = auto-select ephemeral port).
        timeout: seconds to wait for the browser callback.
        inject_request_after_start: for testing only — (method, path) tuple to
            simulate an HTTP request after the server starts. e.g.:
            ("GET", "/callback?code=ABC123")
    """
    # Reset class-level state
    _CallbackHandler.captured_code = None
    _CallbackHandler.captured_error = None

    if port == 0:
        port = _find_free_port()

    server = http.server.HTTPServer(("127.0.0.1", port), _CallbackHandler)
    server.timeout = timeout

    if inject_request_after_start is not None:
        # Test-only path: fire a synthetic request after server starts in a thread
        method, path = inject_request_after_start

        def _inject():
            import time
            time.sleep(0.05)  # Let the server accept before we hit it
            conn_url = f"http://127.0.0.1:{port}{path}"
            try:
                urllib.request.urlopen(conn_url, timeout=5)
            except Exception:
                pass  # response body doesn't matter to the injector

        t = threading.Thread(target=_inject, daemon=True)
        t.start()

    # Handle exactly one request (the callback)
    server.handle_request()
    server.server_close()

    if _CallbackHandler.captured_error:
        print(
            f"ERROR: Authorization cancelled or failed: {_CallbackHandler.captured_error}",
            file=sys.stderr,
        )
        sys.exit(1)

    if not _CallbackHandler.captured_code:
        print("ERROR: No authorization code received (timeout?).", file=sys.stderr)
        sys.exit(1)

    return _CallbackHandler.captured_code


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse

    ap = argparse.ArgumentParser(
        description="Authorize your Zoho CRM account (Authorization Code + loopback redirect)."
    )
    ap.add_argument(
        "--app-creds",
        default=DEFAULT_APP_CREDS,
        help="Path to crm_connected_app.json (default: repo root). "
             "Or set ZCRM_APP_CLIENT_ID / ZCRM_APP_CLIENT_SECRET.",
    )
    ap.add_argument(
        "--accounts",
        default="https://accounts.zoho.eu",
        help="Zoho accounts server (default: .eu DC).",
    )
    ap.add_argument(
        "--port",
        type=int,
        default=0,
        help="Loopback port for OAuth callback (0 = auto-select ephemeral port).",
    )
    ap.add_argument(
        "--out",
        default=DEFAULT_OUT,
        help="Output path for zoho_crm_oauth.json.",
    )
    ap.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Seconds to wait for the browser callback.",
    )
    args = ap.parse_args()

    client_id, client_secret = load_app_creds(args.app_creds)

    port = args.port or _find_free_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"

    # Build authorization URL
    auth_params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "scope": SCOPES,
        "redirect_uri": redirect_uri,
        "access_type": "offline",
        "prompt": "consent",
    })
    auth_url = f"{args.accounts}/oauth/v2/auth?{auth_params}"

    print(f"Opening browser for Zoho authorization...")
    print(f"If the browser does not open, visit this URL manually:")
    print(f"  {auth_url}")
    print(f"Waiting for callback on {redirect_uri} (timeout: {args.timeout}s)...")

    webbrowser.open(auth_url)

    code = start_loopback_server_and_wait(port=port, timeout=args.timeout)

    run_authorization_flow(
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
        accounts_url=args.accounts,
        out_path=args.out,
    )


if __name__ == "__main__":
    main()
