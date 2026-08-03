from __future__ import annotations

import json
import weakref
from pathlib import Path
from typing import Any

from .common import atomic_write_json, log
from . import visuals as base

for name, color in {
    "category": (15, 85, 110),
    "neon": (0, 110, 127),
    "sunset": (95, 18, 100),
    "matrix": (0, 80, 8),
    "mono": (45, 45, 55),
    "blackout": (0, 0, 0),
}.items():
    base.THEMES[name]["window"] = color

_VISUALS: weakref.WeakSet[Any] = weakref.WeakSet()


def _brightness_path(config: dict[str, Any]) -> Path:
    visuals = config.get("visuals", {})
    value = visuals.get(
        "light_brightness_state_file",
        "~/.config/traktor-system-controller/light-brightness.json",
    ) if isinstance(visuals, dict) else "~/.config/traktor-system-controller/light-brightness.json"
    return Path(str(value)).expanduser()


def read_visual_brightness(config: dict[str, Any]) -> float:
    visuals = config.get("visuals", {})
    default = float(visuals.get("light_brightness_default", 0.75)) \
        if isinstance(visuals, dict) else 0.75
    try:
        value = json.loads(_brightness_path(config).read_text(encoding="utf-8"))
        if isinstance(value, dict):
            value = value.get("brightness", default)
        return min(max(float(value), 0.0), 1.0)
    except (FileNotFoundError, ValueError, TypeError, json.JSONDecodeError):
        return min(max(default, 0.0), 1.0)


def set_visual_brightness(config: dict[str, Any], brightness: float) -> None:
    brightness = min(max(float(brightness), 0.0), 1.0)
    atomic_write_json(_brightness_path(config), {"brightness": round(brightness, 4)})
    for visual in list(_VISUALS):
        try:
            visual.set_brightness(brightness)
        except Exception as exc:
            log(f"Could not update controller-light brightness: {exc}")


def _scale(instance: Any, value: int) -> int:
    return min(127, max(0, round(value * instance.brightness)))


_original_f1_init = base.F1Visual.__init__
_original_x1_init = base.X1Visual.__init__


def _f1_init(self: Any, device: Any, config: dict[str, Any], theme: str) -> None:
    self.brightness = read_visual_brightness(config)
    _original_f1_init(self, device, config, theme)
    _VISUALS.add(self)


def _f1_color(self: Any, category: str) -> tuple[int, int, int]:
    raw = base.THEMES[self.theme].get(category, base.THEMES[self.theme]["system"])
    return tuple(_scale(self, value) for value in raw)


def _f1_render(self: Any) -> None:
    packet = bytearray(81)
    packet[0] = 0x80
    shifted = "shift" in self.pressed
    for number in range(1, 17):
        control = f"grid_{number}"
        color = self.color(base.mapping_category(self.config, "f1", control, shifted))
        if control in self.pressed:
            value = _scale(self, 127)
            color = (value, value, value)
        self._grid(packet, number, color)
    for control, index in base.F1_BUTTON_LED_INDEX.items():
        active = base.mapping_category(self.config, "f1", control) != "unmapped"
        idle = 0 if self.theme == "blackout" else (28 if active else 3)
        packet[index] = _scale(self, 127 if control in self.pressed else idle)
    for control, indexes in base.F1_PLAY_LED_INDEX.items():
        active = base.mapping_category(self.config, "f1", control) != "unmapped"
        idle = 0 if self.theme == "blackout" else (42 if active else 3)
        value = _scale(self, 127 if control in self.pressed else idle)
        for index in indexes:
            packet[index] = value
    self.base = packet
    self.write(packet)


def _f1_set_brightness(self: Any, brightness: float) -> None:
    self.brightness = min(max(float(brightness), 0.0), 1.0)
    self._render()


def _x1_init(self: Any, device: Any, config: dict[str, Any], theme: str) -> None:
    self.brightness = read_visual_brightness(config)
    _original_x1_init(self, device, config, theme)
    self.dim_raw = getattr(self, "dim_raw", getattr(self, "dim", 0))
    self.active_raw = getattr(self, "active_raw", getattr(self, "active", 0))
    self.pressed_raw = getattr(self, "pressed_raw", getattr(self, "pressed", 127))
    _VISUALS.add(self)
    self._render()


def _x1_render(self: Any) -> None:
    dim = getattr(self, "dim_raw", getattr(self, "dim", 0))
    active_level = getattr(self, "active_raw", getattr(self, "active", 0))
    pressed_level = getattr(self, "pressed_raw", getattr(self, "pressed", 127))
    packet = bytearray([_scale(self, dim)] * 32)
    packet[0] = _scale(self, 12)
    packet[31] = 0
    shifted = "shift" in self.pressed_controls
    for control, index in base.X1_LED_INDEX.items():
        active = base.mapping_category(self.config, "x1", control, shifted) != "unmapped"
        if active:
            packet[index] = _scale(self, active_level)
        if control in self.pressed_controls:
            packet[index] = _scale(self, pressed_level)
    self.base = packet
    self.write(packet)


def _x1_set_brightness(self: Any, brightness: float) -> None:
    self.brightness = min(max(float(brightness), 0.0), 1.0)
    self._render()


base.F1Visual.__init__ = _f1_init
base.F1Visual.color = _f1_color
base.F1Visual._render = _f1_render
base.F1Visual.set_brightness = _f1_set_brightness
base.X1Visual.__init__ = _x1_init
base.X1Visual._render = _x1_render
base.X1Visual.set_brightness = _x1_set_brightness

F1Visual = base.F1Visual
X1Visual = base.X1Visual
THEMES = base.THEMES
resolve_theme = base.resolve_theme
set_theme = base.set_theme
