"""Mouse clicks, global play/pause, and capturing the next screen click."""

from __future__ import annotations

import time

_MODIFIER_NAMES = frozenset(
    {
        "alt",
        "alt_l",
        "alt_r",
        "alt_gr",
        "ctrl",
        "ctrl_l",
        "ctrl_r",
        "shift",
        "shift_l",
        "shift_r",
        "cmd",
        "cmd_l",
        "cmd_r",
    }
)


def key_to_spec(key) -> str | None:
    from pynput.keyboard import Key, KeyCode

    if isinstance(key, Key):
        name = key.name
        if not name or name in _MODIFIER_NAMES:
            return None
        return f"<{name}>"
    if isinstance(key, KeyCode) and key.char:
        char = key.char
        if len(char) == 1 and char.isprintable() and ord(char) >= 32:
            return char.lower()
    return None


class PynputMouse:
    def __init__(self) -> None:
        from pynput.mouse import Button, Controller

        self._controller = Controller()
        self._button = Button.left
        self.last_click: tuple[int, int] | None = None

    def position(self) -> tuple[int, int]:
        x, y = self._controller.position
        return int(x), int(y)

    def click(self, x: int, y: int) -> None:
        point = (int(x), int(y))
        self._controller.position = point
        self.last_click = point
        time.sleep(0.005)
        self._controller.press(self._button)
        time.sleep(0.005)
        self._controller.release(self._button)


class PynputHotkeys:
    def __init__(self) -> None:
        self._listener = None
        self._capture = None

    def set_hotkey(self, spec: str, callback) -> None:
        self.clear_hotkey()
        from pynput.keyboard import GlobalHotKeys

        self._listener = GlobalHotKeys({spec: callback})
        self._listener.start()

    def clear_hotkey(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            listener.stop()

    def capture_next_key(self, on_result) -> None:
        self.cancel_capture()
        from pynput.keyboard import Listener

        def on_press(key):
            spec = key_to_spec(key)
            if spec is None:
                return None
            on_result(None if spec == "<esc>" else spec)
            return False

        self._capture = Listener(on_press=on_press)
        self._capture.start()

    def cancel_capture(self) -> None:
        capture = self._capture
        self._capture = None
        if capture is not None:
            capture.stop()


class PynputClickCapture:
    def __init__(self) -> None:
        self._mouse = None
        self._keys = None

    @property
    def armed(self) -> bool:
        return self._mouse is not None

    def arm(self, on_click, on_cancel) -> None:
        self.disarm()
        from pynput.keyboard import Key, Listener as KeyListener
        from pynput.mouse import Button, Listener as MouseListener

        def on_mouse(x, y, button, pressed):
            if not pressed or button != Button.left:
                return None
            on_click(int(x), int(y))
            return False

        def on_press(key):
            if key == Key.esc:
                on_cancel()
                return False
            return None

        self._mouse = MouseListener(on_click=on_mouse)
        self._keys = KeyListener(on_press=on_press)
        self._mouse.start()
        self._keys.start()

    def disarm(self) -> None:
        mouse = self._mouse
        keys = self._keys
        self._mouse = None
        self._keys = None
        if mouse is not None:
            mouse.stop()
        if keys is not None:
            keys.stop()
