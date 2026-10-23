"""Pruebas del agente router.

Incluye pruebas offline con un modelo falso y una prueba de integración con
los 15 casos de tests/casos_router.json. El modelo no es determinista, así que
la integración exige un mínimo de 13 aciertos de 15.
"""

import json
import os
import time
from pathlib import Path
from uuid import uuid4

import pytest
from dotenv import load_dotenv

from src.router import graph as router_graph
from src.router.graph import Decision, construir_grafo

RAIZ = Path(__file__).resolve().parents[1]
load_dotenv(RAIZ / ".env")

RUTA_CASOS = RAIZ / "tests" / "casos_router.json"
CASOS: list[dict[str, str]] = json.loads(RUTA_CASOS.read_text(encoding="utf-8"))
MINIMO_ACIERTOS = 13


class ModeloFalso:
    """Sustituto del LLM que devuelve siempre la decisión indicada."""

    def __init__(self, decision: Decision) -> None:
        self.decision = decision

    def with_structured_output(self, schema):
        assert schema is Decision
        return self

    def invoke(self, mensajes):
        return self.decision


def _grafo_con(monkeypatch, ruta: str, motivo: str = "motivo de prueba"):
    monkeypatch.setattr(
        router_graph,
        "crear_modelo",
        lambda: ModeloFalso(Decision(ruta=ruta, motivo=motivo)),
    )
    return construir_grafo()


@pytest.mark.parametrize(
    ("ruta", "mensaje", "fragmento"),
    [
        ("preventa", "¿tienen la polera azul?", "Soy el agente de preventa"),
        ("postventa", "mi pedido llegó roto", "Soy el agente de postventa"),
        ("generica", "¿qué hora es en Tokio?", "Este chat es para ayudarte con la tienda"),
    ],
)
def test_enruta_al_agente_correcto(monkeypatch, ruta, mensaje, fragmento):
    grafo = _grafo_con(monkeypatch, ruta)
    estado = grafo.invoke(
        {"messages": [("user", mensaje)]},
        config={"configurable": {"thread_id": f"test-{ruta}"}},
    )

    assert estado["ruta"] == ruta
    assert estado["motivo"] == "motivo de prueba"
    assert fragmento in estado["respuesta"]


def test_memoria_por_thread_id(monkeypatch):
    grafo = _grafo_con(monkeypatch, "generica")
    config = {"configurable": {"thread_id": "memoria"}}

    grafo.invoke({"messages": [("user", "hola")]}, config=config)
    estado = grafo.invoke({"messages": [("user", "otra vez")]}, config=config)

    # Dos turnos: mensaje del usuario + respuesta del agente en cada uno.
    assert len(estado["messages"]) == 4


def test_el_grafo_tiene_los_nodos_esperados():
    grafo = construir_grafo()
    nodos = set(grafo.get_graph().nodes)
    assert {
        "router",
        "agente_preventa",
        "agente_postventa",
        "respuesta_generica",
    } <= nodos


def test_casos_json_son_15_y_5_por_ruta():
    assert len(CASOS) == 15
    for ruta in ("preventa", "postventa", "generica"):
        assert sum(1 for caso in CASOS if caso["esperado"] == ruta) == 5


def test_casos_json_incluyen_los_dificiles():
    mensajes = {caso["mensaje"] for caso in CASOS}
    assert "¿cuándo llega lo que compré ayer?" in mensajes
    assert "qué caro, ¿hay descuento?" in mensajes
    assert "buenas tardes" in mensajes
    assert "tengo un problema con una polera" in mensajes


def _invocar_router(grafo, mensaje: str, intentos: int = 2):
    """Invoca el router con reintentos y un thread_id nuevo por intento."""
    for intento in range(intentos + 1):
        config = {"configurable": {"thread_id": f"pytest-router-{uuid4()}"}}
        try:
            return grafo.invoke(
                {"messages": [("user", mensaje)]},
                config=config,
            )
        except Exception:
            if intento >= intentos:
                raise
            time.sleep(2**intento)


@pytest.fixture(scope="module")
def resultados_router() -> list[dict[str, str]]:
    """Ejecuta los 15 casos una sola vez contra el router real."""
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        pytest.skip("Requiere GOOGLE_API_KEY o GEMINI_API_KEY para el router real.")

    grafo = construir_grafo()
    resultados: list[dict[str, str]] = []

    for caso in CASOS:
        try:
            estado = _invocar_router(grafo, caso["mensaje"])
            obtenido = estado.get("ruta", "")
            motivo = estado.get("motivo", "")
        except Exception as exc:
            obtenido = "error"
            motivo = f"ERROR: {exc}"

        resultados.append(
            {
                "mensaje": caso["mensaje"],
                "esperado": caso["esperado"],
                "obtenido": obtenido,
                "motivo": motivo,
            }
        )

    return resultados


@pytest.mark.parametrize(
    "caso",
    CASOS,
    ids=[f"{indice:02d}-{caso['esperado']}" for indice, caso in enumerate(CASOS, start=1)],
)
def test_router_caso_real(caso, resultados_router):
    """Comprueba un caso; los fallos se toleran hasta el umbral global."""
    resultado = next(
        item for item in resultados_router if item["mensaje"] == caso["mensaje"]
    )

    if resultado["obtenido"] != caso["esperado"]:
        pytest.xfail(
            f"Ruta obtenida: {resultado['obtenido']}. "
            f"Se permiten hasta {len(CASOS) - MINIMO_ACIERTOS} fallos. "
            f"Motivo: {resultado['motivo']}"
        )

    assert resultado["obtenido"] == caso["esperado"]


def test_router_minimo_13_de_15(resultados_router):
    """El conjunto debe acertar al menos 13 de los 15 casos."""
    aciertos = sum(
        1
        for resultado in resultados_router
        if resultado["obtenido"] == resultado["esperado"]
    )
    fallados = [
        resultado["mensaje"]
        for resultado in resultados_router
        if resultado["obtenido"] != resultado["esperado"]
    ]

    assert aciertos >= MINIMO_ACIERTOS, (
        f"Solo {aciertos}/{len(resultados_router)} aciertos; "
        f"se exigen al menos {MINIMO_ACIERTOS}. Fallados: {fallados}"
    )
