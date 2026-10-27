"""Tests for plugin-claude/scripts/authorize_crm.py — strict TDD, 100% offline.

All network calls (accounts.zoho.eu / zohoapis), browser, and loopback server
are mocked via monkeypatch or in-process loopback on ephemeral ports.
No real credentials: all values are synthetic dummies.
"""
import io
import json
import os
import sys
import threading
import urllib.request
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DUMMY_CLIENT_ID = "test-client-id-1000"
DUMMY_CLIENT_SECRET = "test-client-secret-xyz"
DUMMY_REFRESH_TOKEN = "1000.dummy-refresh.abc"
DUMMY_ACCESS_TOKEN = "1000.dummy-access.xyz"
DUMMY_ACCOUNTS = "https://accounts.zoho.eu"
DUMMY_API_DOMAIN = "https://sandbox.zohoapis.eu"
DUMMY_SCOPE = "ZohoCRM.modules.ALL,ZohoCRM.settings.ALL,ZohoCRM.org.READ"
DUMMY_ORG_ID = "999999999"

# Fake token response that Zoho returns from /oauth/v2/token
FAKE_TOKEN_RESPONSE = {
    "access_token": DUMMY_ACCESS_TOKEN,
    "refresh_token": DUMMY_REFRESH_TOKEN,
    "api_domain": DUMMY_API_DOMAIN,
    "accounts-server": DUMMY_ACCOUNTS,
    "token_type": "Bearer",
    "expires_in": 3600,
    "scope": DUMMY_SCOPE,
}

# Fake /crm/v8/org response for a sandbox org
FAKE_ORG_SANDBOX = {
    "org": [
        {
            "zgid": DUMMY_ORG_ID,
            "type": "sandbox",
            "company_name": "Test Sandbox Corp",
        }
    ]
}

# Fake /crm/v8/org response for a production org
FAKE_ORG_PRODUCTION = {
    "org": [
        {
            "zgid": "888888888",
            "type": "production",
            "company_name": "Real Prod Corp",
        }
    ]
}


def _make_urlopen_mock(token_resp=None, org_resp=None):
    """Returns a mock callable for urllib.request.urlopen that serves fake responses."""

    class FakeResponse:
        def __init__(self, data: bytes):
            self._data = data

        def read(self):
            return self._data

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

    def _urlopen(req, timeout=60):
        url = req.full_url if hasattr(req, "full_url") else req
        if "/oauth/v2/token" in url:
            return FakeResponse(json.dumps(token_resp or FAKE_TOKEN_RESPONSE).encode())
        if "/crm/v8/org" in url:
            return FakeResponse(json.dumps(org_resp or FAKE_ORG_SANDBOX).encode())
        raise AssertionError(f"Unexpected URL in test: {url}")

    return _urlopen


# ---------------------------------------------------------------------------
# Phase 1 — exchange_code: shape of the credentials dict
# ---------------------------------------------------------------------------


class TestExchangeCode:
    """Phase 1: exchange_code() returns a dict with exactly the keys crm.load_creds needs."""

    def test_build_creds_dict_shape(self, monkeypatch):
        """exchange_code() produces a dict with all keys required by crm.load_creds.

        Production change that would make this fail: removing or renaming any of
        the required keys in the returned dict.
        """
        import authorize_crm as ac

        monkeypatch.setattr("urllib.request.urlopen", _make_urlopen_mock())

        result = ac.exchange_code(
            code="1000.dummy-code.test",
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            redirect_uri=f"http://127.0.0.1:19999/callback",
            accounts_url=DUMMY_ACCOUNTS,
        )

        required_keys = {
            "client_id",
            "client_secret",
            "refresh_token",
            "api_domain",
            "accounts_domain",
            "org_id",
            "scopes",
        }
        assert required_keys.issubset(result.keys()), (
            f"Missing keys: {required_keys - result.keys()}"
        )
        assert result["client_id"] == DUMMY_CLIENT_ID
        assert result["client_secret"] == DUMMY_CLIENT_SECRET
        assert result["refresh_token"] == DUMMY_REFRESH_TOKEN
        assert result["api_domain"] == DUMMY_API_DOMAIN
        assert result["scopes"] == DUMMY_SCOPE

    def test_exchange_code_fails_without_refresh_token(self, monkeypatch):
        """exchange_code() raises RuntimeError when Zoho response lacks refresh_token.

        Production change that would make this fail: removing the check for
        'refresh_token' in the token response.
        """
        import authorize_crm as ac

        bad_response = {"access_token": DUMMY_ACCESS_TOKEN, "error": "some_error"}
        monkeypatch.setattr(
            "urllib.request.urlopen", _make_urlopen_mock(token_resp=bad_response)
        )

        with pytest.raises((RuntimeError, SystemExit)):
            ac.exchange_code(
                code="1000.bad-code",
                client_id=DUMMY_CLIENT_ID,
                client_secret=DUMMY_CLIENT_SECRET,
                redirect_uri="http://127.0.0.1:19999/callback",
                accounts_url=DUMMY_ACCOUNTS,
            )


