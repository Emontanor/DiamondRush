"""Resultado ya interpretado de una captura del juego."""
from __future__ import annotations

from .Hud import Hud


class Observation:
    def __init__(self, board: list[list[int]], hud: Hud, is_reliable: bool):
        self.board = board
        self.hud = hud
        self.is_reliable = is_reliable
