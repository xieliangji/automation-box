from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smart_monkey.models import Action, DeviceState, Transition
from smart_monkey.storage.issue_recorder import IssueRecorder


@dataclass(slots=True)
class WatchdogEvent:
    event_type: str
    message: str
    severity: str = "warning"
    log_excerpt: str = ""


class Watchdog:
    def __init__(self, app_package: str, issue_recorder: IssueRecorder) -> None:
        self.app_package = app_package
        self.issue_recorder = issue_recorder
        self._recent_signatures: list[str] = []

    def reset_logcat(self, driver: Any) -> None:
        if hasattr(driver, "clear_logcat"):
            try:
                driver.clear_logcat()
            except Exception:  # noqa: BLE001
                return

    def inspect(
        self,
        previous_state: DeviceState,
        action: Action,
        transition: Transition,
        next_state: DeviceState,
        driver: Any,
    ) -> list[WatchdogEvent]:
        events: list[WatchdogEvent] = []

        log_excerpt = self._read_logcat(driver)
        if self._looks_like_crash(log_excerpt):
            events.append(
                WatchdogEvent(
                    event_type="crash",
                    message="logcat 中检测到疑似 crash 信号",
                    severity="critical",
                    log_excerpt=log_excerpt,
                )
            )
        if self._looks_like_anr(log_excerpt):
            events.append(
                WatchdogEvent(
                    event_type="anr",
                    message="logcat 中检测到疑似 ANR 信号",
                    severity="critical",
                    log_excerpt=log_excerpt,
                )
            )
        if transition.out_of_app:
            events.append(
                WatchdogEvent(
                    event_type="out_of_app",
                    message=f"应用跳出目标包: {next_state.package_name}",
                    severity="warning",
                    log_excerpt=log_excerpt,
                )
            )
        if "permission_like" in next_state.popup_flags or "permission_controller" in next_state.system_flags:
            events.append(
                WatchdogEvent(
                    event_type="permission_dialog",
                    message="检测到疑似权限弹窗或权限控制页",
                    severity="info",
                    log_excerpt=log_excerpt,
                )
            )
        if "settings" in next_state.system_flags:
            events.append(
                WatchdogEvent(
                    event_type="settings_page",
                    message="当前位于系统设置页",
                    severity="info",
                    log_excerpt=log_excerpt,
                )
            )

        unique_events: list[WatchdogEvent] = []
        for event in events:
            signature = f"{event.event_type}|{next_state.state_id}|{event.message}"
            if signature in self._recent_signatures:
                continue
            self._recent_signatures.append(signature)
            self._recent_signatures = self._recent_signatures[-20:]
            unique_events.append(event)
        return unique_events

    def record_events(
        self,
        events: list[WatchdogEvent],
        previous_state: DeviceState,
        action: Action,
        transition: Transition,
        next_state: DeviceState,
        driver: Any,
    ) -> list[Path]:
        issue_dirs: list[Path] = []
        for event in events:
            issue_dirs.append(
                self.issue_recorder.record_issue(
                    issue_type=event.event_type,
                    title=event.message,
                    payload={
                        "event": event,
                        "previous_state": previous_state,
                        "action": action,
                        "transition": transition,
                        "next_state": next_state,
                    },
                    driver=driver,
                )
            )
        return issue_dirs

    def _read_logcat(self, driver: Any) -> str:
        if hasattr(driver, "read_logcat_tail"):
            try:
                return driver.read_logcat_tail(150)
            except Exception:  # noqa: BLE001
                return ""
        return ""

    def _looks_like_crash(self, log_excerpt: str) -> bool:
        signals = [
            "FATAL EXCEPTION",
            "AndroidRuntime",
            "Process: ",
            "has crashed",
            "java.lang.RuntimeException",
        ]
        lower_log = log_excerpt.lower()
        if self.app_package.lower() not in lower_log:
            return False
        return any(signal.lower() in lower_log for signal in signals)

    def _looks_like_anr(self, log_excerpt: str) -> bool:
        signals = [
            f"ANR in {self.app_package}",
            "Application Not Responding",
            "Input dispatching timed out",
            "isn't responding",
        ]
        lower_log = log_excerpt.lower()
        return any(signal.lower() in lower_log for signal in signals)
