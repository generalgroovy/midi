from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from traktor_controller import autocode
from traktor_controller.autocode_visuals import (
    AutocodeF1Visual,
    AutocodeX1Visual,
    f1_indicator_color,
    install,
    x1_indicator_level,
)
from traktor_controller.cli_autocode import validate_config
from traktor_controller.common import ControlEvent, load_config
from traktor_controller.router import EventRouter


class AutocodeIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state = self.root / "state.json"
        self.config = {
            "autocode": {
                "enabled": True,
                "binary": "autocode-local",
                "workspace": str(self.workspace),
                "state_file": str(self.state),
                "poll_seconds": 0.25,
                "f1_indicator": "grid_16",
                "x1_indicator": "hotcue",
            },
            "actions": {},
            "mappings": [],
            "model_controls": {"parameters": {}},
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_state(self, **changes: object) -> None:
        value = {
            "schema_version": 1,
            "sequence": 1,
            "state": "running",
            "workspace": str(self.workspace.resolve()),
            "cue_pending": False,
            **changes,
        }
        self.state.write_text(json.dumps(value), encoding="utf-8")

    def test_real_default_config_and_optional_profile_validate_without_collisions(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        config = load_config(repository / "config.default.json")
        self.assertEqual([], validate_config(config))
        self.assertEqual("linux-ops", config["active_profile"])
        self.assertIn("autocode-ops", config["profiles"])
        actions = {
            mapping["action"]
            for mapping in config["mappings"]
            if mapping.get("profile") == "autocode-ops"
        }
        self.assertIn("autocode_pause", actions)
        self.assertIn("autocode_acknowledge", actions)

    @mock.patch("traktor_controller.autocode.shutil.which")
    def test_action_command_is_fixed_argv_without_shell(self, which: mock.Mock) -> None:
        which.return_value = "/home/otp/.local/bin/autocode-local"
        command = autocode.command(self.config, "pause")
        self.assertEqual(
            [
                "/home/otp/.local/bin/autocode-local",
                "midi-action",
                "pause",
                str(self.workspace.resolve()),
            ],
            command,
        )
        self.assertNotIn("bash", command)
        self.assertNotIn("-c", command)

    @mock.patch("traktor_controller.autocode.subprocess.run")
    @mock.patch("traktor_controller.autocode.shutil.which")
    def test_dispatch_executes_only_allowlisted_action(
        self,
        which: mock.Mock,
        run: mock.Mock,
    ) -> None:
        which.return_value = "/usr/bin/autocode-local"
        run.return_value = subprocess.CompletedProcess([], 0, stdout='{"ok":true}', stderr="")
        result = autocode.dispatch(self.config, "resume")
        self.assertTrue(result["ok"])
        self.assertEqual(
            [
                "/usr/bin/autocode-local",
                "midi-action",
                "resume",
                str(self.workspace.resolve()),
            ],
            run.call_args.args[0],
        )
        with self.assertRaisesRegex(ValueError, "unsupported Autocode action"):
            autocode.dispatch(self.config, "arbitrary-shell")

    def test_state_file_is_bounded_validated_and_workspace_aware(self) -> None:
        self.write_state(state="completed", cue_pending=True)
        value = autocode.read_state(self.config)
        self.assertTrue(value["available"])
        self.assertFalse(value["foreign_workspace"])
        self.assertEqual("completed", value["state"])

        foreign = self.root / "foreign"
        foreign.mkdir()
        self.write_state(workspace=str(foreign))
        self.assertTrue(autocode.read_state(self.config)["foreign_workspace"])

        self.state.unlink()
        target = self.root / "target.json"
        target.write_text("{}", encoding="utf-8")
        self.state.symlink_to(target)
        with self.assertRaisesRegex(RuntimeError, "symbolic link"):
            autocode.read_state(self.config)

    def test_router_translates_distinct_builtin_action_to_closed_enum(self) -> None:
        config = {
            **self.config,
            "mappings": [
                {
                    "profile": "autocode-ops",
                    "device": "f1",
                    "control": "grid_3",
                    "kind": "press",
                    "action": "autocode_pause",
                    "enabled": True,
                }
            ],
        }
        router = EventRouter(config, monitor=False, profile="autocode-ops", dry_run=True)
        mapping = router.mappings[("f1", "grid_3", "press")][0]
        event = ControlEvent("f1", "grid_3", "press", 1)
        with mock.patch("traktor_controller.router.dispatch_autocode") as dispatch:
            router._dispatch(mapping, event)
        dispatch.assert_called_once_with(config, "pause", dry_run=True)

    def test_led_state_translation_is_deterministic(self) -> None:
        self.assertEqual((0, 127, 24), f1_indicator_color({"state": "completed"}))
        self.assertEqual(
            (100, 127, 100),
            f1_indicator_color({"state": "running", "cue_pending": True}),
        )
        self.assertEqual(60, x1_indicator_level({"state": "running"}))
        self.assertEqual(127, x1_indicator_level({"state": "completed", "cue_pending": True}))

    def test_backend_install_replaces_hardware_visual_classes_only(self) -> None:
        from traktor_controller import hardware

        original_runtime = hardware.ControllerRuntime
        install()
        self.assertIs(hardware.F1Visual, AutocodeF1Visual)
        self.assertIs(hardware.X1Visual, AutocodeX1Visual)
        self.assertIs(hardware.ControllerRuntime, original_runtime)

    def test_invalid_integration_configuration_is_reported(self) -> None:
        invalid = {
            **self.config,
            "autocode": {
                "enabled": True,
                "binary": "/tmp/arbitrary command",
                "workspace": "",
                "state_file": "",
                "poll_seconds": 0.01,
            },
        }
        errors = autocode.validate(invalid)
        self.assertTrue(any("simple executable name" in error for error in errors))
        self.assertTrue(any("workspace" in error for error in errors))
        self.assertTrue(any("state_file" in error for error in errors))
        self.assertTrue(any("poll_seconds" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
