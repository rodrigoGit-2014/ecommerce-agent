"""Muestra el estado del webhook del bot de Telegram.

Uso:
    python scripts/webhook_info.py

Llama a getWebhookInfo e imprime la URL configurada, los updates pendientes y
el último error, si existe.
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

TELEGRAM_API = "https://api.telegram.org"


def formatear_fecha(timestamp: int | None) -> str:
    """Convierte el epoch que devuelve Telegram a una fecha legible."""
    if not timestamp:
        return "sin fecha"
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )


def main() -> int:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    if not token:
        print("Falta TELEGRAM_TOKEN en el entorno o en .env.", file=sys.stderr)
        return 1

    try:
        respuesta = httpx.get(
            f"{TELEGRAM_API}/bot{token}/getWebhookInfo",
            timeout=15,
        )
    except httpx.HTTPError as error:
        print(f"No se pudo conectar con Telegram: {error}", file=sys.stderr)
        return 1

    print(f"getWebhookInfo -> HTTP {respuesta.status_code}")
    try:
        datos = respuesta.json()
    except ValueError:
        print(respuesta.text)
        return 1

    print(json.dumps(datos, indent=2, ensure_ascii=False))

    if not datos.get("ok"):
        return 1

    info = datos.get("result", {})
    print()
    print(f"URL configurada: {info.get('url') or '(ninguna)'}")
    print(f"Updates pendientes: {info.get('pending_update_count', 0)}")

    if info.get("last_error_message"):
        print(
            "Último error: "
            f"{formatear_fecha(info.get('last_error_date'))} - "
            f"{info['last_error_message']}"
        )
    else:
        print("Último error: ninguno")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
