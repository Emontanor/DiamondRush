"""Control de teclado y ratón para interactuar con el juego."""
from __future__ import annotations

import os
import subprocess
import time


class Controll:

    MOVE_KEYS = {
        "UP": "103",      # KEY_UP
        "DOWN": "108",    # KEY_DOWN
        "LEFT": "105",    # KEY_LEFT
        "RIGHT": "106",   # KEY_RIGHT
    }

    ANIMATION_WAIT = 0.15
    KEY_HOLD_MS = 60      # tiempo que se mantiene presionada cada flecha

    # Regex sobre el título de la ventana del navegador
    WINDOW_TITLE = "DIAMOND RUSH"

    # Coordenadas lógicas de Hyprland (las mismas que usa Capture con grim)
    RESTART_BUTTON_X = 647
    RESTART_BUTTON_Y = 320
    GAME_CENTER_X = 278 + 427 // 2  # 491
    GAME_CENTER_Y = 260 + 640 // 2  # 580

    def __init__(self):
        socket_path = "/tmp/.ydotool_socket"
        if os.path.exists(socket_path):
            os.environ["YDOTOOL_SOCKET"] = socket_path
        else:
            print("[Controll] ADVERTENCIA: Socket no encontrado. Inicia: ydotoold &")

        # Foco completo una vez: ventana + canvas del juego
        self._focus_window()
        self._click(self.GAME_CENTER_X, self.GAME_CENTER_Y)
        time.sleep(0.3)

    def _run(self, *args: str) -> None:
        command = " ".join(args)
        try:
            subprocess.run(args, check=True, capture_output=True, timeout=2)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode() if e.stderr else "sin detalles"
            print(f"[Controll] ✗ ERROR en {command}: {stderr}")
        except subprocess.TimeoutExpired:
            print(f"[Controll] ✗ Timeout en {command}")

    def _focus_window(self) -> None:
        """Da el foco del teclado al navegador sin depender del cursor."""
        self._run("hyprctl", "dispatch", "focuswindow", f"title:{self.WINDOW_TITLE}")

    def _click(self, x: int, y: int) -> None:
        """Mueve el cursor con Hyprland (posición exacta) y hace clic con ydotool."""
        self._run("hyprctl", "dispatch", "movecursor", str(x), str(y))
        time.sleep(0.05)
        self._run("ydotool", "click", "0xC0")
        time.sleep(0.05)

    def move(self, direction: str) -> None:
        """Presiona la flecha correspondiente y espera la animación."""
        if direction not in self.MOVE_KEYS:
            raise ValueError(f"Dirección inválida: {direction}. Usa: UP, DOWN, LEFT, RIGHT")

        keycode = self.MOVE_KEYS[direction]
        self._focus_window()   # barato y sin clic: recupera el foco si se perdió
        self._run("ydotool", "key", "-d", str(self.KEY_HOLD_MS), f"{keycode}:1", f"{keycode}:0")
        time.sleep(self.ANIMATION_WAIT)

    def restart_level(self) -> None:
        """Clic en el botón de reinicio."""
        self._focus_window()
        self._click(self.RESTART_BUTTON_X, self.RESTART_BUTTON_Y)
