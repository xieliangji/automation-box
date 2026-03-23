from __future__ import annotations

import time
from pathlib import Path

from smart_monkey.action.extractor_v2 import ActionExtractorV2
from smart_monkey.action.scorer_v2 import ActionScorerV2
from smart_monkey.app_watchdog import WatchdogSmartMonkeyApp
from smart_monkey.config_v2 import ProjectConfigV2
from smart_monkey.device.base import DeviceDriver
from smart_monkey.graph.backtrack import BacktrackHelper
from smart_monkey.graph.checkpoint import CheckpointManager
from smart_monkey.graph.navigation_recovery_v2 import NavigationRecoveryV2
from smart_monkey.models import Transition
from smart_monkey.report.html_report import HtmlReportGenerator
from smart_monkey.report.markdown_report import MarkdownReportGenerator
from smart_monkey.report.markdown_report_v2 import MarkdownReportGeneratorV2
from smart_monkey.report.recovery_metrics import RecoveryMetricsGenerator
from smart_monkey.storage.recorder_indexer import RecorderIndexer
from smart_monkey.storage.replay_exporter import ReplayExporter
from smart_monkey.storage.snapshotter import SnapshotConfig, Snapshotter


class SmartMonkeyAppV7(WatchdogSmartMonkeyApp):
    def __init__(self, driver: DeviceDriver, config: ProjectConfigV2, output_dir: str | Path = "output") -> None:
        super().__init__(driver=driver, config=config, output_dir=output_dir)
        self.v2_config = config
        if config.features.use_extractor_v2:
            self.extractor = ActionExtractorV2(config)
        if config.features.use_scorer_v2:
            self.scorer = ActionScorerV2(config)
        self.snapshotter = Snapshotter(
            self.output_dir,
            SnapshotConfig(
                every_n_steps=config.snapshot.every_n_steps,
                enabled=config.snapshot.enabled,
            ),
        )
        self.replay_exporter = ReplayExporter(self.output_dir) if config.features.export_replay else None
        self.recorder_indexer = RecorderIndexer(self.output_dir)
        self.html_report = HtmlReportGenerator(self.output_dir)
        self.markdown_report = MarkdownReportGenerator(self.output_dir)
        self.markdown_report_v2 = MarkdownReportGeneratorV2(self.output_dir)
        self.recovery_metrics = RecoveryMetricsGenerator(self.output_dir)
        self.checkpoint_manager = CheckpointManager(self.output_dir)
        self.backtrack_helper = BacktrackHelper(self.checkpoint_manager, self.output_dir)
        self.navigation_recovery = NavigationRecoveryV2(self.output_dir)
        self._recent_steps: list[dict] = []

    def run(self) -> None:
        if self.v2_config.features.enable_watchdog:
            self.watchdog.reset_logcat(self.driver)
        self._ensure_app_started()
        previous_state = None

        for step in range(self.config.run.max_steps):
            current_state = self.capture_state(step_no=step, suffix="before")
            visit_count = self._mark_visited(current_state.state_id)
            self.runtime.utg.add_state(
                current_state.state_id,
                {
                    "package_name": current_state.package_name,
                    "activity_name": current_state.activity_name,
                    "app_flags": sorted(current_state.app_flags),
                    "popup_flags": sorted(current_state.popup_flags),
                },
            )
            self.checkpoint_manager.consider(current_state, visit_count)

            actions = self.extractor.extract(current_state)
            scored_actions = self.scorer.score(current_state, actions, self.runtime.stats)
            action = self.select_action(scored_actions)
            started_at = time.time()
            result = self.execute_action(action)
            self.driver.wait_idle(self.config.run.post_action_wait_ms)
            next_state = self.capture_state(step_no=step, suffix="after")

            transition = Transition(
                transition_id=action.action_id,
                from_state_id=current_state.state_id,
                to_state_id=next_state.state_id,
                action_id=action.action_id,
                success=result.success,
                changed=current_state.state_id != next_state.state_id,
                crash=False,
                anr=False,
                out_of_app=next_state.package_name != self.config.app.package_name,
                duration_ms=int((time.time() - started_at) * 1000),
                timestamp_ms=next_state.timestamp_ms,
            )

            self.update_runtime(current_state, action, transition)
            self.persist_step(step, current_state, action, transition, next_state)
            self._append_replay(step, action, current_state.state_id)
            self._append_recent_step(step, current_state, action, transition, next_state)

            if self.v2_config.features.enable_watchdog:
                events = self.watchdog.inspect(
                    previous_state=previous_state or current_state,
                    action=action,
                    transition=transition,
                    next_state=next_state,
                    driver=self.driver,
                )
                if events:
                    issue_dirs = self.watchdog.record_events(
                        events=events,
                        previous_state=previous_state or current_state,
                        action=action,
                        transition=transition,
                        next_state=next_state,
                        driver=self.driver,
                    )
                    self._export_issue_replay(issue_dirs)

            if transition.out_of_app or self.should_escape(previous_state, current_state, next_state, transition):
                self._recover_with_navigation_v2(current_state.state_id, transition.out_of_app)

            previous_state = next_state

        self.recorder.record_utg(self.runtime.utg)
        self.recorder_indexer.build()
        self.html_report.generate()
        self.markdown_report.generate()
        self.markdown_report_v2.generate()
        self.recovery_metrics.generate()

    def persist_step(self, step, current_state, action, transition, next_state) -> None:
        screenshot_path = self.snapshotter.maybe_capture(step=step, driver=self.driver, label="periodic")
        super().persist_step(step, current_state, action, transition, next_state)
        if screenshot_path:
            self.recorder.record_step(
                {
                    "step": step,
                    "snapshot_path": screenshot_path,
                    "snapshot_type": "periodic",
                }
            )

    def _recover_with_navigation_v2(self, current_state_id: str, out_of_app: bool) -> None:
        decision = self.backtrack_helper.choose(
            current_state_id=current_state_id,
            stuck_score=self.runtime.stats.stuck_score,
            out_of_app=out_of_app,
        )
        plan = self.navigation_recovery.build_plan(decision, max_actions=4)
        self.recorder.record_step(
            {
                "step": -1,
                "recovery_strategy": decision.strategy,
                "recovery_reason": decision.reason,
                "checkpoint_id": decision.checkpoint.checkpoint_id if decision.checkpoint else None,
                "recovery_plan_actions": len(plan.actions),
                "recovery_anchor_state": plan.anchor_state_id,
            }
        )
        checkpoint_activity = None
        if decision.checkpoint is not None:
            checkpoint_activity = decision.checkpoint.metadata.get("activity_name")
        self.navigation_recovery.execute_plan(
            plan=plan,
            driver=self.driver,
            package_name=self.config.app.package_name,
            activity_name=checkpoint_activity or self.config.app.launch_activity,
        )
        self.runtime.stats.stuck_score = max(0, self.runtime.stats.stuck_score - 5)

    def _append_replay(self, step: int, action, state_id: str) -> None:
        if self.replay_exporter is not None:
            self.replay_exporter.append_action(step=step, action=action, state_id=state_id)

    def _append_recent_step(self, step, current_state, action, transition, next_state) -> None:
        payload = {
            "step": step,
            "current_state_id": current_state.state_id,
            "next_state_id": next_state.state_id,
            "action_type": action.action_type.value,
            "action_id": action.action_id,
            "changed": transition.changed,
            "duration_ms": transition.duration_ms,
            "out_of_app": transition.out_of_app,
        }
        self._recent_steps.append(payload)
        self._recent_steps = self._recent_steps[-30:]

    def _export_issue_replay(self, issue_dirs: list[Path]) -> None:
        if self.replay_exporter is None:
            return
        for issue_dir in issue_dirs:
            self.replay_exporter.export_issue_replay(issue_dir, self._recent_steps)

    def _mark_visited(self, state_id: str) -> int:
        count = self.runtime.stats.visited_states.get(state_id, 0) + 1
        self.runtime.stats.visited_states[state_id] = count
        return count
