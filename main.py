#!/usr/bin/env python3
"""CLI para ejecutar los agentes del proyecto desde la raíz."""

import argparse
import importlib
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.messages import AIMessage

from src.comun import texto_de_mensaje

RAIZ = Path(__file__).resolve().parent
load_dotenv(RAIZ / ".env")


def agentes_disponibles() -> list[str]:
    """Devuelve los agentes con graph.py dentro de src/."""
    carpeta = RAIZ / "src"
    if not carpeta.is_dir():
        return []
    return sorted(
        ruta.name
        for ruta in carpeta.iterdir()
        if ruta.is_dir()
        and not ruta.name.startswith(("_", "."))
        and (ruta / "graph.py").is_file()
    )


def cargar_grafo(nombre: str):
    """Importa y compila el grafo del agente indicado."""
    modulo = importlib.import_module(f"src.{nombre}.graph")
    constructor = getattr(modulo, "construir_grafo", None)
    if constructor is None:
        raise AttributeError(
            f"El agente '{nombre}' no define construir_grafo() en src/{nombre}/graph.py."
        )
    return constructor()


def ejecutar(
    grafo,
    mensaje: str,
    mostrar_saltos: bool,
    thread_id: str = "default",
) -> None:
    """Ejecuta el grafo e imprime la respuesta (y los nodos si se pide)."""
    entrada = {"messages": [("user", mensaje)]}
    config = {"configurable": {"thread_id": thread_id}}

    if not mostrar_saltos:
        estado = grafo.invoke(entrada, config=config)
        print(_texto_de_estado(estado))
        return

    pasos: list[str] = []
    respuesta = ""
    ruta = ""
    motivo = ""

    for actualizacion in grafo.stream(entrada, config=config, stream_mode="updates"):
        for nodo, cambios in actualizacion.items():
            pasos.append(nodo)
            print(f"[nodo] {nodo}")
            if not cambios:
                continue
            if cambios.get("ruta"):
                ruta = cambios["ruta"]
            if cambios.get("motivo"):
                motivo = cambios["motivo"]
            if cambios.get("respuesta"):
                respuesta = cambios["respuesta"]
            for item in cambios.get("messages", []):
                if isinstance(item, AIMessage) and not respuesta:
                    respuesta = texto_de_mensaje(item)

    if ruta:
        print(" → ".join(pasos))
        if motivo:
            print(f"motivo: {motivo}")
    if respuesta:
        print(respuesta)


def _texto_de_estado(estado: dict) -> str:
    if estado.get("respuesta"):
        return estado["respuesta"]
    return texto_de_mensaje(estado["messages"][-1])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta un agente del proyecto.",
        epilog='Ejemplo: python main.py ecommerce "¿Dónde está mi pedido 1001?"',
    )
    parser.add_argument("agente", nargs="?", help="Nombre del agente en src/")
    parser.add_argument("mensaje", nargs="?", help="Mensaje para el agente")
    parser.add_argument(
        "--saltos",
        action="store_true",
        help="Imprime los nodos por los que pasa el grafo.",
    )
    parser.add_argument(
        "--diagrama",
        action="store_true",
        help="Imprime el Mermaid del grafo sin ejecutarlo.",
    )
    parser.add_argument(
        "--thread-id",
        default="default",
        help="Identificador de conversación para la memoria (por defecto: default).",
    )
    args = parser.parse_args()

    disponibles = agentes_disponibles()

    if not args.agente:
        parser.print_help()
        if disponibles:
            print(f"\nAgentes disponibles: {', '.join(disponibles)}")
        return 1

    if args.agente not in disponibles:
        print(
            f"Error: no existe el agente '{args.agente}'. "
            f"Disponibles: {', '.join(disponibles) or 'ninguno'}.",
            file=sys.stderr,
        )
        return 1

    try:
        grafo = cargar_grafo(args.agente)
    except Exception as exc:
        print(f"Error al cargar el agente '{args.agente}': {exc}", file=sys.stderr)
        return 1

    if args.diagrama:
        print(grafo.get_graph().draw_mermaid())
        return 0

    if not args.mensaje:
        print("Error: falta el mensaje.", file=sys.stderr)
        return 1

    if not os.getenv("GOOGLE_API_KEY"):
        print(
            "Error: falta GOOGLE_API_KEY. Copia .env.example a .env y añade tu clave.",
            file=sys.stderr,
        )
        return 1

    try:
        ejecutar(grafo, args.mensaje, args.saltos, args.thread_id)
    except Exception as exc:
        print(f"Error al ejecutar el agente: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
