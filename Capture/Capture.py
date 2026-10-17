"""Captura una región fija de la pantalla usando grim en Wayland/Hyprland."""
from __future__ import annotations

import io
import shutil
import subprocess
from typing import Tuple

from PIL import Image


Region = Tuple[int, int, int, int]
DEFAULT_REGION: Region = (278, 260, 427, 640)


class CaptureError(RuntimeError):
    """Error al capturar la región configurada de la pantalla."""


class Capture:
    """Captura y devuelve imágenes en memoria para el módulo de percepción.

    Args:
        region: (left, top, width, height), en coordenadas de pantalla.
    """

    def __init__(self, region: Region):
        if (
            not isinstance(region, tuple)
            or len(region) != 4
            or any(not isinstance(value, int) or isinstance(value, bool) for value in region)
        ):
            raise ValueError("region debe ser una tupla de cuatro enteros: (left, top, width, height)")
        if region[2] <= 0 or region[3] <= 0:
            raise ValueError("el ancho y el alto de region deben ser mayores que cero")
        if shutil.which("grim") is None:
            raise CaptureError("No se encontró 'grim'. Instálalo en Arch con: sudo pacman -S grim")

        self.region = region

    def grab(self) -> Image.Image:
        """Captura la región y devuelve una imagen PIL sin guardarla en disco."""
        left, top, width, height = self.region
        geometry = f"{left},{top} {width}x{height}"

        try:
            result = subprocess.run(
                ["grim", "-g", geometry, "-"],
                check=True,
                capture_output=True,
                timeout=10,
            )
            with Image.open(io.BytesIO(result.stdout)) as image:
                return image.copy()
        except subprocess.TimeoutExpired as exc:
            raise CaptureError("grim tardó demasiado en capturar la pantalla") from exc
        except subprocess.CalledProcessError as exc:
            detail = exc.stderr.decode(errors="replace").strip()
            message = f"grim no pudo capturar la región {geometry}"
            if detail:
                message += f": {detail}"
            raise CaptureError(message) from exc
        except OSError as exc:
            raise CaptureError(f"No se pudo ejecutar grim: {exc}") from exc
        except Exception as exc:
            # Incluye imágenes de salida vacías o que no sean PNG válidos.
            raise CaptureError(f"grim devolvió una imagen que no se pudo leer: {exc}") from exc
