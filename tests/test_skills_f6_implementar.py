"""AW-188 Fase 6 — skill `implementar` (crítica, seguridad primero).

Verifica:
- Dry-run por defecto (no escribe sin confirmación) — reutiliza patrón de AW-187
- CrmClient con www.zohoapis.com → RuntimeError
- SKILL.md de implementar contiene la confirmación explícita
- SKILL.md de implementar NO contiene rutas a producción
"""
import pathlib
import sys

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
IMPLEMENTAR_DIR = SKILLS_DIR / "implementar"

# Asegurar que parametrizacion está disponible
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def test_skill_md_implementar_existe():
    """SKILL.md de implementar debe existir."""
    assert (IMPLEMENTAR_DIR / "SKILL.md").exists()


def test_crm_client_produccion_lanza_runtime_error():
    """CrmClient con api_domain = www.zohoapis.com debe lanzar RuntimeError (guarda dura)."""
    from parametrizacion.crm import CrmClient
    import pytest
    creds = {
        "api_domain": "https://www.zohoapis.com",
        "accounts_domain": "https://accounts.zoho.com",
        "client_id": "cid",
        "client_secret": "csec",
        "refresh_token": "rt",
    }
    with pytest.raises(RuntimeError, match="producción|www.zohoapis.com|sandbox"):
        CrmClient(creds=creds)


def test_crm_client_sandbox_no_lanza():
    """CrmClient con api_domain = sandbox.zohoapis.com NO debe lanzar RuntimeError."""
    from parametrizacion.crm import CrmClient
    creds = {
        "api_domain": "https://sandbox.zohoapis.com",
        "accounts_domain": "https://accounts.zoho.com",
        "client_id": "cid",
        "client_secret": "csec",
        "refresh_token": "rt",
    }
    # No debe lanzar en el constructor
    client = CrmClient(creds=creds)
    assert client is not None


def test_apply_cli_dry_run_por_defecto(tmp_path):
    """apply_cli.main sin --apply: do_write=False (dry-run). Reusar patrón AW-187."""
    import unittest.mock as mock
    sys.path.insert(0, str(SCRIPTS_DIR))
    from parametrizacion import apply_cli, applicator

    FIXTURE = str(SCRIPTS_DIR / "tests" / "fixtures" / "ir_jaque_r1r3.json")
    CREDS = {"api_domain": "https://sandbox.zohoapis.com",
             "accounts_domain": "https://accounts.zoho.com",
             "client_id": "cid", "client_secret": "csec",
             "refresh_token": "rt", "org_id": "693026068"}
    calls = {"apply": []}

    def fake_apply(ir, client, do_write=False):
        calls["apply"].append({"do_write": do_write})
        return {"actions": [], "results": []}

    with (mock.patch.object(apply_cli, "load_creds", return_value=dict(CREDS)),
          mock.patch.object(apply_cli, "CrmClient", return_value=mock.MagicMock()),
          mock.patch.object(applicator, "apply", fake_apply),
          mock.patch.object(applicator, "build_discovery", return_value={}),
          mock.patch.object(applicator, "plan", return_value=[]),
          mock.patch("builtins.input", side_effect=AssertionError("dry-run no debe pedir confirmación"))):
        rc = apply_cli.main(["--ir", FIXTURE])

    assert rc == 0
    assert all(not c["do_write"] for c in calls["apply"]), "dry-run no debe hacer do_write=True"


def test_skill_md_implementar_exige_confirmacion():
    """SKILL.md de implementar debe exigir confirmación explícita antes de escribir."""
    text = (IMPLEMENTAR_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert any(kw in text.lower() for kw in
               ["confirmación", "confirmacion", "confirmar", "confirma"]), \
        "SKILL.md implementar no exige confirmación"
    assert "dry-run" in text.lower() or "dry_run" in text.lower(), \
        "SKILL.md implementar no menciona dry-run como modo por defecto"


def test_skill_md_implementar_no_tiene_rutas_produccion():
    """SKILL.md de implementar NO debe contener 'www.zohoapis.com'."""
    text = (IMPLEMENTAR_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "www.zohoapis.com" not in text, \
        "SKILL.md implementar menciona www.zohoapis.com (ruta a producción)"


def test_skill_md_implementar_menciona_sandbox():
    """SKILL.md de implementar debe mencionar sandbox-only."""
    text = (IMPLEMENTAR_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "sandbox" in text.lower(), "SKILL.md implementar no menciona sandbox"


def test_skill_md_implementar_menciona_apply_cli():
    """SKILL.md de implementar debe referenciar apply_cli.py como ÚNICA vía de escritura."""
    text = (IMPLEMENTAR_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "apply_cli" in text or "apply_cli.py" in text, \
        "SKILL.md implementar no referencia apply_cli.py"


def test_skill_md_implementar_no_ofrece_otra_via_escritura():
    """SKILL.md de implementar no debe sugerir escribir por otra vía que apply_cli.py."""
    text = (IMPLEMENTAR_DIR / "SKILL.md").read_text(encoding="utf-8")
    # No debe haber invitación a usar requests, urllib directamente para escribir
    bad_patterns = ["requests.post", "urllib.request.urlopen(", "crm.post(", "crm.patch("]
    for pat in bad_patterns:
        assert pat not in text, f"SKILL.md implementar sugiere escribir vía '{pat}'"
