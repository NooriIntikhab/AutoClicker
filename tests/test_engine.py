import threading
import time

from autoclicker.engine import ClickEngine, apply_emergency_stop, default_sleep
from autoclicker.model import ClickPoint


class FakeMouse:
    def __init__(self):
        self.clicks = []
        self.fail = False

    def click(self, x, y):
        if self.fail:
            raise RuntimeError("blocked")
        self.clicks.append((x, y))


def test_clicks_follow_the_saved_order_until_stopped():
    mouse = FakeMouse()
    points = [ClickPoint(1, 2), ClickPoint(3, 4)]
    events = []

    def sleep(stop, _get_interval):
        if len(mouse.clicks) >= 4:
            stop.set()
            return True
        return stop.is_set()

    engine = ClickEngine(mouse, lambda: points, lambda: 0.25, lambda kind, **payload: events.append(kind), sleep)
    assert engine.start() is True
    engine._thread.join(timeout=2)
    assert mouse.clicks == [(1, 2), (3, 4), (1, 2), (3, 4)]
    assert events[0] == "started"
    assert events[-1] == "stopped"
    assert not engine.is_running


def test_empty_set_does_not_start():
    events = []
    engine = ClickEngine(FakeMouse(), lambda: [], lambda: 0.25, lambda kind, **payload: events.append(kind))
    assert engine.start() is False
    assert events == ["empty"]


def test_stop_during_the_gap():
    mouse = FakeMouse()
    started = threading.Event()

    def sleep(stop, _get_interval):
        started.set()
        return stop.wait(2)

    engine = ClickEngine(
        mouse,
        lambda: [ClickPoint(5, 6)],
        lambda: 0.25,
        lambda *_args, **_kwargs: None,
        sleep,
    )
    engine.start()
    assert started.wait(1)
    engine.stop()
    assert not engine.is_running
    assert mouse.clicks == [(5, 6)]


def test_next_cycle_sees_a_new_set_and_a_new_speed():
    mouse = FakeMouse()
    state = {"points": [ClickPoint(1, 1)], "interval": 0.4}
    seen = []

    def sleep(stop, get_interval):
        seen.append(get_interval())
        if len(mouse.clicks) == 1:
            state["points"] = [ClickPoint(9, 8)]
            state["interval"] = 0.1
            return False
        stop.set()
        return True

    engine = ClickEngine(
        mouse,
        lambda: state["points"],
        lambda: state["interval"],
        lambda *_args, **_kwargs: None,
        sleep,
    )
    engine.start()
    engine._thread.join(timeout=2)
    assert mouse.clicks == [(1, 1), (9, 8)]
    assert seen == [0.4, 0.1]


def test_click_failure_stops_the_loop():
    mouse = FakeMouse()
    mouse.fail = True
    events = []
    engine = ClickEngine(
        mouse,
        lambda: [ClickPoint(1, 1)],
        lambda: 0.25,
        lambda kind, **payload: events.append((kind, payload)),
        lambda stop, _interval: False,
    )
    engine.start()
    engine._thread.join(timeout=2)
    assert events[1][0] == "error"
    assert events[-1][0] == "stopped"


def test_pointer_movement_does_not_stop_an_active_run():
    """A far, still pointer used to yield the loop. It must keep clicking."""

    mouse = FakeMouse()
    state = {"pos": (0, 0), "last": None}

    def user_moved_or_stopped():
        last = state["last"]
        if last is None:
            return False
        pos = state["pos"]
        return abs(pos[0] - last[0]) > 18 or abs(pos[1] - last[1]) > 18

    def click(x, y):
        mouse.clicks.append((x, y))
        state["last"] = (x, y)
        state["pos"] = (500, 400)

    mouse.click = click

    def sleep(stop, _get_interval):
        if len(mouse.clicks) >= 3:
            stop.set()
            return True
        return stop.is_set()

    def should_yield():
        return False

    engine = ClickEngine(
        mouse,
        lambda: [ClickPoint(8, 9)],
        lambda: 0.05,
        lambda *_args, **_kwargs: None,
        sleep,
    )
    assert should_yield() is False
    engine.start()
    engine._thread.join(timeout=2)
    assert user_moved_or_stopped() is True
    assert mouse.clicks == [(8, 9), (8, 9), (8, 9)]
    assert not engine.is_running


def test_stop_still_stops_when_nothing_yields():
    mouse = FakeMouse()
    started = threading.Event()

    def sleep(stop, _get_interval):
        started.set()
        return stop.wait(2)

    def should_yield():
        return False

    engine = ClickEngine(
        mouse,
        lambda: [ClickPoint(2, 2)],
        lambda: 0.05,
        lambda *_args, **_kwargs: None,
        sleep,
    )
    assert should_yield() is False
    engine.start()
    assert started.wait(1)
    assert engine.is_running
    engine.stop()
    assert not engine.is_running
    assert mouse.clicks == [(2, 2)]


def test_ctrl_s_t_pauses_a_run_and_does_not_start_one():
    from pynput.keyboard import HotKey, Key, KeyCode

    from autoclicker.devices import EMERGENCY_STOP_SPEC

    mouse = FakeMouse()
    started = threading.Event()

    def sleep(stop, _get_interval):
        started.set()
        return stop.wait(2)

    engine = ClickEngine(
        mouse,
        lambda: [ClickPoint(5, 6)],
        lambda: 0.25,
        lambda *_args, **_kwargs: None,
        sleep,
    )
    paused = ClickEngine(
        FakeMouse(),
        lambda: [ClickPoint(1, 1)],
        lambda: 0.25,
        lambda *_args, **_kwargs: None,
        lambda stop, _interval: stop.wait(2),
    )

    def on_chord():
        apply_emergency_stop(engine)
        apply_emergency_stop(paused)

    hotkey = HotKey(HotKey.parse(EMERGENCY_STOP_SPEC), on_chord)
    assert engine.start() is True
    assert started.wait(1)
    assert engine.is_running
    assert not paused.is_running

    hotkey.press(Key.ctrl)
    hotkey.press(KeyCode.from_char("s"))
    assert engine.is_running
    hotkey.press(KeyCode.from_char("t"))
    assert not engine.is_running
    assert not paused.is_running
    frozen = list(mouse.clicks)
    paused_clicks = list(paused._mouse.clicks)

    hotkey.release(KeyCode.from_char("t"))
    hotkey.press(KeyCode.from_char("t"))
    time.sleep(0.1)
    assert not engine.is_running
    assert not paused.is_running
    assert mouse.clicks == frozen
    assert paused._mouse.clicks == paused_clicks


def test_default_sleep_returns_when_stopped():
    stop = threading.Event()

    def request_stop():
        stop.set()

    timer = threading.Timer(0.05, request_stop)
    timer.start()
    assert default_sleep(stop, lambda: 2) is True
    timer.cancel()
