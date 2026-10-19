"""Build a single-file AutoClicker program for this PC.

Windows output: dist/AutoClicker.exe
macOS and Linux output: dist/AutoClicker
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def hidden_imports() -> list[str]:
    if sys.platform == "win32":
        return ["pynput.keyboard._win32", "pynput.mouse._win32"]
    if sys.platform == "darwin":
        return ["pynput.keyboard._darwin", "pynput.mouse._darwin"]
    return [
        "pynput.keyboard._xorg",
        "pynput.mouse._xorg",
        "pynput.keyboard._uinput",
    ]


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    separator = ";" if sys.platform == "win32" else ":"
    icon = root / "assets" / "icon.ico"
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        "AutoClicker",
        "--distpath",
        str(root / "dist"),
        "--workpath",
        str(root / "build"),
        "--specpath",
        str(root / "build"),
        "--add-data",
        f"{root / 'assets' / 'icon.png'}{separator}assets",
    ]
    if icon.exists():
        command.extend(["--icon", str(icon)])
    for module in hidden_imports():
        command.extend(["--hidden-import", module])
    command.append(str(root / "main.py"))
    subprocess.check_call(command, cwd=root)


if __name__ == "__main__":
    main()
