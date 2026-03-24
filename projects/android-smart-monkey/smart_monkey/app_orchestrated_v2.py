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
from smart_monkey.models import Transition
from smart_monkey.services.recovery_service import RecoveryExecutionResult, RecoveryService
from smart_monkey.services.report_service import ReportService
from smart_monkey.services.runtime_hooks import RuntimeHooks
from smart_monkey.services.telemetry_service import TelemetryService
from smart_monkey.services.watchdog_service import WatchdogService


class SmartMonkeyAppOrchestratedV2(WatchdogSmartMonkeyApp):
    def __init__(self, driver: DeviceDriver, config: ProjectConfigV2, output_dir: str | Path = "output") -> None:
        super().__init__(driver=driver, config=config, output_dir=output_dir)
        self.v2_config = config
        if config.features.use_extractor_v2:
            self.extractor = ActionExtractorV2(config)
        if config.features.use_scorer_v2:
            self.scorer = ActionScorerV2(config)

        self.checkpoint_manager = CheckpointManager(self.output_dir)
        self.backtrack_helper = BacktrackHelper(self.checkpoint_manager, self.output_dir)
        self.telemetry_service = TelemetryService(
            output_dir=self.output_dir,
            snapshot_every_n_steps=config.snapshot.every_n_steps,
            snapshot_enabled=config.snapshot.enabled,
            export_replay=config.features.export_replay,
        )
        self.recovery_service = RecoveryService(
            output_dir=self.output_dir,
            package_name=self.config.app.package_name,
            launch_activity=self.config.app.launch_activity,
            checkpoint_manager=self.checkpoint_manager,
            backtrack_helper=self.backtrack_helper,
        )
        self.report_service = ReportService(self.output_dir)
        self.runtime_hooks = RuntimeHooks(
            config=config,
            checkpoint_manager=self.checkpoint_manager,
            telemetry_service=self.telemetry_service,
            report_service=self.report_service,
        )
        self.watchdog_service = WatchdogService(config=config, watchdog=self.watchdog, telemetry_service=self.telemetry_service)
        self._recovery_capture_no = 0

    def run(self) -> None:
        self.runtime_hooks.on_run_start(self.driver, self.watchdog)
        self._ensure_app_started()
        previous_state = None

        for step in range(self.config.run.max_steps):
            current_state = self.capture_state(step_no=step, suffix="before")
            visit_count = self._mark_visited(current_state.state_id)
            self.runtime_hooks.on_state_captured(current_state, visit_count, self.runtime.utg)

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
            super().persist_step(step, current_state, action, transition, next_state)
            self.runtime_hooks.on_step_persist(step, self.driver, self.recorder, current_state, next_state, action, transition)

            self.watchdog_service.handle(
                driver=self.driver,
                previous_state=previous_state,
                current_state=current_state,
                action=action,
                transition=transition,
                next_state=next_state,
            )

            if transition.out_of_app or self.should_escape(previous_state, current_state, next_state, transition):
                self._recover_orchestrated(step, current_state.state_id, transition.out_of_app)

            previous_state = next_state

        self.runtime_hooks.on_run_finish(self.recorder, self.runtime.utg)

    def _recover_orchestrated(self, step: int, current_state_id: str, out_of_app: bool) -> None:
        self._recovery_capture_no += 1
        recovery_result: RecoveryExecutionResult = self.recovery_service.recover(
            current_state_id=current_state_id,
            stuck_score=self.runtime.stats.stuck_score,
            out_of_app=out_of_app,
            driver=self.driver,
            capture_state_fn=lambda: self.capture_state(step_no=900000 + self._recovery_capture_no, suffix="recovery"),
        )
        self.recorder.record_step(
            {
                "step": -1,
                "recovery_at_step": step,
                "recovery_strategy": recovery_result.plan.strategy,
                "recovery_reason": recovery_result.plan.reason,
                "checkpoint_id": recovery_result.plan.checkpoint_id,
                "recovery_plan_actions": len(recovery_result.plan.actions),
                "recovery_anchor_state": recovery_result.plan.anchor_state_id,
                "recovery_candidate_state_ids": recovery_result.plan.candidate_state_ids,
                "recovery_validation_exact_anchor_hit": recovery_result.validation.exact_anchor_hit if recovery_result.validation else None,
                "recovery_validation_candidate_hit": recovery_result.validation.candidate_hit if recovery_result.validation else None,
                "recovery_validation_in_target_app": recovery_result.validation.in_target_app if recovery_result.validation else None,
            }
        )
        self.runtime.stats.stuck_score = max(0, self.runtime.stats.stuck_score - 5)

    def _mark_visited(self, state_id: str) -> int:
        count = self.runtime.stats.visited_states.get(state_id, 0) + 1
        self.runtime.stats.visited_states[state_id] = count
        return count
