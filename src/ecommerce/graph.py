"""Grafo del agente de ecommerce.

Aquí solo se construye el grafo y se orquesta el flujo. Los prompts viven en
prompts.py y las herramientas en tools.py.
"""

import os
from typing import Annotated, TypedDict

from langchain_core.messages import SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from src.ecommerce.prompts import PROMPT_AGENTE
from src.ecommerce.tools import HERRAMIENTAS

MODELO_POR_DEFECTO = "gemini-3.5-flash-lite"


class Estado(TypedDict):
    messages: Annotated[list, add_messages]


def crear_modelo() -> ChatGoogleGenerativeAI:
    """Crea el modelo configurado en la variable de entorno MODELO."""
    return ChatGoogleGenerativeAI(
        model=os.getenv("MODELO") or MODELO_POR_DEFECTO,
        temperature=0,
    )


def nodo_agente(estado: Estado) -> dict:
    """Nodo conversacional: decide si responde o llama a una herramienta."""
    modelo = crear_modelo().bind_tools(HERRAMIENTAS)
    mensajes = [SystemMessage(content=PROMPT_AGENTE), *estado["messages"]]
    return {"messages": [modelo.invoke(mensajes)]}


def construir_grafo():
    """Compila y devuelve el grafo del agente."""
    grafo = StateGraph(Estado)
    grafo.add_node("agente", nodo_agente)
    grafo.add_node("herramientas", ToolNode(HERRAMIENTAS))

    grafo.add_edge(START, "agente")
    grafo.add_conditional_edges(
        "agente",
        tools_condition,
        {"tools": "herramientas", END: END},
    )
    grafo.add_edge("herramientas", "agente")

    return grafo.compile()
