from __future__ import annotations

import json
import subprocess
from typing import Any

from .actions import ActionDispatcher as BaseActionDispatcher
from .common import ControlEvent, log
from .visual_extensions import set_visual_brightness


class ActionDispatcher(BaseActionDispatcher):
    """Adds controller-light and focused-window actions to the base dispatcher."""

    def _run_sync(self, command: list[str]) -> subprocess.CompletedProcess[str] | None:
        if self.dry_run:
            return None
        try:
            return subprocess.run(
                command, text=True, capture_output=True, check=False, timeout=2.0
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            log(f"Could not query Sway: {exc}")
            return None

    def _sway_json(self, message_type: str) -> Any:
        result = self._run_sync(["swaymsg", "-t", message_type, "-r"])
        if result is None or result.returncode != 0:
            return None
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return None

    def _focused_node(self) -> dict[str, Any] | None:
        tree = self._sway_json("get_tree")
        if not isinstance(tree, dict):
            return None
        stack = [tree]
        while stack:
            node = stack.pop()
            if node.get("focused"):
                return node
            stack.extend(node.get("nodes", []))
            stack.extend(node.get("floating_nodes", []))
        return None

    def _active_outputs(self) -> list[dict[str, Any]]:
        outputs = self._sway_json("get_outputs")
        if not isinstance(outputs, list):
            return []
        return sorted(
            [
                output for output in outputs
                if isinstance(output, dict)
                and output.get("active")
                and isinstance(output.get("rect"), dict)
            ],
            key=lambda output: (
                int(output["rect"].get("x", 0)),
                int(output["rect"].get("y", 0)),
            ),
        )

    def _virtual_bounds(self) -> tuple[int, int, int, int] | None:
        outputs = self._active_outputs()
        if not outputs:
            return None
        min_x = min(int(output["rect"]["x"]) for output in outputs)
        min_y = min(int(output["rect"]["y"]) for output in outputs)
        max_x = max(
            int(output["rect"]["x"]) + int(output["rect"]["width"])
            for output in outputs
        )
        max_y = max(
            int(output["rect"]["y"]) + int(output["rect"]["height"])
            for output in outputs
        )
        return min_x, min_y, max_x, max_y

    def _window_absolute(
        self, mapping: dict[str, Any], event: ControlEvent, mode: str
    ) -> None:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        if self.dry_run:
            log(f"action=window_{mode}_absolute ratio={ratio:.3f}")
            return
        node = self._focused_node()
        bounds = self._virtual_bounds()
        if not node or not bounds or not isinstance(node.get("rect"), dict):
            log("No focused Sway window or active output geometry found.")
            return
        rect = node["rect"]
        con_id = int(node.get("id", 0))
        if not con_id:
            return
        min_x, min_y, max_x, max_y = bounds
        width = max(1, int(rect.get("width", 1)))
        height = max(1, int(rect.get("height", 1)))
        x = int(rect.get("x", min_x))
        y = int(rect.get("y", min_y))
        criteria = f"[con_id={con_id}]"
        if mode == "x":
            target = min_x + round(ratio * max(0, max_x - min_x - width))
            command = f"{criteria} floating enable, move absolute position {target} px {y} px"
        elif mode == "y":
            target = min_y + round(ratio * max(0, max_y - min_y - height))
            command = f"{criteria} floating enable, move absolute position {x} px {target} px"
        elif mode == "width":
            minimum = max(100, int(mapping.get("minimum", 320)))
            maximum = max(minimum, max_x - min_x)
            target = minimum + round(ratio * (maximum - minimum))
            command = f"{criteria} floating enable, resize set width {target} px"
        elif mode == "height":
            minimum = max(100, int(mapping.get("minimum", 220)))
            maximum = max(minimum, max_y - min_y)
            target = minimum + round(ratio * (maximum - minimum))
            command = f"{criteria} floating enable, resize set height {target} px"
        else:
            return
        self._run(["swaymsg", command], f"window_{mode}_absolute")

    def _window_output_absolute(
        self, mapping: dict[str, Any], event: ControlEvent
    ) -> None:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        if self.dry_run:
            log(f"action=window_output_absolute ratio={ratio:.3f}")
            return
        outputs = self._active_outputs()
        node = self._focused_node()
        if not outputs or not node:
            return
        index = min(len(outputs) - 1, round(ratio * (len(outputs) - 1)))
        name = str(outputs[index].get("name", ""))
        con_id = int(node.get("id", 0))
        if name and con_id:
            command = f'[con_id={con_id}] move container to output "{name}", focus'
            self._run(["swaymsg", command], "window_output_absolute")

    def _window_relative(
        self, event: ControlEvent, horizontal: bool, move: bool, action: str
    ) -> None:
        if event.value == 0:
            return
        positive = "right" if horizontal else "down"
        negative = "left" if horizontal else "up"
        direction = positive if event.value > 0 else negative
        command = f"move {direction}" if move else f"focus {direction}"
        for _ in range(min(abs(int(event.value)), 4)):
            self._run(["swaymsg", command], action)

    def dispatch(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        action = str(mapping["action"])
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        if action == "hardware_light_absolute":
            if self.log_actions or self.dry_run:
                log(f"action=hardware_light_absolute brightness={ratio:.3f}")
            if not self.dry_run:
                set_visual_brightness(self.config, ratio)
        elif action == "window_x_absolute":
            self._window_absolute(mapping, event, "x")
        elif action == "window_y_absolute":
            self._window_absolute(mapping, event, "y")
        elif action == "window_width_absolute":
            self._window_absolute(mapping, event, "width")
        elif action == "window_height_absolute":
            self._window_absolute(mapping, event, "height")
        elif action == "window_opacity_absolute":
            minimum = min(max(float(mapping.get("minimum", 0.2)), 0.0), 1.0)
            value = minimum + ratio * (1.0 - minimum)
            self._run(["swaymsg", "opacity", "set", f"{value:.2f}"], action)
        elif action == "window_border_absolute":
            maximum = max(0, int(mapping.get("maximum", 12)))
            self._run(["swaymsg", "border", "pixel", str(round(ratio * maximum))], action)
        elif action == "window_output_absolute":
            self._window_output_absolute(mapping, event)
        elif action == "window_focus_horizontal_relative":
            self._window_relative(event, True, False, action)
        elif action == "window_focus_vertical_relative":
            self._window_relative(event, False, False, action)
        elif action == "window_move_horizontal_relative":
            self._window_relative(event, True, True, action)
        elif action == "window_move_vertical_relative":
            self._window_relative(event, False, True, action)
        else:
            super().dispatch(mapping, event)
