"""AW-191 Fase 1 — Guarda sandbox-only robusta (allowlist) — TDD RED primero.

AC-1: CrmClient rechaza cualquier www.zohoapis.<dc> y acepta sandbox.zohoapis.<dc>.
AC-2: authorize_crm.py (verify_org / assert_sandbox) rechaza www.zohoapis.<dc>;
      guarda org-type intacta.
"""
import sys
import pytest
from pathlib import Path

# conftest.py ya añade scripts/ al sys.path
from parametrizacion import crm as crm_mod
from parametrizacion.crm import CrmClient
import authorize_crm as auth_mod


# ---------------------------------------------------------------------------
# AC-1 — CrmClient: allowlist (sandbox.zohoapis. en vez de denylist www.zohoapis.com)
# ---------------------------------------------------------------------------

SANDBOX_BASE = {
    "accounts_domain": "https://accounts.zoho.eu",
    "client_id": "x", "client_secret": "x", "refresh_token": "x",
}


class TestCrmClientAllowlist:
    """CrmClient debe rechazar cualquier DC productivo y aceptar cualquier DC sandbox."""

    @pytest.mark.parametrize("domain", [
        "https://www.zohoapis.com",
        "https://www.zohoapis.eu",
        "https://www.zohoapis.in",
        "https://www.zohoapis.com.au",
    ])
    def test_rechaza_produccion_todos_los_dc(self, domain):
        """Cualquier www.zohoapis.<dc> → RuntimeError."""
        bad = dict(SANDBOX_BASE, api_domain=domain)
        with pytest.raises(RuntimeError):
            CrmClient(creds=bad)

    @pytest.mark.parametrize("domain", [
        "https://sandbox.zohoapis.com",
        "https://sandbox.zohoapis.eu",
        "https://sandbox.zohoapis.in",
        "https://sandbox.zohoapis.com.au",
    ])
    def test_acepta_sandbox_todos_los_dc(self, domain):
        """Cualquier sandbox.zohoapis.<dc> → OK (sin RuntimeError)."""
        ok = dict(SANDBOX_BASE, api_domain=domain)
        client = CrmClient(creds=ok)
        assert client is not None

    def test_rechaza_dominio_arbitrario(self):
        """Un dominio que no sea sandbox.zohoapis. también debe rechazarse."""
        bad = dict(SANDBOX_BASE, api_domain="https://api.some-other-crm.com")
        with pytest.raises(RuntimeError):
            CrmClient(creds=bad)

    def test_mensaje_error_menciona_sandbox(self):
        """El mensaje de RuntimeError debe mencionar 'sandbox'."""
        bad = dict(SANDBOX_BASE, api_domain="https://www.zohoapis.eu")
        with pytest.raises(RuntimeError, match="sandbox"):
            CrmClient(creds=bad)


# ---------------------------------------------------------------------------
# AC-2 — authorize_crm.py: assert_sandbox y verify_org (allowlist)
# ---------------------------------------------------------------------------

class TestAuthorizeCrmAllowlist:
    """assert_sandbox y verify_org rechazan www.zohoapis.<dc> con sys.exit(1)."""

    @pytest.mark.parametrize("domain", [
        "https://www.zohoapis.com",
        "https://www.zohoapis.eu",
        "https://www.zohoapis.in",
        "https://www.zohoapis.com.au",
    ])
    def test_assert_sandbox_rechaza_produccion(self, domain):
        """assert_sandbox con org sandbox pero domain productivo → sys.exit(1)."""
        org_info = {"type": "sandbox", "zgid": "123"}
        with pytest.raises(SystemExit) as exc_info:
            auth_mod.assert_sandbox(org_info, domain)
        assert exc_info.value.code == 1

    @pytest.mark.parametrize("domain", [
        "https://sandbox.zohoapis.com",
        "https://sandbox.zohoapis.eu",
    ])
    def test_assert_sandbox_acepta_sandbox_dc(self, domain):
        """assert_sandbox con org sandbox y domain sandbox → sin exit."""
        org_info = {"type": "sandbox", "zgid": "123"}
        # No debe lanzar ni SystemExit ni RuntimeError
        auth_mod.assert_sandbox(org_info, domain)

    def test_assert_sandbox_rechaza_org_produccion(self):
        """assert_sandbox con org-type != 'sandbox' → sys.exit(1) (guarda intacta)."""
        org_info = {"type": "production", "zgid": "999"}
        domain = "https://sandbox.zohoapis.eu"
        with pytest.raises(SystemExit) as exc_info:
            auth_mod.assert_sandbox(org_info, domain)
        assert exc_info.value.code == 1

    @pytest.mark.parametrize("domain", [
        "https://www.zohoapis.com",
        "https://www.zohoapis.eu",
        "https://www.zohoapis.in",
        "https://www.zohoapis.com.au",
    ])
    def test_verify_org_rechaza_produccion_sin_request(self, domain):
        """verify_org debe rechazar dominios productivos ANTES de hacer la request HTTP."""
        with pytest.raises(SystemExit) as exc_info:
            auth_mod.verify_org(domain, "fake_access_token")
        assert exc_info.value.code == 1
