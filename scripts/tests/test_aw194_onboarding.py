"""AW-194 — onboarding del plugin: hook SessionStart (autodescubrir Python + bootstrap + avisar).

- doctor: piso 3.10 (AC-5).
- session_start.sh: autodescubre Python ≥3.10, override, JSON estático sin brew (AC-1/2/3/6).
- onboard.py: additionalContext/systemMessage JSON válido (AC-1/4).
- hooks.json: estructura SessionStart.
"""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

# conftest de scripts/tests añade scripts/ al sys.path
import doctor as doc_mod  # noqa: E402

PLUGIN_ROOT = Path(__file__).resolve().parents[2]
HOOKS = PLUGIN_ROOT / "hooks"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_py_stub(dir_: Path, name: str, vercode: int) -> Path:
    """Crea un stub ejecutable que imita un intérprete Python.

    - Con `-c ...` imprime el vercode (major*100+minor), como hace session_start.sh.
    - En otro caso (ejecutar onboard.py) imprime un marcador identificable.
    """
    dir_.mkdir(parents=True, exist_ok=True)
    p = dir_ / name
    p.write_text(
        "#!/bin/sh\n"
        'case "$1" in\n'
        f'  -c) echo {vercode} ;;\n'
        f'  *) echo "RAN_BY:{name}" ;;\n'
        "esac\n"
    )
    p.chmod(p.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return p


def _run_hook(env_extra: dict) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.update(env_extra)
    # /bin/sh por ruta absoluta para no depender del PATH (que controlamos en los tests).
    return subprocess.run(
        ["/bin/sh", str(HOOKS / "session_start.sh")],
        env=env, capture_output=True, text=True,
    )


# ---------------------------------------------------------------------------
# AC-5 — doctor piso 3.10
# ---------------------------------------------------------------------------

def _make_version_stub(dir_: Path, name: str, version_str: str) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    p = dir_ / name
    p.write_text(f"#!/bin/sh\necho {version_str}\n")
    p.chmod(p.stat().st_mode | stat.S_IEXEC)
    return p


def test_doctor_piso_acepta_3_10(tmp_path):
    stub = _make_version_stub(tmp_path, "py310", "3.10.0")
    ok, msg = doc_mod._python_version_ok(stub)
    assert ok, f"3.10 debe aceptarse: {msg}"


def test_doctor_piso_acepta_3_12(tmp_path):
    stub = _make_version_stub(tmp_path, "py312", "3.12.4")
    ok, _ = doc_mod._python_version_ok(stub)
    assert ok


def test_doctor_piso_rechaza_3_9(tmp_path):
    stub = _make_version_stub(tmp_path, "py39", "3.9.6")
    ok, msg = doc_mod._python_version_ok(stub)
    assert not ok and "3.10" in msg, f"3.9 debe rechazarse con mención a 3.10: {msg}"


# ---------------------------------------------------------------------------
# AC-1/2/3/6 — session_start.sh
# ---------------------------------------------------------------------------

def test_hook_elige_312_sobre_39(tmp_path):
    """Con 3.9 y 3.12 en el PATH, el hook elige 3.12 (≥3.10) y delega en onboard."""
    bindir = tmp_path / "bin"
    _make_py_stub(bindir, "python3.12", 312)
    _make_py_stub(bindir, "python3", 309)  # el 3.9 del sistema simulado
    res = _run_hook({
        "PATH": str(bindir),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
    })
    assert "RAN_BY:python3.12" in res.stdout, (
        f"Debe ejecutar onboard con python3.12. stdout={res.stdout!r} stderr={res.stderr!r}"
    )


def test_hook_sin_python_valido_json_estatico_sin_brew(tmp_path):
    """Solo 3.9 disponible → JSON estático válido con systemMessage y python.org (no asume brew)."""
    bindir = tmp_path / "bin"
    _make_py_stub(bindir, "python3", 309)  # shadow del python3 del sistema
    res = _run_hook({
        "PATH": str(bindir),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
    })
    data = json.loads(res.stdout)  # debe ser JSON válido
    out = data["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    assert "python.org" in out["systemMessage"], "el aviso debe ofrecer python.org (no asumir brew)"
    assert "RAN_BY" not in res.stdout, "no debe ejecutar onboard si no hay Python ≥3.10"


def test_hook_respeta_override_python_bin(tmp_path):
    """CLAUDE_PLUGIN_OPTION_PYTHON_BIN válido (≥3.10) se usa como override."""
    bindir = tmp_path / "bin"
    override = _make_py_stub(bindir, "mypython", 311)
    res = _run_hook({
        "PATH": str(bindir),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN_ROOT),
        "CLAUDE_PLUGIN_OPTION_PYTHON_BIN": str(override),
    })
    assert "RAN_BY:mypython" in res.stdout, f"Debe usar el override. stdout={res.stdout!r}"


# ---------------------------------------------------------------------------
# AC-1/4 — onboard.py
# ---------------------------------------------------------------------------

def test_onboard_venv_ok_emite_json_listo(tmp_path):
    """Con un venv que pasa venv_is_ok, onboard emite JSON 'listo' válido (sin install real)."""
    data_dir = tmp_path / "data"
    venv_bin = data_dir / "venv" / "bin"
    venv_bin.mkdir(parents=True)
    fake_py = venv_bin / "python"
    fake_py.write_text("#!/bin/sh\nexit 0\n")  # 'import openpyxl' → exit 0
    fake_py.chmod(fake_py.stat().st_mode | stat.S_IEXEC)

    env = dict(os.environ)
    env["CONSULTORIA_SAGITAZ_DATA"] = str(data_dir)
    res = subprocess.run(
        [sys.executable, str(HOOKS / "onboard.py")],
        env=env, capture_output=True, text=True,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)  # stdout debe ser SOLO el JSON
    out = data["hookSpecificOutput"]
    assert out["hookEventName"] == "SessionStart"
    assert "LISTO" in out["additionalContext"] or "listo" in out["additionalContext"].lower()
    # no fuga de secretos típicos
    assert "refresh_token" not in res.stdout and "client_secret" not in res.stdout


# ---------------------------------------------------------------------------
# hooks.json — estructura
# ---------------------------------------------------------------------------

def test_hooks_json_estructura():
    data = json.loads((HOOKS / "hooks.json").read_text())
    assert "SessionStart" in data["hooks"], "hooks.json debe declarar SessionStart"
    entry = data["hooks"]["SessionStart"][0]["hooks"][0]
    assert "session_start.sh" in entry["command"], "SessionStart debe invocar session_start.sh"
    assert entry.get("type") == "command"


# ---------------------------------------------------------------------------
# AC-7 — python_bin opcional + README
# ---------------------------------------------------------------------------

def test_python_bin_es_opcional():
    """userConfig.python_bin no debe imponer una ruta fija por defecto (autodescubrimiento)."""
    data = json.loads((PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text())
    pb = data["userConfig"]["python_bin"]
    assert "default" not in pb or not pb.get("default"), (
        "python_bin no debe tener default de ruta fija (es override opcional)"
    )


def test_readme_onboarding_sin_3_11_con_python_org():
    """README: piso 3.10 y python.org; sin exigir 3.11 como requisito."""
    txt = (PLUGIN_ROOT / "README.md").read_text()
    assert "3.10" in txt
    assert "python.org" in txt
    assert "Python | 3.11+" not in txt, "el requisito ya no es 3.11+"
