#!/bin/sh
# session_start.sh — AW-194: hook SessionStart del plugin consultoria-sagitaz (macOS-first).
#
# Autodescubre un intérprete Python >= 3.10 y delega el onboarding en onboard.py.
# POSIX sh: NO depende de jq ni de Node. exit 0 SIEMPRE (SessionStart no bloquea).
#
# Orden de búsqueda del intérprete:
#   1. $CLAUDE_PLUGIN_OPTION_PYTHON_BIN (userConfig.python_bin) si es >= 3.10.
#   2. Escaneo por versión: python3.13/3.12/3.11/3.10, luego python3/python (descarta 3.9).
# Si no hay ninguno >= 3.10, imprime un JSON estático avisando (sin asumir Homebrew).

ROOT="${CLAUDE_PLUGIN_ROOT:-$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)}"

# Código de versión (major*100+minor) de un intérprete, o vacío si falla.
py_vercode() {
  "$1" -c 'import sys;print(sys.version_info[0]*100+sys.version_info[1])' 2>/dev/null
}

PY=""

# 1. Override del usuario (userConfig.python_bin → CLAUDE_PLUGIN_OPTION_PYTHON_BIN)
if [ -n "${CLAUDE_PLUGIN_OPTION_PYTHON_BIN:-}" ]; then
  vc=$(py_vercode "$CLAUDE_PLUGIN_OPTION_PYTHON_BIN")
  if [ -n "$vc" ] && [ "$vc" -ge 310 ]; then
    PY="$CLAUDE_PLUGIN_OPTION_PYTHON_BIN"
  fi
fi

# 2. Escaneo por versión (prioriza versiones explícitas; descarta el python3 del sistema si es 3.9)
if [ -z "$PY" ]; then
  for c in python3.13 python3.12 python3.11 python3.10 python3 python; do
    cmd=$(command -v "$c" 2>/dev/null) || continue
    vc=$(py_vercode "$cmd")
    if [ -n "$vc" ] && [ "$vc" -ge 310 ]; then
      PY="$cmd"
      break
    fi
  done
fi

# 3a. Hay intérprete válido → onboarding (onboard.py emite el JSON a stdout).
if [ -n "$PY" ]; then
  exec "$PY" "$ROOT/hooks/onboard.py"
fi

# 3b. No hay Python >= 3.10 → JSON estático (sin jq), sin asumir Homebrew.
printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"El plugin consultoria-sagitaz necesita Python 3.10 o superior, que no se ha encontrado en el sistema. Las skills (matriz, plan, dercas) no funcionaran hasta instalarlo. Indica al consultor que instale Python 3.10+ desde https://www.python.org/downloads/ (o, si ya tiene Homebrew, con: brew install python@3.12) y reinicie la sesion.","systemMessage":"consultoria-sagitaz: falta Python 3.10+. Instalalo desde https://www.python.org/downloads/ (o brew install python@3.12) y reinicia la sesion."}}'
exit 0
