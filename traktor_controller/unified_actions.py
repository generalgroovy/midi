from __future__ import annotations

from typing import Any

from .actions import ActionDispatcher as BaseActionDispatcher
from .common import ControlEvent, log


class ActionDispatcher(BaseActionDispatcher):
    """Merged desktop, model, hardware-light and Sway window actions."""

    @classmethod
    def _active_outputs(cls) -> list[dict[str, Any]]:
        outputs = cls._sway_json("get_outputs")
        if not isinstance(outputs, list):
            return []
        return sorted(
            [
                output for output in outputs
                if isinstance(output, dict)
                and output.get("active", False)
                and isinstance(output.get("rect"), dict)
                and output.get("name")
            ],
            key=lambda output: (
                int(output["rect"].get("x", 0)),
                int(output["rect"].get("y", 0)),
            ),
        )

    def _window_output_absolute(
        self, mapping: dict[str, Any], event: ControlEvent
    ) -> None:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        if self.dry_run:
            log(f"action=window_output_absolute ratio={ratio:.3f}")
            return
        outputs = self._active_outputs()
        if not outputs:
            log("No active Sway outputs found.")
            return
        index = min(len(outputs) - 1, round(ratio * (len(outputs) - 1)))
        name = str(outputs[index]["name"])
        self._run(
            ["swaymsg", f'move container to output "{name}", focus'],
            "window_output_absolute",
        )

    def dispatch(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        action = str(mapping["action"])
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))

        if action == "window_opacity_absolute":
            minimum = min(max(float(mapping.get("minimum", 0.2)), 0.0), 1.0)
            value = minimum + ratio * (1.0 - minimum)
            self._run(["swaymsg", "opacity", "set", f"{value:.2f}"], action)
        elif action == "window_border_absolute":
            maximum = max(0, int(mapping.get("maximum", 12)))
            pixels = round(ratio * maximum)
            command = (
                ["swaymsg", "border", "none"]
                if pixels == 0
                else ["swaymsg", "border", "pixel", str(pixels)]
            )
            self._run(command, action)
        elif action == "window_output_absolute":
            self._window_output_absolute(mapping, event)
        else:
            super().dispatch(mapping, event)
