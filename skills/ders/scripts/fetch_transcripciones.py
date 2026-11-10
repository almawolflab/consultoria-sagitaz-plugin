#!/usr/bin/env python3
"""fetch_transcripciones.py — Descarga las transcripciones de un cliente desde el endpoint AW-185.

Contrato de respuesta del endpoint:
  {
    "status": "ok",
    "cliente": "<nombre>",
    "reuniones": [{"reunion": "m01", "fichero": "m01.txt", "texto": "..."}],
    "n": <int>
  }

Escribe transcripciones.txt concatenando el texto de todas las reuniones.

Uso:
    python fetch_transcripciones.py \\
        --cliente tufisio \\
        --endpoint https://endpoint/api \\
        --token <token>              # o env TEAM_API_TOKEN
        --out ~/Sagitaz/clientes/tufisio/transcripciones.txt

El token NUNCA se imprime en stdout ni stderr.
Errores HTTP (401/403/404/503): mensaje claro + exit!=0.
"""
import argparse
import json
import os
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

# scripts/ del plugin en el path para reusar bootstrap.data_dir() como fuente única de
# la ruta de datos (AW-196 review: DRY, igual que crm.py / authorize_crm.py).
# Este fichero está en <plugin-root>/skills/ders/scripts/ → parents[3] = <plugin-root>.
_SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import bootstrap  # noqa: E402  (scripts/ del plugin está en sys.path)


def _load_materialized():
    """Lee data_dir()/transcripciones.json {endpoint, token}, o {} si no existe/es inválido."""
    f = bootstrap.data_dir() / "transcripciones.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8")) or {}
    except (ValueError, OSError):
        return {}


def _build_url(endpoint, cliente):
    """Construye la URL del endpoint con el parámetro cliente."""
    base = endpoint.rstrip("/")
    params = urllib.parse.urlencode({"cliente": cliente})
    return f"{base}/transcripciones?{params}"


def fetch(endpoint, cliente, token):
    """Hace GET al endpoint y devuelve el JSON de respuesta.

    Lanza urllib.error.HTTPError con el código correcto en errores HTTP.
    """
    url = _build_url(endpoint, cliente)
    req = urllib.request.Request(url, headers={"X-Team-Token": token})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def _concat_reuniones(data):
    """Concatena el texto de todas las reuniones en un único string."""
    reuniones = data.get("reuniones") or []
    partes = []
    for r in reuniones:
        nombre = r.get("reunion") or r.get("fichero") or "reunion"
        texto = r.get("texto") or ""
        partes.append(f"=== {nombre} ===\n{texto}")
    return "\n\n".join(partes)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Descarga transcripciones de cliente desde el endpoint AW-185.")
    parser.add_argument("--cliente", required=True, help="Nombre del cliente")
    parser.add_argument("--endpoint",
                        default=os.environ.get("TRANSCRIPCIONES_ENDPOINT", ""),
                        help="URL base del endpoint (o env TRANSCRIPCIONES_ENDPOINT)")
    parser.add_argument("--token",
                        default=os.environ.get("TEAM_API_TOKEN", ""),
                        help="Token de autenticación (o env TEAM_API_TOKEN)")
    parser.add_argument("--out", default=None,
                        help="Ruta de salida (por defecto: ~/Sagitaz/clientes/<cliente>/transcripciones.txt)")

    args = parser.parse_args(argv)

    # Precedencia: CLI > env (defaults de argparse) > data_dir()/transcripciones.json (AW-196).
    if not args.endpoint or not args.token:
        mat = _load_materialized()
        if not args.endpoint:
            args.endpoint = (mat.get("endpoint") or "").strip()
        if not args.token:
            args.token = (mat.get("token") or "").strip()

    if not args.endpoint:
        print("Error: endpoint no configurado. Fija 'Endpoint de transcripciones' en "
              "los ajustes del plugin, o usa --endpoint / env TRANSCRIPCIONES_ENDPOINT.",
              file=sys.stderr)
        return 1
    if not args.token:
        print("Error: token no configurado. Fija 'Token de equipo' en los ajustes del "
              "plugin, o usa --token / env TEAM_API_TOKEN.", file=sys.stderr)
        return 1

    # Ruta de salida
    if args.out:
        out_path = pathlib.Path(args.out)
    else:
        raiz = pathlib.Path(os.environ.get("SAGITAZ_CLIENTES_ROOT",
                                           pathlib.Path.home() / "Sagitaz" / "clientes"))
        out_path = raiz / args.cliente / "transcripciones.txt"

    try:
        data = fetch(args.endpoint, args.cliente, args.token)
    except urllib.error.HTTPError as e:
        code = e.code
        if code == 401:
            print(f"Error {code}: Token inválido o no autorizado. "
                  "Verifica TEAM_API_TOKEN.", file=sys.stderr)
        elif code == 403:
            print(f"Error {code}: Acceso denegado al endpoint.", file=sys.stderr)
        elif code == 404:
            print(f"Error {code}: Cliente '{args.cliente}' no encontrado en el endpoint.",
                  file=sys.stderr)
        elif code == 503:
            print(f"Error {code}: Servicio no disponible. "
                  "El endpoint de transcripciones está caído.", file=sys.stderr)
        else:
            print(f"Error HTTP {code}: {e.reason}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Error de conexión: {e.reason}", file=sys.stderr)
        return 1
    except Exception as e:  # noqa: BLE001
        print(f"Error inesperado: {e}", file=sys.stderr)
        return 1

    # Concatenar textos
    texto = _concat_reuniones(data)
    n = data.get("n", len(data.get("reuniones") or []))

    # Escribir a disco
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(texto, encoding="utf-8")

    print(f"OK: {n} reunión(es) escritas en {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
