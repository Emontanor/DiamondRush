"""Agente que planifica movimientos a partir del estado del tablero."""
from __future__ import annotations

import ctypes
import os
from array import array
from dataclasses import dataclass
from itertools import chain

@dataclass
class Result:
    moves: list[str]
    is_final: bool

_lib = ctypes.CDLL(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Solver", "libdrsolver.so"))
_solve = _lib.dr_solve
_solve.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p)
_solve.restype = ctypes.c_int
_CAP = 65536
_buf = ctypes.create_string_buffer(_CAP)
_BUF = ctypes.addressof(_buf)
_final = ctypes.c_int(0)
_FINAL = ctypes.addressof(_final)
_flat = chain.from_iterable
_at = ctypes.string_at
_names = [None] * 256
_names[85] = "UP"
_names[68] = "DOWN"
_names[76] = "LEFT"
_names[82] = "RIGHT"
_name = tuple(_names).__getitem__

class Agent:

    def __init__(self):
        return

    def compute(self, board: list[list[int]], use_algorithm_1: bool) -> Result:
        cells = array("i", _flat(board))
        n = _solve(cells.buffer_info()[0], len(cells), use_algorithm_1, _BUF, _CAP, _FINAL)
        if n < 0:
            return Result([], False)
        return Result(list(map(_name, _at(_BUF, n))), _final.value == 1)