# ---------------------------------------------------------------------------
# Phase 2 — Sandbox guard: hard exit on production org or www domain
# ---------------------------------------------------------------------------


class TestSandboxGuard:
    """Phase 2: assert_sandbox() blocks non-sandbox orgs and production domains."""

    def test_rejects_production_org(self, tmp_path, monkeypatch):
        """assert_sandbox raises SystemExit(1) when org type is 'production'.

        Production change that would make this fail: removing or weakening the
        type=='sandbox' check.
        """
        import authorize_crm as ac

        org_info = FAKE_ORG_PRODUCTION["org"][0]
        with pytest.raises(SystemExit) as exc:
            ac.assert_sandbox(org_info, api_domain=DUMMY_API_DOMAIN)
        assert exc.value.code != 0

    def test_rejects_www_domain(self, tmp_path, monkeypatch):
        """assert_sandbox raises SystemExit(1) when api_domain contains www.zohoapis.com.

        Production change that would make this fail: removing the www.zohoapis.com check.
        """
        import authorize_crm as ac

        org_info = FAKE_ORG_SANDBOX["org"][0]  # type is sandbox but domain is prod
        with pytest.raises(SystemExit) as exc:
            ac.assert_sandbox(org_info, api_domain="https://www.zohoapis.com")
        assert exc.value.code != 0

    def test_accepts_sandbox_org(self, monkeypatch):
        """assert_sandbox does NOT raise when type is 'sandbox' and domain is not prod.

        Production change that would make this fail: over-blocking valid sandbox orgs.
        """
        import authorize_crm as ac

        org_info = FAKE_ORG_SANDBOX["org"][0]
        # Should not raise
        ac.assert_sandbox(org_info, api_domain=DUMMY_API_DOMAIN)

    def test_verify_org_calls_crm_endpoint_and_rejects_production(self, monkeypatch):
        """verify_org() calls GET /crm/v8/org and exits if org type != sandbox.

        Production change that would make this fail: not calling /crm/v8/org or
        not exiting on production type.
        """
        import authorize_crm as ac

        monkeypatch.setattr(
            "urllib.request.urlopen",
            _make_urlopen_mock(org_resp=FAKE_ORG_PRODUCTION),
        )

        with pytest.raises(SystemExit) as exc:
            ac.verify_org(
                api_domain=DUMMY_API_DOMAIN,
                access_token=DUMMY_ACCESS_TOKEN,
            )
        assert exc.value.code != 0

    def test_verify_org_returns_org_info_for_sandbox(self, monkeypatch):
        """verify_org() returns org dict when org is sandbox.

        Production change that would make this fail: not returning org info on success.
        """
        import authorize_crm as ac

        monkeypatch.setattr(
            "urllib.request.urlopen",
            _make_urlopen_mock(org_resp=FAKE_ORG_SANDBOX),
        )

        result = ac.verify_org(
            api_domain=DUMMY_API_DOMAIN,
            access_token=DUMMY_ACCESS_TOKEN,
        )
        assert result["type"] == "sandbox"
        assert result["zgid"] == DUMMY_ORG_ID

    def test_full_flow_does_not_write_json_for_production_org(self, tmp_path, monkeypatch):
        """End-to-end: production org causes exit(1) and no zoho_crm_oauth.json is written.

        Production change that would make this fail: writing the file before or
        without checking org type.
        """
        import authorize_crm as ac

        out_path = tmp_path / "zoho_crm_oauth.json"
        monkeypatch.setattr(
            "urllib.request.urlopen",
            _make_urlopen_mock(
                token_resp=FAKE_TOKEN_RESPONSE, org_resp=FAKE_ORG_PRODUCTION
            ),
        )

        with pytest.raises(SystemExit) as exc:
            ac.run_authorization_flow(
                client_id=DUMMY_CLIENT_ID,
                client_secret=DUMMY_CLIENT_SECRET,
                code="1000.test-code",
                redirect_uri="http://127.0.0.1:19999/callback",
                accounts_url=DUMMY_ACCOUNTS,
                out_path=str(out_path),
            )
        assert exc.value.code != 0
        assert not out_path.exists(), "zoho_crm_oauth.json must NOT be created for production org"


