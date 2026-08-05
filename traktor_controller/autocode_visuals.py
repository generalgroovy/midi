from __future__ import annotations

import threading
from typing import Any

from .autocode import enabled, read_state, settings
from .visuals import F1Visual as BaseF1Visual
from .visuals import X1Visual as BaseX1Visual
from .visuals import X1_LED_INDEX


F1_STATE_COLORS = {
    "idle": (0, 0, 0),
    "starting": (0, 55, 110),
    "running": (0, 85, 127),
    "paused": (127, 65, 0),
    "attention": (100, 0, 127),
    "completed": (0, 127, 24),
    "failed": (127, 0, 0),
    "stopped": (30, 20, 0),
}
X1_STATE_LEVELS = {
    "idle": 0,
    "starting": 35,
    "running": 60,
    "paused": 35,
    "attention": 100,
    "completed": 90,
    "failed": 127,
    "stopped": 18,
}


def f1_indicator_color(state: dict[str, Any]) -> tuple[int, int, int]:
    selected = F1_STATE_COLORS.get(str(state.get("state", "idle")), (0, 0, 0))
    if state.get("cue_pending") and str(state.get("state")) in {
        "attention",
        "completed",
        "failed",
        "running",
    }:
        return tuple(max(channel, 100) for channel in selected)
    return selected


def x1_indicator_level(state: dict[str, Any]) -> int:
    selected = X1_STATE_LEVELS.get(str(state.get("state", "idle")), 0)
    if state.get("cue_pending"):
        return 127
    return selected


class _AutocodeOverlay:
    def _initialize_autocode_overlay(self, config: dict[str, Any]) -> None:
        self._autocode_config = config
        self._autocode_stop = threading.Event()
        self._autocode_state: dict[str, Any] = {
            "available": False,
            "state": "idle",
            "cue_pending": False,
        }
        try:
            self._autocode_state = read_state(config)
        except (OSError, RuntimeError, ValueError):
            pass
        interval = float(settings(config).get("poll_seconds", 0.25))
        self._autocode_thread = threading.Thread(
            target=self._autocode_loop,
            args=(max(0.1, min(interval, 10.0)),),
            daemon=True,
            name="midilin-autocode-led",
        )
        self._autocode_thread.start()

    def _autocode_loop(self, interval: float) -> None:
        while not self._autocode_stop.wait(interval):
            try:
                value = read_state(self._autocode_config)
            except (OSError, RuntimeError, ValueError):
                value = {
                    "available": False,
                    "state": "idle",
                    "cue_pending": False,
                }
            signature = (
                value.get("sequence"),
                value.get("state"),
                value.get("cue_pending"),
                value.get("workspace"),
            )
            current = (
                self._autocode_state.get("sequence"),
                self._autocode_state.get("state"),
                self._autocode_state.get("cue_pending"),
                self._autocode_state.get("workspace"),
            )
            if signature != current:
                self._autocode_state = value
                self._render()

    def _stop_autocode_overlay(self) -> None:
        self._autocode_stop.set()
        thread = getattr(self, "_autocode_thread", None)
        if thread is not None:
            thread.join(timeout=2)

    def _show_autocode(self) -> bool:
        return (
            enabled(self._autocode_config)
            and bool(self._autocode_state.get("available"))
            and not bool(self._autocode_state.get("foreign_workspace"))
        )


class AutocodeF1Visual(_AutocodeOverlay, BaseF1Visual):
    def __init__(self, device: Any, config: dict[str, Any], theme: str):
        self._autocode_config = config
        self._autocode_state = {
            "available": False,
            "state": "idle",
            "cue_pending": False,
        }
        super().__init__(device, config, theme)
        self._initialize_autocode_overlay(config)
        self._render()

    def _render(self) -> None:
        super()._render()
        if not self._show_autocode():
            return
        control = str(settings(self.config).get("f1_indicator", "grid_16"))
        if not control.startswith("grid_"):
            return
        try:
            number = int(control.split("_", 1)[1])
        except ValueError:
            return
        if number < 1 or number > 16:
            return
        packet = bytearray(self.base)
        color = tuple(
            self._scale(channel)
            for channel in f1_indicator_color(self._autocode_state)
        )
        self._grid(packet, number, color)
        self.base = packet
        self.write(packet)

    def clear(self) -> None:
        self._stop_autocode_overlay()
        super().clear()


class AutocodeX1Visual(_AutocodeOverlay, BaseX1Visual):
    def __init__(self, device: Any, config: dict[str, Any], theme: str):
        self._autocode_config = config
        self._autocode_state = {
            "available": False,
            "state": "idle",
            "cue_pending": False,
        }
        super().__init__(device, config, theme)
        self._initialize_autocode_overlay(config)
        self._render()

    def _render(self) -> None:
        super()._render()
        if not self._show_autocode():
            return
        control = str(settings(self.config).get("x1_indicator", "hotcue"))
        index = X1_LED_INDEX.get(control)
        if index is None:
            return
        packet = bytearray(self.base)
        packet[index] = self._scale(x1_indicator_level(self._autocode_state))
        self.base = packet
        self.write(packet)

    def clear(self) -> None:
        self._stop_autocode_overlay()
        super().clear()


def install() -> None:
    from . import hardware

    hardware.F1Visual = AutocodeF1Visual
    hardware.X1Visual = AutocodeX1Visual
