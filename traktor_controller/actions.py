from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .common import ControlEvent, log

DEVNULL = subprocess.DEVNULL


class ActionDispatcher:
    def __init__(self, config: dict[str, Any], dry_run: bool = False):
        self.actions: dict[str, Any] = config.get("actions", {})
        self.bass_presets: list[str] = config.get("bass_presets", [])
        self.log_actions = bool(config.get("runtime", {}).get("log_actions", True))
        self.dry_run = dry_run
        self.last_bass_index: int | None = None

    @staticmethod
    def normalized_value(event: ControlEvent, invert: bool = False) -> float:
        span = event.maximum - event.minimum
        if span <= 0:
            return 0.0
        ratio = min(max((event.value - event.minimum) / span, 0.0), 1.0)
        return 1.0 - ratio if invert else ratio

    def _placeholders(self, event: ControlEvent, mapping: dict[str, Any]) -> dict[str, str]:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        return {
            "home": str(Path.home()), "device": event.device,
            "control": event.control, "raw_control": event.raw_control or event.control,
            "kind": event.kind, "value": str(event.value),
            "min": str(event.minimum), "max": str(event.maximum),
            "delta": str(event.value), "ratio": f"{ratio:.6f}",
            "percent": str(round(ratio * 100)),
        }

    def _render(self, spec: Any, event: ControlEvent, mapping: dict[str, Any]) -> list[str] | str:
        values = self._placeholders(event, mapping)
        def render(text: str) -> str:
            for key, value in values.items():
                text = text.replace("{" + key + "}", value)
            return text
        if isinstance(spec, str):
            return render(spec)
        if isinstance(spec, list) and all(isinstance(item, str) for item in spec):
            return [render(item) for item in spec]
        raise ValueError("command must be a string or an array of strings")

    def _run(self, command: list[str] | str, action: str) -> None:
        display = command if isinstance(command, str) else " ".join(command)
        if self.log_actions or self.dry_run:
            log(f"action={action} command={display}")
        if self.dry_run:
            return
        try:
            argv = ["bash", "-lc", command] if isinstance(command, str) else command
            subprocess.Popen(
                argv, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL,
                start_new_session=True,
            )
        except FileNotFoundError:
            log(f"Command not found for action {action}: {display}")
        except Exception as exc:
            log(f"Could not run action {action}: {exc}")

    def _relative_volume(
        self, mapping: dict[str, Any], event: ControlEvent, target: str, action: str
    ) -> None:
        delta = event.value * max(1, int(mapping.get("sensitivity", 1)))
        step = min(max(abs(delta), 1), 10)
        self._run(
            ["wpctl", "set-volume", "-l", "1.0", target,
             f"{step}%{'+' if delta > 0 else '-'}"], action,
        )

    def dispatch(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        action = str(mapping["action"])
        if action in self.actions:
            try:
                self._run(self._render(self.actions[action], event, mapping), action)
            except ValueError as exc:
                log(f"Invalid action {action}: {exc}")
            return

        invert = bool(mapping.get("invert", False))
        ratio = self.normalized_value(event, invert)
        if action == "volume_absolute":
            self._run(["wpctl", "set-volume", "-l", "1.0",
                       "@DEFAULT_AUDIO_SINK@", f"{round(ratio * 100)}%"], action)
        elif action == "volume_relative":
            self._relative_volume(mapping, event, "@DEFAULT_AUDIO_SINK@", action)
        elif action == "source_volume_absolute":
            self._run(["wpctl", "set-volume", "-l", "1.0",
                       "@DEFAULT_AUDIO_SOURCE@", f"{round(ratio * 100)}%"], action)
        elif action == "source_volume_relative":
            self._relative_volume(mapping, event, "@DEFAULT_AUDIO_SOURCE@", action)
        elif action == "brightness_absolute":
            self._run(["brightnessctl", "set", f"{max(1, round(ratio * 100))}%"], action)
        elif action == "brightness_relative":
            delta = event.value * max(1, int(mapping.get("sensitivity", 1)))
            step = min(max(abs(delta), 1), 10)
            self._run(["brightnessctl", "set", f"{step}%{'+' if delta > 0 else '-'}"], action)
        elif action == "bass_preset_absolute":
            if not self.bass_presets:
                log("No bass_presets configured.")
                return
            index = min(len(self.bass_presets) - 1, int(ratio * len(self.bass_presets)))
            if index != self.last_bass_index:
                self.last_bass_index = index
                self._run(["easyeffects", "--load-preset", self.bass_presets[index]], action)
        elif action == "media_seek_relative":
            seconds = event.value * max(1, int(mapping.get("sensitivity", 5)))
            if seconds:
                self._run(["playerctl", "position", f"{abs(seconds)}{'+' if seconds > 0 else '-'}"], action)
        elif action == "workspace_relative":
            self._run(["swaymsg", "workspace", "next" if event.value > 0 else "prev"], action)
        else:
            log(f"Unknown action: {action}")
