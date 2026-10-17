"""Diamond Rush: ambiente sobre el que vive el agente.

main.py es el único que conoce todos los módulos. Guarda el estado visible del juego
(tablero y HUD), orquesta el ciclo y decide cuándo parar. El agente solo recibe un
tablero y devuelve movimientos.

Ciclo:
    capturar -> percibir -> agent.compute(tablero) -> ejecutar plan -> capturar y verificar
    hasta pasar `levels_to_pass` niveles.

Contratos entre módulos:

    Capture(region)
        .grab()                 -> imagen (HUD + grilla, tal como está en la región)

    Perception()
        .parse(imagen)          -> Observation
        Observation.board       -> matriz 12x10 con un código entero por tile
        Observation.hud         -> .level (comparable con ==), .collected, .total
        Observation.is_reliable -> bool: sin celdas desconocidas y consistente con el HUD
        lanza PerceptionError si no logra leer el HUD

    Agent()
        .compute(board)         -> Result
        Result.status           -> Status.PLAN | Status.IMPOSSIBLE | Status.NO_RESULT
        Result.moves            -> lista de movimientos (vacía salvo en Status.PLAN)

    Controll(region)
        .move(move)             -> presiona la flecha y espera la animación
        .restart_level()        -> clic en el botón de reinicio (el de la derecha)
"""
from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from typing import Tuple

from Agent import Agent, Status
from Capture import Capture, DEFAULT_REGION
from Controll import Controll
from Perception import Perception, PerceptionError

log = logging.getLogger("DiamondRush")


@dataclass
class Config:
    # --- Condiciones de parada ---
    levels_to_pass: int = 1                 # cuántos niveles debe pasar antes de terminar
    time_limit: float = 120.0               # límite global de seguridad para toda la ejecución

    # --- Tolerancia a fallos ---
    max_agent_errors: int = 5               # errores del agente en un mismo nivel antes de abortar
    max_perception_retries: int = 5         # lecturas fallidas seguidas antes de abortar

    # --- Tiempos de espera (segundos) ---
    start_delay: float = 5.0                # para enfocar la ventana del juego
    settle_delay: float = 1.0               # tras cambio de nivel o reinicio, deja terminar la animación
    retry_wait: float = 0.3                 # entre lecturas fallidas

    # --- Región de pantalla (left, top, width, height): HUD + grilla. Calibrar. ---
    region: Tuple[int, int, int, int] = DEFAULT_REGION


@dataclass
class RunResult:
    success: bool
    message: str
    levels_passed: int


class Abort(Exception):
    """Detiene toda la ejecución; el mensaje termina en RunResult.message."""


class Environment:
    def __init__(self, config: Config):
        self.cfg = config
        self.capture = Capture(config.region)
        self.perception = Perception()
        self.agent = Agent()
        self.controll = Controll(config.region)

        # Estado del juego visible para main (última observación fiable).
        self.board = None
        self.hud = None

        # Estado de la ejecución.
        self.levels_passed = 0
        self.current_level = None
        self.errors_in_level = 0
        self.at_initial_state = True   # True si no se han ejecutado movimientos desde el inicio/reinicio
        self._deadline = 0.0

    # ------------------------------------------------------------------ API

    def run(self) -> RunResult:
        try:
            self._run()
            return RunResult(True, f"Niveles completados: {self.levels_passed}.", self.levels_passed)
        except Abort as stop:
            return RunResult(False, str(stop), self.levels_passed)
        except KeyboardInterrupt:
            return RunResult(False, "Interrumpido por el usuario.", self.levels_passed)

    # ----------------------------------------------------------- ciclo principal

    def _run(self) -> None:
        log.info("Empezando en %.0f s: enfoca la ventana del juego.", self.cfg.start_delay)
        time.sleep(self.cfg.start_delay)

        self._start_global_timer()
        self._observe()
        self.current_level = self.hud.level

        while self.levels_passed < self.cfg.levels_to_pass:
            self._check_time()
            result = self.agent.compute(self.board)

            if result.status == Status.IMPOSSIBLE:
                self._handle_impossible()
                continue

            if result.status != Status.PLAN or not result.moves:
                self._register_error("el agente no devolvió un plan")
                continue

            log.info("Plan de %d movimientos.", len(result.moves))
            self._execute(result.moves)
            self.at_initial_state = False

            self._observe()
            if self.hud.level != self.current_level:
                self._confirm_level_change()
            else:
                self._register_error("el nivel no cambió tras ejecutar el plan")

    # ------------------------------------------------------------- acciones

    def _execute(self, moves) -> None:
        """Un movimiento a la vez, para poder revisar el tiempo entre cada uno."""
        for move in moves:
            self._check_time()
            self.controll.move(move)

    def _handle_impossible(self) -> None:
        if self.at_initial_state:
            # Sin haber movido nada, "imposible" no se arregla reiniciando.
            raise Abort(
                "El agente declara el nivel imposible desde su posición inicial: "
                "revisar la percepción o el agente."
            )
        log.warning("El nivel no se puede completar debido a la distribución. Reiniciando nivel.")
        self.controll.restart_level()
        time.sleep(self.cfg.settle_delay)
        self._observe()
        self.at_initial_state = True

    def _confirm_level_change(self) -> None:
        """Acepta el cambio solo si dos lecturas seguidas coinciden (evita leer la transición)."""
        candidate = self.hud.level
        for _ in range(self.cfg.max_perception_retries):
            time.sleep(self.cfg.settle_delay)
            self._observe()
            if self.hud.level == candidate and candidate != self.current_level:
                self._on_level_passed()
                return
            candidate = self.hud.level
            if candidate == self.current_level:
                break
        self._register_error("cambio de nivel no confirmado")

    def _on_level_passed(self) -> None:
        self.levels_passed += 1
        self.current_level = self.hud.level
        self.errors_in_level = 0
        self.at_initial_state = True
        log.info("Nivel superado (%d/%d).", self.levels_passed, self.cfg.levels_to_pass)

    def _register_error(self, reason: str) -> None:
        self.errors_in_level += 1
        log.warning("Error %d/%d en el nivel: %s.", self.errors_in_level, self.cfg.max_agent_errors, reason)
        if self.errors_in_level >= self.cfg.max_agent_errors:
            raise Abort("Incapacidad de completar")

    # ----------------------------------------------------------- observación

    def _observe(self) -> None:
        """Captura y percibe, reintentando hasta obtener una observación fiable."""
        failures = 0
        while True:
            self._check_time()
            try:
                observation = self.perception.parse(self.capture.grab())
                if observation.is_reliable:
                    self.board = observation.board
                    self.hud = observation.hud
                    return
                reason = "observación no fiable (celdas desconocidas o HUD inconsistente)"
            except PerceptionError as exc:
                reason = str(exc)

            failures += 1
            log.warning("Lectura fallida %d/%d: %s", failures, self.cfg.max_perception_retries, reason)
            if failures >= self.cfg.max_perception_retries:
                raise Abort(f"No se pudo leer el juego: {reason}")
            time.sleep(self.cfg.retry_wait)

    # ---------------------------------------------------------------- tiempo

    def _start_global_timer(self) -> None:
        """Fija una sola fecha límite para toda la ejecución."""
        self._deadline = time.monotonic() + self.cfg.time_limit

    def _check_time(self) -> None:
        if time.monotonic() > self._deadline:
            raise Abort(
                f"Tiempo global agotado: más de {self.cfg.time_limit:.0f} s de ejecución. "
                f"Niveles completados: {self.levels_passed}."
            )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    result = Environment(Config()).run()
    print(result.message)
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(main())
