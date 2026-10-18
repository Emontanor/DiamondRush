"""Prueba de un solo ciclo del sistema DiamondRush."""
from __future__ import annotations

import logging
import time

from Agent import Agent
from Capture import Capture, DEFAULT_REGION
from Controll import Controll
from Perception import Perception, PerceptionError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("TestCycle")

def test_single_cycle():
    """Ejecuta un solo ciclo: capturar -> percibir -> planificar -> ejecutar."""

    # Inicializar módulos
    capture = Capture(DEFAULT_REGION)
    perception = Perception()
    agent = Agent()
    controll = Controll()

    # Dar tiempo para enfocar la ventana del juego
    log.info("Iniciando en 1 segundo. Enfoca la ventana del juego...")
    time.sleep(1)

    # 1. Capturar pantalla
    log.info("Capturando pantalla...")
    imagen = capture.grab()
    log.info(f"Captura exitosa: {imagen.size} px")

    # 2. Percibir estado
    log.info("Procesando percepción...")
    try:
        observation = perception.parse(imagen)
        log.info(f"Percepción exitosa:")
        log.info(f"  - Nivel: {observation.hud.level}")
        log.info(f"  - Diamantes: {observation.hud.collected}/{observation.hud.total}")
        log.info(f"  - Tablero: {len(observation.board)}x{len(observation.board[0])}")
        log.info(f"  - Confiable: {observation.is_reliable}")
    except PerceptionError as exc:
        log.error(f"Error de percepción: {exc}")
        return

    # 3. Planificar
    log.info("Consultando al agente...")
    result = agent.compute(observation.board)
    log.info(f"Resultado del agente:")
    log.info(f"  - Status: {result.status}")
    log.info(f"  - Movimientos: {len(result.moves)}")
    log.info(f"  - Es final: {result.is_final}")
    log.info(f"  - Plan: {result.moves}")

    # 4. Ejecutar movimientos
    if result.moves:
        log.info(f"Ejecutando {len(result.moves)} movimientos...")
        for i, move in enumerate(result.moves, 1):
            log.info(f"  [{i}/{len(result.moves)}] {move}")
            controll.move(move)
        log.info("Ejecución completada")
    else:
        log.warning("No hay movimientos para ejecutar")

    log.info("Ciclo de prueba completado exitosamente")

if __name__ == "__main__":
    try:
        test_single_cycle()
    except KeyboardInterrupt:
        log.info("Prueba interrumpida por el usuario")
    except Exception as exc:
        log.error(f"Error inesperado: {exc}", exc_info=True)
