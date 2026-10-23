"""Grafo del agente router.

Clasifica el mensaje y lo deriva a uno de los tres agentes destino. Los agentes
destino son cascarones por ahora. Los prompts viven en prompts.py.
"""

import os
from typing import Annotated, Literal, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field

from src.comun import texto_de_mensaje
from src.router.prompts import (
    PROMPT_GENERICA,
    PROMPT_POSTVENTA,
    PROMPT_PREVENTA,
    PROMPT_ROUTER,
)

MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"


class Decision(BaseModel):
    ruta: Literal["preventa", "postventa", "generica"] = Field(
        description="A qué agente va el mensaje."
    )
    motivo: str = Field(description="Una frase: por qué esa ruta.")


class Estado(TypedDict):
    mensaje: str
    ruta: str
    motivo: str
    respuesta: str
    messages: Annotated[list, add_messages]


def crear_modelo() -> ChatGoogleGenerativeAI:
    """Crea el modelo configurado en la variable de entorno MODELO."""
    return ChatGoogleGenerativeAI(
        model=os.getenv("MODELO") or MODELO_POR_DEFECTO,
        # Temperatura 0 para que el enrutado sea estable en las pruebas.
        temperature=0,
    )


def nodo_router(estado: Estado) -> dict:
    """Clasifica el último mensaje y guarda la ruta y el motivo."""
    mensaje = texto_de_mensaje(estado["messages"][-1])
    modelo = crear_modelo().with_structured_output(Decision)
    decision = modelo.invoke(
        [
            SystemMessage(content=PROMPT_ROUTER),
            HumanMessage(content=mensaje),
        ]
    )
    return {
        "mensaje": mensaje,
        "ruta": decision.ruta,
        "motivo": decision.motivo,
    }


def agente_preventa(estado: Estado) -> dict:
    """Cascarón del agente de preventa."""
    respuesta = PROMPT_PREVENTA.format(mensaje=estado["mensaje"])
    return {"respuesta": respuesta, "messages": [AIMessage(content=respuesta)]}


def agente_postventa(estado: Estado) -> dict:
    """Cascarón del agente de postventa."""
    respuesta = PROMPT_POSTVENTA.format(mensaje=estado["mensaje"])
    return {"respuesta": respuesta, "messages": [AIMessage(content=respuesta)]}


def respuesta_generica(estado: Estado) -> dict:
    """Cascarón para mensajes ajenos a la tienda; no usa el modelo."""
    return {"respuesta": PROMPT_GENERICA, "messages": [AIMessage(content=PROMPT_GENERICA)]}


def decidir_ruta(estado: Estado) -> str:
    """Devuelve la ruta decidida por el nodo router."""
    return estado["ruta"]


def construir_grafo():
    """Compila el grafo con memoria por thread_id."""
    grafo = StateGraph(Estado)
    grafo.add_node("router", nodo_router)
    grafo.add_node("agente_preventa", agente_preventa)
    grafo.add_node("agente_postventa", agente_postventa)
    grafo.add_node("respuesta_generica", respuesta_generica)

    grafo.add_edge(START, "router")
    grafo.add_conditional_edges(
        "router",
        decidir_ruta,
        {
            "preventa": "agente_preventa",
            "postventa": "agente_postventa",
            "generica": "respuesta_generica",
        },
    )
    grafo.add_edge("agente_preventa", END)
    grafo.add_edge("agente_postventa", END)
    grafo.add_edge("respuesta_generica", END)

    return grafo.compile(checkpointer=MemorySaver())
