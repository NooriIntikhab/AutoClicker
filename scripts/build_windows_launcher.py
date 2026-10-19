"""Build the double-click AutoClicker.exe that carries the app icon."""

from __future__ import annotations

import struct
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
WINDOWS = ROOT / "windows"
PNG = ROOT / "assets" / "icon.png"
SIZES = (16, 24, 32, 48, 64, 128, 256)


def _dib(image: Image.Image) -> bytes:
    image = image.convert("RGBA")
    width, height = image.size
    raw = image.tobytes("raw", "RGBA")
    xor_rows = []
    for y in range(height - 1, -1, -1):
        row = bytearray()
        for x in range(width):
            start = (y * width + x) * 4
            r, g, b, a = raw[start : start + 4]
            row.extend((b, g, r, a))
        xor_rows.append(bytes(row))
    xor = b"".join(xor_rows)
    mask_stride = ((width + 31) // 32) * 4
    mask = b"\x00" * (mask_stride * height)
    header = struct.pack(
        "<IiiHHIIiiII",
        40,
        width,
        height * 2,
        1,
        32,
        0,
        len(xor) + len(mask),
        0,
        0,
        0,
        0,
    )
    return header + xor + mask


def write_bmp_icon(png_path: Path, ico_path: Path) -> None:
    source = Image.open(png_path)
    blobs = []
    for size in SIZES:
        resized = source.resize((size, size), Image.Resampling.LANCZOS)
        blobs.append(_dib(resized))
    header = struct.pack("<HHH", 0, 1, len(blobs))
    entries = []
    offset = 6 + 16 * len(blobs)
    for size, blob in zip(SIZES, blobs):
        stored = 0 if size >= 256 else size
        entries.append(struct.pack("<BBBBHHII", stored, stored, 0, 0, 1, 32, len(blob), offset))
        offset += len(blob)
    ico_path.write_bytes(header + b"".join(entries) + b"".join(blobs))


def build() -> None:
    if not PNG.exists():
        raise SystemExit(f"Missing {PNG}")
    icon = WINDOWS / "icon.ico"
    write_bmp_icon(PNG, icon)
    obj = WINDOWS / "launcher.o"
    subprocess.check_call(
        ["x86_64-w64-mingw32-windres", "launcher.rc", "-o", "launcher.o"],
        cwd=WINDOWS,
    )
    subprocess.check_call(
        [
            "x86_64-w64-mingw32-gcc",
            "-municode",
            "-mwindows",
            "-O2",
            "-s",
            "-Wall",
            "-Wextra",
            "-static",
            "-o",
            str(ROOT / "AutoClicker.exe"),
            "launcher.c",
            "launcher.o",
            "-lshell32",
        ],
        cwd=WINDOWS,
    )
    obj.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        build()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
