from __future__ import annotations

import unittest

from traktor_controller.cli import validate_config


class ProfileOverlapTests(unittest.TestCase):
    def test_wildcard_mapping_overlaps_named_profile_mapping(self) -> None:
        base = {
            "device": "f1",
            "control": "grid_1",
            "kind": "press",
            "action": "script_slot",
            "slot": "one",
        }
        config = {
            "actions": {},
            "mappings": [
                base,
                {**base, "slot": "two", "profile": "linux-ops"},
            ],
            "model_controls": {"parameters": {}},
            "layout_rules": {"no_repeated_actions_per_controller": False},
        }
        errors = validate_config(config)
        self.assertTrue(any("overlapping profiles" in error for error in errors))

    def test_nonoverlapping_profile_sets_remain_valid(self) -> None:
        base = {
            "device": "f1",
            "control": "grid_1",
            "kind": "press",
            "action": "script_slot",
            "slot": "one",
        }
        config = {
            "actions": {},
            "mappings": [
                {**base, "profile": "linux-ops"},
                {**base, "slot": "two", "profiles": ["model-control", "media"]},
            ],
            "model_controls": {"parameters": {}},
            "layout_rules": {"no_repeated_actions_per_controller": False},
        }
        self.assertEqual(validate_config(config), [])


if __name__ == "__main__":
    unittest.main()
