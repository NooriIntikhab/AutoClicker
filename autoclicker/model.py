"""Saved click sets, speed, and the setup steps that confirm each spot."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

SLOT_COUNT = 5
MAX_CLICKS = 5
MIN_INTERVAL = 0.05
MAX_INTERVAL = 2.0
DEFAULT_INTERVAL = 0.25
DEFAULT_HOTKEY = "<f6>"

_HOTKEY_RE = re.compile(r"^[a-z0-9]$|^<[a-z0-9_]+>$")
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


@dataclass(frozen=True)
class ClickPoint:
    x: int
    y: int


@dataclass
class ClickSet:
    points: list[ClickPoint] = field(default_factory=list)


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


def format_hotkey(spec: str) -> str:
    if not isinstance(spec, str) or not spec:
        return "F6"
    if spec.startswith("<") and spec.endswith(">") and len(spec) > 2:
        name = spec[1:-1].replace("_", " ")
        if len(name) >= 2 and name[0] == "f" and name[1:].isdigit():
            return "F" + name[1:]
        return name.title()
    if len(spec) == 1:
        return spec.upper()
    return spec


def is_valid_hotkey(spec: object) -> bool:
    if not isinstance(spec, str) or not _HOTKEY_RE.fullmatch(spec):
        return False
    if spec.startswith("<") and spec[1:-1] in _MODIFIER_NAMES:
        return False
    return True


def order_text(count: int) -> str:
    if count <= 0:
        return "No clicks in this set yet"
    if count == 1:
        return "Click 1 repeats until you pause"
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
        if not is_valid_hotkey(self.hotkey):
            self.hotkey = DEFAULT_HOTKEY
        self.slots = _fit_slots(self.slots)

    def active_points(self) -> list[ClickPoint]:
        return list(self.slots[self.active_slot].points)

    def to_dict(self) -> dict:
        return {
            "version": 1,
            "active_slot": self.active_slot,
            "hotkey": self.hotkey,
            "interval": self.interval,
            "slots": [
                {"points": [{"x": point.x, "y": point.y} for point in slot.points]}
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
            parsed_slots[index] = ClickSet(points=_parse_points(slot))
    hotkey = data.get("hotkey", DEFAULT_HOTKEY)
    if not is_valid_hotkey(hotkey):
        hotkey = DEFAULT_HOTKEY
    return Settings(
        active_slot=_clamp_slot(data.get("active_slot", 0)),
        hotkey=hotkey,
        interval=clamp_interval(data.get("interval", DEFAULT_INTERVAL)),
        slots=parsed_slots,
    )


class SetupSession:
    """One pass through "how many clicks" and a confirm for every spot."""

    def __init__(self, count: int) -> None:
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_CLICKS:
            raise ValueError("count must be from 1 to 5")
        self.count = count
        self.points: list[ClickPoint] = []
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
        slot.points = list(slot.points[:MAX_CLICKS])
    return fitted


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
        points.append(ClickPoint(x, y))
        if len(points) == MAX_CLICKS:
            break
    return points


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
