"""
BFS para encontrar la ruta más corta en un mapa de 20x20 con un
obstáculo central de 5x5 y bordes bloqueados, pasando por paradas
intermedias configurables, y envío del resultado al sketch del
Arduino UNO Q mediante Arduino_RouterBridge (RPC).
"""

import time
from collections import deque
from arduino.app_utils import App, Bridge  # API Python de RouterBridge en Arduino App Lab (UNO Q)

FILAS = 20
COLUMNAS = 20

# El inicio y la meta se ubican dentro del área transitable,
# ya que los bordes del mapa son obstáculos fijos.
INICIO = (1, 1)
META = (18, 18)

# ============================================================
# CONFIGURACIÓN DE PARADAS
# Arduino App Lab no provee una terminal interactiva (stdin),
# por lo que las paradas se definen aquí como una lista de
# tuplas (X, Y) -> (columna, fila).
# Ejemplo: PARADAS_CONFIG = [(5, 5), (15, 10)]
# ============================================================
PARADAS_CONFIG = [
    (5, 5),
    (15, 10),
]


def generar_mapa():
    """Genera la matriz 20x20 con bordes bloqueados y un obstáculo de 5x5 en el centro."""
    mapa = [[0 for _ in range(COLUMNAS)] for _ in range(FILAS)]

    # Bordes del mapa como obstáculo (zona que no se debe tocar)
    for f in range(FILAS):
        mapa[f][0] = 1
        mapa[f][COLUMNAS - 1] = 1
    for c in range(COLUMNAS):
        mapa[0][c] = 1
        mapa[FILAS - 1][c] = 1

    # Obstáculo de 5x5 centrado en el mapa
    inicio_fila = (FILAS - 5) // 2
    inicio_col = (COLUMNAS - 5) // 2
    for f in range(inicio_fila, inicio_fila + 5):
        for c in range(inicio_col, inicio_col + 5):
            mapa[f][c] = 1  # 1 = obstáculo

    return mapa


def imprimir_mapa(mapa, ruta=None, paradas=None):
    """Imprime el mapa. Si se da una ruta, la marca con '*'. Las paradas se marcan con 'P'."""
    ruta_set = set(ruta) if ruta else set()
    paradas_set = set(paradas) if paradas else set()

    for f in range(FILAS):
        fila_str = ""
        for c in range(COLUMNAS):
            if (f, c) == INICIO:
                fila_str += " I "
            elif (f, c) == META:
                fila_str += " M "
            elif (f, c) in paradas_set:
                fila_str += " P "
            elif mapa[f][c] == 1:
                fila_str += " # "
            elif (f, c) in ruta_set:
                fila_str += " * "
            else:
                fila_str += " . "
        print(fila_str)
    print()


def bfs(mapa, inicio, meta):
    """Búsqueda en anchura para encontrar la ruta más corta entre inicio y meta."""
    visitados = {inicio}
    padres = {inicio: None}
    cola = deque([inicio])

    movimientos = [(-1, 0), (1, 0), (0, -1), (0, 1)]

    while cola:
        actual = cola.popleft()

        if actual == meta:
            break

        f, c = actual
        for df, dc in movimientos:
            vecino = (f + df, c + dc)
            nf, nc = vecino

            if 0 <= nf < FILAS and 0 <= nc < COLUMNAS:
                if mapa[nf][nc] == 0 and vecino not in visitados:
                    visitados.add(vecino)
                    padres[vecino] = actual
                    cola.append(vecino)

    if meta not in padres:
        return None

    ruta = []
    nodo = meta
    while nodo is not None:
        ruta.append(nodo)
        nodo = padres[nodo]
    ruta.reverse()

    return ruta


def pedir_paradas(mapa):
    """
    Valida las paradas intermedias definidas en PARADAS_CONFIG.
    X = columna, Y = fila. Verifica que estén dentro del mapa,
    que no sean obstáculo y que no coincidan con inicio/meta.
    """
    paradas = []

    for i, (x, y) in enumerate(PARADAS_CONFIG):
        if not (0 <= x < COLUMNAS and 0 <= y < FILAS):
            print(f"Parada {i + 1} ({x}, {y}) fuera del mapa, se ignora.")
            continue

        if mapa[y][x] == 1:
            print(f"Parada {i + 1} ({x}, {y}) cae en un obstáculo, se ignora.")
            continue

        punto = (y, x)
        if punto == INICIO or punto == META:
            print(f"Parada {i + 1} ({x}, {y}) coincide con inicio/meta, se ignora.")
            continue

        paradas.append(punto)

    return paradas


