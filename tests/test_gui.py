import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="window tests need a display")


class FakeMouse:
    def __init__(self):
        self.clicks = []
        self.last_click = None

    def click(self, x, y):
        self.last_click = (x, y)
        self.clicks.append((x, y))

    def position(self):
        place = getattr(self, "place", None)
        if place is not None:
            return place
        return self.last_click or (0, 0)


class FakeHotkeys:
    def __init__(self):
        self.spec = None
        self.callback = None
        self.capturing = False
        self._on_result = None
        self.fail_set = False

    def set_hotkey(self, spec, callback):
        if self.fail_set:
            raise RuntimeError("no keyboard")
        self.spec = spec
        self.callback = callback
        self.capturing = False

    def clear_hotkey(self):
        self.spec = None
        self.callback = None

    def capture_next_key(self, on_result):
        self.capturing = True
        self._on_result = on_result

    def cancel_capture(self):
        self.capturing = False
        self._on_result = None

    def emit_key(self, spec):
        callback = self._on_result
        self._on_result = None
        self.capturing = False
        if callback is not None:
            callback(spec)


class FakeEmergency:
    def __init__(self):
        self.spec = "<ctrl>+s+t"
        self.callback = None
        self.started = False
        self.stopped = False

    def start(self, callback):
        self.started = True
        self.stopped = False
        self.callback = callback

    def stop(self):
        self.stopped = True
        self.callback = None


class FakeCapture:
    def __init__(self):
        self.armed = False
        self._on_click = None
        self._on_cancel = None

    def arm(self, on_click, on_cancel):
        self.armed = True
        self._on_click = on_click
        self._on_cancel = on_cancel

    def disarm(self):
        self.armed = False
        self._on_click = None
        self._on_cancel = None

    def emit(self, x, y):
        if self._on_click is not None:
            self._on_click(x, y)

    def emit_cancel(self):
        if self._on_cancel is not None:
            self._on_cancel()


@pytest.fixture
def app(tmp_path):
    import tkinter as tk

    from autoclicker.model import Settings
    from autoclicker.storage import load_settings, save_settings
    from autoclicker.ui import AutoClickerApp

    path = tmp_path / "settings.json"
    root = tk.Tk()
    mouse = FakeMouse()
    hotkeys = FakeHotkeys()
    capture = FakeCapture()
    emergency = FakeEmergency()

    def save(settings):
        save_settings(settings, path)

    window = AutoClickerApp(root, Settings(), mouse, hotkeys, capture, save, emergency)
    window.mouse_log = mouse
    window.path = path
    window.load = lambda: load_settings(path)
    yield window
    window.close()


def _drive_setup(window, points):
    state = {"phase": "select", "index": 0}

    def pump():
        phase = state["phase"]
        if phase == "select" and window.count_buttons:
            window.count_buttons[len(points) - 1].invoke()
            state["phase"] = "next"
            window.root.after(20, pump)
            return
        if phase == "next" and window.count_next is not None:
            state["phase"] = "click"
            window.root.after(20, pump)
            window.count_next.invoke()
            return
        if phase == "click" and window.capture.armed:
            x, y = points[state["index"]]
            state["phase"] = "confirm"
            window.root.after(20, pump)
            window.capture.emit(x, y)
            return
        if phase == "confirm" and window.confirm_accept is not None:
            state["index"] += 1
            state["phase"] = "click" if state["index"] < len(points) else "done"
            if state["phase"] != "done":
                window.root.after(20, pump)
            window.confirm_accept.invoke()
            return
        if phase != "done":
            window.root.after(20, pump)

    window.root.after(20, pump)


