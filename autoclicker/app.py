"""Start the auto-clicker window."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from autoclicker.devices import (
    PynputClickCapture,
    PynputEmergencyStop,
    PynputHotkeys,
    PynputMouse,
)
from autoclicker.storage import load_settings, save_settings
from autoclicker.ui import AutoClickerApp


def configure_windows_process() -> None:
    if sys.platform != "win32":
        return
    import ctypes

    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Local.AutoClicker")
    except Exception:
        pass


def main() -> None:
    configure_windows_process()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        print(f"AutoClicker could not open a window: {exc}", file=sys.stderr)
        sys.exit(1)
    try:
        mouse = PynputMouse()
        hotkeys = PynputHotkeys()
        capture = PynputClickCapture()
        emergency = PynputEmergencyStop()
    except Exception as exc:
        root.withdraw()
        messagebox.showerror(
            "AutoClicker",
            "Could not use the mouse and keyboard on this PC.\n\n"
            f"{exc}\n\n"
            "On macOS, allow this app under Accessibility. "
            "On Linux, run it in an X11 session.",
        )
        root.destroy()
        sys.exit(1)
    app = AutoClickerApp(
        root, load_settings(), mouse, hotkeys, capture, save_settings, emergency
    )
    app.run()