def construir_ruta_con_paradas(mapa, inicio, paradas, meta):
    """
    Calcula la ruta completa pasando por inicio -> paradas -> meta,
    concatenando los segmentos BFS entre cada par de puntos consecutivos.
    """
    puntos = [inicio] + paradas + [meta]
    ruta_completa = [puntos[0]]

    for i in range(len(puntos) - 1):
        origen = puntos[i]
        destino = puntos[i + 1]

        segmento = bfs(mapa, origen, destino)
        if segmento is None:
            print(f"No se encontró ruta entre {origen} y {destino}.")
            return None

        # Se omite el primer punto del segmento para no duplicarlo
        ruta_completa.extend(segmento[1:])

    return ruta_completa


def ruta_a_texto(ruta):
    """Convierte la ruta a un string compacto: 'f0,c0;f1,c1;...' para enviar por Bridge."""
    return ";".join(f"{f},{c}" for f, c in ruta)


def reportar_estado_motor(bridge, estado):
    """
    Notifica al Arduino UNO Q el estado actual del motor.
    estado: "MOVIMIENTO" | "GIRO" | "DETENCION"
    """
    respuesta = bridge.call("actualizar_estado_motor", estado)
    if respuesta:
        print(f"[Motor] Estado '{estado}' confirmado por Arduino: {respuesta}")
    else:
        print(f"[Motor] Error al reportar estado '{estado}'")


def ejecutar_ruta(bridge, ruta, paradas, meta):
    """
    Recorre la ruta calculada paso a paso, con 1 segundo de pausa por punto:
    - MOVIMIENTO: cuando se avanza en línea recta (misma dirección que el paso anterior).
    - GIRO: cuando cambia la dirección respecto al paso anterior.
    - DETENCION: cuando el punto actual es una parada establecida o el punto final.
    """
    paradas_set = set(paradas)

    direccion_anterior = None
    for i in range(1, len(ruta)):
        f_prev, c_prev = ruta[i - 1]
        f_act, c_act = ruta[i]
        punto_act = (f_act, c_act)
        direccion = (f_act - f_prev, c_act - c_prev)

        if direccion_anterior is not None and direccion != direccion_anterior:
            reportar_estado_motor(bridge, "GIRO")
        else:
            reportar_estado_motor(bridge, "MOVIMIENTO")

        time.sleep(1)

        if punto_act in paradas_set or punto_act == meta:
            reportar_estado_motor(bridge, "DETENCION")
            time.sleep(1)

        direccion_anterior = direccion


def main():
    bridge = Bridge()

    mapa = generar_mapa()

    print("Mapa generado (I = inicio, M = meta, # = obstáculo):")
    imprimir_mapa(mapa)

    paradas = pedir_paradas(mapa)

    ruta = construir_ruta_con_paradas(mapa, INICIO, paradas, META)

    if ruta is None:
        print("No se encontró una ruta posible hacia la meta.")
        respuesta = bridge.call("recibir_ruta", "ERROR", "")
    else:
        print(f"Ruta encontrada con {len(ruta)} pasos:")
        print(ruta)
        print()

        print("Mapa con la ruta (I = inicio, M = meta, P = parada, # = obstáculo, * = ruta):")
        imprimir_mapa(mapa, ruta, paradas)

        # Llamada RPC al sketch: envía estado y ruta
        respuesta = bridge.call("recibir_ruta", "OK", ruta_a_texto(ruta))

    if respuesta:
        print(f"Respuesta del Arduino UNO Q: {respuesta}")
    else:
        print("Error en la llamada RPC: sin respuesta")
        return

    if ruta is not None:
        ejecutar_ruta(bridge, ruta, paradas, META)


if __name__ == "__main__":
    main()