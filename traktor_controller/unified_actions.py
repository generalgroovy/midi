from __future__ import annotations

import shlex
import threading
from typing import Any

from .actions import ActionDispatcher as BaseActionDispatcher
from .common import ControlEvent, log


class ActionDispatcher(BaseActionDispatcher):
    """Merged desktop, model, hardware-light and Sway window actions."""

    def __init__(self, config: dict[str, Any], dry_run: bool = False):
        super().__init__(config, dry_run=dry_run)
        self.color_temperature_timer: threading.Timer | None = None

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

    def _set_color_temperature(
        self, mapping: dict[str, Any], event: ControlEvent
    ) -> None:
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))
        minimum = max(1000, int(mapping.get("minimum_kelvin", 2500)))
        maximum = min(25000, int(mapping.get("maximum_kelvin", 6500)))
        if maximum <= minimum:
            maximum = minimum + 100
        kelvin = round(minimum + ratio * (maximum - minimum))
        method = str(mapping.get("adjustment_method", "wayland"))
        delay = max(0.05, float(mapping.get("debounce_ms", 180)) / 1000.0)
        takeover = bool(mapping.get("take_ownership", True))
        reset_at_max = bool(mapping.get("reset_at_max", True))

        prefix = ""
        if takeover:
            prefix = (
                "pkill -x gammastep 2>/dev/null || true; "
                "pkill -x wlsunset 2>/dev/null || true; "
            )
        quoted_method = shlex.quote(method)
        if reset_at_max and ratio >= 0.995:
            command = prefix + f"exec gammastep -m {quoted_method} -x"
        else:
            command = (
                prefix
                + f"exec gammastep -P -m {quoted_method} -O {int(kelvin)}"
            )

        if self.log_actions or self.dry_run:
            log(
                f"action=color_temperature_absolute kelvin={kelvin} "
                f"method={method} takeover={takeover} "
                f"debounce_ms={round(delay * 1000)}"
            )
        if self.dry_run:
            self._run(command, "color_temperature_absolute")
            return

        if self.color_temperature_timer:
            self.color_temperature_timer.cancel()

        def apply() -> None:
            self._run(command, "color_temperature_absolute")
            self.color_temperature_timer = None

        timer = threading.Timer(delay, apply)
        timer.daemon = True
        self.color_temperature_timer = timer
        timer.start()

    def dispatch(self, mapping: dict[str, Any], event: ControlEvent) -> None:
        action = str(mapping["action"])
        ratio = self.normalized_value(event, bool(mapping.get("invert", False)))

        if action == "color_temperature_absolute":
            self._set_color_temperature(mapping, event)
        elif action == "window_opacity_absolute":
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
