"""Códigos enteros compartidos para las casillas del tablero."""
from enum import IntEnum


class TileCode(IntEnum):
    UNKNOWN = -1
    FLOOR = 0
    WALL = 1
    HOLE = 2
    SPIKES_ACTIVE = 3
    SPIKES_INACTIVE = 4
    LAVA = 5
    DIAMOND = 6
    KEY = 7
    ROCK = 8
    PLAYER = 9
    LOCKED_DOOR = 10
    EXIT_CLOSED = 11
    EXIT_OPEN = 12
