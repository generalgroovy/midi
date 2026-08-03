from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .common import ControlEvent, atomic_write_json, atomic_write_text, log

DEVNULL = subprocess.DEVNULL


class ActionDispatcher:
    def __init__(self, config: dict[str, Any], dry_run: bool = False):
        self.config = config
        self.actions: dict[str, Any] = config.get("actions", {})
        self.bass_presets: list[str] = config.get("bass_presets", [])
        self.model_controls: dict[str, Any] = config.get("model_controls", {})
        self.script_slots: dict[str, Any] = config.get("script_slots", {})
        self.log_actions = bool(config.get("runtime", {}).get("log_actions", True))
        self.notify_actions = bool(config.get("runtime", {}).get("notify_actions", False))
        self.dry_run = dry_run
        self.last_bass_index: int | None = None
        self.model_hook_timers: dict[str, threading.Timer] = {}

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
            "slot": str(mapping.get("slot", "")),
            "parameter": str(mapping.get("parameter", "")),
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

    def _notify(self, title: str, body: str) -> None:
        if self.dry_run or not shutil.which("notify-send"):
            return
        subprocess.Popen(
            ["notify-send", title, body], stdin=DEVNULL, stdout=DEVNULL,
            stderr=DEVNULL, start_new_session=True,
        )

    def _confirm(self, title: str, text: str) -> bool:
        if self.dry_run:
            return True
        if shutil.which("zenity") and (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY")):
            result = subprocess.run(
                ["zenity", "--question", f"--title={title}", f"--text={text}"],
                stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL, check=False,
            )
            return result.returncode == 0
        log(f"Confirmation unavailable for: {title}: {text}")
        return False

    def _run(self, command: list[str] | str, action: str, confirm: str | None = None) -> None:
        display = command if isinstance(command, str) else " ".join(command)
        if self.log_actions or self.dry_run:
            log(f"action={action} command={display}")
        if self.dry_run:
            return
        if confirm and not self._confirm("Traktor system controller", confirm):
            log(f"Cancelled action={action}")
            return
        try:
            argv = ["bash", "-lc", command] if isinstance(command, str) else command
            subprocess.Popen(
                argv, stdin=DEVNULL, stdout=DEVNULL, stderr=DEVNULL,
                start_new_session=True,
            )
            if self.notify_actions:
                self._notify("Traktor action", action)
        except FileNotFoundError:
            log(f"Command not found for action {action}: {display}")
        except Exception as exc:
            log(f"Could not run action {action}: {exc}")

    def _relative_volume(
        self, mapping: dict[str, Any], event: ControlEvent,
        target: str, action: str,
    ) -> None:
        delta = event.value * max(1, int(mapping.get("sensitivity", 1)))
        step = min(max(abs(delta), 1), 10)
        self._run(
            ["wpctl", "set-volume", "-l", "1.0", target,
             f"{step}%{'+' if delta > 0 else '-'}"],
            action,
        )

    @staticmethod
    def _quantize(value: float, step: float) -> float:
        return value if step <= 0 else round(value / step) * step

    def _model_state_path(self) -> Path:
        return Path(str(self.model_controls.get(
            "state_file", "~/.config/traktor-system-controller/model-controls.json"
        ))).expanduser()

    def _read_model_state(self) -> dict[str, Any]:
        parameters = self.model_controls.get("parameters", {})
        defaults = {
            str(name): spec.get("default")
            for name, spec in parameters.items()
            if isinstance(spec, dict) and "default" in spec
        } if isinstance(parameters, dict) else {}
        path = self._model_state_path()
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                defaults.update(value)
        except (FileNotFoundError, json.JSONDecodeError):
            pass
        return defaults

    def _schedule_model_hook(self, parameter: str, value: float, path: Path) -> None:
        hook = str(self.model_controls.get("hook", "")).strip()
        notify = bool(self.model_controls.get("notify", False))
        if not hook and not notify:
            return
        previous = self.model_hook_timers.pop(parameter, None)
        if previous:
            previous.cancel()
        delay = max(
            0.05, float(self.model_controls.get("debounce_ms", 250)) / 1000.0
        )

        def fire() -> None:
            if hook:
                hook_path = Path(hook).expanduser()
                if hook_path.exists() and os.access(hook_path, os.X_OK):
                    self._run(
                        [str(hook_path), parameter, str(value), str(path)],
                        f"model_hook:{parameter}",
                    )
            if notify:
                self._notify("Model control", f"{parameter} = {value}")
            self.model_hook_timers.pop(parameter, None)

        timer = threading.Timer(delay, fire)
        timer.daemon = True
        self.model_hook_timers[parameter] = timer
        timer.start()

    def _set_model_parameter(
        self, mapping: dict[str, Any], event: ControlEvent, relative: bool
    ) -> None:
        parameter = str(mapping.get("parameter", "")).strip()
        parameters = self.model_controls.get("parameters", {})
        spec = parameters.get(parameter) if isinstance(parameters, dict) else None
        if not parameter or not isinstance(spec, dict):
            log(f"Unknown model parameter: {parameter!r}")
            return
        minimum = float(spec.get("min", 0.0))
        maximum = float(spec.get("max", 1.0))
        step = float(spec.get("step", 0.01))
        state = self._read_model_state()
        current = float(state.get(parameter, spec.get("default", minimum)))
        if relative:
            value = current + event.value * float(mapping.get("sensitivity", 1)) * step
        else:
            ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
            value = minimum + ratio * (maximum - minimum)
        value = min(max(self._quantize(value, step), minimum), maximum)
        decimals = int(spec.get(
            "decimals",
            max(0, -int(math.floor(math.log10(step)))) if 0 < step < 1 else 0,
        ))
        value = round(value, decimals)
        state[parameter] = value
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        state["source"] = {"device": event.device, "control": event.control}
        path = self._model_state_path()
        if self.log_actions or self.dry_run:
            log(f"action=model_parameter parameter={parameter} value={value} state={path}")
        if self.dry_run:
            return
        atomic_write_json(path, state)
        self._schedule_model_hook(parameter, value, path)

    def _run_script_slot(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        slot = str(mapping.get("slot", "")).strip()
        spec = self.script_slots.get(slot)
        if not slot or not isinstance(spec, dict):
            log(f"Unknown script slot: {slot!r}")
            return
        if not bool(spec.get("enabled", False)):
            log(f"Script slot disabled: {slot}")
            self._notify("Script slot disabled", slot)
            return
        command = spec.get("command")
        if command is None:
            log(f"Script slot has no command: {slot}")
            return
        rendered = self._render(command, event, {**mapping, "slot": slot})
        confirmation = str(spec.get("confirm", "")).strip() or None
        self._run(rendered, f"script_slot:{slot}", confirmation)

    def _controller_brightness_path(self) -> Path:
        visuals = self.config.get("visuals", {})
        if not isinstance(visuals, dict):
            visuals = {}
        return Path(str(visuals.get(
            "brightness_state_file",
            "~/.config/traktor-system-controller/controller-brightness",
        ))).expanduser()

    def _set_controller_brightness(self, ratio: float) -> None:
        percent = min(max(round(ratio * 100), 0), 100)
        path = self._controller_brightness_path()
        if self.log_actions or self.dry_run:
            log(f"action=controller_brightness_absolute percent={percent} state={path}")
        if self.dry_run:
            return
        atomic_write_text(path, f"{percent}\n")

    @staticmethod
    def _sway_json(message_type: str) -> Any:
        try:
            result = subprocess.run(
                ["swaymsg", "-t", message_type, "-r"],
                text=True, capture_output=True, timeout=1.5, check=False,
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
        except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
            return None
        return None

    @classmethod
    def _focused_node(cls) -> dict[str, Any] | None:
        tree = cls._sway_json("get_tree")
        if not isinstance(tree, dict):
            return None

        def walk(node: dict[str, Any]) -> dict[str, Any] | None:
            if node.get("focused"):
                return node
            for child in [*node.get("nodes", []), *node.get("floating_nodes", [])]:
                if isinstance(child, dict):
                    found = walk(child)
                    if found:
                        return found
            return None

        return walk(tree)

    @classmethod
    def _focused_output(cls) -> dict[str, Any] | None:
        node = cls._focused_node()
        outputs = cls._sway_json("get_outputs")
        if not node or not isinstance(outputs, list):
            return None
        rect = node.get("rect", {})
        center_x = float(rect.get("x", 0)) + float(rect.get("width", 0)) / 2
        center_y = float(rect.get("y", 0)) + float(rect.get("height", 0)) / 2
        for output in outputs:
            if not isinstance(output, dict) or not output.get("active", False):
                continue
            out = output.get("rect", {})
            x = float(out.get("x", 0))
            y = float(out.get("y", 0))
            width = float(out.get("width", 0))
            height = float(out.get("height", 0))
            if x <= center_x < x + width and y <= center_y < y + height:
                return output
        return next(
            (output for output in outputs
             if isinstance(output, dict) and output.get("focused")),
            None,
        )

    def _window_axis_absolute(
        self, event: ControlEvent, mapping: dict[str, Any], axis: str
    ) -> None:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        node = self._focused_node()
        output = self._focused_output()
        if node and output:
            rect = node.get("rect", {})
            out = output.get("rect", {})
            current_x = int(rect.get("x", 0))
            current_y = int(rect.get("y", 0))
            width = int(rect.get("width", 0))
            height = int(rect.get("height", 0))
            out_x = int(out.get("x", 0))
            out_y = int(out.get("y", 0))
            out_width = int(out.get("width", 0))
            out_height = int(out.get("height", 0))
            x = current_x
            y = current_y
            if axis == "x":
                x = out_x + round(ratio * max(out_width - width, 0))
            else:
                y = out_y + round(ratio * max(out_height - height, 0))
            self._run(
                ["swaymsg", "move", "position", str(x), "px", str(y), "px"],
                f"window_{axis}_absolute",
            )
            return
        pct = round(ratio * 100)
        other = int(mapping.get("other_axis_percent", 50))
        x_pct, y_pct = (pct, other) if axis == "x" else (other, pct)
        self._run(
            ["swaymsg", "move", "position", str(x_pct), "ppt", str(y_pct), "ppt"],
            f"window_{axis}_absolute",
        )

    def _window_size_absolute(
        self, event: ControlEvent, mapping: dict[str, Any], axis: str
    ) -> None:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        minimum = max(5, int(mapping.get("minimum_percent", 20)))
        maximum = min(100, int(mapping.get("maximum_percent", 100)))
        percent = round(minimum + ratio * (maximum - minimum))
        output = self._focused_output()
        if output:
            rect = output.get("rect", {})
            full = int(rect.get("width" if axis == "width" else "height", 0))
            if full > 0:
                pixels = max(100, round(full * percent / 100))
                self._run(
                    ["swaymsg", "resize", "set", axis, str(pixels), "px"],
                    f"window_{axis}_absolute",
                )
                return
        self._run(
            ["swaymsg", "resize", "set", axis, str(percent), "ppt"],
            f"window_{axis}_absolute",
        )

    def _window_relative(
        self, event: ControlEvent, mapping: dict[str, Any],
        mode: str, axis: str,
    ) -> None:
        if event.value == 0:
            return
        base = max(1, int(mapping.get("sensitivity", 40)))
        amount = min(max(abs(event.value) * base, 1), 400)
        if mode == "move":
            direction = (
                "right" if axis == "horizontal" and event.value > 0 else
                "left" if axis == "horizontal" else
                "down" if event.value > 0 else "up"
            )
            command = ["swaymsg", "move", direction, str(amount), "px"]
            action = f"window_move_{axis}_relative"
        else:
            change = "grow" if event.value > 0 else "shrink"
            dimension = "width" if axis == "horizontal" else "height"
            command = ["swaymsg", "resize", change, dimension, str(amount), "px"]
            action = f"window_resize_{dimension}_relative"
        self._run(command, action)

    def dispatch(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        action = str(mapping["action"])
        if action in self.actions:
            try:
                confirm = mapping.get("confirm")
                self._run(
                    self._render(self.actions[action], event, mapping),
                    action, str(confirm) if confirm else None,
                )
            except ValueError as exc:
                log(f"Invalid action {action}: {exc}")
            return

        invert = bool(mapping.get("invert", False))
        ratio = self.normalized_value(event, invert)

        if action == "volume_absolute":
            self._run(
                ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SINK@",
                 f"{round(ratio * 100)}%"],
                action,
            )
        elif action == "volume_relative":
            self._relative_volume(mapping, event, "@DEFAULT_AUDIO_SINK@", action)
        elif action == "source_volume_absolute":
            self._run(
                ["wpctl", "set-volume", "-l", "1.0", "@DEFAULT_AUDIO_SOURCE@",
                 f"{round(ratio * 100)}%"],
                action,
            )
        elif action == "source_volume_relative":
            self._relative_volume(mapping, event, "@DEFAULT_AUDIO_SOURCE@", action)
        elif action == "brightness_absolute":
            self._run(
                ["brightnessctl", "set", f"{max(1, round(ratio * 100))}%"],
                action,
            )
        elif action == "brightness_relative":
            delta = event.value * max(1, int(mapping.get("sensitivity", 1)))
            step = min(max(abs(delta), 1), 10)
            self._run(
                ["brightnessctl", "set", f"{step}%{'+' if delta > 0 else '-'}"],
                action,
            )
        elif action == "controller_brightness_absolute":
            self._set_controller_brightness(ratio)
        elif action == "bass_preset_absolute":
            if not self.bass_presets:
                log("No bass_presets configured.")
                return
            index = min(
                len(self.bass_presets) - 1,
                int(ratio * len(self.bass_presets)),
            )
            if index != self.last_bass_index:
                self.last_bass_index = index
                self._run(
                    ["easyeffects", "--load-preset", self.bass_presets[index]],
                    action,
                )
        elif action == "media_seek_relative":
            seconds = event.value * max(1, int(mapping.get("sensitivity", 5)))
            if seconds:
                self._run(
                    ["playerctl", "position",
                     f"{abs(seconds)}{'+' if seconds > 0 else '-'}"],
                    action,
                )
        elif action == "workspace_relative":
            self._run(
                ["swaymsg", "workspace", "next" if event.value > 0 else "prev"],
                action,
            )
        elif action == "sway_gap_absolute":
            maximum = max(1, int(mapping.get("maximum", 48)))
            self._run(
                ["swaymsg", "gaps", "inner", "all", "set",
                 str(round(ratio * maximum))],
                action,
            )
        elif action == "pointer_accel_absolute":
            value = -1.0 + ratio * 2.0
            self._run(
                ["swaymsg", "input", "type:pointer", "pointer_accel",
                 f"{value:.2f}"],
                action,
            )
        elif action == "scroll_factor_absolute":
            minimum = float(mapping.get("minimum", 0.1))
            maximum = float(mapping.get("maximum", 3.0))
            value = minimum + ratio * (maximum - minimum)
            self._run(
                ["swaymsg", "input", "type:touchpad", "scroll_factor",
                 f"{value:.2f}"],
                action,
            )
        elif action == "color_temperature_absolute":
            minimum = int(mapping.get("minimum_kelvin", 2500))
            maximum = int(mapping.get("maximum_kelvin", 6500))
            kelvin = round(minimum + ratio * (maximum - minimum))
            self._run(["gammastep", "-O", str(kelvin)], action)
        elif action == "window_move_horizontal_relative":
            self._window_relative(event, mapping, "move", "horizontal")
        elif action == "window_move_vertical_relative":
            self._window_relative(event, mapping, "move", "vertical")
        elif action == "window_resize_width_relative":
            self._window_relative(event, mapping, "resize", "horizontal")
        elif action == "window_resize_height_relative":
            self._window_relative(event, mapping, "resize", "vertical")
        elif action == "window_x_absolute":
            self._window_axis_absolute(event, mapping, "x")
        elif action == "window_y_absolute":
            self._window_axis_absolute(event, mapping, "y")
        elif action == "window_width_absolute":
            self._window_size_absolute(event, mapping, "width")
        elif action == "window_height_absolute":
            self._window_size_absolute(event, mapping, "height")
        elif action == "model_parameter_absolute":
            self._set_model_parameter(mapping, event, relative=False)
        elif action == "model_parameter_relative":
            self._set_model_parameter(mapping, event, relative=True)
        elif action == "script_slot":
            self._run_script_slot(mapping, event)
        else:
            log(f"Unknown action: {action}")
