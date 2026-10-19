"""The downloaded folder includes a double-click Windows program with the app icon."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_windows_launcher_carries_the_icon():
    program = ROOT / "AutoClicker.exe"
    data = program.read_bytes()
    assert data[:2] == b"MZ"
    assert b".rsrc" in data
    assert "AutoClicker".encode("utf-16-le") in data


def test_linux_launcher_points_at_the_icon():
    desktop = (ROOT / "AutoClicker.desktop").read_text(encoding="utf-8")
    assert "Name=AutoClicker" in desktop
    assert "Icon=assets/icon.png" in desktop
    assert "run.sh" in desktop
    assert (ROOT / "assets" / "icon.png").exists()
