from __future__ import annotations

import time
from pathlib import Path

from loguru import logger

from smart_monkey.action.extractor_runtime import RuntimeActionExtractor
from smart_monkey.action.scorer_runtime import RuntimeActionScorer
from smart_monkey.app_watchdog import WatchdogSmartMonkeyApp
from smart_monkey.runtime_config import RuntimeConfig
from smart_monkey.device.base import DeviceDriver
from smart_monkey.graph.backtrack import BacktrackHelper
from smart_monkey.graph.checkpoint import CheckpointManager
from smart_monkey.models import Transition
from smart_monkey.services.orchestration_service import OrchestrationService
from smart_monkey.services.login_bootstrap_service import LoginBootstrapService
from smart_monkey.services.recovery_audit_service import RecoveryAuditService
from smart_monkey.services.recovery_service import RecoveryExecutionResult, RecoveryService
from smart_monkey.services.report_service import ReportService
from smart_monkey.services.runtime_hooks import RuntimeHooks
from smart_monkey.services.telemetry_service import TelemetryService
from smart_monkey.services.watchdog_service import WatchdogService


class SmartMonkeyAppRuntime(WatchdogSmartMonkeyApp):
    """Single maintained runtime flow."""

    def __init__(self, driver: DeviceDriver, config: RuntimeConfig, output_dir: str | Path = "output") -> None:
        super().__init__(driver=driver, config=config, output_dir=output_dir)
        if config.features.use_runtime_extractor:
            self.extractor = RuntimeActionExtractor(config)
        if config.features.use_runtime_scorer:
            self.scorer = RuntimeActionScorer(config)

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
        baseline_dir = config.run.benchmark_baseline_dir.strip() if getattr(config.run, "benchmark_baseline_dir", "") else ""
        self.report_service = ReportService(self.output_dir, baseline_dir=baseline_dir or None)
        self.runtime_hooks = RuntimeHooks(
            config=config,
            checkpoint_manager=self.checkpoint_manager,
            telemetry_service=self.telemetry_service,
            report_service=self.report_service,
        )
        self.watchdog_service = WatchdogService(config=config, watchdog=self.watchdog, telemetry_service=self.telemetry_service)
        self.recovery_audit_service = RecoveryAuditService(self.output_dir)
        self.login_bootstrap_service = LoginBootstrapService(config=config)
        self.orchestration_service = OrchestrationService(
            config=config,
            runtime_hooks=self.runtime_hooks,
            watchdog_service=self.watchdog_service,
            recovery_audit_service=self.recovery_audit_service,
            login_bootstrap_service=self.login_bootstrap_service,
        )
        self._recovery_capture_no = 0

    def run(self) -> None:
        self.runtime_hooks.on_run_start(self.driver, self.watchdog)
        self._ensure_app_started()
        previous_state = None
        logger.info("runtime run started max_steps={}", self.config.run.max_steps)

        for step in range(self.config.run.max_steps):
            current_state = self.capture_state(step_no=step, suffix="before")
            visit_count = self._mark_visited(current_state.state_id)
            self.runtime_hooks.on_state_captured(current_state, visit_count, self.runtime.utg)
            if current_state.package_name != self.config.app.package_name:
                logger.warning(
                    "step={} pre-action state out_of_app package={} expected={} triggering recovery",
                    step,
                    current_state.package_name,
                    self.config.app.package_name,
                )
                self._recover_runtime(step, current_state.state_id, True)
                previous_state = current_state
                continue
            bootstrap_attempt = self.orchestration_service.before_step(
                step=step,
                state=current_state,
                driver=self.driver,
                recorder=self.recorder,
            )
            if bootstrap_attempt is not None and bootstrap_attempt.status == "attempted":
                self.driver.wait_idle(self.config.run.post_action_wait_ms)
                current_state = self.capture_state(step_no=step, suffix="bootstrap")
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
            self.orchestration_service.after_transition(
                step=step,
                driver=self.driver,
                recorder=self.recorder,
                previous_state=previous_state,
                current_state=current_state,
                next_state=next_state,
                action=action,
                transition=transition,
            )

            if transition.out_of_app or self.should_escape(previous_state, current_state, next_state, transition):
                logger.warning(
                    "step={} recovery trigger out_of_app={} stuck_score={}",
                    step,
                    transition.out_of_app,
                    self.runtime.stats.stuck_score,
                )
                self._recover_runtime(step, current_state.state_id, transition.out_of_app)

            previous_state = next_state

        artifacts = self.orchestration_service.finish_run(self.recorder, self.runtime.utg)
        logger.info("runtime run finished artifacts={}", artifacts)

    def _recover_runtime(self, step: int, current_state_id: str, out_of_app: bool) -> None:
        self._recovery_capture_no += 1
        before_stuck_score = self.runtime.stats.stuck_score
        logger.warning(
            "recovery start step={} state={} out_of_app={} stuck_score={}",
            step,
            current_state_id,
            out_of_app,
            before_stuck_score,
        )
        recovery_result: RecoveryExecutionResult = self.recovery_service.recover(
            current_state_id=current_state_id,
            stuck_score=self.runtime.stats.stuck_score,
            out_of_app=out_of_app,
            driver=self.driver,
            capture_state_fn=lambda: self.capture_state(step_no=900000 + self._recovery_capture_no, suffix="recovery"),
            avoid_login_checkpoint=self.config.policy.prefer_functional_pages,
        )
        self.runtime.stats.stuck_score = max(0, self.runtime.stats.stuck_score - 5)
        self.orchestration_service.record_recovery(
            recorder=self.recorder,
            at_step=step,
            before_stuck_score=before_stuck_score,
            after_stuck_score=self.runtime.stats.stuck_score,
            recovery_result=recovery_result,
        )
        logger.warning(
            "recovery done step={} strategy={} in_target_app={} after_stuck_score={}",
            step,
            recovery_result.plan.strategy,
            recovery_result.validation.in_target_app if recovery_result.validation else None,
            self.runtime.stats.stuck_score,
        )

    def _mark_visited(self, state_id: str) -> int:
        count = self.runtime.stats.visited_states.get(state_id, 0) + 1
        self.runtime.stats.visited_states[state_id] = count
        return count
