"""Pruebas de las herramientas del agente de ecommerce."""

from src.ecommerce.tools import buscar_productos, consultar_pedido


def test_consultar_pedido_existente():
    respuesta = consultar_pedido.invoke({"numero_pedido": "1001"})
    assert "enviado" in respuesta
    assert "1001" in respuesta


def test_consultar_pedido_inexistente():
    respuesta = consultar_pedido.invoke({"numero_pedido": "9999"})
    assert "No existe" in respuesta


def test_buscar_productos_por_categoria():
    respuesta = buscar_productos.invoke({"consulta": "audio"})
    assert "Auriculares" in respuesta


def test_buscar_productos_sin_resultados():
    respuesta = buscar_productos.invoke({"consulta": "ordenador cuántico"})
    assert "No hay productos" in respuesta
