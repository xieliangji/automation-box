from __future__ import annotations

from pathlib import Path

from smart_monkey.app import SmartMonkeyApp
from smart_monkey.config import ProjectConfig
from smart_monkey.device.base import DeviceDriver
from smart_monkey.monitor.watchdog import Watchdog
from smart_monkey.storage.issue_recorder import IssueRecorder


class WatchdogSmartMonkeyApp(SmartMonkeyApp):
    def __init__(self, driver: DeviceDriver, config: ProjectConfig, output_dir: str | Path = "output") -> None:
        super().__init__(driver=driver, config=config, output_dir=output_dir)
        self.issue_recorder = IssueRecorder(self.output_dir)
        self.watchdog = Watchdog(app_package=config.app.package_name, issue_recorder=self.issue_recorder)

    def run(self) -> None:
        self.watchdog.reset_logcat(self.driver)
        self._ensure_app_started()
        previous_state = None

        for step in range(self.config.run.max_steps):
            current_state = self.capture_state(step_no=step, suffix="before")
            self._mark_visited(current_state.state_id)
            self.runtime.utg.add_state(
                current_state.state_id,
                {
                    "package_name": current_state.package_name,
                    "activity_name": current_state.activity_name,
                    "app_flags": sorted(current_state.app_flags),
                    "popup_flags": sorted(current_state.popup_flags),
                },
            )

            actions = self.extractor.extract(current_state)
            scored_actions = self.scorer.score(current_state, actions, self.runtime.stats)
            action = self.select_action(scored_actions)
            result = self.execute_action(action)
            self.driver.wait_idle(self.config.run.post_action_wait_ms)
            next_state = self.capture_state(step_no=step, suffix="after")

            transition = self._build_transition(current_state, action, next_state, result)
            self.update_runtime(current_state, action, transition)
            self.persist_step(step, current_state, action, transition, next_state)

            events = self.watchdog.inspect(
                previous_state=previous_state or current_state,
                action=action,
                transition=transition,
                next_state=next_state,
                driver=self.driver,
            )
            if events:
                self.watchdog.record_events(
                    events=events,
                    previous_state=previous_state or current_state,
                    action=action,
                    transition=transition,
                    next_state=next_state,
                    driver=self.driver,
                )

            if transition.out_of_app:
                self.recover_from_out_of_app()
            elif self.should_escape(previous_state, current_state, next_state, transition):
                self.escape()

            previous_state = next_state

        self.recorder.record_utg(self.runtime.utg)

    def _build_transition(self, current_state, action, next_state, result):
        from smart_monkey.models import Transition

        return Transition(
            transition_id=action.action_id,
            from_state_id=current_state.state_id,
            to_state_id=next_state.state_id,
            action_id=action.action_id,
            success=result.success,
            changed=current_state.state_id != next_state.state_id,
            crash=False,
            anr=False,
            out_of_app=next_state.package_name != self.config.app.package_name,
            duration_ms=0,
            timestamp_ms=next_state.timestamp_ms,
        )
