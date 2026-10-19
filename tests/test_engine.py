import threading

from autoclicker.engine import ClickEngine, default_sleep
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


def test_yield_lets_the_user_hold_the_pointer():
    mouse = FakeMouse()
    calls = {"n": 0}

    def should_yield():
        calls["n"] += 1
        return calls["n"] < 4

    def sleep(stop, _get_interval):
        stop.set()
        return True

    engine = ClickEngine(
        mouse,
        lambda: [ClickPoint(3, 4)],
        lambda: 0.25,
        lambda *_args, **_kwargs: None,
        sleep,
        should_yield,
    )
    engine.start()
    engine._thread.join(timeout=2)
    assert mouse.clicks == [(3, 4)]
    assert calls["n"] >= 4


def test_default_sleep_returns_when_stopped():
    stop = threading.Event()

    def request_stop():
        stop.set()

    timer = threading.Timer(0.05, request_stop)
    timer.start()
    assert default_sleep(stop, lambda: 2) is True
    timer.cancel()
