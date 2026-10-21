"""Clasifica el tablero y lee el HUD a partir de una captura del juego."""
from __future__ import annotations

import io
import re
import shutil
import statistics
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageOps, ImageStat

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
    PLAYABLE_COLS = BOARD_COLS - 2
    EXTRA_TOP_ROW_LEVELS = frozenset({8, 20})
    HUD_HEIGHT_RATIO = 0.20
    CELL_SIZE = (48, 48)
    CELL_BORDER_TRIM = 1

    # Distancia media por canal, en escala 0..255. Se calibrarán con la matriz
    # impresa por debug_perception.py y capturas nuevas.
    MAX_MATCH_DISTANCE = 42.0
    MIN_CLASS_MARGIN = 2.0

    _FOLDER_CODES = {
        "Diamante": TileCode.DIAMOND,
        #"Hueco": TileCode.HOLE,
        "Lava": TileCode.LAVA,
        "Llave": TileCode.KEY,
        "Pared": TileCode.WALL,
        "Personaje": TileCode.PLAYER,
        "Piedra": TileCode.ROCK,
        "Piso": TileCode.FLOOR,
        "PuertaLlave": TileCode.LOCKED_DOOR,
        "PlacaPresion": TileCode.PRESSURE_PLATE,
        "Relic": TileCode.RELIC,
    }

    def __init__(self, sprites_dir: str | Path | None = None):
        self.sprites_dir = (
            Path(sprites_dir)
            if sprites_dir is not None
            else Path(__file__).resolve().parent / "Sprites"
        )
        self._templates = self._load_templates()

    def parse(self, imagen: Image.Image) -> Observation:
        """Clasifica el tablero y devuelve solo la zona sin muros constantes.

        La banda superior, equivalente al 20% de la captura calibrada, se usa
        para leer el HUD. El tablero visual normalmente es 12x10. En los niveles
        configurados para incluir una fila superior adicional se usa 13x10.
        La matriz devuelta omite las columnas laterales y la fila inferior
        (11x8 normal, 12x8 con fila adicional). Solo conserva códigos.
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

        # Primero leemos el HUD con la región base. Algunos niveles tienen una
        # fila de tablero por encima de ese límite, tapada parcialmente por UI.
        hud_image = imagen.crop((0, 0, width, hud_height))
        hud = self._read_hud(hud_image)
        hud_height, grid_rows = self.board_layout(height, hud.level)
        board_height = height - hud_height
        board: list[list[int]] = []
        unknown_cells: list[tuple[int, int]] = []

        playable_rows = grid_rows - 1  # La fila inferior de la grilla sigue siendo muro.
        for row in range(playable_rows):
            y0 = hud_height + round(row * board_height / grid_rows)
            y1 = hud_height + round((row + 1) * board_height / grid_rows)
            row_codes: list[int] = []

            for col in range(1, 1 + self.PLAYABLE_COLS):
                x0 = round(col * width / self.BOARD_COLS)
                x1 = round((col + 1) * width / self.BOARD_COLS)
                cell_image = imagen.crop((x0, y0, x1, y1))
                code = self._classify_cell(cell_image)
                if code == TileCode.UNKNOWN:
                    # Coordenadas en la grilla visual usada, útiles para depurar.
                    unknown_cells.append((row, col))
                row_codes.append(int(code))
            board.append(row_codes)

        # remaining_diamonds = hud.total - hud.collected
        # observed_diamonds = sum(
        #     code == TileCode.DIAMOND
        #     for row_codes in board
        #     for code in row_codes
        # )
        reliable = not unknown_cells
        return Observation(board=board, hud=hud, is_reliable=reliable)

    @classmethod
    def board_layout(cls, image_height: int, level: int) -> tuple[int, int]:
        """Devuelve (inicio_vertical_del_tablero, filas_visuales) para un nivel.

        En los niveles configurados en EXTRA_TOP_ROW_LEVELS, adelanta el inicio
        una altura de celda base y añade una fila, manteniendo el paso vertical.
        """
        hud_height = round(image_height * cls.HUD_HEIGHT_RATIO)
        if level not in cls.EXTRA_TOP_ROW_LEVELS:
            return hud_height, cls.BOARD_ROWS

        base_board_height = image_height - hud_height
        extra_row_height = round(base_board_height / cls.BOARD_ROWS)
        return hud_height - extra_row_height, cls.BOARD_ROWS + 1

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
        elif folder == "PuertaReja":
            if "cerrada" in stem.casefold():
                return TileCode.DOOR_CLOSED
            if "abierta" in stem.casefold():
                return TileCode.DOOR_OPEN
        elif folder == "Hueco":
            if "vacio" in stem.casefold():
                return TileCode.HOLE_EMPTY
            if "lleno" in stem.casefold():
                return TileCode.HOLE_FILLED
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

    @staticmethod
    def _read_hud(hud_image: Image.Image) -> Hud:
        executable = shutil.which("tesseract")
        if executable is None:
            raise PerceptionError(
                "No se encontró Tesseract OCR. En Arch instala tesseract y "
                "tesseract-data-eng: sudo pacman -S tesseract tesseract-data-eng"
            )

        # Una única región fija cubre "Level N", el diamante y "X/Y" en ambos
        # casos (nivel de uno y de dos dígitos). Se elimina el icono azul antes
        # del OCR para que no se confunda con un cero pegado al nivel.
        width, height = hud_image.size
        config = "tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789/"
        y1 = round(height * 0.52)
        # En HUDs con nivel de dos dígitos el borde del panel y el texto quedan
        # más próximos al límite izquierdo de la región anterior. Este margen
        # extra conserva completa la "L" de "Level".
        text_roi = hud_image.crop((round(width * 0.25), 0, round(width * 0.72), y1))
        text_roi, diamond_removed = Perception._remove_hud_diamond(text_roi)
        if not diamond_removed:
            raise PerceptionError(
                "No se detectó el diamante azul en la región del HUD; "
                "se evita interpretar un nivel posiblemente contaminado por el icono."
            )

        text_roi = ImageOps.autocontrast(text_roi.convert("L"))
        text_roi = text_roi.resize(
            (text_roi.width * 3, text_roi.height * 3),
            Image.Resampling.LANCZOS,
        )
        text_roi = text_roi.point(lambda value: 255 if value >= 145 else 0)

        png_buffer = io.BytesIO()
        text_roi.save(png_buffer, format="PNG")
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

        text = result.stdout.decode(errors="replace").strip()
        # En ocasiones Tesseract recorta o no reconoce la primera "L" aunque
        # el resto de la etiqueta y los dígitos estén claros.
        level_match = re.search(r"(?:\bLevel|\bevel)\s*(\d+)", text, re.IGNORECASE)
        count_match = re.search(r"(\d+)\s*/\s*(\d+)", text)
        if level_match is None or count_match is None:
            raise PerceptionError(
                f"No se reconocieron nivel y contador en el HUD: {text!r}"
            )

        return Hud(
            level=int(level_match.group(1)),
            collected=int(count_match.group(1)),
            total=int(count_match.group(2)),
        )

    @staticmethod
    def _remove_hud_diamond(image: Image.Image) -> tuple[Image.Image, bool]:
        """Borra el componente azul/cian del diamante dentro de la línea del HUD."""
        image = image.convert("RGB")
        pixels = image.load()
        blue_points: list[tuple[int, int]] = []

        # El texto es casi blanco/gris; el icono tiene canales G/B claramente
        # mayores que R. El filtro se aplica solo a la banda del HUD, alrededor
        # del renglón que contiene nivel, diamante y contador.
        for y in range(image.height):
            for x in range(image.width):
                red, green, blue = pixels[x, y]
                if blue - red >= 35 and green - red >= 25 and blue >= 75:
                    blue_points.append((x, y))

        if len(blue_points) < 8:
            return image, False

        left = max(0, min(x for x, _ in blue_points) - 3)
        top = max(0, min(y for _, y in blue_points) - 3)
        right = min(image.width - 1, max(x for x, _ in blue_points) + 3)
        bottom = min(image.height - 1, max(y for _, y in blue_points) + 3)

        # Estima el color del fondo del panel con un anillo alrededor del icono;
        # así se borra también su contorno y no queda una forma que OCR confunda.
        ring: list[tuple[int, int, int]] = []
        for x in range(left, right + 1):
            if top > 0:
                ring.append(pixels[x, top - 1])
            if bottom < image.height - 1:
                ring.append(pixels[x, bottom + 1])
        for y in range(top, bottom + 1):
            if left > 0:
                ring.append(pixels[left - 1, y])
            if right < image.width - 1:
                ring.append(pixels[right + 1, y])

        if not ring:
            return image, False
        background = tuple(
            int(statistics.median(color[channel] for color in ring))
            for channel in range(3)
        )
        ImageDraw.Draw(image).rectangle((left, top, right, bottom), fill=background)
        return image, True
