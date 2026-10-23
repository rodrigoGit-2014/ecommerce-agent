"""Pruebas de la API FastAPI con un grafo falso (sin llamar a Gemini)."""

import logging

import pytest
from fastapi.testclient import TestClient

from api.app import app

RESPUESTA_FALSA = {
    "ruta": "preventa",
    "motivo": "El usuario pregunta por stock antes de comprar.",
    "respuesta": "Soy el agente de preventa. Recibí: ¿Tienen stock?.",
}


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
    "payload",
    [
        {"update_id": 1},
        {"message": {"text": "hola"}},
        [1, 2, 3],
    ],
)
def test_telegram_acepta_cualquier_json(cliente, payload):
    respuesta = cliente.post("/telegram", json=payload)

    assert respuesta.status_code == 200
    assert respuesta.json() == {"ok": True}


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
