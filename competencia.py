from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Tuple

from Agent import Agent
from Capture import Capture, DEFAULT_REGION
from Controll import Controll
from Perception import Perception, PerceptionError

log = logging.getLogger("DiamondRush")

@dataclass
class Config:
    # --- Condiciones de parada ---
    time_limit: float = 120.0               # límite global de seguridad para toda la ejecución

    # --- Tolerancia a fallos ---
    max_agent_errors: int = 5               # planes finales que no completan el nivel

    # --- Tiempos de espera (segundos) ---
    settle_delay: float = 0.15               # tras cambio de nivel o reinicio, deja terminar la animación

    # --- Región de pantalla (left, top, width, height): HUD + grilla. Calibrar. ---
    region: Tuple[int, int, int, int] = DEFAULT_REGION

class Abort(Exception):
    """Detiene toda la ejecución; el mensaje termina en RunResult.message."""

class Environment: 
    def __init__(self, config: Config):
        self.cfg = config
        self.capture = Capture(config.region)
        self.perception = Perception()
        self.agent = Agent()
        self.controll = Controll()

        self.errors_in_level = 0
        self.deadline = 0.0
        self.initial_level = None

    def run(self) -> int:
        try:
            log.info("Empezando: enfoca la ventana del juego.")
            self._start_global_timer()
            self.observe()
            self.initial_level = self.hud.level

            while True:
                self.check_time()
                result = self.agent.compute(self.board)

                # Un plan vacío equivale a que el agente aún no propone acción.
                if not result.moves:
                    log.info("El agente no propuso movimientos; se vuelve a observar.")
                    time.sleep(self.cfg.settle_delay)
                    self.observe()
                    continue

                log.info("Plan de %d movimientos%s",
                         len(result.moves),
                         " (final)" if result.is_final else "")
                self.execute(result.moves)

                if result.is_final:
                    time.sleep(self.cfg.settle_delay)
                    self.observe()
                    if self.hud.level == self.initial_level + 1:
                        elapsed = time.monotonic() - (self.deadline - self.cfg.time_limit)
                        log.info("Nivel %s completado en %.1f s.", self.initial_level, elapsed)
                        return 0
                    self._register_error("el plan final no completó el nivel")
                else:
                    self.observe()
        except Abort as stop:
            log.warning("Ejecución abortada: %s", stop)
            return 1
        except KeyboardInterrupt:
            log.warning("Interrumpido por el usuario")
            return 130


    # --- Capture Management
    def observe(self) -> None:
        try:
            observation = self.perception.parse(self.capture.grab())
            if observation.is_reliable:
                self.board = observation.board
                self.hud = observation.hud
                return
            reason = "observación no fiable (celdas desconocidas o HUD inconsistente)"
        except PerceptionError as exc:
            reason = str(exc)
        
        raise Abort(f"No se pudo leer el juego: {reason}")

    # --- Controll Management
    def execute(self, moves):
        for move in moves:
            self.controll.move(move)

    # --- Error Management
    def _register_error(self, reason: str):
        self.errors_in_level += 1
        log.warning("Error %d/%d en el nivel: %s.", self.errors_in_level, self.cfg.max_agent_errors, reason)
        if self.errors_in_level >= self.cfg.max_agent_errors:
            raise Abort("El agente fue incapaz de resolver el nivel")

    # --- Time Management
    def _start_global_timer(self) -> None:
        self.deadline = time.monotonic() + self.cfg.time_limit

    def check_time(self) -> None:
        if time.monotonic() > self.deadline:
            raise Abort(
                f"Tiempo global agotado: más de {self.cfg.time_limit:.0f} s de ejecución. "
            )

def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return Environment(Config()).run()

if __name__ == "__main__":
    raise SystemExit(main())
