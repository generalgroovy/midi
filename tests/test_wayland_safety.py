from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest import mock

from traktor_controller.common import load_config
from traktor_controller.unified_actions import ActionDispatcher


class WaylandSafetyTests(unittest.TestCase):
    def test_active_color_temperature_fails_without_wayland_environment(self) -> None:
        config = load_config(Path("config.default.json"))
        dispatcher = ActionDispatcher(config, dry_run=False)
        mapping = {
            "backend": "gammastep",
            "adjustment_method": "wayland",
            "minimum_kelvin": 2500,
            "maximum_kelvin": 6500,
        }
        with mock.patch.dict(os.environ, {}, clear=True):
            with mock.patch.object(dispatcher, "_run_checked") as run_checked:
                applied = dispatcher._apply_color_temperature(mapping, 0.5, 4500)
        self.assertFalse(applied)
        run_checked.assert_not_called()


if __name__ == "__main__":
    unittest.main()
