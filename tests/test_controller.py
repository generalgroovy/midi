from __future__ import annotations

import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from traktor_controller.actions import ActionDispatcher
from traktor_controller.cli import validate_config
from traktor_controller.common import load_config
from traktor_controller.router import EventRouter


class FakeDispatcher:
    def __init__(self) -> None:
        self.actions: list[str] = []

    def dispatch(self, mapping, event) -> None:
        signature = mapping["action"]
        if signature == "script_slot":
            signature += ":" + mapping["slot"]
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
    def test_default_config_and_unique_layout(self) -> None:
        config = load_config(Path("config.default.json"))
        self.assertEqual([], validate_config(config))
        self.assertGreaterEqual(len(config["mappings"]), 100)
        for device in ("f1", "x1"):
            signatures = []
            for mapping in config["mappings"]:
                if mapping.get("device") != device or not mapping.get("enabled", True):
                    continue
                action = mapping["action"]
                if action == "script_slot":
                    action += ":" + mapping["slot"]
                elif action.startswith("model_parameter_"):
                    action += ":" + mapping["parameter"]
                signatures.append(action)
            self.assertEqual(len(signatures), len(set(signatures)), device)

    def test_required_high_value_bindings(self) -> None:
        config = load_config(Path("config.default.json"))
        bindings = {
            (m["device"], m["control"], m["kind"]): m["action"]
            for m in config["mappings"]
            if m.get("enabled", True) and not m.get("requires")
        }
        self.assertEqual(
            "controller_brightness_absolute",
            bindings[("f1", "knob_4", "absolute")],
        )
        self.assertEqual(
            "close_focused_window",
            bindings[("f1", "grid_16", "press")],
        )
        self.assertEqual(
            "window_move_horizontal_relative",
            bindings[("x1", "deck_a_browse_encoder", "relative")],
        )
        self.assertEqual(
            "window_resize_height_relative",
            bindings[("x1", "deck_b_loop_encoder", "relative")],
        )
        close_bindings = [
            m for m in config["mappings"]
            if m.get("enabled", True) and m.get("action") == "close_focused_window"
        ]
        self.assertEqual(1, len(close_bindings))

    def test_x1_alias_and_shift_layer(self) -> None:
        config = {"actions": {"normal": ["true"], "shifted": ["true"]}, "mappings": [
            {"device": "x1", "control": "deck_a_play", "kind": "press", "action": "normal", "unless": "x1.shift"},
            {"device": "x1", "control": "deck_a_play", "kind": "press", "action": "shifted", "requires": "x1.shift"},
        ]}
        router = EventRouter(config, monitor=False)
        fake = FakeDispatcher()
        router.dispatcher = fake
        router.emit(SimpleNamespace(device="x1", control="BTN_36", kind="press", value=1))
        router.emit(SimpleNamespace(device="x1", control="BTN_0", kind="press", value=1))
        self.assertEqual(["shifted"], fake.actions)

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
            event = SimpleNamespace(
                device="x1", control="fx1_dry_wet",
                raw_control="fx1_dry_wet", kind="absolute",
                value=2048, minimum=0, maximum=4096,
            )
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
            event = SimpleNamespace(
                device="f1", control="knob_4", raw_control="knob_4",
                kind="absolute", value=1024, minimum=0, maximum=4096,
            )
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
        event = SimpleNamespace(
            device="f1", control="grid_2", raw_control="grid_2",
            kind="press", value=1, minimum=0, maximum=1,
        )
        rendered = dispatcher._render(
            dispatcher.script_slots["codex"]["command"],
            event, {"slot": "codex"},
        )
        self.assertEqual(["echo", "codex", "grid_2"], rendered)

    def test_f1_visual_packet_and_press_feedback(self) -> None:
        backend = load_backend()
        with tempfile.TemporaryDirectory() as directory:
            config = load_config(Path("config.default.json"))
            config["visuals"]["brightness_state_file"] = str(Path(directory) / "brightness")
            device = FakeHid()
            visual = backend.F1Visual(device, config, "category")
            self.assertEqual(0x80, device.writes[-1][0])
            self.assertEqual(81, len(device.writes[-1]))
            visual.feedback("grid_1", True)
            packet = device.writes[-1]
            self.assertEqual((127, 127, 127), (packet[26], packet[27], packet[25]))
            visual.clear()

    def test_live_visual_brightness_scaling(self) -> None:
        backend = load_backend()
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "brightness"
            state.write_text("50\n")
            config = load_config(Path("config.default.json"))
            config["visuals"]["brightness_state_file"] = str(state)
            device = FakeHid()
            visual = backend.F1Visual(device, config, "category")
            visual.feedback("grid_1", True)
            packet = device.writes[-1]
            self.assertEqual((64, 64, 64), (packet[26], packet[27], packet[25]))
            state.write_text("25\n")
            time.sleep(0.2)
            packet = device.writes[-1]
            self.assertLessEqual(max(packet[25:28]), 32)
            visual.clear()

    def test_x1_visual_led_write(self) -> None:
        backend = load_backend()
        with tempfile.TemporaryDirectory() as directory:
            config = load_config(Path("config.default.json"))
            config["visuals"]["brightness_state_file"] = str(Path(directory) / "brightness")
            device = FakeUsb()
            visual = backend.X1Visual(device, config, "neon")
            self.assertEqual(0x01, device.writes[-1][0])
            visual.feedback("deck_a_play", True)
            self.assertEqual(127, device.writes[-1][1][24])
            visual.clear()

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
