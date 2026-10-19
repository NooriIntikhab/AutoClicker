import json

from autoclicker.model import ClickPoint
from autoclicker.storage import load_settings, save_settings, settings_path


def test_round_trip(tmp_path):
    path = tmp_path / "settings.json"
    settings = load_settings(path)
    settings.active_slot = 2
    settings.hotkey = "<f8>"
    settings.interval = 0.5
    settings.slots[2].points = [ClickPoint(8, 9), ClickPoint(-20, 400)]
    save_settings(settings, path)
    loaded = load_settings(path)
    assert loaded.active_slot == 2
    assert loaded.hotkey == "<f8>"
    assert loaded.interval == 0.5
    assert loaded.slots[2].points == [ClickPoint(8, 9), ClickPoint(-20, 400)]
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


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


def test_settings_path_override(monkeypatch, tmp_path):
    target = tmp_path / "custom.json"
    monkeypatch.setenv("AUTOCLICKER_SETTINGS", str(target))
    assert settings_path() == target


def test_default_settings_path_name(monkeypatch):
    monkeypatch.delenv("AUTOCLICKER_SETTINGS", raising=False)
    path = settings_path()
    assert path.name == "settings.json"
    assert path.parent.name == "AutoClicker"
