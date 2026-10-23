"""Herramientas del agente de ecommerce.

Los datos son de ejemplo y viven en memoria. Sustitúyelos por una base de
datos o una API real cuando el proyecto avance.
"""

from langchain_core.tools import tool

PEDIDOS: dict[str, dict[str, str]] = {
    "1001": {
        "estado": "enviado",
        "transportista": "MRW",
        "entrega_estimada": "2026-10-25",
    },
    "1002": {
        "estado": "en preparación",
        "transportista": "Correos",
        "entrega_estimada": "2026-10-28",
    },
}

PRODUCTOS: list[dict[str, str]] = [
    {"nombre": "Auriculares inalámbricos", "categoria": "audio", "precio": "49.90 €"},
    {"nombre": "Teclado mecánico", "categoria": "informática", "precio": "79.00 €"},
    {"nombre": "Mochila urbana", "categoria": "accesorios", "precio": "34.50 €"},
]


@tool
def consultar_pedido(numero_pedido: str) -> str:
    """Consulta el estado de un pedido por su número (por ejemplo, 1001)."""
    pedido = PEDIDOS.get(numero_pedido.strip())
    if pedido is None:
        return f"No existe ningún pedido con el número {numero_pedido}."
    return (
        f"Pedido {numero_pedido}: estado {pedido['estado']}, "
        f"transportista {pedido['transportista']}, "
        f"entrega estimada {pedido['entrega_estimada']}."
    )


@tool
def buscar_productos(consulta: str) -> str:
    """Busca productos del catálogo por nombre o categoría."""
    termino = consulta.strip().lower()
    encontrados = [
        producto
        for producto in PRODUCTOS
        if termino in producto["nombre"].lower() or termino in producto["categoria"].lower()
    ]
    if not encontrados:
        return f"No hay productos que coincidan con «{consulta}»."
    return "\n".join(
        f"- {producto['nombre']} ({producto['categoria']}): {producto['precio']}"
        for producto in encontrados
    )


HERRAMIENTAS = [consultar_pedido, buscar_productos]
