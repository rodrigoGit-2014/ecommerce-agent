# Ecommerce Agent

Proyecto de agentes con LangGraph + Gemini, API FastAPI y despliegue en Railway.

## Requisitos

- Python 3.12
- Una clave de Google AI Studio

## Puesta en marcha

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edita .env y añade GOOGLE_API_KEY
```

## Uso

```bash
python main.py ecommerce "¿Dónde está mi pedido 1001?"
python main.py ecommerce "¿Dónde está mi pedido 1001?" --saltos
python main.py ecommerce --diagrama

python main.py router "¿tienen la polera azul en talla M?" --saltos
```

Los agentes con memoria (como `router`) guardan la conversación por
`thread_id`. La CLI usa `default`; puedes cambiarlo con `--thread-id`:

```bash
python main.py router "mi pedido 4521 llegó roto" --saltos --thread-id cliente-42
```

## API

```bash
uvicorn api.app:app --reload --port 8000
```

- `GET /health` → `{"status": "ok"}`
- `POST /chat` con `{"user_id": "...", "texto": "..."}` → `{ruta, motivo, respuesta}`
- `POST /telegram` → webhook provisional, oculto en Swagger

El router usa `user_id` como `thread_id`, así que conserva la memoria por
usuario. El grafo se compila una sola vez al arrancar la API.

Curl de ejemplo:

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "usuario-123", "texto": "¿Tienen la polera azul en talla M?"}'
```

Respuesta:

```json
{
  "ruta": "preventa",
  "motivo": "El usuario pregunta por disponibilidad de stock antes de comprar.",
  "respuesta": "Soy el agente de preventa. Recibí: ¿Tienen la polera azul en talla M?. Pronto podré ayudarte con productos y compras."
}
```

Swagger completo con ejemplos listos para "Try it out":

```text
http://localhost:8000/docs
```

También hay una colección de Bruno en `bruno/` con los entornos **Local** y
**Railway** (variable `baseUrl`).

## Pruebas

```bash
pytest
```

`pytest` incluye la integración del router contra Gemini usando
`tests/casos_router.json` (15 casos, mínimo 13 aciertos). Requiere
`GOOGLE_API_KEY`; si no está definida, esos tests se omiten.

Tabla de resultados de los 15 casos:

```bash
python scripts/test_router.py
```

Prueba manual ampliada del router:

```bash
python scripts/probar_router.py
python scripts/probar_router.py --ruta preventa -v
```

## Estructura

```
src/{nombre_agente}/   graph.py, prompts.py y tools.py de cada agente
api/app.py             API FastAPI
bruno/                 colección y entornos de Bruno
main.py                CLI de los agentes
scripts/               scripts sueltos
tests/                 pruebas de pytest
```

Las reglas completas del proyecto están en `AGENTS.md`.

## Despliegue en Railway

`railway.toml` es la única configuración de despliegue:

- Build con **Railpack**.
- Arranque con `uvicorn api.app:app --host 0.0.0.0 --port $PORT`.
- Healthcheck en `/health`, con 100 segundos de timeout.
- Reinicio automático en caso de fallo (máximo 3 intentos).

El proyecto ya incluye `.python-version` con `3.12` y las dependencias en
`requirements.txt`. Configura las variables de entorno (`GOOGLE_API_KEY`,
`MODELO`, etc.) en la pestaña **Variables** del servicio en Railway; no van en
`railway.toml`.
