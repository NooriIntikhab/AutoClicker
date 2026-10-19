"""Repeat the active click list until pause, emergency stop, or quit."""

from __future__ import annotations

import sys
import threading
import time
from collections.abc import Callable, Sequence

EventCallback = Callable[..., None]
Sleep = Callable[[threading.Event, Callable[[], float]], bool]


class ClickEngine:
    def __init__(
        self,
        mouse,
        get_points: Callable[[], Sequence[object]],
        get_interval: Callable[[], float],
        on_event: EventCallback,
        sleep: Sleep | None = None,
    ) -> None:
        self._mouse = mouse
        self._get_points = get_points
        self._get_interval = get_interval
        self._on_event = on_event
        self._sleep = sleep or default_sleep
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._generation = 0

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive() and not self._stop.is_set()

    def start(self) -> bool:
        with self._lock:
            if self._thread and self._thread.is_alive() and not self._stop.is_set():
                return True
            points = list(self._get_points() or [])
            if not points:
                self._emit("empty")
                return False
            # Release a previous loop without waiting on it. Waiting here can
            # deadlock: the loop may be inside a mouse call while this method
            # is running on the window's click handler.
            self._stop.set()
            self._generation += 1
            generation = self._generation
            self._stop = threading.Event()
            self._thread = threading.Thread(
                target=self._loop,
                args=(generation,),
                name="autoclicker",
                daemon=True,
            )
            self._emit("started")
            self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()

    def _loop(self, generation: int) -> None:
        try:
            while not self._stop.is_set() and generation == self._generation:
                points = list(self._get_points() or [])
                if not points:
                    self._emit("empty")
                    break
                for index, point in enumerate(points):
                    if self._stop.is_set() or generation != self._generation:
                        break
                    # Pointer movement, a stopped pointer, and screen changes
                    # do not pause this loop. stop() is pause, close, or Ctrl+S+T.
                    try:
                        self._mouse.click(int(point.x), int(point.y))
                    except Exception as exc:
                        print(f"AutoClicker click failed: {exc}", file=sys.stderr)
                        self._emit(
                            "error",
                            message="Could not click. Check input permissions for this app.",
                        )
                        return
                    self._emit("click", index=index, count=len(points))
                    if self._sleep(self._stop, self._interval):
                        return
        finally:
            if generation == self._generation:
                self._emit("stopped")

    def _interval(self) -> float:
        try:
            value = float(self._get_interval())
        except (TypeError, ValueError):
            value = 0.25
        if value < 0.01:
            return 0.01
        if value > 5:
            return 5
        return value

    def _emit(self, kind: str, **payload) -> None:
        try:
            self._on_event(kind, **payload)
        except Exception as exc:
            print(f"AutoClicker event failed: {exc}", file=sys.stderr)


def apply_emergency_stop(engine: ClickEngine) -> None:
    """Ctrl+S+T pauses a run. It never starts clicking."""

    engine.stop()


def default_sleep(stop: threading.Event, get_interval: Callable[[], float]) -> bool:
    """Wait for the gap between clicks. True means stop was requested."""

    elapsed = 0.0
    last = time.monotonic()
    while True:
        if stop.is_set():
            return True
        interval = get_interval()
        if elapsed >= interval:
            return False
        step = min(0.03, interval - elapsed)
        if stop.wait(step):
            return True
        now = time.monotonic()
        elapsed += now - last
        last = now
