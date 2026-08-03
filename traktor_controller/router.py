from __future__ import annotations

import time
from typing import Any

from .advanced_actions import ActionDispatcher
from .common import ControlEvent, X1_DEFAULT_ALIASES, log


class EventRouter:
    def __init__(
        self, config: dict[str, Any], monitor: bool,
        profile: str | None = None, dry_run: bool = False,
    ):
        self.config = config
        self.monitor = monitor
        self.profile = profile or str(config.get("active_profile", "linux-ops"))
        self.dispatcher = ActionDispatcher(config, dry_run=dry_run)
        self.mappings: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
        self.last_dispatch: dict[tuple[str, str, str], float] = {}
        self.held: set[tuple[str, str]] = set()

        self.aliases = {"x1": dict(X1_DEFAULT_ALIASES), "f1": {}}
        configured = config.get("control_aliases", {})
        if isinstance(configured, dict):
            for device, aliases in configured.items():
                if isinstance(aliases, dict):
                    self.aliases.setdefault(str(device), {}).update(
                        {str(raw): str(logical) for raw, logical in aliases.items()}
                    )

        for mapping in config.get("mappings", []):
            if not isinstance(mapping, dict) or not bool(mapping.get("enabled", True)):
                continue
            if not self._profile_matches(mapping):
                continue
            key = (str(mapping["device"]), str(mapping["control"]), str(mapping["kind"]))
            self.mappings.setdefault(key, []).append(mapping)

    def _profile_matches(self, mapping: dict[str, Any]) -> bool:
        value = mapping.get("profile", mapping.get("profiles"))
        if value is None:
            return True
        if isinstance(value, str):
            return value == self.profile
        return isinstance(value, list) and self.profile in {str(item) for item in value}

    def _state_key(self, token: str, event: ControlEvent) -> tuple[str, str]:
        token = token.strip()
        for separator in (".", ":"):
            if separator in token:
                device, control = token.split(separator, 1)
                return device, control
        return event.device, token

    def _conditions_match(self, mapping: dict[str, Any], event: ControlEvent) -> bool:
        requires = mapping.get("requires", [])
        unless = mapping.get("unless", [])
        requires = [requires] if isinstance(requires, str) else requires
        unless = [unless] if isinstance(unless, str) else unless
        return (
            all(self._state_key(str(token), event) in self.held for token in requires)
            and all(self._state_key(str(token), event) not in self.held for token in unless)
        )

    def _normalize(self, event: Any) -> ControlEvent:
        raw = str(event.control)
        return ControlEvent(
            device=str(event.device),
            control=self.aliases.get(str(event.device), {}).get(raw, raw),
            kind=str(event.kind), value=int(event.value),
            minimum=int(getattr(event, "minimum", 0)),
            maximum=int(getattr(event, "maximum", 1)),
            source=str(getattr(event, "source", "")), raw_control=raw,
        )

    def emit(self, raw_event: Any) -> None:
        event = self._normalize(raw_event)
        held_key = (event.device, event.control)
        if event.kind == "press":
            self.held.add(held_key)
        try:
            if self.monitor:
                log(event.describe())
                return
            key = (event.device, event.control, event.kind)
            mappings = self.mappings.get(key, [])
            if event.kind == "absolute" and mappings:
                now = time.monotonic()
                if now - self.last_dispatch.get(key, 0.0) < 0.04:
                    return
                self.last_dispatch[key] = now
            for mapping in mappings:
                if self._conditions_match(mapping, event):
                    self.dispatcher.dispatch(mapping, event)
        finally:
            if event.kind == "release":
                self.held.discard(held_key)
