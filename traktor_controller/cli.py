from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .common import BUILTIN_ACTIONS, DEFAULT_CONFIG, load_config
from .eventlog import clear as clear_events
from .eventlog import emit, event_path, read_tail
from .router import EventRouter
from .unified_actions import ActionDispatcher


def load_backend() -> Any:
    candidates: list[Path] = []
    if os.environ.get("TRAKTOR_CONTROLLER_BACKEND"):
        candidates.append(Path(os.environ["TRAKTOR_CONTROLLER_BACKEND"]).expanduser())
    candidates.extend([
        Path.home() / ".local/lib/traktor-system-controller/backend.py",
        Path(__file__).resolve().parents[1] / "traktor-system-controller.py",
    ])
    for path in candidates:
        if not path.is_file():
            continue
        spec = importlib.util.spec_from_file_location("traktor_hardware_backend", path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    raise SystemExit("Traktor hardware backend not found; run install.sh.")


def _mapping_signature(mapping: dict[str, Any]) -> str:
    action = str(mapping.get("action", ""))
    if action == "script_slot":
        return f"script_slot:{mapping.get('slot', '')}"
    if action in {"model_parameter_absolute", "model_parameter_relative"}:
        return f"{action}:{mapping.get('parameter', '')}"
    return action


def _tokens(mapping: dict[str, Any], field: str, prefix: str,
            errors: list[str]) -> tuple[str, ...]:
    value = mapping.get(field, [])
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        errors.append(f"{prefix} {field} must be a string or array")
        return ()
    tokens = tuple(sorted(str(item).strip() for item in value if str(item).strip()))
    if len(tokens) != len(set(tokens)):
        errors.append(f"{prefix} {field} contains duplicates")
    return tokens


def _profiles(mapping: dict[str, Any], prefix: str,
              errors: list[str]) -> tuple[str, ...]:
    value = mapping.get("profile", mapping.get("profiles"))
    if value is None:
        return ("*",)
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        errors.append(f"{prefix} profile/profiles must be a string or array")
        return ()
    profiles = tuple(sorted(str(item).strip() for item in value if str(item).strip()))
    if not profiles:
        errors.append(f"{prefix} profile/profiles must not be empty")
    if len(profiles) != len(set(profiles)):
        errors.append(f"{prefix} profile/profiles contains duplicates")
    return profiles


def _profiles_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    return "*" in left or "*" in right or bool(set(left).intersection(right))


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(config.get("actions", {}), dict):
        errors.append("actions must be an object")
    mappings = config.get("mappings", [])
    if not isinstance(mappings, list):
        return errors + ["mappings must be an array"]
    known_actions = set(config.get("actions", {})) | BUILTIN_ACTIONS
    signatures: dict[tuple[str, str], int] = {}
    collisions: dict[
        tuple[str, str, str, tuple[str, ...], tuple[str, ...]],
        list[tuple[int, tuple[str, ...]]],
    ] = {}
    enforce_unique = bool(config.get("layout_rules", {}).get(
        "no_repeated_actions_per_controller", True
    ))
    for index, mapping in enumerate(mappings):
        prefix = f"mappings[{index}]"
        if not isinstance(mapping, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ("device", "control", "kind", "action"):
            if key not in mapping:
                errors.append(f"{prefix} missing {key}")
        if "action" in mapping and str(mapping["action"]) not in known_actions:
            errors.append(f"{prefix} references unknown action {mapping['action']!r}")
        if mapping.get("kind") not in {"press", "release", "relative", "absolute", None}:
            errors.append(f"{prefix} has unsupported kind {mapping.get('kind')!r}")
        if mapping.get("action") == "script_slot" and not mapping.get("slot"):
            errors.append(f"{prefix} script_slot requires slot")
        if mapping.get("action") in {"model_parameter_absolute", "model_parameter_relative"} and not mapping.get("parameter"):
            errors.append(f"{prefix} model action requires parameter")
        requires = _tokens(mapping, "requires", prefix, errors)
        unless = _tokens(mapping, "unless", prefix, errors)
        profiles = _profiles(mapping, prefix, errors)
        overlap = sorted(set(requires).intersection(unless))
        if overlap:
            errors.append(
                f"{prefix} requires and excludes the same control(s): {', '.join(overlap)}"
            )
        if not bool(mapping.get("enabled", True)):
            continue
        collision_key = (
            str(mapping.get("device", "")),
            str(mapping.get("control", "")),
            str(mapping.get("kind", "")),
            requires,
            unless,
        )
        prior_records = collisions.setdefault(collision_key, [])
        for prior_index, prior_profiles in prior_records:
            if _profiles_overlap(prior_profiles, profiles):
                errors.append(
                    f"{prefix} is ambiguous with mappings[{prior_index}]: "
                    "same input and conditions in overlapping profiles"
                )
                break
        prior_records.append((index, profiles))
        if enforce_unique:
            key = (str(mapping.get("device", "")), _mapping_signature(mapping))
            if key in signatures:
                errors.append(
                    f"{prefix} repeats {_mapping_signature(mapping)!r} on {key[0]} "
                    f"(already mappings[{signatures[key]}])"
                )
            else:
                signatures[key] = index
    parameters = config.get("model_controls", {}).get("parameters", {})
    if not isinstance(parameters, dict):
        errors.append("model_controls.parameters must be an object")
    else:
        for name, spec in parameters.items():
            if not isinstance(spec, dict):
                errors.append(f"model parameter {name!r} must be an object")
                continue
            if float(spec.get("max", 1)) <= float(spec.get("min", 0)):
                errors.append(f"model parameter {name!r} max must exceed min")
    return errors


def show_layout(config: dict[str, Any], profile: str | None) -> int:
    selected = profile or str(config.get("active_profile", "linux-ops"))
    router = EventRouter(config, monitor=False, profile=selected, dry_run=True)
    print(f"Active profile: {selected}")
    details = config.get("profiles", {}).get(selected, {})
    if isinstance(details, dict) and details.get("description"):
        print(f"Description: {details['description']}")
    print()
    rows: list[tuple[str, str, str, str, str]] = []
    for (device, control, kind), mappings in router.mappings.items():
        for mapping in mappings:
            modifiers: list[str] = []
            for key in ("requires", "unless"):
                value = mapping.get(key)
                if value:
                    values = value if isinstance(value, list) else [value]
                    modifiers.append(f"{key}=" + ",".join(str(item) for item in values))
            rows.append((device, control, kind, _mapping_signature(mapping), " ".join(modifiers)))
    for device, control, kind, action, modifiers in sorted(rows):
        print(f"{device:3} {control:27} {kind:8} -> {action}" + (f" [{modifiers}]" if modifiers else ""))
    return 0


def show_model_state(config: dict[str, Any]) -> int:
    path = Path(str(config.get("model_controls", {}).get(
        "state_file", "~/.config/traktor-system-controller/model-controls.json"
    ))).expanduser()
    if not path.exists():
        print(f"No model state yet: {path}")
        return 1
    print(path.read_text(encoding="utf-8"), end="")
    return 0


def _service_state() -> dict[str, Any]:
    command = [
        "systemctl", "--user", "show", "traktor-system-controller.service",
        "--property=LoadState,ActiveState,SubState,MainPID", "--no-pager",
    ]
    try:
        result = subprocess.run(command, text=True, capture_output=True, timeout=5, check=False)
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "error": str(exc)}
    values: dict[str, Any] = {"available": result.returncode == 0}
    for line in result.stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = int(value) if key == "MainPID" and value.isdigit() else value
    if result.returncode != 0:
        values["error"] = (result.stderr or result.stdout).strip()
    return values


def _json_status(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    errors = validate_config(config)
    controls = config.get("display_controls", {})
    path = event_path()
    return {
        "schema_version": 1,
        "application": "midilin",
        "config": str(config_path.expanduser().resolve()),
        "config_valid": not errors,
        "config_errors": errors,
        "active_profile": str(config.get("active_profile", "linux-ops")),
        "enabled_mappings": sum(
            1 for mapping in config.get("mappings", [])
            if isinstance(mapping, dict) and mapping.get("enabled", True)
        ),
        "service": _service_state(),
        "environment": {
            "wayland_display": bool(os.environ.get("WAYLAND_DISPLAY")),
            "sway_socket": bool(os.environ.get("SWAYSOCK")),
            "xdg_runtime_dir": bool(os.environ.get("XDG_RUNTIME_DIR")),
        },
        "backends": {
            "brightnessctl": shutil.which("brightnessctl"),
            "ddcutil": shutil.which("ddcutil"),
            "wlsunset": shutil.which("wlsunset"),
            "gammastep": shutil.which("gammastep"),
            "swaymsg": shutil.which("swaymsg"),
        },
        "display_controls": controls if isinstance(controls, dict) else {},
        "event_log": {
            "path": str(path),
            "exists": path.exists(),
            "bytes": path.stat().st_size if path.exists() else 0,
            "recent_events": len(read_tail(100)),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--profile")
    parser.add_argument("--monitor", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--list-devices", action="store_true")
    parser.add_argument("--list-ports", action="store_true")
    parser.add_argument("--show-layout", action="store_true")
    parser.add_argument("--validate-config", action="store_true")
    parser.add_argument("--approve-connected", action="store_true")
    parser.add_argument("--deny-connected", action="store_true")
    parser.add_argument("--forget-device-decisions", action="store_true")
    parser.add_argument("--list-themes", action="store_true")
    parser.add_argument("--set-theme")
    parser.add_argument("--visual-theme")
    parser.add_argument("--model-state", action="store_true")
    parser.add_argument("--gui", action="store_true")
    parser.add_argument("--set-brightness", type=int, metavar="PERCENT")
    parser.add_argument("--set-temperature", type=int, metavar="KELVIN")
    parser.add_argument("--diagnose-display", action="store_true")
    parser.add_argument("--event-log", type=Path)
    parser.add_argument("--event-tail", type=int, metavar="COUNT")
    parser.add_argument("--clear-event-log", action="store_true")
    parser.add_argument("--json-status", action="store_true")
    args = parser.parse_args()

    if args.event_log:
        os.environ["MIDILIN_EVENT_LOG"] = str(args.event_log.expanduser())
    if args.gui:
        from .gui import main as gui_main
        return gui_main()
    if args.clear_event_log:
        removed = clear_events()
        print(f"Event log {'removed' if removed else 'already absent'}: {event_path()}")
        return 0
    if args.event_tail is not None:
        print(json.dumps(read_tail(args.event_tail), indent=2, ensure_ascii=False))
        return 0

    config_path = args.config.expanduser()
    config = load_config(config_path)
    errors = validate_config(config)
    if args.json_status:
        print(json.dumps(_json_status(config_path, config), indent=2, ensure_ascii=False))
        return 0
    if args.validate_config:
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Configuration valid: {args.config}")
        return 0
    if errors:
        emit("runtime_rejected", reason="invalid-config", errors=errors)
        raise SystemExit("Invalid configuration:\n- " + "\n- ".join(errors))

    dispatcher = ActionDispatcher(config)
    if args.set_brightness is not None:
        return 0 if dispatcher.set_brightness_percent(args.set_brightness) else 1
    if args.set_temperature is not None:
        return 0 if dispatcher.set_color_temperature_kelvin(args.set_temperature) else 1
    if args.diagnose_display:
        for line in dispatcher.diagnose_displays():
            print(line)
        return 0
    if args.model_state:
        return show_model_state(config)
    if args.show_layout:
        return show_layout(config, args.profile)

    backend = load_backend()
    if args.list_devices or args.list_ports:
        return backend.list_devices()
    if args.list_themes:
        print("\n".join(sorted(backend.THEMES)))
        return 0
    if args.set_theme:
        backend.set_theme(config, args.set_theme)
        print(f"Visual theme set to {args.set_theme}. Restart the service to apply it.")
        return 0
    if args.approve_connected:
        return backend.approve_connected(config, "always")
    if args.deny_connected:
        return backend.approve_connected(config, "never")
    if args.forget_device_decisions:
        return backend.forget_device_decisions(config)

    selected_profile = args.profile or str(config.get("active_profile", "linux-ops"))
    emit(
        "runtime_started",
        pid=os.getpid(),
        profile=selected_profile,
        monitor=args.monitor,
        dry_run=args.dry_run,
        config=str(config_path.resolve()),
        event_log=str(event_path()),
    )
    print(f"Structured event log: {event_path()}")
    runtime = backend.ControllerRuntime(
        EventRouter(config, monitor=args.monitor, profile=args.profile, dry_run=args.dry_run),
        config=config, visual_theme=args.visual_theme,
    )
    try:
        runtime.run()
    except KeyboardInterrupt:
        emit("runtime_stopped", reason="keyboard-interrupt", pid=os.getpid())
        print()
        return 0
    emit("runtime_stopped", reason="normal", pid=os.getpid())
    return 0
