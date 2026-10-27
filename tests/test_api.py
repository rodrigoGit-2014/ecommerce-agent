"""Pruebas de la API FastAPI con un grafo falso (sin llamar a Gemini)."""

import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

import api.app as api_app
from api.app import app, enviar_mensaje_telegram

RESPUESTA_FALSA = {
    "ruta": "preventa",
    "motivo": "El usuario pregunta por stock antes de comprar.",
    "respuesta": "Soy el agente de preventa. Recibí: ¿Tienen stock?.",
}

SECRETO = "secreto-de-prueba"
CABECERA_SECRETO = {"X-Telegram-Bot-Api-Secret-Token": SECRETO}


class GrafoFalso:
    """Grafo de prueba que registra las llamadas y devuelve una ruta fija."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.llamadas: list[dict] = []

    def invoke(self, entrada, config):
        self.llamadas.append({"entrada": entrada, "config": config})
        if self.error is not None:
            raise self.error
        return dict(RESPUESTA_FALSA)


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as cliente:
        yield cliente


def test_health(cliente):
    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_el_grafo_se_compila_al_arrancar(cliente):
    assert app.state.grafo is not None


def test_chat_invoca_el_router_con_user_id_como_thread_id(cliente, monkeypatch):
    grafo = GrafoFalso()
    monkeypatch.setattr(app.state, "grafo", grafo)

    respuesta = cliente.post(
        "/chat",
        json={"user_id": "usuario-42", "texto": "¿Tienen stock?"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == RESPUESTA_FALSA
    assert grafo.llamadas == [
        {
            "entrada": {"messages": [("user", "¿Tienen stock?")]},
            "config": {"configurable": {"thread_id": "usuario-42"}},
        }
    ]


@pytest.mark.parametrize(
    "cuerpo",
    [
        {},
        {"texto": "hola"},
        {"user_id": "usuario-1"},
        {"user_id": "usuario-1", "texto": "   "},
    ],
)
def test_chat_valida_el_body(cliente, cuerpo):
    respuesta = cliente.post("/chat", json=cuerpo)
    assert respuesta.status_code == 422


def test_chat_devuelve_502_sin_filtrar_detalles(cliente, monkeypatch, caplog):
    error = RuntimeError("fallo interno con detalle sensible")
    monkeypatch.setattr(app.state, "grafo", GrafoFalso(error=error))

    with caplog.at_level(logging.ERROR, logger="api.app"):
        respuesta = cliente.post(
            "/chat",
            json={"user_id": "usuario-1", "texto": "hola"},
        )

    assert respuesta.status_code == 502
    assert respuesta.json() == {
        "detail": (
            "El modelo no pudo procesar el mensaje. "
            "Inténtalo de nuevo más tarde."
        )
    }
    assert "detalle sensible" not in respuesta.text
    assert "Traceback" not in respuesta.text
    assert "detalle sensible" in caplog.text


@pytest.mark.parametrize(
    "cabeceras",
    [
        {},
        {"X-Telegram-Bot-Api-Secret-Token": "otro-secreto"},
    ],
)
def test_telegram_rechaza_el_secreto_invalido(cliente, monkeypatch, cabeceras):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)

    respuesta = cliente.post(
        "/telegram",
        json={"update_id": 1, "message": {"chat": {"id": 1}, "text": "hola"}},
        headers=cabeceras,
    )

    assert respuesta.status_code == 403


def test_telegram_rechaza_si_no_hay_secreto_configurado(cliente, monkeypatch):
    monkeypatch.delenv("TELEGRAM_SECRET", raising=False)

    respuesta = cliente.post(
        "/telegram",
        json={"update_id": 1, "message": {"chat": {"id": 1}, "text": "hola"}},
        headers=CABECERA_SECRETO,
    )

    assert respuesta.status_code == 403


@pytest.mark.parametrize(
    "payload",
    [
        {"update_id": 1},
        {"update_id": 2, "message": {"chat": {"id": 99}}},
        {"update_id": 3, "message": {"chat": {"id": 99}, "text": "   "}},
        {"update_id": 4, "edited_message": {"chat": {"id": 99}, "text": "hola"}},
        {"update_id": 5, "message": {"text": "hola"}},
        [1, 2, 3],
    ],
)
def test_telegram_ignora_updates_sin_texto(cliente, monkeypatch, payload):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    grafo = GrafoFalso()
    monkeypatch.setattr(app.state, "grafo", grafo)
    enviados: list[tuple[int | str, str]] = []

    async def enviar_falso(chat_id, texto):
        enviados.append((chat_id, texto))

    monkeypatch.setattr(api_app, "enviar_mensaje_telegram", enviar_falso)

    respuesta = cliente.post("/telegram", json=payload, headers=CABECERA_SECRETO)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    assert grafo.llamadas == []
    assert enviados == []


def test_telegram_invoca_el_grafo_y_responde_al_chat(cliente, monkeypatch):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    grafo = GrafoFalso()
    monkeypatch.setattr(app.state, "grafo", grafo)
    enviados: list[tuple[int | str, str]] = []

    async def enviar_falso(chat_id, texto):
        enviados.append((chat_id, texto))

    monkeypatch.setattr(api_app, "enviar_mensaje_telegram", enviar_falso)

    respuesta = cliente.post(
        "/telegram",
        json={
            "update_id": 10,
            "message": {
                "message_id": 1,
                "chat": {"id": 123456, "type": "private"},
                "text": "mi pedido 4521 llegó roto",
            },
        },
        headers=CABECERA_SECRETO,
    )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    assert grafo.llamadas == [
        {
            "entrada": {"messages": [("user", "mi pedido 4521 llegó roto")]},
            "config": {"configurable": {"thread_id": "123456"}},
        }
    ]
    assert enviados == [(123456, RESPUESTA_FALSA["respuesta"])]


def test_telegram_responde_200_si_el_grafo_falla(cliente, monkeypatch, caplog):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    monkeypatch.setattr(
        app.state, "grafo", GrafoFalso(error=RuntimeError("fallo del modelo"))
    )
    enviados: list[tuple[int | str, str]] = []

    async def enviar_falso(chat_id, texto):
        enviados.append((chat_id, texto))

    monkeypatch.setattr(api_app, "enviar_mensaje_telegram", enviar_falso)

    with caplog.at_level(logging.ERROR, logger="api.app"):
        respuesta = cliente.post(
            "/telegram",
            json={
                "update_id": 11,
                "message": {"chat": {"id": 7}, "text": "hola"},
            },
            headers=CABECERA_SECRETO,
        )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    assert enviados == []
    assert "fallo del modelo" in caplog.text


def test_telegram_responde_200_si_sendmessage_falla(cliente, monkeypatch, caplog):
    monkeypatch.setenv("TELEGRAM_SECRET", SECRETO)
    monkeypatch.setattr(app.state, "grafo", GrafoFalso())

    async def enviar_roto(chat_id, texto):
        raise RuntimeError("Telegram no responde")

    monkeypatch.setattr(api_app, "enviar_mensaje_telegram", enviar_roto)

    with caplog.at_level(logging.ERROR, logger="api.app"):
        respuesta = cliente.post(
            "/telegram",
            json={
                "update_id": 12,
                "message": {"chat": {"id": 7}, "text": "hola"},
            },
            headers=CABECERA_SECRETO,
        )

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}
    assert "Telegram no responde" in caplog.text


class RespuestaHTTPFalsa:
    status_code = 200

    def raise_for_status(self) -> None:
        return None


def test_enviar_mensaje_telegram_usa_sendmessage(cliente, monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "token-de-prueba")
    registro: list[tuple[str, dict]] = []

    class ClienteFalso:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json):
            registro.append((url, json))
            return RespuestaHTTPFalsa()

    monkeypatch.setattr(api_app.httpx, "AsyncClient", ClienteFalso)

    asyncio.run(enviar_mensaje_telegram(123456, "Hola desde el bot"))

    assert registro == [
        (
            "https://api.telegram.org/bottoken-de-prueba/sendMessage",
            {"chat_id": 123456, "text": "Hola desde el bot"},
        )
    ]


def test_enviar_mensaje_telegram_sin_token_no_hace_red(
    cliente, monkeypatch, caplog
):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)

    class ClienteProhibido:
        def __init__(self, **kwargs):
            raise AssertionError("no debería crear el cliente HTTP")

    monkeypatch.setattr(api_app.httpx, "AsyncClient", ClienteProhibido)

    with caplog.at_level(logging.ERROR, logger="api.app"):
        asyncio.run(enviar_mensaje_telegram(123456, "Hola"))

    assert "TELEGRAM_TOKEN no está configurado" in caplog.text


def test_openapi_tiene_titulo_tags_y_respuestas_documentadas(cliente):
    openapi = cliente.get("/openapi.json").json()

    assert openapi["info"]["title"] == "Ecommerce Router API"
    assert openapi["info"]["version"] == "1.0.0"
    assert "preventa" in openapi["info"]["description"]
    assert "postventa" in openapi["info"]["description"]
    assert "generica" in openapi["info"]["description"]
    assert {tag["name"] for tag in openapi["tags"]} == {
        "salud",
        "chat",
        "telegram",
    }

    assert "/telegram" not in openapi["paths"]
    chat = openapi["paths"]["/chat"]["post"]
    assert chat["tags"] == ["chat"]
    assert {"200", "422", "502"} <= set(chat["responses"])
    assert "Body inválido" in chat["responses"]["422"]["description"]

    request = openapi["components"]["schemas"]["ChatRequest"]
    assert request["example"] == {
        "user_id": "usuario-123",
        "texto": "¿Tienen la polera azul en talla M?",
    }
    assert request["properties"]["user_id"]["description"]
    assert request["properties"]["texto"]["description"]

    response = openapi["components"]["schemas"]["ChatResponse"]
    assert response["example"]["ruta"] == "preventa"
    assert response["properties"]["motivo"]["description"]
    assert response["properties"]["respuesta"]["description"]