# ---------------------------------------------------------------------------
# Phase 3 — Round-trip compatibility with crm.py
# ---------------------------------------------------------------------------


class TestCrmCompatibility:
    """Phase 3: zoho_crm_oauth.json produced by authorize_crm is loadable by crm.load_creds."""

    def test_token_loadable_by_crm(self, tmp_path, monkeypatch):
        """crm.load_creds(path) succeeds on the JSON written by run_authorization_flow.

        Production change that would make this fail: writing wrong key names or
        missing required keys.
        """
        import authorize_crm as ac

        out_path = tmp_path / "zoho_crm_oauth.json"
        monkeypatch.setattr(
            "urllib.request.urlopen",
            _make_urlopen_mock(
                token_resp=FAKE_TOKEN_RESPONSE, org_resp=FAKE_ORG_SANDBOX
            ),
        )

        ac.run_authorization_flow(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            code="1000.test-code",
            redirect_uri="http://127.0.0.1:19999/callback",
            accounts_url=DUMMY_ACCOUNTS,
            out_path=str(out_path),
        )

        assert out_path.exists()

        # Now load via crm.load_creds — must not raise
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
        from pipeline.parametrizacion import crm as crm_module

        creds = crm_module.load_creds(str(out_path))
        for key in ("client_id", "client_secret", "refresh_token", "api_domain"):
            assert creds.get(key), f"crm.load_creds missing required key: {key}"

    def test_crm_client_constructs_without_network(self, tmp_path, monkeypatch):
        """CrmClient(creds) constructs without error when creds have valid sandbox domain.

        Production change that would make this fail: writing www.zohoapis.com as api_domain.
        """
        import authorize_crm as ac

        out_path = tmp_path / "zoho_crm_oauth.json"
        monkeypatch.setattr(
            "urllib.request.urlopen",
            _make_urlopen_mock(
                token_resp=FAKE_TOKEN_RESPONSE, org_resp=FAKE_ORG_SANDBOX
            ),
        )

        ac.run_authorization_flow(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            code="1000.test-code",
            redirect_uri="http://127.0.0.1:19999/callback",
            accounts_url=DUMMY_ACCOUNTS,
            out_path=str(out_path),
        )

        from pipeline.parametrizacion import crm as crm_module

        creds = crm_module.load_creds(str(out_path))
        # Must not raise RuntimeError("www.zohoapis.com")
        client = crm_module.CrmClient(creds=creds)
        assert client is not None

    def test_output_file_has_0600_permissions(self, tmp_path, monkeypatch):
        """Written zoho_crm_oauth.json has permissions 0600 (owner-only read/write).

        Production change that would make this fail: not calling os.chmod(path, 0o600).
        """
        import authorize_crm as ac

        out_path = tmp_path / "zoho_crm_oauth.json"
        monkeypatch.setattr(
            "urllib.request.urlopen",
            _make_urlopen_mock(
                token_resp=FAKE_TOKEN_RESPONSE, org_resp=FAKE_ORG_SANDBOX
            ),
        )

        ac.run_authorization_flow(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            code="1000.test-code",
            redirect_uri="http://127.0.0.1:19999/callback",
            accounts_url=DUMMY_ACCOUNTS,
            out_path=str(out_path),
        )

        stat = out_path.stat()
        permissions = stat.st_mode & 0o777
        assert permissions == 0o600, f"Expected 0600, got {oct(permissions)}"


# ---------------------------------------------------------------------------
# Phase 4 — Loopback callback server
# ---------------------------------------------------------------------------


