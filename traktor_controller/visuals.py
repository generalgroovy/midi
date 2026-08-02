from __future__ import annotations

from pathlib import Path
from typing import Any

THEME_KEYS = (
    "application", "workspace", "audio", "system", "monitor",
    "maintenance", "model", "script", "media", "unmapped",
)
THEMES = {
    "category": {
        "application": (18, 70, 95), "workspace": (70, 28, 100),
        "audio": (100, 42, 8), "system": (100, 12, 22),
        "monitor": (8, 90, 50), "maintenance": (100, 75, 5),
        "model": (95, 15, 90), "script": (8, 80, 100),
        "media": (10, 100, 30), "unmapped": (4, 4, 8),
    },
    "neon": {
        "application": (0, 105, 127), "workspace": (90, 0, 127),
        "audio": (127, 40, 0), "system": (127, 0, 35),
        "monitor": (0, 127, 45), "maintenance": (127, 95, 0),
        "model": (127, 0, 115), "script": (0, 95, 127),
        "media": (0, 127, 20), "unmapped": (3, 3, 7),
    },
    "sunset": {
        "application": (90, 20, 70), "workspace": (75, 8, 105),
        "audio": (127, 35, 0), "system": (115, 5, 25),
        "monitor": (70, 35, 95), "maintenance": (127, 75, 0),
        "model": (110, 0, 85), "script": (100, 15, 65),
        "media": (127, 50, 5), "unmapped": (5, 2, 5),
    },
}
THEMES["matrix"] = {
    key: ((0, 80, 8) if key != "unmapped" else (0, 3, 0))
    for key in THEME_KEYS
}
THEMES["mono"] = {
    key: ((45, 45, 55) if key != "unmapped" else (2, 2, 3))
    for key in THEME_KEYS
}
THEMES["blackout"] = {key: (0, 0, 0) for key in THEME_KEYS}

F1_BUTTON_LED_INDEX = {
    "browse": 17, "size": 18, "type": 19, "reverse": 20,
    "shift": 21, "capture": 22, "quant": 23, "sync": 24,
}
F1_PLAY_LED_INDEX = {
    "play_4": (73, 74), "play_3": (75, 76),
    "play_2": (77, 78), "play_1": (79, 80),
}
X1_LED_INDEX = {
    "shift": 29, "hotcue": 31,
    "fx1_on": 8, "fx1_button_1": 7, "fx1_button_2": 6, "fx1_button_3": 5,
    "fx2_on": 4, "fx2_button_1": 3, "fx2_button_2": 2, "fx2_button_3": 1,
    "deck_a_fx1": 25, "deck_a_fx2": 26,
    "deck_b_fx1": 27, "deck_b_fx2": 28,
    "deck_a_in": 18, "deck_a_out": 17,
    "deck_a_beat_left": 20, "deck_a_beat_right": 19,
    "deck_a_cue": 22, "deck_a_cup": 21,
    "deck_a_play": 24, "deck_a_sync": 23,
    "deck_b_in": 16, "deck_b_out": 15,
    "deck_b_beat_left": 14, "deck_b_beat_right": 13,
    "deck_b_cue": 12, "deck_b_cup": 11,
    "deck_b_play": 10, "deck_b_sync": 9,
}


def log(message: str) -> None:
    print(message, flush=True)


def resolve_theme(config: dict[str, Any], override: str | None = None) -> str:
    if override:
        return override if override in THEMES else "category"
    visuals = config.get("visuals", {})
    path = Path(str(visuals.get(
        "theme_state_file", "~/.config/traktor-system-controller/visual-theme"
    ))).expanduser()
    try:
        value = path.read_text(encoding="utf-8").strip()
        if value in THEMES:
            return value
    except FileNotFoundError:
        pass
    value = str(visuals.get("theme", "category"))
    return value if value in THEMES else "category"


def set_theme(config: dict[str, Any], theme: str) -> None:
    if theme not in THEMES:
        raise ValueError(f"Unknown theme {theme!r}; choose from {', '.join(THEMES)}")
    path = Path(str(config.get("visuals", {}).get(
        "theme_state_file", "~/.config/traktor-system-controller/visual-theme"
    ))).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(theme + "\n", encoding="utf-8")


def _requires_shift(mapping: dict[str, Any], device: str) -> bool:
    value = mapping.get("requires", [])
    values = [value] if isinstance(value, str) else value
    return any(str(item) in {"shift", f"{device}.shift", f"{device}:shift"} for item in values)


