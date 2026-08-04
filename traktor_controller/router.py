from __future__ import annotations

import time
from typing import Any

from .common import ControlEvent, X1_DEFAULT_ALIASES, log
from .eventlog import emit as emit_event
from .unified_actions import ActionDispatcher


class EventRouter:
    def __init__(
        self, config: dict[str, Any], monitor: bool,
        profile: str | None = None, dry_run: bool = False,
    ):
        self.config = config
        self.monitor = monitor
        self.dry_run = dry_run
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

        for index, mapping in enumerate(config.get("mappings", [])):
            if not isinstance(mapping, dict) or not bool(mapping.get("enabled", True)):
                continue
            if not self._profile_matches(mapping):
                continue
            mapping = {**mapping, "_mapping_index": index}
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
        emit_event(
            "control_input",
            profile=self.profile,
            monitor=self.monitor,
            dry_run=self.dry_run,
            device=event.device,
            control=event.control,
            raw_control=event.raw_control,
            event_kind=event.kind,
            value=event.value,
            minimum=event.minimum,
            maximum=event.maximum,
            ratio=event.ratio,
            source=event.source,
            held=[f"{device}.{control}" for device, control in sorted(self.held)],
        )
        if event.kind == "press":
            self.held.add(held_key)
            emit_event(
                "modifier_state",
                event_kind="press",
                control=f"{event.device}.{event.control}",
                held=[f"{device}.{control}" for device, control in sorted(self.held)],
            )
        try:
            if self.monitor:
                log(event.describe())
                return
            key = (event.device, event.control, event.kind)
            mappings = self.mappings.get(key, [])
            if event.kind == "absolute" and mappings:
                now = time.monotonic()
                elapsed = now - self.last_dispatch.get(key, 0.0)
                if elapsed < 0.04:
                    emit_event(
                        "input_throttled",
                        device=event.device,
                        control=event.control,
                        event_kind=event.kind,
                        elapsed_seconds=elapsed,
                    )
                    return
                self.last_dispatch[key] = now
            matched = 0
            for mapping in mappings:
                if self._conditions_match(mapping, event):
                    matched += 1
                    emit_event(
                        "mapping_selected",
                        mapping_index=mapping.get("_mapping_index"),
                        profile=self.profile,
                        action=mapping.get("action"),
                        device=event.device,
                        control=event.control,
                        event_kind=event.kind,
                        requires=mapping.get("requires", []),
                        unless=mapping.get("unless", []),
                        held=[f"{device}.{control}" for device, control in sorted(self.held)],
                    )
                    self.dispatcher.dispatch(mapping, event)
            if matched == 0:
                emit_event(
                    "mapping_unmatched",
                    profile=self.profile,
                    device=event.device,
                    control=event.control,
                    event_kind=event.kind,
                    candidates=len(mappings),
                    held=[f"{device}.{control}" for device, control in sorted(self.held)],
                )
        finally:
            if event.kind == "release":
                self.held.discard(held_key)
                emit_event(
                    "modifier_state",
                    event_kind="release",
                    control=f"{event.device}.{event.control}",
                    held=[f"{device}.{control}" for device, control in sorted(self.held)],
                )
