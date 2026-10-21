"""Agente que planifica movimientos a partir del estado del tablero."""
from __future__ import annotations

import ctypes
import os
import subprocess
import tempfile
from array import array
from dataclasses import dataclass
from itertools import chain
from pathlib import Path

@dataclass
class Result:
    moves: list[str]
    is_final: bool

_ROOT = Path(__file__).resolve().parent.parent
_SOLVER_DIR = _ROOT / "Solver"
_LIB_PATH = _SOLVER_DIR / "libdrsolver.so"
_SOURCES = tuple(_SOLVER_DIR / name for name in (
    "orchestrator.cpp", "algorithm1.cpp", "algorithm2.cpp"
))


def _load_solver() -> ctypes.CDLL:
    """Build the native solver when needed, then load it."""
    if not _LIB_PATH.exists() or any(source.stat().st_mtime > _LIB_PATH.stat().st_mtime for source in _SOURCES):
        fd, temporary_path = tempfile.mkstemp(prefix="libdrsolver-", suffix=".so", dir=_SOLVER_DIR)
        os.close(fd)
        try:
            subprocess.run(
                ["g++", "-O3", "-std=c++17", "-fPIC", "-shared",
                 *(str(source) for source in _SOURCES), "-o", temporary_path],
                cwd=_ROOT,
                check=True,
                capture_output=True,
                text=True,
            )
            os.replace(temporary_path, _LIB_PATH)
        except (OSError, subprocess.CalledProcessError) as exc:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass
            detail = exc.stderr.strip() if isinstance(exc, subprocess.CalledProcessError) and exc.stderr else str(exc)
            raise RuntimeError(f"No se pudo compilar el solver nativo: {detail}") from exc
    return ctypes.CDLL(str(_LIB_PATH))


_lib = _load_solver()
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
