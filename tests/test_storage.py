import json

from autoclicker.model import MAX_CLICKS, ClickPoint, display_set_name
from autoclicker.storage import load_settings, save_settings, settings_path


def test_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    settings = load_settings(path)
    settings.active_slot = 2
    settings.hotkey = "<ctrl>+a"
    settings.interval = 0.5
    settings.slots[2].name = "Farm"
    settings.slots[2].points = [ClickPoint(i, i + 3) for i in range(12)]
    settings.slots[2].points.extend([ClickPoint(8, 9), ClickPoint(-20, 400)])
    save_settings(settings, path)
    loaded = load_settings(path)
    assert loaded.active_slot == 2
    assert loaded.hotkey == "<ctrl>+a"
    assert loaded.interval == 0.5
    assert loaded.slots[2].name == "Farm"
    assert loaded.slots[2].points[0] == ClickPoint(0, 3)
    assert loaded.slots[2].points[-1] == ClickPoint(-20, 400)
    assert len(loaded.slots[2].points) == 14
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert payload["slots"][2]["name"] == "Farm"


def test_corrupt_file_falls_back_and_is_kept(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    settings = load_settings(path)
    assert settings.active_slot == 0
    assert settings.slots[0].points == []
    assert (tmp_path / "settings.corrupt.json").read_text(encoding="utf-8") == "{not json"


def test_missing_file_is_a_fresh_app(tmp_path):
    settings = load_settings(tmp_path / "missing.json")
    assert len(settings.slots) == 5


def test_old_settings_file_without_names_loads(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "active_slot": 0,
                "hotkey": "<f6>",
                "interval": 0.25,
                "slots": [{"points": [{"x": 3, "y": 4}, {"x": 5, "y": 6}]}],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_settings(path)
    assert loaded.slots[0].name == ""
    assert loaded.slots[0].points == [ClickPoint(3, 4), ClickPoint(5, 6)]
    assert [display_set_name(slot.name, index) for index, slot in enumerate(loaded.slots)] == [
        "Set 1",
        "Set 2",
        "Set 3",
        "Set 4",
        "Set 5",
    ]


def test_saved_stop_chord_falls_back_and_extra_points_trim(tmp_path):
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "hotkey": "<ctrl>+t+s",
                "slots": [{"name": "Wide", "points": [{"x": i, "y": 1} for i in range(MAX_CLICKS + 5)]}],
            }
        ),
        encoding="utf-8",
    )
    loaded = load_settings(path)
    assert loaded.hotkey == "<f6>"
    assert loaded.slots[0].name == "Wide"
    assert len(loaded.slots[0].points) == MAX_CLICKS


def test_settings_path_override(monkeypatch, tmp_path):
    target = tmp_path / "custom.json"
    monkeypatch.setenv("AUTOCLICKER_SETTINGS", str(target))
    assert settings_path() == target


def test_default_settings_path_name(monkeypatch):
    monkeypatch.delenv("AUTOCLICKER_SETTINGS", raising=False)
    path = settings_path()
    assert path.name == "settings.json"
    assert path.parent.name == "AutoClicker"
