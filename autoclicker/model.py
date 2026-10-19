"""Saved click sets, speed, and the setup steps that confirm each spot."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

SLOT_COUNT = 5
MAX_NAME_LENGTH = 32
MIN_INTERVAL = 0.05
MAX_INTERVAL = 2.0
DEFAULT_INTERVAL = 0.25
DEFAULT_HOTKEY = "<f6>"
# F8 always stops clicking and cannot be the play/pause key.
EMERGENCY_STOP_SPEC = "<f8>"

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
_MODIFIER_CANON = {
    "<ctrl>": "ctrl",
    "<ctrl_l>": "ctrl",
    "<ctrl_r>": "ctrl",
    "<alt>": "alt",
    "<alt_l>": "alt",
    "<alt_r>": "alt",
    "<alt_gr>": "alt",
    "<shift>": "shift",
    "<shift_l>": "shift",
    "<shift_r>": "shift",
}
_MODIFIER_ORDER = ("ctrl", "alt", "shift")
_MODIFIER_LABELS = {
    "ctrl": "Ctrl",
    "ctrl_l": "Ctrl",
    "ctrl_r": "Ctrl",
    "alt": "Alt",
    "alt_l": "Alt",
    "alt_r": "Alt",
    "alt_gr": "Alt",
    "shift": "Shift",
    "shift_l": "Shift",
    "shift_r": "Shift",
    "cmd": "Cmd",
    "cmd_l": "Cmd",
    "cmd_r": "Cmd",
}


@dataclass(frozen=True)
class ClickPoint:
    x: int
    y: int
    enabled: bool = True


@dataclass
class ClickSet:
    points: list[ClickPoint] = field(default_factory=list)
    name: str = ""

    def __post_init__(self) -> None:
        self.name = clean_name(self.name)
        self.points = [
            point for point in list(self.points) if isinstance(point, ClickPoint)
        ]


def default_slots() -> list[ClickSet]:
    return [ClickSet() for _ in range(SLOT_COUNT)]


def clamp_interval(seconds: float) -> float:
    try:
        value = float(seconds)
    except (TypeError, ValueError):
        return DEFAULT_INTERVAL
    if value < MIN_INTERVAL:
        return MIN_INTERVAL
    if value > MAX_INTERVAL:
        return MAX_INTERVAL
    return value


def gap_from_slider(position: float) -> float:
    """Map a 0–1 slider position to a gap. 0 is slowest, 1 is fastest."""

    try:
        position = float(position)
    except (TypeError, ValueError):
        position = 0.5
    position = min(1.0, max(0.0, position))
    log_slow = math.log(MAX_INTERVAL)
    log_fast = math.log(MIN_INTERVAL)
    return math.exp(log_slow + (log_fast - log_slow) * position)


def slider_from_gap(seconds: float) -> float:
    seconds = clamp_interval(seconds)
    log_slow = math.log(MAX_INTERVAL)
    log_fast = math.log(MIN_INTERVAL)
    if log_fast == log_slow:
        return 0.0
    position = (math.log(seconds) - log_slow) / (log_fast - log_slow)
    return min(1.0, max(0.0, position))


def format_speed(seconds: float) -> str:
    seconds = clamp_interval(seconds)
    if seconds >= 1:
        text = f"{seconds:.1f}".rstrip("0").rstrip(".")
        return f"1 click every {text} s"
    per_second = 1.0 / seconds
    if per_second >= 10:
        text = str(int(round(per_second)))
    else:
        text = f"{per_second:.1f}".rstrip("0").rstrip(".")
    noun = "click" if text == "1" else "clicks"
    return f"{text} {noun}/sec"


def clean_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:MAX_NAME_LENGTH]


def display_set_name(name: object, index: int) -> str:
    cleaned = clean_name(name)
    if cleaned:
        return cleaned
    try:
        number = int(index) + 1  # type: ignore[arg-type]
    except (TypeError, ValueError):
        number = 1
    if isinstance(index, bool) or number < 1 or number > SLOT_COUNT:
        number = 1
    return f"Set {number}"


def format_hotkey(spec: str) -> str:
    if not isinstance(spec, str) or not spec:
        return "F6"
    parts = [part for part in spec.split("+") if part]
    if not parts:
        return "F6"
    return " + ".join(_format_hotkey_part(part) for part in parts)


def is_valid_hotkey(spec: object) -> bool:
    return canonical_hotkey(spec) is not None


def canonical_hotkey(spec: object) -> str | None:
    """Return the stored play/pause spec, or None when it cannot be used."""

    parsed = _parts_of_hotkey(spec)
    if parsed is None:
        return None
    modifiers, keys = parsed
    if len(keys) != 1 or len(modifiers) != len(set(modifiers)):
        return None
    key = keys[0]
    if not modifiers:
        if key == EMERGENCY_STOP_SPEC:
            return None
        return key
    ordered = [name for name in _MODIFIER_ORDER if name in modifiers]
    return "+".join(f"<{name}>" for name in ordered) + "+" + key


def is_stop_key(spec: object) -> bool:
    """True only for the fixed F8 stop key."""

    return _parts_of_hotkey(spec) == ([], [EMERGENCY_STOP_SPEC])


def parse_click_count(value: object) -> int | None:
    """A whole number of clicks, 1 or more. Anything else is not a count."""

    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        number = value
    elif isinstance(value, str):
        text = value.strip()
        if not re.fullmatch(r"\d+", text):
            return None
        number = int(text)
    else:
        return None
    if number < 1:
        return None
    return number


def order_text(count: int) -> str:
    if count <= 0:
        return "No clicks in this set yet"
    if count == 1:
        return "Click 1 repeats until you pause"
    if count > 8:
        return f"1 → 2 → 3 → … → {count}, then it repeats"
    sequence = " → ".join(str(index) for index in range(1, count + 1))
    return f"{sequence}, then it repeats"


def contains_point(
    x: int,
    y: int,
    bounds: tuple[int, int, int, int],
    pad: int = 0,
) -> bool:
    left, top, width, height = bounds
    return left - pad <= x < left + width + pad and top - pad <= y < top + height + pad


@dataclass
class Settings:
    active_slot: int = 0
    hotkey: str = DEFAULT_HOTKEY
    interval: float = DEFAULT_INTERVAL
    slots: list[ClickSet] = field(default_factory=default_slots)

    def __post_init__(self) -> None:
        self.active_slot = _clamp_slot(self.active_slot)
        self.interval = clamp_interval(self.interval)
        self.hotkey = canonical_hotkey(self.hotkey) or DEFAULT_HOTKEY
        self.slots = _fit_slots(self.slots)

    def active_points(self) -> list[ClickPoint]:
        return list(self.slots[self.active_slot].points)

    def enabled_points(self) -> list[ClickPoint]:
        return [point for point in self.active_points() if point.enabled]

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "active_slot": self.active_slot,
            "hotkey": canonical_hotkey(self.hotkey) or DEFAULT_HOTKEY,
            "interval": self.interval,
            "slots": [
                {
                    "name": clean_name(slot.name),
                    "points": [
                        {"x": point.x, "y": point.y, "on": bool(point.enabled)}
                        for point in list(slot.points)
                        if isinstance(point, ClickPoint)
                    ],
                }
                for slot in self.slots
            ],
        }


def settings_from_dict(data: object) -> Settings:
    if not isinstance(data, dict):
        raise ValueError("settings must be an object")
    slots = data.get("slots")
    parsed_slots = default_slots()
    if isinstance(slots, list):
        for index, slot in enumerate(slots[:SLOT_COUNT]):
            parsed_slots[index] = _parse_slot(slot)
    hotkey = data.get("hotkey", DEFAULT_HOTKEY)
    return Settings(
        active_slot=_clamp_slot(data.get("active_slot", 0)),
        hotkey=hotkey if isinstance(hotkey, str) else DEFAULT_HOTKEY,
        interval=clamp_interval(data.get("interval", DEFAULT_INTERVAL)),
        slots=parsed_slots,
    )


class SetupSession:
    """Confirm each new spot. Spots already saved stay unless the count shrinks."""

    def __init__(self, count: int, existing: list[ClickPoint] | None = None) -> None:
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ValueError("count must be a whole number of 1 or more")
        kept: list[ClickPoint] = []
        if existing:
            for point in existing:
                if isinstance(point, ClickPoint):
                    kept.append(point)
                if len(kept) >= count:
                    break
        self.count = count
        self.points: list[ClickPoint] = kept
        self.pending: ClickPoint | None = None

    @property
    def index(self) -> int:
        return len(self.points) + 1

    @property
    def done(self) -> bool:
        return self.pending is None and len(self.points) >= self.count

    def offer(self, x: int, y: int) -> None:
        self.pending = ClickPoint(int(x), int(y))

    def accept(self) -> None:
        if self.pending is None:
            raise RuntimeError("No spot is waiting to be confirmed")
        if len(self.points) >= self.count:
            raise RuntimeError("All spots are already confirmed")
        self.points.append(self.pending)
        self.pending = None

    def reject(self) -> None:
        self.pending = None


def _clamp_slot(value: object) -> int:
    try:
        slot = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0
    if isinstance(value, bool) or slot < 0 or slot >= SLOT_COUNT:
        return 0
    return slot


def _fit_slots(slots: list[ClickSet]) -> list[ClickSet]:
    fitted = list(slots[:SLOT_COUNT])
    while len(fitted) < SLOT_COUNT:
        fitted.append(ClickSet())
    for slot in fitted:
        slot.points = list(slot.points)
    return fitted


def _format_hotkey_part(part: str) -> str:
    if part.startswith("<") and part.endswith(">") and len(part) > 2:
        name = part[1:-1]
        if name in _MODIFIER_LABELS:
            return _MODIFIER_LABELS[name]
        if len(name) >= 2 and name[0] == "f" and name[1:].isdigit():
            return "F" + name[1:]
        return name.replace("_", " ").title()
    if len(part) == 1:
        return part.upper()
    return part


def _split_hotkey(spec: str) -> list[str] | None:
    if not spec or spec != spec.strip() or "++" in spec:
        return None
    parts = spec.split("+") if "+" in spec else [spec]
    if any(not part for part in parts):
        return None
    return parts


def _normalize_key(part: str) -> str | None:
    if len(part) == 1:
        if part.isalpha():
            if not part.isascii():
                return None
            return part.lower()
        if part.isascii() and part.isprintable() and ord(part) > 32 and part != "+":
            return part
        return None
    if len(part) > 2 and part[0] == "<" and part[-1] == ">":
        name = part[1:-1]
        if not re.fullmatch(r"[a-z0-9_]+", name):
            return None
        if name in _MODIFIER_NAMES:
            return None
        return f"<{name}>"
    return None


def _parts_of_hotkey(spec: object) -> tuple[list[str], list[str]] | None:
    if not isinstance(spec, str):
        return None
    parts = _split_hotkey(spec)
    if parts is None:
        return None
    modifiers: list[str] = []
    keys: list[str] = []
    for part in parts:
        canon = _MODIFIER_CANON.get(part)
        if canon:
            modifiers.append(canon)
            continue
        key = _normalize_key(part)
        if key is None:
            return None
        keys.append(key)
    return modifiers, keys


def _parse_slot(slot: object) -> ClickSet:
    if not isinstance(slot, dict):
        return ClickSet()
    name = slot.get("name", "")
    return ClickSet(points=_parse_points(slot), name=name if isinstance(name, str) else "")


def _parse_points(slot: object) -> list[ClickPoint]:
    if not isinstance(slot, dict):
        return []
    raw_points = slot.get("points")
    if not isinstance(raw_points, list):
        return []
    points: list[ClickPoint] = []
    for raw in raw_points:
        if not isinstance(raw, dict):
            continue
        x = _parse_coord(raw.get("x"))
        y = _parse_coord(raw.get("y"))
        if x is None or y is None:
            continue
        points.append(ClickPoint(x, y, enabled=_parse_on(raw)))
    return points


def _parse_on(raw: dict) -> bool:
    if "on" not in raw:
        return True
    return raw.get("on") is True


def _parse_coord(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if abs(number) > 100_000:
        return None
    return number
