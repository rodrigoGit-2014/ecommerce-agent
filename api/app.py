"""API FastAPI del router de ecommerce.

Se levanta desde la raíz con:
    uvicorn api.app:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any, AsyncIterator, Literal

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

from src.router.graph import construir_grafo  # noqa: E402

logger = logging.getLogger("api.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Compila el grafo una sola vez al arrancar la aplicación."""
    app.state.grafo = construir_grafo()
    logger.info("Grafo del router compilado al arrancar la API.")
    yield


tags_metadata = [
    {
        "name": "salud",
        "description": "Estado del servicio y modelo configurado.",
    },
    {
        "name": "chat",
        "description": "Enrutado del mensaje y respuesta del agente elegido.",
    },
    {
        "name": "telegram",
        "description": "Webhook de Telegram (oculto en Swagger).",
    },
]

app = FastAPI(
    title="Ecommerce Router API",
    version="1.0.0",
    description=(
        "Router de atención al cliente de un ecommerce. Recibe cada mensaje y "
        "decide a qué agente enviarlo.\n\n"
        "- **preventa**: intención de compra o dudas antes de comprar.\n"
        "- **postventa**: pedidos existentes, devoluciones, cambios y garantías.\n"
        "- **generica**: temas ajenos a la tienda o saludos sin una petición."
    ),
    openapi_tags=tags_metadata,
    lifespan=lifespan,
)


class HealthResponse(BaseModel):
    status: Literal["ok"] = Field(
        ...,
        description="Estado del servicio.",
        examples=["ok"],
    )

    model_config = ConfigDict(
        json_schema_extra={"example": {"status": "ok"}}
    )


class ChatRequest(BaseModel):
    user_id: str = Field(
        ...,
        min_length=1,
        description=(
            "Identificador del usuario. Se usa como thread_id para conservar "
            "la memoria de la conversación."
        ),
        examples=["usuario-123"],
    )
    texto: str = Field(
        ...,
        min_length=1,
        description="Mensaje del usuario que el router debe clasificar.",
        examples=["¿Tienen la polera azul en talla M?"],
    )

    model_config = ConfigDict(
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "user_id": "usuario-123",
                "texto": "¿Tienen la polera azul en talla M?",
            }
        },
    )


class ChatResponse(BaseModel):
    ruta: Literal["preventa", "postventa", "generica"] = Field(
        ...,
        description="Ruta elegida por el router.",
        examples=["preventa"],
    )
    motivo: str = Field(
        ...,
        description="Explicación breve de por qué el router eligió esa ruta.",
        examples=["El usuario pregunta por stock antes de comprar."],
    )
    respuesta: str = Field(
        ...,
        description="Respuesta del agente correspondiente a la ruta elegida.",
        examples=["Soy el agente de preventa. Recibí: ..."],
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "ruta": "preventa",
                "motivo": "El usuario pregunta por stock antes de comprar.",
                "respuesta": (
                    "Soy el agente de preventa. Recibí: ¿Tienen la polera azul "
                    "en talla M?. Pronto podré ayudarte con productos y compras."
                ),
            }
        }
    )


@app.get(
    "/health",
    tags=["salud"],
    response_model=HealthResponse,
    summary="Comprobar el estado del servicio",
    description="Devuelve el estado de la API y el modelo configurado.",
)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post(
    "/chat",
    tags=["chat"],
    response_model=ChatResponse,
    summary="Enviar un mensaje al router",
    description=(
        "Clasifica el mensaje en `preventa`, `postventa` o `generica` y "
        "devuelve la respuesta del agente. La memoria se guarda por `user_id`."
    ),
    responses={
        200: {
            "description": "El router clasificó el mensaje y devolvió la respuesta."
        },
        422: {
            "description": (
                "Body inválido: falta `user_id` o `texto`, o están vacíos."
            )
        },
        502: {
            "description": (
                "El modelo no pudo procesar la petición. El detalle queda en "
                "los logs del servidor."
            )
        },
    },
)
def chat(peticion: ChatRequest, request: Request) -> ChatResponse:
    grafo = request.app.state.grafo

    try:
        estado = grafo.invoke(
            {"messages": [("user", peticion.texto)]},
            config={"configurable": {"thread_id": peticion.user_id}},
        )
        return ChatResponse(
            ruta=estado["ruta"],
            motivo=estado["motivo"],
            respuesta=estado["respuesta"],
        )
    except Exception:
        logger.exception(
            "Error al invocar el router para user_id=%s", peticion.user_id
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "El modelo no pudo procesar el mensaje. "
                "Inténtalo de nuevo más tarde."
            ),
        ) from None


@app.post(
    "/telegram",
    tags=["telegram"],
    include_in_schema=False,
    summary="Webhook de Telegram",
)
async def telegram(
    payload: Annotated[Any, Body()] = None,
) -> dict[str, bool]:
    """Recibe las actualizaciones de Telegram (se completará más adelante)."""
    _ = payload
    return {"ok": True}