def test_window_has_five_sets_and_highlights_the_one_in_use(app):
    from autoclicker.model import ClickPoint
    from autoclicker.ui import ACCENT

    assert [button.text() for button in app.slot_buttons] == [
        "Set 1",
        "Set 2",
        "Set 3",
        "Set 4",
        "Set 5",
    ]
    assert app.slot_caption.cget("text") == "Set 1 is in use"
    assert app.slot_buttons[0].bg == ACCENT
    app.play_button.invoke()
    assert not app.engine.is_running
    assert "Set up clicks" in app.status_label.cget("text")
    app.settings.slots[3].points = [ClickPoint(3, 4)]
    app.on_slot_clicked(3)
    assert app.settings.active_slot == 3
    assert app.slot_caption.cget("text") == "Set 4 is in use"
    assert app.slot_buttons[3].bg == ACCENT
    assert app.slot_buttons[0].bg != ACCENT


def test_setup_saves_confirmed_spots_in_order(app):
    points = [(120, 80), (400, 220), (640, 360)]
    _drive_setup(app, points)
    app.root.after(4000, app.cancel_setup)
    app.run_setup()
    assert [(point.x, point.y) for point in app.settings.slots[0].points] == points
    assert "Saved 3 clicks in Set 1" in app.status_label.cget("text")
    assert "1 → 2 → 3" in app.order_label.cget("text")
    loaded = app.load()
    assert [(point.x, point.y) for point in loaded.slots[0].points] == points


def test_pick_again_does_not_keep_the_rejected_spot(app):
    state = {"tries": 0}

    def pump():
        if app.count_buttons and state["tries"] == 0:
            state["tries"] = 1
            app.count_buttons[0].invoke()
            app.root.after(20, pump)
            return
        if state["tries"] == 1 and app.count_next is not None:
            state["tries"] = 2
            app.root.after(20, pump)
            app.count_next.invoke()
            return
        if state["tries"] == 2 and app.capture.armed:
            state["tries"] = 3
            app.root.after(20, pump)
            app.capture.emit(10, 10)
            return
        if state["tries"] == 3 and app.confirm_retry is not None:
            state["tries"] = 4
            app.root.after(20, pump)
            app.confirm_retry.invoke()
            return
        if state["tries"] == 4 and app.capture.armed:
            state["tries"] = 5
            app.root.after(20, pump)
            app.capture.emit(70, 90)
            return
        if state["tries"] == 5 and app.confirm_accept is not None:
            state["tries"] = 6
            app.confirm_accept.invoke()
            return
        app.root.after(20, pump)

    app.root.after(20, pump)
    app.root.after(4000, app.cancel_setup)
    app.run_setup()
    assert [(point.x, point.y) for point in app.settings.active_points()] == [(70, 90)]


def test_cancel_keeps_the_old_set(app):
    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(1, 1)]
    app.refresh()

    def pump():
        if app.count_buttons:
            app._cancel_count()
            return
        app.root.after(20, pump)

    app.root.after(20, pump)
    app.run_setup()
    assert app.settings.active_points() == [ClickPoint(1, 1)]


def test_edit_replaces_one_spot(app):
    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(1, 1), ClickPoint(2, 2)]
    app.refresh()

    def pump():
        if app.capture.armed and app._banner_title.cget("text").startswith("New spot"):
            app.root.after(20, accept_later)
            app.capture.emit(50, 60)
            return
        app.root.after(20, pump)

    def accept_later():
        if app.confirm_accept is not None:
            app.confirm_accept.invoke()
            return
        app.root.after(20, accept_later)

    app.root.after(20, pump)
    app.root.after(4000, app.cancel_setup)
    app.edit_point(1)
    assert app.settings.active_points() == [ClickPoint(1, 1), ClickPoint(50, 60)]
    assert app.load().slots[0].points[1] == ClickPoint(50, 60)


def test_play_clicks_in_order_and_pause_stops_it(app):
    import time

    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(4, 5), ClickPoint(6, 7)]
    app.settings.interval = 0.05
    app.refresh()
    app._last_toggle = 0
    app.play_button.invoke()
    deadline = time.time() + 2
    while len(app.mouse_log.clicks) < 2 and time.time() < deadline:
        time.sleep(0.02)
    assert app.mouse_log.clicks[:2] == [(4, 5), (6, 7)]
    time.sleep(0.3)
    app._last_toggle = 0
    app.play_button.invoke()
    app.root.update()
    assert app.play_button.text() == "Play"
    assert not app.engine.is_running


