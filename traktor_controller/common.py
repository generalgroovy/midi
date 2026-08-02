from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG = Path.home() / ".config/traktor-system-controller/config.json"

BUILTIN_ACTIONS = {
    "volume_absolute", "volume_relative",
    "source_volume_absolute", "source_volume_relative",
    "brightness_absolute", "brightness_relative",
    "bass_preset_absolute", "media_seek_relative", "workspace_relative",
    "sway_gap_absolute", "model_parameter_absolute", "model_parameter_relative",
    "script_slot",
}

X1_DEFAULT_ALIASES = {
    "BTN_0": "deck_a_play", "BTN_1": "deck_a_cue",
    "BTN_2": "deck_a_beat_left", "BTN_3": "deck_a_out",
    "BTN_8": "deck_a_fx2", "BTN_9": "deck_a_fx1",
    "BTN_12": "deck_b_in", "BTN_13": "deck_b_beat_right",
    "BTN_14": "deck_b_cup", "BTN_15": "deck_b_sync",
    "BTN_16": "deck_b_play", "BTN_17": "deck_b_cue",
    "BTN_18": "deck_b_beat_left", "BTN_19": "deck_b_out",
    "BTN_20": "deck_a_in", "BTN_21": "deck_a_beat_right",
    "BTN_22": "deck_a_cup", "BTN_23": "deck_a_sync",
    "BTN_24": "deck_a_browse_button", "BTN_25": "deck_b_browse_button",
    "BTN_26": "deck_a_loop_button", "BTN_27": "deck_b_loop_button",
    "BTN_28": "fx1_on", "BTN_29": "fx1_button_1",
    "BTN_30": "fx1_button_2", "BTN_31": "fx1_button_3",
    "BTN_32": "fx2_on", "BTN_33": "fx2_button_1",
    "BTN_34": "fx2_button_2", "BTN_35": "fx2_button_3",
    "BTN_36": "shift", "BTN_37": "deck_b_fx2",
    "BTN_38": "deck_b_fx1", "BTN_39": "hotcue",
    "ABS_X": "deck_a_browse_encoder", "ABS_Y": "deck_b_browse_encoder",
    "ABS_Z": "deck_a_loop_encoder", "ABS_MISC": "deck_b_loop_encoder",
    "ABS_HAT0X": "fx1_dry_wet", "ABS_HAT0Y": "fx2_dry_wet",
    "ABS_HAT1X": "fx1_knob_1", "ABS_HAT1Y": "fx2_knob_1",
    "ABS_HAT2X": "fx1_knob_2", "ABS_HAT2Y": "fx2_knob_2",
    "ABS_HAT3X": "fx1_knob_3", "ABS_HAT3Y": "fx2_knob_3",
}


def log(message: str) -> None:
    print(message, flush=True)


def expand_path(value: str | Path) -> Path:
    return Path(value).expanduser()


def atomic_write_json(path: Path, value: Any) -> None:
    path = path.expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _merge(base: Any, extra: Any) -> Any:
    if isinstance(base, dict) and isinstance(extra, dict):
        result = dict(base)
        for key, value in extra.items():
            result[key] = _merge(result[key], value) if key in result else value
        return result
    if isinstance(base, list) and isinstance(extra, list):
        return [*base, *extra]
    return extra


def load_config(path: Path, seen: set[Path] | None = None) -> dict[str, Any]:
    path = path.expanduser().resolve()
    seen = seen or set()
    if path in seen:
        raise SystemExit(f"Recursive config include: {path}")
    seen.add(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"Configuration not found: {path}")
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"Configuration root must be an object: {path}")

    result: dict[str, Any] = {}
    includes = data.pop("include", [])
    if isinstance(includes, str):
        includes = [includes]
    if not isinstance(includes, list):
        raise SystemExit(f"include must be a string or array: {path}")
    for item in includes:
        child = load_config(path.parent / str(item), seen)
        result = _merge(result, child)
    return _merge(result, data)


@dataclass(frozen=True)
class ControlEvent:
    device: str
    control: str
    kind: str
    value: int
    minimum: int = 0
    maximum: int = 1
    source: str = ""
    raw_control: str = ""

    def describe(self) -> str:
        raw = (
            f" raw={self.raw_control}"
            if self.raw_control and self.raw_control != self.control else ""
        )
        return (
            f"device={self.device} control={self.control}{raw} kind={self.kind} "
            f"value={self.value} min={self.minimum} max={self.maximum} "
            f"source={self.source}"
        )
