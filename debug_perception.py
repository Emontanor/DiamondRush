"""Captura el juego, guarda la imagen completa e imprime la observación."""
from __future__ import annotations

import sys
from time import perf_counter

from Capture import Capture, CaptureError, DEFAULT_REGION
from Perception import Perception, PerceptionError, TileCode


def main() -> int:
    started = perf_counter()
    try:
        image = Capture(DEFAULT_REGION).grab()
        observation = Perception().parse(image)
    except (CaptureError, PerceptionError, OSError) as exc:
        print(f"No se pudo generar la observación: {exc}", file=sys.stderr)
        print(f"Tiempo total: {perf_counter() - started:.3f} s")
        return 1

    print(f"Captura procesada en memoria: {image.width}x{image.height} px")
    print(f"HUD: nivel={observation.hud.level}, diamantes="
          f"{observation.hud.collected}/{observation.hud.total}")
    print(f"Observación fiable: {observation.is_reliable}")
    board_width = len(observation.board[0]) if observation.board else 0
    print(f"Board {len(observation.board)}x{board_width} "
          "(sin columnas de muro ni fila inferior; códigos numéricos):")
    for row in observation.board:
        print("[" + ", ".join(f"{code:2d}" for code in row) + "]")

    print("Leyenda:")
    for tile in TileCode:
        print(f"  {int(tile):2d}: {tile.name}")
    print(f"Tiempo total: {perf_counter() - started:.3f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
