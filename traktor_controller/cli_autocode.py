from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from . import cli as base
from .autocode import AUTOCODE_ACTIONS, dispatch, read_state, settings, validate
from .common import DEFAULT_CONFIG, load_config


_BASE_VALIDATE = base.validate_config
_BASE_JSON_STATUS = base._json_status


def validate_config(config: dict[str, Any]) -> list[str]:
    return [*_BASE_VALIDATE(config), *validate(config)]


def _json_status(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    value = _BASE_JSON_STATUS(config_path, config)
    try:
        state = read_state(config)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        state = {"available": False, "error": str(exc)}
    value["autocode"] = {
        "enabled": bool(settings(config).get("enabled", False)),
        "workspace": str(settings(config).get("workspace", "~/Projects/flux2")),
        "state": state,
        "actions": sorted(AUTOCODE_ACTIONS),
        "arbitrary_commands": False,
    }
    value["config_errors"] = validate_config(config)
    value["config_valid"] = not value["config_errors"]
    return value


def _config_argument(arguments: list[str]) -> Path:
    for index, value in enumerate(arguments):
        if value == "--config" and index + 1 < len(arguments):
            return Path(arguments[index + 1]).expanduser()
        if value.startswith("--config="):
            return Path(value.split("=", 1)[1]).expanduser()
    return DEFAULT_CONFIG


def _special(arguments: list[str]) -> int | None:
    config_path = _config_argument(arguments)
    config = load_config(config_path)
    errors = validate_config(config)
    if "--autocode-state" in arguments:
        if errors:
            raise SystemExit("Invalid configuration:\n- " + "\n- ".join(errors))
        print(json.dumps(read_state(config), indent=2, ensure_ascii=False))
        return 0
    if "--autocode-action" in arguments:
        index = arguments.index("--autocode-action")
        if index + 1 >= len(arguments):
            raise SystemExit("--autocode-action requires an action name")
        action = arguments[index + 1]
        if action not in AUTOCODE_ACTIONS:
            raise SystemExit(
                "Unsupported Autocode action; choose one of: "
                + ", ".join(sorted(AUTOCODE_ACTIONS))
            )
        if errors:
            raise SystemExit("Invalid configuration:\n- " + "\n- ".join(errors))
        result = dispatch(config, action)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result.get("ok", False) else 1
    return None


def main() -> int:
    special = _special(sys.argv[1:])
    if special is not None:
        return special
    base.validate_config = validate_config
    base._json_status = _json_status
    return base.main()
