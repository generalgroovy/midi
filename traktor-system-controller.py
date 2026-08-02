#!/usr/bin/env python3
"""
Use Traktor Kontrol X1/F1 MIDI controls as Linux system controls.

Run:
  traktor-system-controller --list-ports
  traktor-system-controller --monitor
  traktor-system-controller

Configuration:
  ~/.config/traktor-system-controller/config.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import mido

DEFAULT_CONFIG = Path.home() / ".config/traktor-system-controller/config.json"
DEVNULL = subprocess.DEVNULL


def log(message: str) -> None:
    print(message, flush=True)


def run_quiet(command: list[str] | str) -> None:
    try:
        if isinstance(command, str):
            subprocess.Popen(
                ["bash", "-lc", command],
                stdin=DEVNULL,
                stdout=DEVNULL,
                stderr=DEVNULL,
                start_new_session=True,
            )
        else:
            subprocess.Popen(
                command,
                stdin=DEVNULL,
                stdout=DEVNULL,
                stderr=DEVNULL,
                start_new_session=True,
            )
    except FileNotFoundError:
        log(f"Command not found: {command}")
    except Exception as exc:
        log(f"Could not run {command!r}: {exc}")


def load_config(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(
            f"Configuration not found: {path}\n"
            "Copy config.example.json there and edit it."
        )
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")


class Controller:
    def __init__(self, config: dict[str, Any], monitor: bool, monitor_all: bool):
        self.config = config
        self.monitor = monitor
        self.monitor_all = monitor_all
        self.active_ports: set[str] = set()
        self.active_lock = threading.Lock()
        self.last_button: dict[tuple[Any, ...], float] = {}
        self.last_continuous: dict[tuple[Any, ...], float] = {}
        self.last_bass_index: int | None = None

        self.aliases: dict[str, list[str]] = config.get("device_aliases", {})
        self.actions: dict[str, list[str] | str] = config.get("actions", {})
        self.bass_presets: list[str] = config.get("bass_presets", [])

        self.buttons: dict[tuple[str, str, int, int], str] = {}
        for item in config.get("button_mappings", []):
            key = (
                str(item["device"]),
                str(item["type"]),
                int(item.get("channel", 0)),
                int(item["number"]),
            )
            self.buttons[key] = str(item["action"])

        self.ccs: dict[tuple[str, int, int], dict[str, Any]] = {}
        for item in config.get("cc_mappings", []):
            key = (
                str(item["device"]),
                int(item.get("channel", 0)),
                int(item["number"]),
            )
            self.ccs[key] = item

    def classify_device(self, port_name: str) -> str | None:
        lowered = port_name.casefold()
        for device, aliases in self.aliases.items():
            if any(alias.casefold() in lowered for alias in aliases):
                return device
        return "all" if self.monitor_all else None

    @staticmethod
    def describe(device: str, port_name: str, message: mido.Message) -> str:
        base = (
            f"device={device} port={port_name!r} type={message.type} "
            f"channel={getattr(message, 'channel', '-')}"
        )
        if message.type in ("note_on", "note_off"):
            return (
                f"{base} note={message.note} "
                f"velocity={message.velocity}"
            )
        if message.type == "control_change":
            return (
                f"{base} control={message.control} "
                f"value={message.value}"
            )
        if message.type == "program_change":
            return f"{base} program={message.program}"
        return f"{base} message={message}"

    @staticmethod
    def relative_delta(value: int, mode: str) -> int:
        if mode == "binary-offset":
            # Common encoder format: 65 = +1, 63 = -1.
            return value - 64
        if mode == "sign-magnitude":
            # Common encoder format: 1 = +1, 65 = -1.
            return -(value - 64) if value >= 64 else value
        # Default: two's-complement; 1 = +1, 127 = -1.
        return value if value <= 63 else value - 128

    def trigger_button(
        self, key: tuple[str, str, int, int], action: str
    ) -> None:
        now = time.monotonic()
        if now - self.last_button.get(key, 0.0) < 0.15:
            return
        self.last_button[key] = now
        self.dispatch(action)

    def process(self, device: str, port_name: str, message: mido.Message) -> None:
        if self.monitor:
            log(self.describe(device, port_name, message))
            return

        channel = int(getattr(message, "channel", 0))

        if message.type == "note_on" and message.velocity > 0:
            key = (device, "note", channel, int(message.note))
            action = self.buttons.get(key)
            if action:
                self.trigger_button(key, action)
            return

        if message.type == "control_change":
            button_key = (device, "cc_button", channel, int(message.control))
            button_action = self.buttons.get(button_key)
            if button_action and message.value >= 64:
                self.trigger_button(button_key, button_action)

            cc_key = (device, channel, int(message.control))
            mapping = self.ccs.get(cc_key)
            if not mapping:
                return

            # Limit subprocess churn from dense fader/knob event streams.
            now = time.monotonic()
            if now - self.last_continuous.get(cc_key, 0.0) < 0.025:
                return
            self.last_continuous[cc_key] = now

            action = str(mapping["action"])
            if action.endswith("_relative"):
                mode = str(mapping.get("relative_mode", "twos-complement"))
                delta = self.relative_delta(int(message.value), mode)
                if delta:
                    self.dispatch(action, delta=delta)
            else:
                self.dispatch(action, value=int(message.value))

    def dispatch(
        self, action: str, value: int | None = None, delta: int | None = None
    ) -> None:
        if action in self.actions:
            run_quiet(self.actions[action])
            return

        if action == "volume_absolute" and value is not None:
            percent = round(value * 100 / 127)
            run_quiet(
                ["wpctl", "set-volume", "-l", "1.0",
                 "@DEFAULT_AUDIO_SINK@", f"{percent}%"]
            )
            return

        if action == "volume_relative" and delta is not None:
            step = min(max(abs(delta), 1), 5)
            suffix = "+" if delta > 0 else "-"
            run_quiet(
                ["wpctl", "set-volume", "-l", "1.0",
                 "@DEFAULT_AUDIO_SINK@", f"{step}%{suffix}"]
            )
            return

        if action == "brightness_absolute" and value is not None:
            percent = max(1, round(value * 100 / 127))
            run_quiet(["brightnessctl", "set", f"{percent}%"])
            return

        if action == "brightness_relative" and delta is not None:
            step = min(max(abs(delta), 1), 5)
            suffix = "+" if delta > 0 else "-"
            run_quiet(["brightnessctl", "set", f"{step}%{suffix}"])
            return

        if action == "bass_preset_absolute" and value is not None:
            if not self.bass_presets:
                log("No bass_presets configured.")
                return
            count = len(self.bass_presets)
            index = min(count - 1, int(value * count / 128))
            if index == self.last_bass_index:
                return
            self.last_bass_index = index
            preset = self.bass_presets[index]
            run_quiet(["easyeffects", "--load-preset", preset])
            log(f"Bass preset: {preset}")
            return

        log(f"Unknown or incomplete action: {action}")

    def port_worker(self, port_name: str, device: str) -> None:
        try:
            with mido.open_input(port_name) as port:
                log(f"Connected: {device} -> {port_name}")
                for message in port:
                    self.process(device, port_name, message)
        except Exception as exc:
            log(f"Port closed or failed: {port_name}: {exc}")
        finally:
            with self.active_lock:
                self.active_ports.discard(port_name)

    def run(self) -> None:
        log("Watching for Traktor MIDI ports. Ctrl+C stops.")
        while True:
            names = mido.get_input_names()
            for name in names:
                device = self.classify_device(name)
                if device is None:
                    continue
                with self.active_lock:
                    if name in self.active_ports:
                        continue
                    self.active_ports.add(name)
                threading.Thread(
                    target=self.port_worker,
                    args=(name, device),
                    daemon=True,
                ).start()
            time.sleep(2.0)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument(
        "--monitor",
        action="store_true",
        help="Print events from matching X1/F1 ports; execute nothing.",
    )
    parser.add_argument(
        "--monitor-all",
        action="store_true",
        help="Print events from every MIDI input port.",
    )
    parser.add_argument(
        "--list-ports",
        action="store_true",
        help="List MIDI input ports and exit.",
    )
    args = parser.parse_args()

    if args.list_ports:
        names = mido.get_input_names()
        if not names:
            print("No MIDI input ports found.")
            return 1
        print("\n".join(names))
        return 0

    config = load_config(args.config)
    controller = Controller(
        config=config,
        monitor=args.monitor or args.monitor_all,
        monitor_all=args.monitor_all,
    )
    try:
        controller.run()
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    sys.exit(main())
