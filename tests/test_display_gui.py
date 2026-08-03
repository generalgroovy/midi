from pathlib import Path

from traktor_controller.common import ControlEvent, load_config
from traktor_controller.unified_actions import ActionDispatcher


def test_display_defaults_and_brightness_dry_run():
    config = load_config(Path("config.default.json"))
    settings = config["display_controls"]
    assert settings["brightness"]["backend"] == "auto"
    assert settings["color_temperature"]["maximum_kelvin"] == 6500
    dispatcher = ActionDispatcher(config, dry_run=True)
    assert dispatcher.set_brightness_percent(50)
    dispatcher.dispatch(
        {"action": "brightness_absolute"},
        ControlEvent("f1", "knob_4", "absolute", 50, 0, 100),
    )


def test_color_temperature_dry_run(monkeypatch):
    config = load_config(Path("config.default.json"))
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-test")
    dispatcher = ActionDispatcher(config, dry_run=True)
    assert dispatcher.set_color_temperature_kelvin(4500)
