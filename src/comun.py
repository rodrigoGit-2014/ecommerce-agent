"""Utilidades compartidas por la CLI y la API."""

from langchain_core.messages import BaseMessage


def texto_de_mensaje(mensaje: BaseMessage | str) -> str:
    """Extrae el texto de un mensaje, sea str, AIMessage o bloques de contenido."""
    if isinstance(mensaje, str):
        return mensaje

    contenido = mensaje.content
    if isinstance(contenido, str):
        return contenido

    partes: list[str] = []
    for bloque in contenido:
        if isinstance(bloque, str):
            partes.append(bloque)
        elif isinstance(bloque, dict):
            texto = bloque.get("text")
            if isinstance(texto, str) and texto:
                partes.append(texto)
    return "\n".join(partes).strip()
