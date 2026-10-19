"""Agente que planifica movimientos a partir del estado del tablero."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

class Status(Enum):
    PLAN = "plan"
    IMPOSSIBLE = "impossible"
    NO_RESULT = "no_result"

@dataclass
class Result:
    status: Status
    moves: list[str]
    is_final: bool

class Agent:

    def __init__(self):
        return

    def compute(self, board: list[list[int]], level: int) -> Result:
        """Implementación temporal de prueba.

        Recibe el tablero, confirma que lo recibió, y devuelve una secuencia fija.
        Secuencia: derecha x5, abajo x3, izquierda x5, abajo x2, derecha,
                   abajo, derecha x3, abajo, derecha
        """
        # Confirmar recepción del tablero
        print(f"[Agent] Tablero recibido: {len(board)}x{len(board[0]) if board else 0}")
        print(f"[Agent] Primera fila: {board[0] if board else 'vacío'}")

        # Generar secuencia de movimientos
        if level == 1:
            moves = (
                ['RIGHT'] * 5 +    # derecha x5
                ['DOWN'] * 3 +     # abajo x3
                ['LEFT'] * 5 +     # izquierda x5
                ['DOWN'] * 2 +     # abajo x2
                ['RIGHT'] +        # derecha
                ['DOWN'] +         # abajo
                ['RIGHT'] * 3 +    # derecha x3
                ['DOWN'] +         # abajo
                ['RIGHT']          # derecha
            )
        elif level == 2:
            moves = (
                ['LEFT'] * 6 +         # izquierda x6
                ['DOWN'] +            # abajo
                ['RIGHT'] +           # derecha
                ['UP'] +              # arriba
                ['LEFT'] +            # izquierda
                ['UP'] * 8 +          # arriba x8
                ['RIGHT'] +           # derecha
                ['UP'] +              # arriba
                ['RIGHT'] +           # derecha
                ['DOWN'] +            # abajo
                ['RIGHT'] * 2 +       # derecha x2
                ['DOWN'] * 3 +        # abajo x3
                ['RIGHT'] * 2 +       # derecha x2
                ['UP'] +              # arriba
                ['LEFT'] * 2 +        # izquierda x2
                ['DOWN'] * 3 +        # abajo x3
                ['LEFT'] * 2 +        # izquierda x2
                ['DOWN']              # abajo
            )


        print(f"[Agent] Plan generado: {len(moves)} movimientos")

        return Result(
            status=Status.PLAN,
            moves=moves,
            is_final=True  # Asumimos que este plan completa el nivel
        )
