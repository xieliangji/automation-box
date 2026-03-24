from __future__ import annotations

from pathlib import Path
from typing import Any


class WatchdogService:
    def __init__(self, config: Any, watchdog: Any, telemetry_service: Any) -> None:
        self.config = config
        self.watchdog = watchdog
        self.telemetry_service = telemetry_service

    def handle(
        self,
        driver: Any,
        previous_state: Any,
        current_state: Any,
        action: Any,
        transition: Any,
        next_state: Any,
    ) -> list[Path]:
        if not self.config.features.enable_watchdog:
            return []
        events = self.watchdog.inspect(
            previous_state=previous_state or current_state,
            action=action,
            transition=transition,
            next_state=next_state,
            driver=driver,
        )
        if not events:
            return []
        issue_dirs = self.watchdog.record_events(
            events=events,
            previous_state=previous_state or current_state,
            action=action,
            transition=transition,
            next_state=next_state,
            driver=driver,
        )
        self.telemetry_service.export_issue_replay(issue_dirs)
        return issue_dirs
