from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from traktor_controller.cli import validate_config
from traktor_controller.eventlog import clear, emit, event_path, read_tail, redact
from traktor_controller.router import EventRouter


class EventLedgerTests(unittest.TestCase):
    def test_append_redact_tail_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "events.jsonl"
            with mock.patch.dict(os.environ, {"MIDILIN_EVENT_LOG": str(target)}):
                first = emit(
                    "test",
                    message="password=hunter2",
                    nested={"token": "token=abc"},
                )
                emit("test", value=2)
                self.assertEqual(first["message"], "password=<REDACTED>")
                self.assertEqual(first["nested"]["token"], "token=<REDACTED>")
                self.assertEqual(event_path(), target)
                self.assertEqual(read_tail(1)[0]["value"], 2)
                lines = target.read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(lines), 2)
                self.assertTrue(all(json.loads(line)["schema_version"] == 1 for line in lines))
                self.assertNotIn("hunter2", target.read_text(encoding="utf-8"))
                self.assertTrue(clear())
                self.assertFalse(target.exists())

    def test_redaction_handles_bearer_and_openai_shaped_secrets(self) -> None:
        rendered = redact("Authorization: Bearer secret sk-abcdefghijklmnop")
        self.assertNotIn("secret", rendered)
        self.assertNotIn("sk-abcdefghijklmnop", rendered)
        self.assertEqual(rendered.count("<REDACTED>"), 2)


class ValidationTests(unittest.TestCase):
    def test_rejects_same_profile_input_conditions_and_impossible_conditions(self) -> None:
        base = {
            "device": "f1",
            "control": "grid_1",
            "kind": "press",
            "action": "script_slot",
            "slot": "one",
            "profile": "linux-ops",
            "requires": ["f1.shift"],
        }
        duplicate = {**base, "slot": "two"}
        impossible = {
            **base,
            "control": "grid_2",
            "unless": ["f1.shift"],
        }
        config = {
            "actions": {},
            "mappings": [base, duplicate, impossible],
            "model_controls": {"parameters": {}},
            "layout_rules": {"no_repeated_actions_per_controller": False},
        }
        errors = validate_config(config)
        self.assertTrue(any("ambiguous" in error for error in errors))
        self.assertTrue(any("requires and excludes" in error for error in errors))

    def test_same_input_can_be_distinct_across_profiles(self) -> None:
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
                {**base, "profile": "model-control"},
            ],
            "model_controls": {"parameters": {}},
            "layout_rules": {"no_repeated_actions_per_controller": False},
        }
        self.assertEqual(validate_config(config), [])


class RouterEvidenceTests(unittest.TestCase):
    def test_selected_and_unmatched_inputs_are_logged(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "events.jsonl"
            config = {
                "active_profile": "linux-ops",
                "mappings": [
                    {
                        "device": "f1",
                        "control": "grid_1",
                        "kind": "press",
                        "action": "script_slot",
                        "slot": "one",
                    }
                ],
            }
            with mock.patch.dict(os.environ, {"MIDILIN_EVENT_LOG": str(target)}):
                router = EventRouter(config, monitor=False, dry_run=True)
                with mock.patch.object(router.dispatcher, "dispatch") as dispatch:
                    router.emit(SimpleNamespace(
                        device="f1", control="grid_1", kind="press",
                        value=1, minimum=0, maximum=1, source="test",
                    ))
                    router.emit(SimpleNamespace(
                        device="f1", control="grid_2", kind="press",
                        value=1, minimum=0, maximum=1, source="test",
                    ))
                dispatch.assert_called_once()
                kinds = [item["kind"] for item in read_tail(50)]
                self.assertIn("control_input", kinds)
                self.assertIn("mapping_selected", kinds)
                self.assertIn("mapping_unmatched", kinds)


if __name__ == "__main__":
    unittest.main()
