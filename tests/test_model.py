import pytest

from autoclicker.model import (
    MAX_CLICKS,
    MAX_INTERVAL,
    MIN_INTERVAL,
    ClickPoint,
    Settings,
    SetupSession,
    canonical_hotkey,
    contains_point,
    display_set_name,
    format_hotkey,
    format_speed,
    gap_from_slider,
    is_stop_key,
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
    assert format_hotkey("<ctrl>+a") == "Ctrl + A"
    assert format_hotkey("<alt>+<f8>") == "Alt + F8"
    assert format_hotkey("<shift>+<space>") == "Shift + Space"
    assert format_hotkey("<ctrl>+<shift>+x") == "Ctrl + Shift + X"
    assert is_valid_hotkey("<f6>")
    assert is_valid_hotkey("b")
    assert is_valid_hotkey("<ctrl>+a")
    assert is_valid_hotkey("<alt>+<f4>")
    assert is_valid_hotkey("<shift>+b")
    assert is_valid_hotkey("<ctrl>+<alt>+z")
    assert is_valid_hotkey("<ctrl_l>+b")
    assert canonical_hotkey("<ctrl_l>+b") == "<ctrl>+b"
    assert canonical_hotkey("<shift>+<ctrl>+x") == "<ctrl>+<shift>+x"
    assert not is_valid_hotkey("<ctrl>")
    assert not is_valid_hotkey("<shift_l>")
    assert not is_valid_hotkey("<alt>")
    assert not is_valid_hotkey("ctrl+a")
    assert not is_valid_hotkey("<ctrl>+s+t")
    assert not is_valid_hotkey("<ctrl>+t+s")
    assert not is_valid_hotkey("<ctrl_l>+s+t")
    assert not is_valid_hotkey("<f8>")
    assert not is_valid_hotkey("<cmd>+a")
    assert not is_valid_hotkey("")
    assert is_stop_key("<f8>")
    assert not is_stop_key("<ctrl>+s+t")
    assert not is_stop_key("<ctrl>+s")
    assert not is_stop_key("<f6>")
    assert not is_stop_key("<shift>+<f8>")


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


def test_setup_session_keeps_saved_spots_and_allows_thirty():
    existing = [ClickPoint(1, 1), ClickPoint(2, 2)]
    session = SetupSession(4, existing)
    assert session.index == 3
    assert session.points == existing
    session.offer(3, 3)
    session.accept()
    session.offer(4, 4)
    session.accept()
    assert session.done
    assert session.points == existing + [ClickPoint(3, 3), ClickPoint(4, 4)]

    smaller = SetupSession(1, existing)
    assert smaller.done
    assert smaller.points == [ClickPoint(1, 1)]

    assert SetupSession(MAX_CLICKS).count == MAX_CLICKS
    with pytest.raises(ValueError):
        SetupSession(0)
    with pytest.raises(ValueError):
        SetupSession(MAX_CLICKS + 1)


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
    assert settings.slots[0].name == ""
    assert len(settings.slots) == 5
    assert settings_from_dict(settings.to_dict()).slots[0].points == settings.slots[0].points
    assert [display_set_name(slot.name, index) for index, slot in enumerate(settings.slots)] == [
        "Set 1",
        "Set 2",
        "Set 3",
        "Set 4",
        "Set 5",
    ]


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
    assert [slot.name for slot in settings.slots] == ["", "", "", "", ""]


def test_names_chords_and_long_sets_round_trip():
    points = [ClickPoint(i, i + 1) for i in range(12)]
    settings = Settings(hotkey="<ctrl>+a", active_slot=2)
    settings.slots[2].name = "  Farm north  "
    settings.slots[2].points = points
    restored = settings_from_dict(settings.to_dict())
    assert restored.active_slot == 2
    assert restored.hotkey == "<ctrl>+a"
    assert restored.slots[2].name == "Farm north"
    assert restored.slots[2].points == points
    assert display_set_name(restored.slots[2].name, 2) == "Farm north"
    assert display_set_name("", 0) == "Set 1"
    assert display_set_name("   ", 4) == "Set 5"
    assert restored.to_dict()["version"] == 1


def test_old_settings_without_names_still_load():
    settings = settings_from_dict(
        {
            "version": 1,
            "active_slot": 1,
            "hotkey": "<f7>",
            "interval": 0.5,
            "slots": [{"points": [{"x": 3, "y": 4}]}],
        }
    )
    assert settings.active_slot == 1
    assert settings.hotkey == "<f7>"
    assert settings.slots[0].points == [ClickPoint(3, 4)]
    assert settings.slots[0].name == ""
    assert [display_set_name(slot.name, index) for index, slot in enumerate(settings.slots)] == [
        "Set 1",
        "Set 2",
        "Set 3",
        "Set 4",
        "Set 5",
    ]


def test_too_many_points_and_f8_are_repaired():
    settings = settings_from_dict(
        {
            "hotkey": "<f8>",
            "slots": [
                {
                    "name": "Big",
                    "points": [{"x": i, "y": i, "on": i % 2 == 0} for i in range(40)],
                }
            ],
        }
    )
    assert settings.hotkey == "<f6>"
    assert settings.slots[0].name == "Big"
    assert len(settings.slots[0].points) == MAX_CLICKS
    assert settings.slots[0].points[0] == ClickPoint(0, 0, enabled=True)
    assert settings.slots[0].points[1] == ClickPoint(1, 1, enabled=False)
    assert settings.slots[0].points[-1] == ClickPoint(29, 29, enabled=False)
    assert settings_from_dict({"hotkey": "<alt>+b"}).hotkey == "<alt>+b"
    assert settings_from_dict({"hotkey": "<ctrl>+s+t"}).hotkey == "<f6>"


def test_old_points_without_a_toggle_stay_on():
    settings = settings_from_dict({"slots": [{"points": [{"x": 3, "y": 4}, {"x": 5, "y": 6, "on": False}]}]})
    assert settings.slots[0].points == [
        ClickPoint(3, 4, enabled=True),
        ClickPoint(5, 6, enabled=False),
    ]
    assert settings.enabled_points() == [ClickPoint(3, 4, enabled=True)]
