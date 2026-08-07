from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from traktor_controller.eventlog import clear, emit, event_files, event_path, read_tail


class EventLogRetentionTests(unittest.TestCase):
    def test_rotates_reads_across_segments_and_clears(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "events.jsonl"
            environment = {
                "MIDILIN_EVENT_LOG": str(target),
                "MIDILIN_EVENT_LOG_MAX_BYTES": "1024",
                "MIDILIN_EVENT_LOG_BACKUPS": "2",
                "MIDILIN_EVENT_LOG_MODE": "full",
            }
            with mock.patch.dict(os.environ, environment, clear=False):
                for sequence in range(12):
                    emit("test", sequence=sequence, payload="x" * 300)
                self.assertTrue(target.exists())
                self.assertTrue(target.with_name("events.jsonl.1").exists())
                self.assertEqual(
                    [item["sequence"] for item in read_tail(3)],
                    [9, 10, 11],
                )
                self.assertTrue(clear())
                self.assertFalse(any(path.exists() for path in event_files()))

    def test_actions_mode_suppresses_high_volume_routing_noise(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "events.jsonl"
            with mock.patch.dict(
                os.environ,
                {
                    "MIDILIN_EVENT_LOG": str(target),
                    "MIDILIN_EVENT_LOG_MODE": "actions",
                },
                clear=False,
            ):
                emit("control_input", value=1)
                emit("mapping_unmatched", control="knob_1")
                emit("modifier_state", event_kind="press")
                emit(
                    "mapping_selected",
                    action="volume_absolute",
                    event_kind="absolute",
                )
                emit(
                    "mapping_selected",
                    action="media_play_pause",
                    event_kind="press",
                )
                self.assertEqual(
                    [item["kind"] for item in read_tail(10)],
                    ["mapping_selected"],
                )

    def test_default_logging_does_not_fsync_each_controller_event(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "events.jsonl"
            with mock.patch.dict(
                os.environ,
                {
                    "MIDILIN_EVENT_LOG": str(target),
                    "MIDILIN_EVENT_LOG_MODE": "full",
                },
                clear=False,
            ), mock.patch("os.fsync") as fsync:
                emit("mapping_selected", action="media_play_pause", event_kind="press")
                fsync.assert_not_called()
                self.assertTrue(target.exists())

    def test_explicit_fsync_mode_remains_available(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "events.jsonl"
            with mock.patch.dict(
                os.environ,
                {
                    "MIDILIN_EVENT_LOG": str(target),
                    "MIDILIN_EVENT_LOG_MODE": "full",
                    "MIDILIN_EVENT_LOG_FSYNC": "1",
                },
                clear=False,
            ), mock.patch("os.fsync") as fsync:
                emit("mapping_selected", action="media_play_pause", event_kind="press")
                fsync.assert_called_once()

    def test_off_mode_creates_no_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "events.jsonl"
            with mock.patch.dict(
                os.environ,
                {
                    "MIDILIN_EVENT_LOG": str(target),
                    "MIDILIN_EVENT_LOG_MODE": "off",
                },
                clear=False,
            ):
                event = emit("mapping_selected", action="volume_absolute")
                self.assertEqual(event["kind"], "mapping_selected")
                self.assertFalse(target.exists())
                self.assertEqual(read_tail(10), [])

    def test_runtime_logging_failure_is_nonfatal_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outside = root / "outside.jsonl"
            outside.write_text("outside\n", encoding="utf-8")
            target = root / "events.jsonl"
            target.symlink_to(outside)
            with mock.patch.dict(
                os.environ,
                {
                    "MIDILIN_EVENT_LOG": str(target),
                    "MIDILIN_EVENT_LOG_STRICT": "0",
                },
                clear=False,
            ):
                event = emit("mapping_selected", action="media_play_pause")
            self.assertIn("symbolic link", event.get("log_error", ""))
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")

    def test_invalid_limits_fail_closed_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            with mock.patch.dict(
                os.environ,
                {
                    "MIDILIN_EVENT_LOG": str(Path(raw) / "events.jsonl"),
                    "MIDILIN_EVENT_LOG_MAX_BYTES": "100",
                    "MIDILIN_EVENT_LOG_STRICT": "1",
                },
                clear=False,
            ):
                with self.assertRaisesRegex(ValueError, "between"):
                    emit("test")

    def test_symbolic_link_log_target_is_rejected_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            outside = root / "outside.jsonl"
            outside.write_text("outside\n", encoding="utf-8")
            target = root / "events.jsonl"
            target.symlink_to(outside)
            with mock.patch.dict(
                os.environ,
                {
                    "MIDILIN_EVENT_LOG": str(target),
                    "MIDILIN_EVENT_LOG_STRICT": "1",
                },
                clear=False,
            ):
                with self.assertRaisesRegex(RuntimeError, "symbolic link"):
                    emit("test")
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")

    def test_event_files_are_private(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "state" / "events.jsonl"
            with mock.patch.dict(
                os.environ,
                {"MIDILIN_EVENT_LOG": str(target)},
                clear=False,
            ):
                emit("test")
                self.assertEqual(event_path(), target)
                self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
                self.assertEqual(target.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