class TestLoopbackCallback:
    """Phase 4: loopback HTTP server captures code and handles errors."""

    def test_callback_captures_code(self):
        """Loopback server captures the authorization code from GET /callback?code=X.

        Production change that would make this fail: not extracting the 'code'
        query parameter from the callback URL.
        """
        import authorize_crm as ac

        code_captured = ac.start_loopback_server_and_wait(
            inject_request_after_start=("GET", "/callback?code=AUTH_CODE_123")
        )
        assert code_captured == "AUTH_CODE_123"

    def test_callback_error_causes_system_exit(self):
        """Loopback server exits with non-zero when callback has ?error=access_denied.

        Production change that would make this fail: not checking for 'error'
        query parameter in the callback.
        """
        import authorize_crm as ac

        with pytest.raises(SystemExit) as exc:
            ac.start_loopback_server_and_wait(
                inject_request_after_start=("GET", "/callback?error=access_denied")
            )
        assert exc.value.code != 0

    def test_callback_error_writes_no_file(self, tmp_path, monkeypatch):
        """AC 9: cancelled/denied consent exits non-zero AND leaves no partial file.

        Production change that would make this fail: writing any credential file
        before the callback outcome is known.
        """
        import authorize_crm as ac

        out_path = tmp_path / "zoho_crm_oauth.json"
        monkeypatch.setattr(ac, "DEFAULT_OUT", str(out_path))

        with pytest.raises(SystemExit) as exc:
            ac.start_loopback_server_and_wait(
                inject_request_after_start=("GET", "/callback?error=access_denied")
            )
        assert exc.value.code != 0
        assert not out_path.exists(), "no credential file may exist after a denied consent"
        assert list(tmp_path.iterdir()) == [], "no partial/temp files may be left behind"


# ---------------------------------------------------------------------------
# Phase 5 — No secrets in stdout and gitignore
# ---------------------------------------------------------------------------


class TestNoSecretsLeak:
    """Phase 5: No secrets appear in stdout/stderr; gitignore covers credential files."""

    def test_no_secrets_in_stdout(self, tmp_path, monkeypatch, capsys):
        """run_authorization_flow() prints nothing containing client_secret/refresh_token/access_token.

        Production change that would make this fail: printing any secret value
        to stdout or stderr.
        """
        import authorize_crm as ac

        out_path = tmp_path / "zoho_crm_oauth.json"
        monkeypatch.setattr(
            "urllib.request.urlopen",
            _make_urlopen_mock(
                token_resp=FAKE_TOKEN_RESPONSE, org_resp=FAKE_ORG_SANDBOX
            ),
        )

        ac.run_authorization_flow(
            client_id=DUMMY_CLIENT_ID,
            client_secret=DUMMY_CLIENT_SECRET,
            code="1000.test-code",
            redirect_uri="http://127.0.0.1:19999/callback",
            accounts_url=DUMMY_ACCOUNTS,
            out_path=str(out_path),
        )

        captured = capsys.readouterr()
        combined = captured.out + captured.err

        assert DUMMY_CLIENT_SECRET not in combined, "client_secret must not appear in output"
        assert DUMMY_REFRESH_TOKEN not in combined, "refresh_token must not appear in output"
        assert DUMMY_ACCESS_TOKEN not in combined, "access_token must not appear in output"

    def test_gitignore_covers_connected_app_json(self):
        """crm_connected_app.json is listed in .gitignore.

        Production change that would make this fail: removing crm_connected_app.json
        from .gitignore.
        """
        # parents[0]=tests dir, parents[1]=plugin-claude dir, parents[2]=worktree root
        gitignore = Path(__file__).resolve().parents[2] / ".gitignore"
        content = gitignore.read_text()
        assert "crm_connected_app.json" in content, (
            "crm_connected_app.json must be listed in .gitignore"
        )

    def test_gitignore_covers_oauth_json(self):
        """zoho_crm_oauth.json is listed in .gitignore (already there, regression check).

        Production change that would make this fail: accidentally removing zoho_crm_oauth.json
        from .gitignore.
        """
        gitignore = Path(__file__).resolve().parents[2] / ".gitignore"
        content = gitignore.read_text()
        assert "zoho_crm_oauth.json" in content, (
            "zoho_crm_oauth.json must be listed in .gitignore"
        )
