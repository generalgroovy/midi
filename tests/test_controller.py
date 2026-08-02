from __future__ import annotations

import tempfile
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
        self.actions.append(mapping["action"])


class ControllerTests(unittest.TestCase):
    def test_default_config_and_includes(self) -> None:
        config = load_config(Path("config.default.json"))
        self.assertEqual([], validate_config(config))
        self.assertGreaterEqual(len(config["mappings"]), 60)

    def test_x1_alias(self) -> None:
        config = {"actions": {"go": ["true"]}, "mappings": [
            {"device": "x1", "control": "deck_a_play", "kind": "press", "action": "go"}
        ]}
        router = EventRouter(config, monitor=False)
        fake = FakeDispatcher()
        router.dispatcher = fake
        router.emit(SimpleNamespace(device="x1", control="BTN_0", kind="press", value=1))
        self.assertEqual(["go"], fake.actions)

    def test_shift_layer(self) -> None:
        config = {"actions": {"normal": ["true"], "shifted": ["true"]}, "mappings": [
            {"device": "x1", "control": "deck_a_play", "kind": "press", "action": "normal", "unless": "x1.shift"},
            {"device": "x1", "control": "deck_a_play", "kind": "press", "action": "shifted", "requires": "x1.shift"}
        ]}
        router = EventRouter(config, monitor=False)
        fake = FakeDispatcher()
        router.dispatcher = fake
        router.emit(SimpleNamespace(device="x1", control="BTN_36", kind="press", value=1))
        router.emit(SimpleNamespace(device="x1", control="BTN_0", kind="press", value=1))
        self.assertEqual(["shifted"], fake.actions)

    def test_command_placeholders(self) -> None:
        dispatcher = ActionDispatcher({"actions": {"test": ["echo", "{control}", "{percent}"]}}, dry_run=True)
        event = SimpleNamespace(device="f1", control="knob_1", raw_control="knob_1", kind="absolute", value=2048, minimum=0, maximum=4096)
        command = dispatcher._render(dispatcher.actions["test"], event, {})
        self.assertEqual(["echo", "knob_1", "50"], command)

    def test_recursive_include_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text('{"include":"config.json"}')
            with self.assertRaises(SystemExit):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
