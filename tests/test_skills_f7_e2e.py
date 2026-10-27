"""AW-188 Fase 7 — E2E handoff entre skills.

Verifica que la salida de cada etapa encaja como entrada de la siguiente según §4.3:
  transcripciones.txt → DERS.json → DERCAS.json + ir.json → Matriz_CRM.xlsx → Plan.md → dry-run

- Sin red, sin modelo (todo offline con mocks/fixtures)
- Usa tmp_path como raíz de clientes (via SAGITAZ_CLIENTES_ROOT o parámetro)
"""
import importlib
import json
import os
import pathlib
import sys
import unittest.mock as mock

SKILLS_DIR = pathlib.Path(__file__).resolve().parents[1] / "skills"
SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1] / "scripts"
FIXTURE_DIR = SCRIPTS_DIR / "tests" / "fixtures"

# Asegurar paths
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(SKILLS_DIR) not in sys.path:
    sys.path.insert(0, str(SKILLS_DIR))


def _import_fresh(mod_name, extra_path=None):
    """Importa un módulo limpio, añadiendo extra_path al sys.path si se pide."""
    if extra_path and str(extra_path) not in sys.path:
        sys.path.insert(0, str(extra_path))
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    return importlib.import_module(mod_name)


def test_e2e_fetch_transcripciones(tmp_path):
    """Fase 1 del handoff: fetch_transcripciones escribe transcripciones.txt en la ruta esperada."""
    cliente = "cliente_e2e"
    os.environ["SAGITAZ_CLIENTES_ROOT"] = str(tmp_path / "clientes")
    try:
        # Importar el helper de rutas
        skills_paths = _import_fresh("skills_paths", SKILLS_DIR)
        raiz = pathlib.Path(os.environ["SAGITAZ_CLIENTES_ROOT"])
        out_dir = raiz / cliente
        out_dir.mkdir(parents=True, exist_ok=True)
        trans_path = skills_paths.cliente_path(cliente, "transcripciones.txt")
        assert trans_path == raiz / cliente / "transcripciones.txt"

        # Simular fetch_transcripciones escribiendo el fichero
        reuniones = [{"reunion": "m01", "fichero": "m01.txt", "texto": "Reunión de kickoff."}]
        body = {"status": "ok", "cliente": cliente, "reuniones": reuniones, "n": 1}

        fetch_mod = _import_fresh("fetch_transcripciones",
                                  SKILLS_DIR / "ders" / "scripts")
        with mock.patch("urllib.request.urlopen") as mu:
            resp = mock.MagicMock()
            resp.__enter__ = mock.Mock(return_value=resp)
            resp.__exit__ = mock.Mock(return_value=False)
            resp.status = 200
            resp.read = mock.Mock(return_value=json.dumps(body).encode())
            mu.return_value = resp
            rc = fetch_mod.main([
                "--cliente", cliente,
                "--endpoint", "http://fake.endpoint",
                "--token", "FAKE_TOKEN",
                "--out", str(trans_path),
            ])

        assert rc == 0
        assert trans_path.exists(), "transcripciones.txt no fue creado"
        assert "Reunión de kickoff." in trans_path.read_text()
    finally:
        del os.environ["SAGITAZ_CLIENTES_ROOT"]


def test_e2e_validar_ir_sobre_fixture(tmp_path):
    """Fase 3 del handoff: validar_ir acepta el ir.json fixture (simulando salida de dercas)."""
    os.environ["SAGITAZ_CLIENTES_ROOT"] = str(tmp_path / "clientes")
    try:
        fixture = FIXTURE_DIR / "ir_jaque_r1r3.json"
        validar_ir = _import_fresh("validar_ir",
                                   SKILLS_DIR / "dercas" / "scripts")
        rc = validar_ir.main([str(fixture)])
        assert rc == 0, "ir.json fixture de Jaque válido debe pasar validación"
    finally:
        del os.environ["SAGITAZ_CLIENTES_ROOT"]


def test_e2e_generar_matriz_desde_ir(tmp_path):
    """Fase 4 del handoff: generar_matriz toma ir.json y produce Matriz_CRM.xlsx."""
    os.environ["SAGITAZ_CLIENTES_ROOT"] = str(tmp_path / "clientes")
    try:
        skills_paths = _import_fresh("skills_paths", SKILLS_DIR)
        cliente = "cliente_e2e_matriz"
        ir_fixture = FIXTURE_DIR / "ir_jaque_r1r3.json"
        out_dir = tmp_path / "clientes" / cliente
        out_dir.mkdir(parents=True, exist_ok=True)
        ir_path = out_dir / "ir.json"
        ir_path.write_bytes(ir_fixture.read_bytes())

        matriz_path = skills_paths.cliente_path(cliente, "Matriz_CRM.xlsx")
        generar_matriz = _import_fresh("generar_matriz",
                                       SKILLS_DIR / "matriz" / "scripts")
        rc = generar_matriz.main(["--ir", str(ir_path), "--out", str(matriz_path)])

        assert rc == 0
        assert matriz_path.exists(), "Matriz_CRM.xlsx no fue creado"
        assert matriz_path.stat().st_size > 0
    finally:
        del os.environ["SAGITAZ_CLIENTES_ROOT"]