def test_minimize_does_not_stop_clicking(app):
    import time

    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(8, 9)]
    app.settings.interval = 0.05
    app.refresh()
    app._last_toggle = 0
    app.toggle_play()
    app.minimize_window()
    time.sleep(0.35)
    assert len(app.mouse_log.clicks) >= 1
    assert app.engine.is_running
    app.engine.stop()


def test_rebind_play_key_is_saved(app):
    app.hotkey_button.invoke()
    assert app.hotkeys.capturing
    app.hotkeys.emit_key("b")
    app.root.update()
    assert app.settings.hotkey == "b"
    assert app.hotkeys.spec == "b"
    assert app.load().hotkey == "b"
    assert app.hotkey_value.cget("text") == "B"


def test_speed_bar_saves_a_faster_gap(app):
    app.on_speed(1)
    app.root.update()
    assert app.settings.interval == pytest.approx(0.05)
    assert "20 clicks/sec" in app.speed_value.cget("text")
    app.persist()
    assert app.load().interval == pytest.approx(0.05)


def test_pointer_movement_does_not_stop_clicking(app):
    import time

    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(4, 5)]
    app.settings.interval = 0.05
    app.refresh()
    app.mouse_log.place = (1800, 900)
    app._last_toggle = 0
    app.toggle_play()
    deadline = time.time() + 2
    while len(app.mouse_log.clicks) < 2 and time.time() < deadline:
        app.root.update()
        time.sleep(0.02)
    assert app.mouse_log.clicks[:2] == [(4, 5), (4, 5)]
    assert app.engine.is_running
    app.engine.stop()


def test_window_shows_emergency_stop_and_keeps_the_play_key(app):
    assert app.emergency_label.cget("text") == "Ctrl + S + T stops clicking"
    assert app.emergency.spec == "<ctrl>+s+t"
    assert app.emergency.started
    assert app.settings.hotkey == "<f6>"
    assert app.hotkeys.spec == "<f6>"
    app.hotkey_button.invoke()
    app.hotkeys.emit_key("s")
    app.root.update()
    assert app.settings.hotkey == "s"
    assert app.hotkeys.spec == "s"
    assert app.emergency.spec == "<ctrl>+s+t"
    assert app.emergency.callback == app._emergency_pressed


def test_ctrl_s_t_pauses_and_does_not_start(app):
    import time

    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(4, 5)]
    app.settings.interval = 0.05
    app.refresh()
    assert not app.engine.is_running
    app.emergency.callback()
    app.root.update()
    assert not app.engine.is_running
    assert app.mouse_log.clicks == []

    app._block_start_until = 0
    app._last_toggle = 0
    app.toggle_play()
    deadline = time.time() + 2
    while not app.mouse_log.clicks and time.time() < deadline:
        time.sleep(0.02)
    assert app.engine.is_running
    app.emergency.callback()
    app.root.update()
    assert not app.engine.is_running
    thread = app.engine._thread
    if thread is not None:
        thread.join(timeout=1)
    frozen = list(app.mouse_log.clicks)
    app.emergency.callback()
    app.root.update()
    time.sleep(0.15)
    app.root.update()
    assert not app.engine.is_running
    assert app.mouse_log.clicks == frozen
    assert app.play_button.text() == "Play"


def test_chord_does_not_start_when_the_play_key_is_s(app):
    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(1, 1)]
    app.refresh()
    app.hotkey_button.invoke()
    app.hotkeys.emit_key("s")
    app.root.update()
    app._last_toggle = 0
    app.hotkeys.callback()
    app.emergency.callback()
    app.root.update()
    assert not app.engine.is_running
    assert app.mouse_log.clicks == []


