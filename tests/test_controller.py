from __future__ import annotations

import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from traktor_controller.cli import validate_config
from traktor_controller.common import ControlEvent, load_config
from traktor_controller.router import EventRouter
from traktor_controller.unified_actions import ActionDispatcher


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


def load_backend():
    path = Path("traktor-system-controller.py").resolve()
    spec = importlib.util.spec_from_file_location("test_backend", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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

    def test_f1_unified_controls(self) -> None:
        bindings = {
            (m["device"], m["control"], m["kind"], tuple(m.get("requires", []))): m["action"]
            for m in self.config["mappings"]
            if m.get("enabled", True)
        }
        self.assertEqual(
            "controller_brightness_absolute",
            bindings[("f1", "knob_3", "absolute", ())],
        )
        self.assertEqual(
            "brightness_absolute",
            bindings[("f1", "knob_4", "absolute", ())],
        )
        self.assertEqual(
            "color_temperature_absolute",
            bindings[("f1", "fader_3", "absolute", ())],
        )
        self.assertEqual(
            "close_focused_window",
            bindings[("f1", "reverse", "press", ())],
        )
        close_bindings = [
            m for m in self.config["mappings"]
            if m.get("enabled", True) and m.get("action") == "close_focused_window"
        ]
        self.assertEqual(1, len(close_bindings))

    def test_x1_window_cockpit_controls(self) -> None:
        expected_absolute = {
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
        self.assertEqual(expected_absolute, actual)
        relative = {
            mapping["control"]: mapping["action"]
            for mapping in self.config["mappings"]
            if mapping.get("device") == "x1"
            and mapping.get("kind") == "relative"
        }
        self.assertEqual("window_move_horizontal_relative", relative["deck_a_browse_encoder"])
        self.assertEqual("window_move_vertical_relative", relative["deck_b_browse_encoder"])
        self.assertEqual("window_resize_width_relative", relative["deck_a_loop_encoder"])
        self.assertEqual("window_resize_height_relative", relative["deck_b_loop_encoder"])

    def test_shift_and_hotcue_layers_route_exclusively(self) -> None:
        router = EventRouter(self.config, monitor=False)
        fake = FakeDispatcher()
        router.dispatcher = fake

        router.emit(SimpleNamespace(device="f1", control="shift", kind="press", value=1))
        router.emit(SimpleNamespace(
            device="f1", control="knob_1", kind="absolute", value=2048,
            minimum=0, maximum=4096,
        ))
        self.assertEqual(["model_parameter_absolute:temperature"], fake.actions)

        fake.actions.clear()
        router.emit(SimpleNamespace(device="x1", control="BTN_39", kind="press", value=1))
        router.emit(SimpleNamespace(device="x1", control="BTN_20", kind="press", value=1))
        self.assertEqual(["system_info"], fake.actions)

    def test_color_temperature_uses_wayland_reset_and_debounce(self) -> None:
        dispatcher = ActionDispatcher(self.config, dry_run=True)
        commands: list[tuple[list[str] | str, str]] = []
        dispatcher._run = lambda command, action, confirm=None: commands.append((command, action))
        dispatcher.dispatch(
            {
                "action": "color_temperature_absolute",
                "minimum_kelvin": 2500,
                "maximum_kelvin": 6500,
                "adjustment_method": "wayland",
                "debounce_ms": 180,
            },
            ControlEvent("f1", "fader_3", "absolute", 2048, 0, 4096),
        )
        self.assertEqual(
            (["gammastep", "-P", "-m", "wayland", "-O", "4500"],
             "color_temperature_absolute"),
            commands[-1],
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

    def test_controller_brightness_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "brightness"
            config = {
                "runtime": {"log_actions": False},
                "visuals": {"brightness_state_file": str(path)},
            }
            dispatcher = ActionDispatcher(config)
            event = ControlEvent("f1", "knob_3", "absolute", 1024, 0, 4096)
            dispatcher.dispatch({"action": "controller_brightness_absolute"}, event)
            self.assertEqual("25", path.read_text().strip())

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
            event, {"slot": "codex"},
        )
        self.assertEqual(["echo", "codex", "grid_2"], rendered)

    def test_visual_feedback_and_live_brightness(self) -> None:
        backend = load_backend()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "brightness"
            state.write_text("50\n")
            config = load_config(Path("config.default.json"))
            config["visuals"]["brightness_state_file"] = str(state)
            f1_device = FakeHid()
            x1_device = FakeUsb()
            f1 = backend.F1Visual(f1_device, config, "category")
            x1 = backend.X1Visual(x1_device, config, "neon")
            f1.feedback("grid_1", True)
            packet = f1_device.writes[-1]
            self.assertEqual((64, 64, 64), (packet[26], packet[27], packet[25]))
            x1.feedback("deck_a_play", True)
            self.assertEqual(64, x1_device.writes[-1][1][24])
            state.write_text("25\n")
            time.sleep(0.2)
            self.assertLessEqual(max(f1_device.writes[-1][25:28]), 32)
            f1.clear()
            x1.clear()

    def test_connection_always_policy(self) -> None:
        backend = load_backend()
        with tempfile.TemporaryDirectory() as directory:
            config = {
                "connection": {
                    "policy": "always",
                    "state_file": str(Path(directory) / "devices.json"),
                }
            }
            consent = backend.ConnectionConsent(config)
            self.assertTrue(consent.allowed("x1", "X1"))


if __name__ == "__main__":
    unittest.main()
