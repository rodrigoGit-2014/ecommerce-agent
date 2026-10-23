#!/usr/bin/env python3
"""Ejecuta los casos de tests/casos_router.json contra el router real.

Uso (desde la raíz del proyecto):
    python scripts/test_router.py

Muestra una tabla con el resultado de cada caso y termina con el total de
aciertos. El código de salida es 0 si se alcanza el mínimo de 13/15.
"""

import json
import os
import sys
from itertools import zip_longest
from pathlib import Path
from textwrap import wrap
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv

load_dotenv(RAIZ / ".env")

from src.router.graph import construir_grafo  # noqa: E402

RUTA_CASOS = RAIZ / "tests" / "casos_router.json"
MINIMO_ACIERTOS = 13
ANCHO_MENSAJE = 44
ANCHO_MOTIVO = 70


def cargar_casos() -> list[dict[str, str]]:
    """Carga y valida el JSON de casos."""
    datos = json.loads(RUTA_CASOS.read_text(encoding="utf-8"))
    if not isinstance(datos, list) or not datos:
        raise ValueError(f"{RUTA_CASOS} debe contener una lista de casos.")

    for indice, caso in enumerate(datos, start=1):
        if not isinstance(caso, dict) or not {"mensaje", "esperado"} <= caso.keys():
            raise ValueError(f"El caso {indice} debe tener 'mensaje' y 'esperado'.")
    return datos


def dividir(texto: str, ancho: int) -> list[str]:
    """Divide un texto en líneas del ancho indicado."""
    return wrap(" ".join(texto.split()), width=ancho) or [""]


def mostrar_tabla(filas: list[dict[str, str]]) -> None:
    """Imprime la tabla de resultados, con motivos completos en varias líneas."""
    print(
        f"{'MENSAJE':<{ANCHO_MENSAJE}} "
        f"{'ESPERADO':<10} {'OBTENIDO':<10} {'✔/✘':<4} MOTIVO"
    )
    print("-" * (ANCHO_MENSAJE + 10 + 10 + 4 + ANCHO_MOTIVO + 4))

    for fila in filas:
        marca = "✔" if fila["ok"] else "✘"
        lineas_mensaje = dividir(fila["mensaje"], ANCHO_MENSAJE)
        lineas_motivo = dividir(fila["motivo"], ANCHO_MOTIVO)

        for indice, (mensaje, motivo) in enumerate(
            zip_longest(lineas_mensaje, lineas_motivo, fillvalue="")
        ):
            if indice == 0:
                print(
                    f"{mensaje:<{ANCHO_MENSAJE}} "
                    f"{fila['esperado']:<10} {fila['obtenido']:<10} "
                    f"{marca:<4} {motivo}"
                )
            else:
                print(
                    f"{mensaje:<{ANCHO_MENSAJE}} "
                    f"{'':<10} {'':<10} {'':<4} {motivo}"
                )


def main() -> int:
    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        print(
            "Error: falta GOOGLE_API_KEY. Copia .env.example a .env y añade tu clave.",
            file=sys.stderr,
        )
        return 1

    try:
        casos = cargar_casos()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error al leer los casos: {exc}", file=sys.stderr)
        return 1

    grafo = construir_grafo()
    filas: list[dict[str, str]] = []

    for caso in casos:
        config = {"configurable": {"thread_id": f"cli-router-{uuid4()}"}}
        try:
            estado = grafo.invoke(
                {"messages": [("user", caso["mensaje"])]},
                config=config,
            )
            obtenido = estado.get("ruta", "")
            motivo = estado.get("motivo", "")
        except Exception as exc:
            obtenido = "error"
            motivo = f"ERROR: {exc}"

        filas.append(
            {
                "mensaje": caso["mensaje"],
                "esperado": caso["esperado"],
                "obtenido": obtenido,
                "motivo": motivo,
                "ok": obtenido == caso["esperado"],
            }
        )

    mostrar_tabla(filas)

    total = len(filas)
    aciertos = sum(1 for fila in filas if fila["ok"])
    porcentaje = (aciertos / total * 100) if total else 0
    fallos = [fila for fila in filas if not fila["ok"]]

    print()
    print(f"Aciertos: {aciertos}/{total} ({porcentaje:.1f}%)")
    print(f"Umbral mínimo: {MINIMO_ACIERTOS}/{total}")

    if fallos:
        print("\nCasos fallados:")
        for fila in fallos:
            print(f"- «{fila['mensaje']}»")
            print(f"  esperado: {fila['esperado']} | obtenido: {fila['obtenido']}")
            print(f"  motivo: {fila['motivo'] or '(vacío)'}")
    else:
        print("\nSin fallos.")

    return 0 if aciertos >= MINIMO_ACIERTOS else 1


if __name__ == "__main__":
    raise SystemExit(main())
