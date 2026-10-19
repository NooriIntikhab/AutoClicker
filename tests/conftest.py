"""Start a display for the window tests when this machine does not have one."""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import time

_XVFB = None


def _ensure_display() -> None:
    global _XVFB
    if os.environ.get("DISPLAY") or _XVFB is not None:
        return
    if shutil.which("Xvfb") is None:
        return
    for number in range(99, 110):
        if os.path.exists(f"/tmp/.X11-unix/X{number}"):
            continue
        display = f":{number}"
        process = subprocess.Popen(
            ["Xvfb", display, "-screen", "0", "1280x800x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.4)
        if process.poll() is not None:
            continue
        os.environ["DISPLAY"] = display
        _XVFB = process
        atexit.register(process.terminate)
        return


_ensure_display()
