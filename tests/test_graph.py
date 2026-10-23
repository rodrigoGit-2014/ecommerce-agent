"""Pruebas del grafo del agente de ecommerce."""

from src.ecommerce.graph import construir_grafo


def test_el_grafo_tiene_los_nodos_esperados():
    grafo = construir_grafo()
    nodos = set(grafo.get_graph().nodes)
    assert {"agente", "herramientas"} <= nodos


def test_el_diagrama_mermaid_incluye_los_nodos():
    grafo = construir_grafo()
    diagrama = grafo.get_graph().draw_mermaid()
    assert "agente" in diagrama
    assert "herramientas" in diagrama