def test_play_key_can_be_a_chord_and_changed_again(app):
    app.hotkey_button.invoke()
    app.hotkeys.emit_key("<ctrl>+a")
    app.root.update()
    assert app.settings.hotkey == "<ctrl>+a"
    assert app.hotkey_value.cget("text") == "Ctrl + A"
    assert app.load().hotkey == "<ctrl>+a"

    app.hotkey_button.invoke()
    app.hotkeys.emit_key("<shift>+<f8>")
    app.root.update()
    assert app.settings.hotkey == "<shift>+<f8>"
    assert app.hotkey_value.cget("text") == "Shift + F8"
    assert app.load().hotkey == "<shift>+<f8>"
    assert app.emergency.spec == "<ctrl>+s+t"

    app.hotkey_button.invoke()
    app.hotkeys.emit_key("<ctrl>+s+t")
    app.root.update()
    assert app.settings.hotkey == "<shift>+<f8>"
    assert app.hotkeys.spec == "<shift>+<f8>"
    assert app.load().hotkey == "<shift>+<f8>"
    assert "stop" in app.status_label.cget("text").lower()


def test_sets_can_be_named_and_renamed(app):
    app.rename_button.invoke()
    app.name_entry.insert(0, "Farm")
    app.name_save.invoke()
    assert app.slot_buttons[0].text() == "Farm"
    assert app.slot_caption.cget("text") == "Farm is in use"
    assert app.load().slots[0].name == "Farm"
    assert app.slot_buttons[1].text() == "Set 2"

    app.rename_button.invoke()
    app.name_entry.delete(0, "end")
    app.name_entry.insert(0, "Nope")
    app.name_cancel.invoke()
    assert app.settings.slots[0].name == "Farm"
    assert app.slot_caption.cget("text") == "Farm is in use"
    assert app.load().slots[0].name == "Farm"

    app.rename_button.invoke()
    app.name_entry.delete(0, "end")
    app.name_entry.insert(0, "Barn")
    app.name_save.invoke()
    assert app.slot_buttons[0].text() == "Barn"
    assert app.load().slots[0].name == "Barn"

    app.rename_button.invoke()
    app.name_entry.delete(0, "end")
    app.name_entry.insert(0, "   ")
    app.name_save.invoke()
    assert app.settings.slots[0].name == ""
    assert app.slot_buttons[0].text() == "Set 1"
    assert app.slot_caption.cget("text") == "Set 1 is in use"


def test_custom_name_shows_on_another_set(app):
    from autoclicker.model import ClickPoint

    app.settings.slots[2].name = "Farm"
    app.settings.slots[2].points = [ClickPoint(4, 5)]
    app.on_slot_clicked(2)
    assert app.slot_buttons[2].text() == "Farm"
    assert app.slot_caption.cget("text") == "Farm is in use"
    assert app.slot_buttons[0].text() == "Set 1"


def test_add_click_keeps_the_spots_already_saved(app):
    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(5, 6), ClickPoint(7, 8)]
    app.refresh()

    def pump():
        if app.capture.armed and app._banner_title.cget("text").startswith("Click spot"):
            app.root.after(20, accept_later)
            app.capture.emit(50, 60)
            return
        app.root.after(20, pump)

    def accept_later():
        if app.confirm_accept is not None:
            app.confirm_accept.invoke()
            return
        app.root.after(20, accept_later)

    app.root.after(20, pump)
    app.root.after(4000, app.cancel_setup)
    app.add_button.invoke()
    assert app.settings.active_points() == [
        ClickPoint(5, 6),
        ClickPoint(7, 8),
        ClickPoint(50, 60),
    ]
    assert app.load().slots[0].points == app.settings.active_points()


def test_cancel_add_or_edit_keeps_the_saved_set(app):
    from autoclicker.model import ClickPoint

    saved = [ClickPoint(5, 6), ClickPoint(7, 8)]
    app.settings.slots[0].points = list(saved)
    app.persist()
    app.refresh()

    def cancel_when_armed():
        if app.capture.armed:
            app.cancel_setup()
            return
        app.root.after(20, cancel_when_armed)

    app.root.after(20, cancel_when_armed)
    app.root.after(4000, app.cancel_setup)
    app.add_point()
    assert app.settings.active_points() == saved

    app.root.after(20, cancel_when_armed)
    app.root.after(4000, app.cancel_setup)
    app.edit_point(0)
    assert app.settings.active_points() == saved
    assert app.load().slots[0].points == saved


