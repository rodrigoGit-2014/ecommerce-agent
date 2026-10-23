#!/usr/bin/env python3
"""Prueba el enrutado del agente router con todos los escenarios previstos.

Uso (desde la raíz del proyecto):
    python scripts/probar_router.py
    python scripts/probar_router.py --ruta preventa -v
    python scripts/probar_router.py --pausa 0.5

Cada caso usa un thread_id nuevo para no mezclar memoria. El script termina
con código 1 si algún caso falla.
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from uuid import uuid4

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv

load_dotenv(RAIZ / ".env")

from src.comun import texto_de_mensaje  # noqa: E402
from src.router.graph import construir_grafo  # noqa: E402

Ruta = Literal["preventa", "postventa", "generica"]

PREFIJOS_RESPUESTA = {
    "preventa": "Soy el agente de preventa.",
    "postventa": "Soy el agente de postventa.",
    "generica": "Este chat es para ayudarte con la tienda",
}


@dataclass(frozen=True)
class Caso:
    mensaje: str
    esperada: Ruta
    borde: bool = False


CASOS: tuple[Caso, ...] = (
    # --- Preventa: productos, precios, stock y recomendaciones ---
    Caso("¿tienen la polera azul en talla M?", "preventa"),
    Caso("¿Les queda stock del teclado mecánico?", "preventa"),
    Caso("¿Cuánto cuesta la mochila urbana?", "preventa"),
    Caso("¿Qué auriculares me recomiendan para correr?", "preventa"),
    Caso("¿La chaqueta es impermeable?", "preventa"),
    Caso("Quiero comprar un regalo para mi hermano.", "preventa"),
    # --- Preventa: promociones, pago y envío antes de comprar ---
    Caso("¿Hay descuentos por primera compra?", "preventa"),
    Caso("¿Aceptan pago con transferencia?", "preventa"),
    Caso("¿Puedo pagar contra entrega?", "preventa"),
    Caso("¿Tienen envío gratis?", "preventa"),
    Caso("¿Cuánto cuesta y cuánto demora el envío a Valparaíso?", "preventa"),
    Caso("¿Venden tarjetas de regalo?", "preventa"),
    # --- Postventa: pedidos existentes, daños y seguimiento ---
    Caso("mi pedido 4521 llegó roto", "postventa"),
    Caso("¿Dónde está mi pedido 4521?", "postventa"),
    Caso("Mi pedido lleva dos semanas sin llegar y nadie me responde.", "postventa"),
    Caso("Recibí el color equivocado.", "postventa"),
    Caso("Falta un artículo en el paquete que recibí.", "postventa"),
    Caso("Quiero actualizar la dirección de entrega de mi pedido.", "postventa"),
    # --- Postventa: devoluciones, cambios, garantía y reembolsos ---
    Caso("quiero devolver unas zapatillas", "postventa"),
    Caso("Quiero cambiar la polera que compré por una talla L.", "postventa"),
    Caso("El producto que recibí está defectuoso, ¿aplica garantía?", "postventa"),
    Caso("Me cobraron dos veces por mi compra.", "postventa"),
    Caso("Quiero cancelar el pedido 7788.", "postventa"),
    Caso("¿Cómo va el reembolso de mi devolución?", "postventa"),
    Caso("Compré unas zapatillas y quiero saber la política de devoluciones.", "postventa"),
    # --- Genérica: saludos y temas ajenos a la tienda ---
    Caso("hola", "generica"),
    Caso("Buenos días, ¿cómo estás?", "generica"),
    Caso("Gracias, eso era todo.", "generica"),
    Caso("¿Qué hora es en Tokio?", "generica"),
    Caso("Cuéntame un chiste.", "generica"),
    Caso("¿Va a llover mañana en Santiago?", "generica"),
    Caso("¿Cuánto es 17 por 23?", "generica"),
    Caso("¿Quién ganó el mundial de fútbol?", "generica"),
    Caso("Escríbeme un poema sobre el mar.", "generica"),
    Caso("¿Eres un bot?", "generica"),
    # --- Casos límite: mezcla de saludo, compra previa y ambigüedad ---
    Caso("Hola, ¿tienen stock de la polera azul?", "preventa", borde=True),
    Caso("Hola, mi pedido llegó roto.", "postventa", borde=True),
    Caso("Vi una promo en Instagram, ¿sigue vigente?", "preventa", borde=True),
    Caso("No puedo completar mi compra, ¿me ayudan?", "preventa", borde=True),
    # Sin compra previa: es una condición antes de comprar, no una devolución.
    Caso("¿Cuál es la política de devoluciones?", "preventa", borde=True),
    Caso("Mi pedido 4521.", "postventa", borde=True),
)


@dataclass
class Resultado:
    caso: Caso
    ruta: str
    motivo: str
    respuesta: str
    problemas: list[str]

    @property
    def ok(self) -> bool:
        return not self.problemas


def ejecutar_caso(grafo, caso: Caso, reintentos: int) -> Resultado:
    """Invoca el grafo con un thread_id aislado y valida el estado final."""
    config = {"configurable": {"thread_id": f"prueba-{uuid4()}"}}

    for intento in range(reintentos + 1):
        try:
            estado = grafo.invoke(
                {"messages": [("user", caso.mensaje)]},
                config=config,
            )
            break
        except Exception as exc:
            if intento >= reintentos:
                raise
            espera = 2**intento
            print(
                f"  Reintento {intento + 1}/{reintentos} en {espera}s: {exc}",
                file=sys.stderr,
            )
            time.sleep(espera)

    ruta = estado.get("ruta", "")
    motivo = estado.get("motivo", "")
    respuesta = estado.get("respuesta") or texto_de_mensaje(estado["messages"][-1])

    problemas: list[str] = []
    if ruta != caso.esperada:
        problemas.append(f"ruta esperada '{caso.esperada}', obtenida '{ruta}'")
    if not motivo.strip():
        problemas.append("motivo vacío")
    if PREFIJOS_RESPUESTA[caso.esperada] not in respuesta:
        problemas.append("la respuesta no corresponde al agente elegido")
    if len(estado.get("messages", [])) != 2:
        problemas.append("el estado no contiene el mensaje y la respuesta")

    return Resultado(caso, ruta, motivo, respuesta, problemas)


def probar_memoria(grafo, reintentos: int) -> tuple[bool, str]:
    """Comprueba que dos turnos del mismo thread_id acumulan mensajes."""
    for intento in range(reintentos + 1):
        config = {"configurable": {"thread_id": f"memoria-{uuid4()}"}}
        try:
            grafo.invoke(
                {"messages": [("user", "hola")]},
                config=config,
            )
            estado = grafo.invoke(
                {"messages": [("user", "¿qué hora es en Tokio?")]},
                config=config,
            )
            break
        except Exception as exc:
            if intento >= reintentos:
                return False, f"error al invocar el grafo: {exc}"
            print(
                f"  Reintento de memoria en {intento + 1}s: {exc}",
                file=sys.stderr,
            )
            time.sleep(intento + 1)

    cantidad = len(estado.get("messages", []))
    if cantidad != 4:
        return False, f"se esperaban 4 mensajes tras dos turnos, hay {cantidad}"
    return True, "4 mensajes acumulados tras dos turnos"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prueba todos los escenarios de enrutado del agente router."
    )
    parser.add_argument(
        "--ruta",
        choices=["preventa", "postventa", "generica"],
        help="Ejecuta solo los casos cuya ruta esperada sea esta.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Muestra el motivo y la respuesta de cada caso.",
    )
    parser.add_argument(
        "--pausa",
        type=float,
        default=0.2,
        help="Segundos de espera entre casos (por defecto: 0.2).",
    )
    parser.add_argument(
        "--reintentos",
        type=int,
        default=2,
        help="Reintentos ante errores de API (por defecto: 2).",
    )
    args = parser.parse_args()

    if not (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")):
        print(
            "Error: falta GOOGLE_API_KEY. Copia .env.example a .env y añade tu clave.",
            file=sys.stderr,
        )
        return 1

    casos = [caso for caso in CASOS if not args.ruta or caso.esperada == args.ruta]
    if not casos:
        print("No hay casos para la ruta indicada.", file=sys.stderr)
        return 1

    grafo = construir_grafo()
    resultados: list[Resultado] = []

    print(f"Probando {len(casos)} escenarios del router...\n")
    for indice, caso in enumerate(casos, start=1):
        etiqueta = "límite" if caso.borde else caso.esperada
        try:
            resultado = ejecutar_caso(grafo, caso, args.reintentos)
        except Exception as exc:
            resultado = Resultado(caso, "", "", "", [f"error de ejecución: {exc}"])

        resultados.append(resultado)
        marca = "OK  " if resultado.ok else "FALLO"
        print(f"[{indice:02d}] {marca} [{etiqueta}] «{caso.mensaje}»")
        if resultado.ok:
            print(f"       → {resultado.ruta}")
        else:
            print(f"       → {resultado.ruta or '(sin ruta)'} | {'; '.join(resultado.problemas)}")
        if args.verbose:
            print(f"       motivo: {resultado.motivo}")
            print(f"       respuesta: {resultado.respuesta}")
        print()
        time.sleep(args.pausa)

    print("-" * 60)
    rutas: tuple[Ruta, ...] = ("preventa", "postventa", "generica")
    for ruta in rutas:
        casos_ruta = [r for r in resultados if r.caso.esperada == ruta]
        if not casos_ruta:
            continue
        correctos = sum(1 for r in casos_ruta if r.ok)
        print(f"{ruta:<12} {correctos}/{len(casos_ruta)}")

    memoria_ok, memoria_detalle = probar_memoria(grafo, args.reintentos)
    print(f"memoria      {'OK' if memoria_ok else 'FALLO'} ({memoria_detalle})")

    fallos = [r for r in resultados if not r.ok]
    correctos = len(resultados) - len(fallos)
    print("-" * 60)
    print(f"Resultado: {correctos}/{len(resultados)} escenarios correctos")

    if fallos:
        print("\nFallos:")
        for resultado in fallos:
            print(f"- «{resultado.caso.mensaje}»: {'; '.join(resultado.problemas)}")

    return 0 if not fallos and memoria_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
