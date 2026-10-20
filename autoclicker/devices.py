"""Mouse clicks, global play/pause, emergency stop, and click capture."""

from __future__ import annotations

import time

from autoclicker.model import DEFAULT_STOP_HOTKEY

# Default only. The listener follows the saved stop key.
EMERGENCY_STOP_SPEC = DEFAULT_STOP_HOTKEY

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


def modifier_name(key) -> str | None:
    name = getattr(key, "name", None)
    if name in ("ctrl", "ctrl_l", "ctrl_r"):
        return "ctrl"
    if name in ("alt", "alt_l", "alt_r", "alt_gr"):
        return "alt"
    if name in ("shift", "shift_l", "shift_r"):
        return "shift"
    return None


def _control_letter(key) -> str | None:
    char = getattr(key, "char", None)
    if not isinstance(char, str) or len(char) != 1:
        return None
    code = ord(char)
    if 1 <= code <= 26:
        return chr(ord("a") + code - 1)
    return None


class HotkeyRecorder:
    """Collect Ctrl, Alt, or Shift plus one key. A modifier alone keeps waiting."""

    def __init__(self) -> None:
        self._modifiers: set[str] = set()

    def press(self, key) -> str | None:
        modifier = modifier_name(key)
        if modifier:
            self._modifiers.add(modifier)
            return None
        spec = key_to_spec(key)
        if spec is None and "ctrl" in self._modifiers:
            spec = _control_letter(key)
        if spec is None:
            return None
        if spec == "<esc>" or not self._modifiers:
            return spec
        ordered = [name for name in ("ctrl", "alt", "shift") if name in self._modifiers]
        return "+".join(f"<{name}>" for name in ordered) + "+" + spec

    def release(self, key) -> None:
        modifier = modifier_name(key)
        if modifier:
            self._modifiers.discard(modifier)


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

        recorder = HotkeyRecorder()
        done = False

        def on_press(key):
            nonlocal done
            if done:
                return False
            try:
                key = listener.canonical(key)
            except Exception:
                pass
            spec = recorder.press(key)
            if spec is None:
                return None
            done = True
            on_result(None if spec == "<esc>" else spec)
            return False

        def on_release(key):
            try:
                key = listener.canonical(key)
            except Exception:
                pass
            recorder.release(key)

        listener = Listener(on_press=on_press, on_release=on_release)
        self._capture = listener
        listener.start()

    def cancel_capture(self) -> None:
        capture = self._capture
        self._capture = None
        if capture is not None:
            capture.stop()


class PynputEmergencyStop:
    """Global stop listener. Pressing the saved stop key only pauses.

    Ctrl+S+T is not watched. The spec starts as F8 and changes when a new stop key is saved.
    """

    def __init__(self) -> None:
        self.spec = DEFAULT_STOP_HOTKEY
        self._listener = None

    def set_hotkey(self, spec: str, callback) -> None:
        self.spec = spec
        self.start(callback)

    def start(self, callback) -> None:
        self.stop()
        from pynput.keyboard import GlobalHotKeys

        self._listener = GlobalHotKeys({self.spec: callback})
        self._listener.start()

    def stop(self) -> None:
        listener = self._listener
        self._listener = None
        if listener is not None:
            listener.stop()


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
