import os

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="pynput needs a display on Linux")


def test_key_to_spec_maps_letters_and_function_keys():
    from pynput.keyboard import Key, KeyCode

    from autoclicker.devices import key_to_spec

    assert key_to_spec(Key.f6) == "<f6>"
    assert key_to_spec(Key.space) == "<space>"
    assert key_to_spec(Key.esc) == "<esc>"
    assert key_to_spec(Key.ctrl_l) is None
    assert key_to_spec(Key.shift) is None
    assert key_to_spec(KeyCode.from_char("A")) == "a"
    assert key_to_spec(KeyCode.from_char("\x01")) is None


def test_recorder_builds_modifier_chords_and_ignores_a_modifier_alone():
    from pynput.keyboard import HotKey, Key, KeyCode

    from autoclicker.devices import HotkeyRecorder

    recorder = HotkeyRecorder()
    assert recorder.press(Key.ctrl_l) is None
    spec = recorder.press(KeyCode.from_char("a"))
    assert spec == "<ctrl>+a"
    HotKey.parse(spec)

    recorder = HotkeyRecorder()
    assert recorder.press(Key.shift_r) is None
    spec = recorder.press(Key.f6)
    assert spec == "<shift>+<f6>"
    HotKey.parse(spec)

    recorder = HotkeyRecorder()
    assert recorder.press(Key.alt) is None
    recorder.press(Key.ctrl)
    spec = recorder.press(KeyCode.from_char("Z"))
    assert spec == "<ctrl>+<alt>+z"
    HotKey.parse(spec)

    recorder = HotkeyRecorder()
    recorder.press(Key.ctrl)
    assert recorder.press(KeyCode.from_char("\x01")) == "<ctrl>+a"

    recorder = HotkeyRecorder()
    recorder.press(Key.alt_l)
    recorder.release(Key.alt_l)
    assert recorder.press(KeyCode.from_char("c")) == "c"

    recorder = HotkeyRecorder()
    assert recorder.press(Key.esc) == "<esc>"
    assert recorder.press(Key.cmd) is None
