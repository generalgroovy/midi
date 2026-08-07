from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from traktor_controller.autocode_visuals import _AutocodeOverlay
from traktor_controller.common import load_config


class _DummyOverlay(_AutocodeOverlay):
    def _render(self) -> None:
        raise AssertionError("disabled Autocode overlay must not render")


class CoreRuntimeRegressionTests(unittest.TestCase):
    def test_default_runtime_keeps_linux_ops_and_autocode_disabled(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        config = load_config(repository / "config.default.json")
        self.assertEqual("linux-ops", config.get("active_profile"))
        self.assertFalse(config.get("autocode", {}).get("enabled"))

    def test_disabled_autocode_overlay_starts_no_background_thread(self) -> None:
        overlay = _DummyOverlay()
        config = {"autocode": {"enabled": False}}
        with mock.patch("traktor_controller.autocode_visuals.threading.Thread") as thread:
            overlay._initialize_autocode_overlay(config)
        thread.assert_not_called()
        self.assertIsNone(overlay._autocode_thread)
        overlay._stop_autocode_overlay()

    def test_recovery_script_preserves_config_and_forces_core_profile(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        script = (repository / "update-and-test.sh").read_text(encoding="utf-8")
        self.assertIn("git stash push --include-untracked", script)
        self.assertIn('value["active_profile"] = "linux-ops"', script)
        self.assertIn('autocode["enabled"] = False', script)
        self.assertIn("bash validate-local.sh", script)
        self.assertIn("MIDILIN_UPDATE_TEST_OK", script)


if __name__ == "__main__":
    unittest.main()
