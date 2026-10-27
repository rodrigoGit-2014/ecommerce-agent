"""Registra el webhook del bot de Telegram.

Uso:
    python scripts/set_webhook.py

Lee TELEGRAM_TOKEN, TELEGRAM_SECRET y PUBLIC_URL del entorno (o de .env) y
llama a setWebhook con PUBLIC_URL + "/telegram".
"""

import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

TELEGRAM_API = "https://api.telegram.org"


def main() -> int:
    token = os.getenv("TELEGRAM_TOKEN", "").strip()
    secreto = os.getenv("TELEGRAM_SECRET", "").strip()
    public_url = os.getenv("PUBLIC_URL", "").strip().rstrip("/")

    faltantes = [
        nombre
        for nombre, valor in (
            ("TELEGRAM_TOKEN", token),
            ("TELEGRAM_SECRET", secreto),
            ("PUBLIC_URL", public_url),
        )
        if not valor
    ]
    if faltantes:
        print(
            "Faltan variables de entorno: " + ", ".join(faltantes),
            file=sys.stderr,
        )
        return 1

    if not public_url.startswith("https://"):
        print(
            "PUBLIC_URL debe empezar con https:// (Telegram no acepta http).",
            file=sys.stderr,
        )
        return 1

    url_webhook = f"{public_url}/telegram"

    try:
        respuesta = httpx.post(
            f"{TELEGRAM_API}/bot{token}/setWebhook",
            json={"url": url_webhook, "secret_token": secreto},
            timeout=15,
        )
    except httpx.HTTPError as error:
        print(f"No se pudo conectar con Telegram: {error}", file=sys.stderr)
        return 1

    print(f"setWebhook -> HTTP {respuesta.status_code}")
    try:
        datos = respuesta.json()
    except ValueError:
        print(respuesta.text)
        return 1

    print(json.dumps(datos, indent=2, ensure_ascii=False))
    return 0 if respuesta.is_success and datos.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
