"""Códigos enteros compartidos para las casillas del tablero."""
from enum import IntEnum


class TileCode(IntEnum):
    UNKNOWN = -1
    FLOOR = 0
    WALL = 1
    HOLE_EMPTY = 2
    HOLE_FILLED = 3
    SPIKES_ACTIVE = 4
    SPIKES_INACTIVE = 5
    LAVA = 6
    DIAMOND = 7
    KEY = 8
    ROCK = 9
    PLAYER = 10
    LOCKED_DOOR = 11
    EXIT_CLOSED = 12
    EXIT_OPEN = 13
    PRESSURE_PLATE = 14
    DOOR_OPEN = 15
    DOOR_CLOSED = 16
