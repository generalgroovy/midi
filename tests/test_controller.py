from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from traktor_controller.advanced_actions import ActionDispatcher
from traktor_controller.cli import validate_config
from traktor_controller.common import ControlEvent, load_config
from traktor_controller.router import EventRouter
from traktor_controller.visual_extensions import (
    F1Visual, X1Visual, read_visual_brightness,
)


class FakeDispatcher:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def dispatch(self, mapping, event) -> None:
        signature = mapping["action"]
        if signature == "script_slot":
            signature += ":" + mapping["slot"]
        elif signature.startswith("model_parameter_"):
            signature += ":" + mapping["parameter"]
        self.actions.append(signature)


class FakeHid:
    def __init__(self) -> None:
        self.writes: list[bytes] = []

    def write(self, data) -> int:
        self.writes.append(bytes(data))
        return len(data)


class FakeUsb:
    def __init__(self) -> None:
        self.writes: list[tuple[int, bytes]] = []

    def write(self, endpoint, data, timeout=0):
        self.writes.append((endpoint, bytes(data)))
        return len(data)

    def read(self, endpoint, length, timeout=0):
        return bytes([0] * length)


class ControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(Path("config.default.json"))

    def test_default_config_is_unique_and_complete(self) -> None:
        self.assertEqual([], validate_config(self.config))
        self.assertGreaterEqual(len(self.config["mappings"]), 120)
        for device in ("f1", "x1"):
            signatures: list[str] = []
            for mapping in self.config["mappings"]:
                if mapping.get("device") != device or not mapping.get("enabled", True):
                    continue
                action = mapping["action"]
                if action == "script_slot":
                    action += ":" + mapping["slot"]
                elif action.startswith("model_parameter_"):
                    action += ":" + mapping["parameter"]
                signatures.append(action)
            self.assertEqual(len(signatures), len(set(signatures)), device)

    def test_f1_has_single_close_binding_and_light_knob(self) -> None:
        close = [
            mapping for mapping in self.config["mappings"]
            if mapping.get("action") == "close_focused_window"
        ]
        self.assertEqual(1, len(close))
        self.assertEqual(("f1", "reverse", "press"), (
            close[0]["device"], close[0]["control"], close[0]["kind"]
        ))
        light = [
            mapping for mapping in self.config["mappings"]
            if mapping.get("action") == "hardware_light_absolute"
        ]
        self.assertEqual(1, len(light))
        self.assertEqual("knob_3", light[0]["control"])
        self.assertEqual(["f1.shift"], light[0]["unless"])
        self.assertEqual(
            ["swaymsg", "kill"],
            self.config["actions"]["close_focused_window"],
        )

    def test_x1_eight_knobs_are_unique_window_controls(self) -> None:
        expected = {
            "fx1_dry_wet": "window_x_absolute",
            "fx1_knob_1": "window_y_absolute",
            "fx1_knob_2": "window_width_absolute",
            "fx1_knob_3": "window_height_absolute",
            "fx2_dry_wet": "window_opacity_absolute",
            "fx2_knob_1": "window_border_absolute",
            "fx2_knob_2": "sway_gap_absolute",
            "fx2_knob_3": "window_output_absolute",
        }
        actual = {
            mapping["control"]: mapping["action"]
            for mapping in self.config["mappings"]
            if mapping.get("device") == "x1"
            and mapping.get("kind") == "absolute"
        }
        self.assertEqual(expected, actual)

    def test_shift_and_hotcue_layers_route_exclusively(self) -> None:
        router = EventRouter(self.config, monitor=False)
        fake = FakeDispatcher()
        router.dispatcher = fake

        router.emit(SimpleNamespace(
            device="f1", control="shift", kind="press", value=1
        ))
        router.emit(SimpleNamespace(
            device="f1", control="knob_1", kind="absolute", value=2048,
            minimum=0, maximum=4096,
        ))
        self.assertEqual(["model_parameter_absolute:temperature"], fake.actions)

        fake.actions.clear()
        router.emit(SimpleNamespace(
            device="x1", control="BTN_39", kind="press", value=1
        ))
        router.emit(SimpleNamespace(
            device="x1", control="BTN_20", kind="press", value=1
        ))
        self.assertEqual(["system_info"], fake.actions)

    def test_hardware_light_updates_f1_and_x1_live(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = dict(self.config)
            config["visuals"] = dict(self.config["visuals"])
            config["visuals"]["light_brightness_state_file"] = str(
                Path(directory) / "brightness.json"
            )
            f1_device = FakeHid()
            x1_device = FakeUsb()
            f1 = F1Visual(f1_device, config, "category")
            x1 = X1Visual(x1_device, config, "category")

            dispatcher = ActionDispatcher(config)
            dispatcher.dispatch(
                {"action": "hardware_light_absolute"},
                ControlEvent("f1", "knob_3", "absolute", 1024, 0, 4096),
            )
            self.assertAlmostEqual(0.25, read_visual_brightness(config), places=3)
            self.assertAlmostEqual(0.25, f1.brightness, places=3)
            self.assertAlmostEqual(0.25, x1.brightness, places=3)
            self.assertLess(max(f1_device.writes[-1][1:]), 128)
            self.assertLess(max(x1_device.writes[-1][1]), 128)

    def test_window_controls_are_safe_in_dry_run(self) -> None:
        dispatcher = ActionDispatcher(self.config, dry_run=True)
        event = ControlEvent("x1", "fx1_dry_wet", "absolute", 2048, 0, 4095)
        dispatcher.dispatch({"action": "window_x_absolute"}, event)
        dispatcher.dispatch({"action": "window_output_absolute"}, event)
        dispatcher.dispatch(
            {"action": "window_opacity_absolute", "minimum": 0.2}, event
        )

    def test_model_parameter_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            config = {
                "runtime": {"log_actions": False},
                "model_controls": {
                    "state_file": str(path), "notify": False,
                    "parameters": {
                        "temperature": {
                            "min": 0.0, "max": 2.0, "step": 0.01,
                            "default": 0.7, "decimals": 2,
                        }
                    },
                },
            }
            dispatcher = ActionDispatcher(config)
            event = ControlEvent("f1", "knob_1", "absolute", 2048, 0, 4096)
            dispatcher.dispatch(
                {"action": "model_parameter_absolute", "parameter": "temperature"},
                event,
            )
            state = json.loads(path.read_text())
            self.assertEqual(1.0, state["temperature"])

    def test_script_slot_dry_run(self) -> None:
        config = {
            "runtime": {"log_actions": False},
            "script_slots": {
                "codex": {
                    "enabled": True,
                    "command": ["echo", "{slot}", "{control}"],
                }
            },
        }
        dispatcher = ActionDispatcher(config, dry_run=True)
        event = ControlEvent("f1", "grid_2", "press", 1)
        rendered = dispatcher._render(
            dispatcher.script_slots["codex"]["command"],
            event,
            {"slot": "codex"},
        )
        self.assertEqual(["echo", "codex", "grid_2"], rendered)


if __name__ == "__main__":
    unittest.main()
