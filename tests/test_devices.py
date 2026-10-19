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
