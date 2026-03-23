from __future__ import annotations

from pathlib import Path

from smart_monkey.app_v7 import SmartMonkeyAppV7
from smart_monkey.config_v2 import ProjectConfigV2
from smart_monkey.device.base import DeviceDriver
from smart_monkey.graph.navigation_recovery_v2 import RecoveryPlanV2
from smart_monkey.graph.recovery_validator import RecoveryValidator
from smart_monkey.report.html_report_v3 import HtmlReportGeneratorV3


class SmartMonkeyAppV8(SmartMonkeyAppV7):
    def __init__(self, driver: DeviceDriver, config: ProjectConfigV2, output_dir: str | Path = "output") -> None:
        super().__init__(driver=driver, config=config, output_dir=output_dir)
        self.recovery_validator = RecoveryValidator(self.output_dir, target_package=self.config.app.package_name)
        self.html_report_v3 = HtmlReportGeneratorV3(self.output_dir)
        self._recovery_capture_no = 0

    def run(self) -> None:
        super().run()
        self.html_report_v3.generate()

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
        self._validate_recovery(plan)

    def _validate_recovery(self, plan: RecoveryPlanV2) -> None:
        self._recovery_capture_no += 1
        state = self.capture_state(step_no=900000 + self._recovery_capture_no, suffix="recovery")
        result = self.recovery_validator.validate(
            actual_state=state,
            expected_anchor_state=plan.anchor_state_id,
            candidate_state_ids=plan.candidate_state_ids,
            reason=plan.reason,
        )
        self.recorder.record_step(
            {
                "step": -1,
                "recovery_validation_actual_state": result.actual_state_id,
                "recovery_validation_exact_anchor_hit": result.exact_anchor_hit,
                "recovery_validation_candidate_hit": result.candidate_hit,
                "recovery_validation_in_target_app": result.in_target_app,
            }
        )