def test_higher_count_asks_only_for_the_new_spots(app):
    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(1, 1), ClickPoint(2, 2)]
    app.refresh()
    added = [(8, 8), (9, 9)]
    state = {"phase": "select", "index": 0}

    def pump():
        phase = state["phase"]
        if phase == "select" and app.count_buttons:
            assert len(app.count_buttons) == 30
            app.count_buttons[3].invoke()
            state["phase"] = "next"
            app.root.after(20, pump)
            return
        if phase == "next" and app.count_next is not None:
            state["phase"] = "click"
            app.root.after(20, pump)
            app.count_next.invoke()
            return
        if phase == "click" and app.capture.armed:
            if state["index"] == 0:
                assert app._banner_title.cget("text") == "Click spot 3 of 4"
            x, y = added[state["index"]]
            state["phase"] = "confirm"
            app.root.after(20, pump)
            app.capture.emit(x, y)
            return
        if phase == "confirm" and app.confirm_accept is not None:
            state["index"] += 1
            state["phase"] = "click" if state["index"] < len(added) else "done"
            if state["phase"] != "done":
                app.root.after(20, pump)
            app.confirm_accept.invoke()
            return
        if phase != "done":
            app.root.after(20, pump)

    app.root.after(20, pump)
    app.root.after(4000, app.cancel_setup)
    app.run_setup()
    assert [(point.x, point.y) for point in app.settings.active_points()] == [
        (1, 1),
        (2, 2),
        (8, 8),
        (9, 9),
    ]


def test_cancel_while_adding_spots_keeps_the_saved_set(app):
    from autoclicker.model import ClickPoint

    app.settings.slots[0].points = [ClickPoint(1, 1), ClickPoint(2, 2)]
    app.refresh()
    state = {"phase": "select"}

    def pump():
        phase = state["phase"]
        if phase == "select" and app.count_buttons:
            app.count_buttons[3].invoke()
            state["phase"] = "next"
            app.root.after(20, pump)
            return
        if phase == "next" and app.count_next is not None:
            state["phase"] = "click"
            app.root.after(20, pump)
            app.count_next.invoke()
            return
        if phase == "click" and app.capture.armed:
            app.cancel_setup()
            return
        app.root.after(20, pump)

    app.root.after(20, pump)
    app.root.after(4000, app.cancel_setup)
    app.run_setup()
    assert app.settings.active_points() == [ClickPoint(1, 1), ClickPoint(2, 2)]


def test_many_spots_scroll_inside_a_bounded_window(app):
    from autoclicker.model import MAX_CLICKS, ClickPoint
    from autoclicker.ui import MAX_POINT_LIST_HEIGHT

    app.settings.slots[0].points = [ClickPoint(i, 1) for i in range(6)]
    app.refresh()
    app.root.update()
    short = app.root.winfo_height()
    app.settings.slots[0].points = [ClickPoint(i, 1) for i in range(MAX_CLICKS)]
    app.refresh()
    app.root.update()
    tall = app.root.winfo_height()
    assert len(app.edit_buttons) == MAX_CLICKS
    assert app.points_canvas.winfo_height() <= MAX_POINT_LIST_HEIGHT
    assert app.points_scrollbar.winfo_manager() == "pack"
    assert tall < 900
    assert tall - short < 180

    app.settings.slots[0].points = [ClickPoint(1, 1)]
    app.refresh()
    app.root.update_idletasks()
    assert app.points_scrollbar.winfo_manager() == ""


def test_clicks_on_the_window_are_not_saved_as_spots(app):
    from autoclicker.model import contains_point
    from autoclicker.ui import _widget_bounds

    app.root.update_idletasks()
    bounds = _widget_bounds(app.root)
    assert bounds is not None
    assert contains_point(bounds[0] + 4, bounds[1] + 4, bounds, pad=8)
    assert app._click_hits_app(bounds[0] + 4, bounds[1] + 4)
    assert not app._click_hits_app(bounds[0] - 40, bounds[1] + bounds[3] + 40)