def mapping_category(
    config: dict[str, Any], device: str, control: str, shifted: bool = False,
) -> str:
    categories = config.get("visuals", {}).get("action_categories", {})
    candidates = [
        mapping for mapping in config.get("mappings", [])
        if isinstance(mapping, dict)
        and mapping.get("enabled", True)
        and mapping.get("device") == device
        and mapping.get("control") == control
        and _requires_shift(mapping, device) == shifted
    ]
    if not candidates and shifted:
        return "unmapped"
    if not candidates:
        candidates = [
            mapping for mapping in config.get("mappings", [])
            if isinstance(mapping, dict)
            and mapping.get("enabled", True)
            and mapping.get("device") == device
            and mapping.get("control") == control
        ]
    if not candidates:
        return "unmapped"
    action = str(candidates[0].get("action"))
    if action == "script_slot":
        return "script"
    if action.startswith("model_parameter_"):
        return "model"
    return str(categories.get(action, candidates[0].get("category", "system")))


class F1Visual:
    def __init__(self, device: Any, config: dict[str, Any], theme: str):
        self.device = device
        self.config = config
        self.theme = theme
        self.pressed: set[str] = set()
        self.base = bytearray(81)
        self.base[0] = 0x80
        self._render()

    def color(self, category: str) -> tuple[int, int, int]:
        return THEMES[self.theme].get(category, THEMES[self.theme]["system"])

    @staticmethod
    def _grid(packet: bytearray, number: int, rgb: tuple[int, int, int]) -> None:
        red, green, blue = rgb
        offset = 25 + (number - 1) * 3
        packet[offset:offset + 3] = bytes((blue, red, green))

    def write(self, packet: bytearray) -> None:
        try:
            self.device.write(bytes(packet))
        except Exception as exc:
            log(f"F1 LED write failed: {exc}")

    def _render(self) -> None:
        packet = bytearray(81)
        packet[0] = 0x80
        shifted = "shift" in self.pressed
        for number in range(1, 17):
            control = f"grid_{number}"
            color = self.color(mapping_category(self.config, "f1", control, shifted))
            if control in self.pressed:
                color = (127, 127, 127)
            self._grid(packet, number, color)
        for control, index in F1_BUTTON_LED_INDEX.items():
            active = mapping_category(self.config, "f1", control) != "unmapped"
            packet[index] = 127 if control in self.pressed else (28 if active else 3)
        for control, indexes in F1_PLAY_LED_INDEX.items():
            active = mapping_category(self.config, "f1", control) != "unmapped"
            value = 127 if control in self.pressed else (42 if active else 3)
            for index in indexes:
                packet[index] = value
        self.base = packet
        self.write(packet)

    def feedback(self, control: str, pressed: bool) -> None:
        if pressed:
            self.pressed.add(control)
        else:
            self.pressed.discard(control)
        self._render()

    def clear(self) -> None:
        packet = bytearray(81)
        packet[0] = 0x80
        self.write(packet)


class X1Visual:
    def __init__(self, device: Any, config: dict[str, Any], theme: str):
        self.device = device
        self.config = config
        self.theme = theme
        self.pressed_controls: set[str] = set()
        options = config.get("visuals", {}).get("x1", {})
        self.dim = int(options.get("dim", 5))
        self.active = int(options.get("active", 0 if theme == "blackout" else 28))
        self.pressed = int(options.get("pressed", 127))
        self.base = bytearray(32)
        self._render()

    def write(self, packet: bytearray) -> None:
        try:
            self.device.write(0x01, packet, timeout=100)
            try:
                self.device.read(0x81, 1, timeout=30)
            except Exception:
                pass
        except Exception as exc:
            log(f"X1 LED write failed: {exc}")

    def _render(self) -> None:
        packet = bytearray([self.dim] * 32)
        packet[0] = 12
        packet[31] = 0
        shifted = "shift" in self.pressed_controls
        for control, index in X1_LED_INDEX.items():
            active = mapping_category(self.config, "x1", control, shifted) != "unmapped"
            if active:
                packet[index] = self.active
            if control in self.pressed_controls:
                packet[index] = self.pressed
        self.base = packet
        self.write(packet)

    def feedback(self, control: str, pressed: bool) -> None:
        if control not in X1_LED_INDEX:
            return
        if pressed:
            self.pressed_controls.add(control)
        else:
            self.pressed_controls.discard(control)
        self._render()

    def clear(self) -> None:
        packet = bytearray(32)
        packet[0] = 12
        self.write(packet)
