"""Guarda cada celda de una captura para revisar y recolectar sprites nuevos.

Los recortes se escriben en sprites_recolectados/captura_<fecha>/ y se nombran
con coordenadas 0-based. Lee el nivel del HUD para elegir la geometría correcta.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys

from Capture import Capture, CaptureError, DEFAULT_REGION
from Perception import Perception, PerceptionError


def main() -> int:
    project_root = Path(__file__).resolve().parent
    run_name = datetime.now().strftime("captura_%Y%m%d_%H%M%S_%f")
    output_dir = project_root / "sprites_recolectados" / run_name

    try:
        image = Capture(DEFAULT_REGION).grab()
        width, height = image.size
        initial_hud_height = round(height * Perception.HUD_HEIGHT_RATIO)
        hud_strip = image.crop((0, 0, width, initial_hud_height))
        hud = Perception._read_hud(hud_strip)
        hud_height, grid_rows = Perception.board_layout(height, hud.level)
        board_height = height - hud_height

        if width < Perception.BOARD_COLS or board_height < grid_rows:
            raise ValueError(
                f"Captura demasiado pequeña para dividir la grilla "
                f"{grid_rows}x{Perception.BOARD_COLS}: {width}x{height} px"
            )

        output_dir.mkdir(parents=True, exist_ok=False)
        for row in range(grid_rows):
            y0 = hud_height + round(row * board_height / grid_rows)
            y1 = hud_height + round((row + 1) * board_height / grid_rows)

            for col in range(Perception.BOARD_COLS):
                x0 = round(col * width / Perception.BOARD_COLS)
                x1 = round((col + 1) * width / Perception.BOARD_COLS)
                cell = image.crop((x0, y0, x1, y1))
                cell.save(output_dir / f"fila_{row:02d}_columna_{col:02d}.png")

    except (CaptureError, PerceptionError, OSError, ValueError) as exc:
        print(f"No se pudieron recolectar los sprites: {exc}", file=sys.stderr)
        return 1

    total = grid_rows * Perception.BOARD_COLS
    print(f"Nivel detectado: {hud.level}; grilla: {grid_rows}x{Perception.BOARD_COLS}.")
    print(f"Guardados {total} recortes de {width}x{height} px en:")
    print(output_dir)
    print("Los nombres usan coordenadas 0-based de la grilla visual.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
