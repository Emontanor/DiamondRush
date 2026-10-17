"""Clasifica el tablero y lee el HUD a partir de una captura del juego."""
from __future__ import annotations

import io
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageOps, ImageStat

from .Hud import Hud
from .Observation import Observation
from .TileCode import TileCode


class PerceptionError(Exception):
    """Error al interpretar la imagen del juego o leer sus datos del HUD."""


@dataclass(frozen=True)
class _Template:
    code: TileCode
    image: Image.Image
    path: Path


class Perception:
    BOARD_ROWS = 12
    BOARD_COLS = 10
    HUD_HEIGHT_RATIO = 0.20
    CELL_SIZE = (48, 48)
    CELL_BORDER_TRIM = 1

    # Distancia media por canal, en escala 0..255. Se calibrarán con la matriz
    # impresa por debug_perception.py y capturas nuevas.
    MAX_MATCH_DISTANCE = 42.0
    MIN_CLASS_MARGIN = 2.0

    _FOLDER_CODES = {
        "Diamante": TileCode.DIAMOND,
        "Hueco": TileCode.HOLE,
        "Lava": TileCode.LAVA,
        "Llave": TileCode.KEY,
        "Pared": TileCode.WALL,
        "Personaje": TileCode.PLAYER,
        "Piedra": TileCode.ROCK,
        "Piso": TileCode.FLOOR,
        "PuertaLlave": TileCode.LOCKED_DOOR,
    }

    def __init__(self, sprites_dir: str | Path | None = None):
        self.sprites_dir = (
            Path(sprites_dir)
            if sprites_dir is not None
            else Path(__file__).resolve().parent / "Sprites"
        )
        self._templates = self._load_templates()

    def parse(self, imagen: Image.Image) -> Observation:
        """Segmenta y clasifica 12x10 celdas sin guardar sus recortes.

        La banda superior, equivalente al 20% de la captura calibrada, se usa
        para leer el HUD. Las celdas se recortan y clasifican una por una; solo
        se conserva la matriz final de códigos enteros.
        """
        if not isinstance(imagen, Image.Image):
            raise TypeError("parse espera una imagen PIL.Image.Image")

        imagen = imagen.convert("RGB")
        width, height = imagen.size
        hud_height = round(height * self.HUD_HEIGHT_RATIO)
        board_height = height - hud_height
        if width < self.BOARD_COLS or board_height < self.BOARD_ROWS:
            raise PerceptionError(
                f"Captura demasiado pequeña para dividir el tablero "
                f"12x10: {width}x{height} px"
            )

        hud_image = imagen.crop((0, 0, width, hud_height))
        hud = self._read_hud(hud_image)
        board: list[list[int]] = []
        unknown_cells: list[tuple[int, int]] = []

        for row in range(self.BOARD_ROWS):
            y0 = hud_height + round(row * board_height / self.BOARD_ROWS)
            y1 = hud_height + round((row + 1) * board_height / self.BOARD_ROWS)
            row_codes: list[int] = []

            for col in range(self.BOARD_COLS):
                # Estas celdas son muros por las reglas y geometría del juego;
                # no hace falta compararlas con plantillas.
                if col in (0, self.BOARD_COLS - 1) or row == self.BOARD_ROWS - 1:
                    code = TileCode.WALL
                else:
                    x0 = round(col * width / self.BOARD_COLS)
                    x1 = round((col + 1) * width / self.BOARD_COLS)
                    cell_image = imagen.crop((x0, y0, x1, y1))
                    code = self._classify_cell(cell_image)
                    if code == TileCode.UNKNOWN:
                        unknown_cells.append((row, col))

                row_codes.append(int(code))
            board.append(row_codes)

        remaining_diamonds = hud.total - hud.collected
        observed_diamonds = sum(
            code == TileCode.DIAMOND
            for row_codes in board
            for code in row_codes
        )
        reliable = not unknown_cells and observed_diamonds == remaining_diamonds
        return Observation(board=board, hud=hud, is_reliable=reliable)

    def _load_templates(self) -> list[_Template]:
        if not self.sprites_dir.is_dir():
            raise PerceptionError(f"No existe la carpeta de sprites: {self.sprites_dir}")

        templates: list[_Template] = []
        for folder in sorted(path for path in self.sprites_dir.iterdir() if path.is_dir()):
            for path in sorted(folder.glob("*.png")):
                code = self._code_for_template(folder.name, path.stem)
                try:
                    with Image.open(path) as sprite:
                        normalized = self._normalize_cell(sprite.convert("RGB"))
                except OSError as exc:
                    raise PerceptionError(f"No se pudo leer el sprite {path}: {exc}") from exc
                templates.append(_Template(code=code, image=normalized, path=path))

        if not templates:
            raise PerceptionError(f"No hay sprites PNG en {self.sprites_dir}")
        return templates

    def _code_for_template(self, folder: str, stem: str) -> TileCode:
        if folder == "Salida":
            if "abierta" in stem.casefold():
                return TileCode.EXIT_OPEN
            if "cerrada" in stem.casefold():
                return TileCode.EXIT_CLOSED
        elif folder == "Pinchos":
            if "desactivados" in stem.casefold():
                return TileCode.SPIKES_INACTIVE
            if "activados" in stem.casefold():
                return TileCode.SPIKES_ACTIVE
        elif folder in self._FOLDER_CODES:
            return self._FOLDER_CODES[folder]

        raise PerceptionError(
            f"No se conoce la etiqueta del sprite {folder}/{stem}.png; "
            "añade su clase a Perception._code_for_template()."
        )

    def _normalize_cell(self, image: Image.Image) -> Image.Image:
        image = image.convert("RGB")
        trim = self.CELL_BORDER_TRIM
        if image.width > trim * 2 and image.height > trim * 2:
            image = image.crop((trim, trim, image.width - trim, image.height - trim))
        return image.resize(self.CELL_SIZE, Image.Resampling.BILINEAR)

    def _classify_cell(self, cell: Image.Image) -> TileCode:
        candidate = self._normalize_cell(cell)
        best_by_code: dict[TileCode, float] = {}

        for template in self._templates:
            difference = ImageChops.difference(candidate, template.image)
            score = sum(ImageStat.Stat(difference).mean[:3]) / 3
            previous = best_by_code.get(template.code)
            if previous is None or score < previous:
                best_by_code[template.code] = score

        ranked = sorted(best_by_code.items(), key=lambda item: item[1])
        if not ranked or ranked[0][1] > self.MAX_MATCH_DISTANCE:
            return TileCode.UNKNOWN
        if len(ranked) > 1 and ranked[1][1] - ranked[0][1] < self.MIN_CLASS_MARGIN:
            return TileCode.UNKNOWN
        return ranked[0][0]

    def _read_hud(self, hud_image: Image.Image) -> Hud:
        executable = shutil.which("tesseract")
        if executable is None:
            raise PerceptionError(
                "No se encontró Tesseract OCR. En Arch instala tesseract y "
                "tesseract-data-eng: sudo pacman -S tesseract tesseract-data-eng"
            )

        # El panel con nivel y contador ocupa el centro de la franja superior.
        width, height = hud_image.size
        text_roi = hud_image.crop((round(width * 0.20), 0, round(width * 0.80), round(height * 0.52)))
        text_roi = ImageOps.autocontrast(text_roi.convert("L"))
        text_roi = text_roi.resize(
            (text_roi.width * 3, text_roi.height * 3),
            Image.Resampling.LANCZOS,
        )
        text_roi = text_roi.point(lambda value: 255 if value >= 145 else 0)

        png_buffer = io.BytesIO()
        text_roi.save(png_buffer, format="PNG")
        config = "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/"
        try:
            result = subprocess.run(
                [executable, "stdin", "stdout", "-l", "eng", "--psm", "6", "-c", config],
                input=png_buffer.getvalue(),
                check=True,
                capture_output=True,
                timeout=5,
            )
        except subprocess.TimeoutExpired as exc:
            raise PerceptionError("Tesseract tardó demasiado en leer el HUD") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode(errors="replace").strip()
            raise PerceptionError(f"Tesseract no pudo leer el HUD: {detail}") from exc

        text = result.stdout.decode(errors="replace")
        # OCR a veces concatena un artefacto al nivel (p. ej. "Level1T0/12").
        # Basta con reconocer los dígitos después de "Level"; el contador se
        # extrae por separado de toda la salida.
        level_match = re.search(r"\bLevel\s*(\d+)", text, re.IGNORECASE)
        # El artefacto "T" queda pegado al primer dígito del contador:
        # "Level1T0/12". Sin límite de palabra, todavía se reconoce "0/12".
        count_match = re.search(r"(\d+)\s*/\s*(\d+)", text)
        if level_match is None or count_match is None:
            raise PerceptionError(f"No se reconocieron nivel y contador en el HUD: {text.strip()!r}")

        return Hud(
            level=int(level_match.group(1)),
            collected=int(count_match.group(1)),
            total=int(count_match.group(2)),
        )