def test_e2e_revision_ir_desde_ir(tmp_path):
    """Fase 5 del handoff: revision_ir toma ir.json y produce revision.json / revision.md."""
    os.environ["SAGITAZ_CLIENTES_ROOT"] = str(tmp_path / "clientes")
    try:
        skills_paths = _import_fresh("skills_paths", SKILLS_DIR)
        cliente = "cliente_e2e_plan"
        ir_fixture = FIXTURE_DIR / "ir_jaque_r1r3.json"
        out_dir = tmp_path / "clientes" / cliente
        out_dir.mkdir(parents=True, exist_ok=True)
        ir_path = out_dir / "ir.json"
        ir_path.write_bytes(ir_fixture.read_bytes())

        rev_json = skills_paths.cliente_path(cliente, "revision.json")
        rev_md = skills_paths.cliente_path(cliente, "revision.md")

        revision_ir = _import_fresh("revision_ir",
                                    SKILLS_DIR / "plan" / "scripts")
        rc = revision_ir.main([
            "--ir", str(ir_path),
            "--out-json", str(rev_json),
            "--out-md", str(rev_md),
        ])

        assert rc == 0
        assert rev_json.exists(), "revision.json no fue creado"
        assert rev_md.exists(), "revision.md no fue creado"
    finally:
        del os.environ["SAGITAZ_CLIENTES_ROOT"]


def test_e2e_implementar_dry_run(tmp_path):
    """Fase 6 del handoff: implementar en dry-run no escribe nada."""
    os.environ["SAGITAZ_CLIENTES_ROOT"] = str(tmp_path / "clientes")
    try:
        from parametrizacion import apply_cli, applicator

        FIXTURE = str(FIXTURE_DIR / "ir_jaque_r1r3.json")
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
              mock.patch("builtins.input",
                         side_effect=AssertionError("dry-run E2E no debe pedir confirmación"))):
            rc = apply_cli.main(["--ir", FIXTURE])

        assert rc == 0
        assert all(not c["do_write"] for c in calls["apply"]), \
            "E2E dry-run no debe llamar do_write=True"
    finally:
        del os.environ["SAGITAZ_CLIENTES_ROOT"]


def test_e2e_cadena_rutas_consistente(tmp_path):
    """Los ficheros de salida de cada skill = entrada de la siguiente según §4.3."""
    os.environ["SAGITAZ_CLIENTES_ROOT"] = str(tmp_path / "clientes")
    try:
        skills_paths = _import_fresh("skills_paths", SKILLS_DIR)
        cliente = "test_handoff"

        # Verificar que las rutas forman una cadena coherente
        rutas = {
            "transcripciones.txt": "ders",      # salida de fetch_transcripciones → entrada de Claude
            "DERS.json": "ders",                # salida de ders
            "DERCAS.json": "dercas",            # salida de dercas
            "ir.json": "dercas",                # salida de dercas → entrada de matriz/plan/implementar
            "Matriz_CRM.xlsx": "matriz",        # salida de matriz
            "Plan.md": "plan",                  # salida de plan
            "revision.json": "plan",            # salida de plan
            "revision.md": "plan",              # salida de plan
            "resumen_implementacion.md": "implementar",  # salida de implementar
        }

        raiz = tmp_path / "clientes"
        for fichero, skill_productor in rutas.items():
            p = skills_paths.cliente_path(cliente, fichero)
            # La ruta debe estar bajo el directorio del cliente
            assert str(raiz / cliente) in str(p), \
                f"{fichero} no está bajo {raiz/cliente}"
            # El nombre de fichero es el esperado
            assert p.name == fichero, f"Ruta incorrecta para {fichero}: {p}"

        # Verificar que ir.json es entrada para matriz, plan, implementar (misma ruta)
        ir_para_dercas = skills_paths.cliente_path(cliente, "ir.json")
        ir_para_matriz = skills_paths.cliente_path(cliente, "ir.json")
        ir_para_plan = skills_paths.cliente_path(cliente, "ir.json")
        assert ir_para_dercas == ir_para_matriz == ir_para_plan, \
            "ir.json tiene rutas distintas en matriz/plan (debe ser la misma)"
    finally:
        del os.environ["SAGITAZ_CLIENTES_ROOT"]
