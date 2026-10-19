import pytest

from autoclicker.model import (
    MAX_INTERVAL,
    MIN_INTERVAL,
    ClickPoint,
    Settings,
    SetupSession,
    contains_point,
    format_hotkey,
    format_speed,
    gap_from_slider,
    is_valid_hotkey,
    order_text,
    settings_from_dict,
    slider_from_gap,
)


def test_slider_round_trip():
    for position in (0, 0.25, 0.5, 0.75, 1):
        gap = gap_from_slider(position)
        assert slider_from_gap(gap) == pytest.approx(position)
    assert gap_from_slider(0) == pytest.approx(MAX_INTERVAL)
    assert gap_from_slider(1) == pytest.approx(MIN_INTERVAL)
    assert gap_from_slider(-2) == pytest.approx(MAX_INTERVAL)
    assert gap_from_slider(4) == pytest.approx(MIN_INTERVAL)


def test_speed_labels():
    assert format_speed(0.25) == "4 clicks/sec"
    assert format_speed(0.05) == "20 clicks/sec"
    assert format_speed(1) == "1 click every 1 s"
    assert format_speed(2) == "1 click every 2 s"


def test_hotkey_labels_and_validation():
    assert format_hotkey("<f6>") == "F6"
    assert format_hotkey("<space>") == "Space"
    assert format_hotkey("a") == "A"
    assert is_valid_hotkey("<f8>")
    assert is_valid_hotkey("b")
    assert not is_valid_hotkey("<ctrl>")
    assert not is_valid_hotkey("<shift_l>")
    assert not is_valid_hotkey("ctrl+a")
    assert not is_valid_hotkey("<ctrl>+s+t")
    assert not is_valid_hotkey("")


def test_order_text():
    assert "No clicks" in order_text(0)
    assert order_text(1) == "Click 1 repeats until you pause"
    assert order_text(3) == "1 → 2 → 3, then it repeats"


def test_setup_session_confirms_each_spot_before_saving_it():
    session = SetupSession(3)
    assert session.index == 1
    session.offer(10, 20)
    session.reject()
    assert session.points == []
    session.offer(11, 21)
    session.accept()
    session.offer(12, 22)
    session.accept()
    assert not session.done
    session.offer(13, 23)
    session.accept()
    assert session.done
    assert session.points == [
        ClickPoint(11, 21),
        ClickPoint(12, 22),
        ClickPoint(13, 23),
    ]


def test_setup_session_rejects_counts_outside_one_to_five():
    with pytest.raises(ValueError):
        SetupSession(0)
    with pytest.raises(ValueError):
        SetupSession(6)


def test_settings_repair_bad_values():
    settings = settings_from_dict(
        {
            "active_slot": 9,
            "hotkey": "<ctrl>",
            "interval": 99,
            "slots": [
                {"points": [{"x": 1, "y": 2}, {"x": True, "y": 3}, {"x": "4", "y": "5"}]},
                "nope",
            ],
        }
    )
    assert settings.active_slot == 0
    assert settings.hotkey == "<f6>"
    assert settings.interval == 2.0
    assert settings.slots[0].points == [ClickPoint(1, 2), ClickPoint(4, 5)]
    assert len(settings.slots) == 5
    assert settings_from_dict(settings.to_dict()).slots[0].points == settings.slots[0].points


def test_contains_point_uses_padding():
    bounds = (100, 50, 40, 20)
    assert contains_point(100, 50, bounds)
    assert not contains_point(99, 50, bounds)
    assert contains_point(90, 40, bounds, pad=12)
    assert not contains_point(80, 40, bounds, pad=12)


def test_new_settings_have_five_empty_sets():
    settings = Settings()
    assert len(settings.slots) == 5
    assert settings.active_points() == []
    assert settings.hotkey == "<f6>"
