from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from .common import BUILTIN_ACTIONS, DEFAULT_CONFIG, load_config
from .router import EventRouter


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


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(config.get("actions", {}), dict):
        errors.append("actions must be an object")
    mappings = config.get("mappings", [])
    if not isinstance(mappings, list):
        return errors + ["mappings must be an array"]
    known_actions = set(config.get("actions", {})) | BUILTIN_ACTIONS
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
    return errors


def show_layout(config: dict[str, Any], profile: str | None) -> int:
    selected = profile or str(config.get("active_profile", "desktop"))
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
            rows.append((device, control, kind, str(mapping["action"]), " ".join(modifiers)))
    for device, control, kind, action, modifiers in sorted(rows):
        print(f"{device:3} {control:26} {kind:8} -> {action}" + (f" [{modifiers}]" if modifiers else ""))
    return 0


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
    args = parser.parse_args()

    backend = load_backend()
    if args.list_devices or args.list_ports:
        return backend.list_devices()
    config = load_config(args.config)
    errors = validate_config(config)
    if args.validate_config:
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Configuration valid: {args.config}")
        return 0
    if errors:
        raise SystemExit("Invalid configuration:\n- " + "\n- ".join(errors))
    if args.show_layout:
        return show_layout(config, args.profile)
    runtime = backend.ControllerRuntime(
        EventRouter(config, monitor=args.monitor, profile=args.profile, dry_run=args.dry_run)
    )
    try:
        runtime.run()
    except KeyboardInterrupt:
        print()
        return 0
