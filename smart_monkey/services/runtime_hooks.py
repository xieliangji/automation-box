from __future__ import annotations

from pathlib import Path
from typing import Any

from smart_monkey.models import Action, DeviceState, Transition


class RuntimeHooks:
    def __init__(self, config: Any, checkpoint_manager: Any, telemetry_service: Any, report_service: Any) -> None:
        self.config = config
        self.checkpoint_manager = checkpoint_manager
        self.telemetry_service = telemetry_service
        self.report_service = report_service

    def on_run_start(self, driver: Any, watchdog: Any | None = None) -> None:
        if self.config.features.enable_watchdog and watchdog is not None:
            watchdog.reset_logcat(driver)

    def on_state_captured(self, state: DeviceState, visit_count: int, utg: Any) -> None:
        utg.add_state(
            state.state_id,
            {
                "package_name": state.package_name,
                "activity_name": state.activity_name,
                "app_flags": sorted(state.app_flags),
                "popup_flags": sorted(state.popup_flags),
            },
        )
        self.checkpoint_manager.consider(state, visit_count)

    def on_step_persist(
        self,
        step: int,
        driver: Any,
        recorder: Any,
        current_state: DeviceState,
        next_state: DeviceState,
        action: Action,
        transition: Transition,
    ) -> None:
        self.telemetry_service.maybe_capture_periodic_snapshot(step=step, driver=driver, recorder=recorder)
        self.telemetry_service.append_replay(step=step, action=action, state_id=current_state.state_id)
        self.telemetry_service.append_recent_step(
            {
                "step": step,
                "current_state_id": current_state.state_id,
                "next_state_id": next_state.state_id,
                "action_type": action.action_type.value,
                "action_id": action.action_id,
                "changed": transition.changed,
                "duration_ms": transition.duration_ms,
                "out_of_app": transition.out_of_app,
            }
        )

    def on_watchdog_events(self, issue_dirs: list[Path]) -> None:
        self.telemetry_service.export_issue_replay(issue_dirs)

    def on_run_finish(self, recorder: Any, utg: Any) -> dict[str, str]:
        recorder.record_utg(utg)
        if self.telemetry_service.runtime_metrics:
            recorder.record_step(
                {
                    "step": -1,
                    "runtime_metrics": self.telemetry_service.runtime_metrics,
                }
            )
        return self.report_service.generate_all()
