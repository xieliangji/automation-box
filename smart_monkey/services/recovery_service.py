from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smart_monkey.graph.backtrack import BacktrackHelper
from smart_monkey.graph.checkpoint import CheckpointManager
from smart_monkey.graph.navigation_recovery import NavigationRecovery, RecoveryPlan
from smart_monkey.graph.recovery_validator import RecoveryValidationResult, RecoveryValidator
from smart_monkey.models import DeviceState


@dataclass(slots=True)
class RecoveryExecutionResult:
    plan: RecoveryPlan
    validation: RecoveryValidationResult | None
    checkpoint_activity: str | None


class RecoveryService:
    def __init__(
        self,
        output_dir: str | Path,
        package_name: str,
        launch_activity: str | None,
        checkpoint_manager: CheckpointManager,
        backtrack_helper: BacktrackHelper,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.package_name = package_name
        self.launch_activity = launch_activity
        self.checkpoint_manager = checkpoint_manager
        self.backtrack_helper = backtrack_helper
        self.navigation_recovery = NavigationRecovery(self.output_dir)
        self.recovery_validator = RecoveryValidator(self.output_dir, target_package=package_name)

    def recover(
        self,
        current_state_id: str,
        stuck_score: int,
        out_of_app: bool,
        driver: Any,
        capture_state_fn,
        avoid_login_checkpoint: bool = True,
    ) -> RecoveryExecutionResult:
        decision = self.backtrack_helper.choose(
            current_state_id=current_state_id,
            stuck_score=stuck_score,
            out_of_app=out_of_app,
            avoid_login_checkpoint=avoid_login_checkpoint,
        )
        plan = self.navigation_recovery.build_plan(decision, max_actions=4)
        checkpoint_activity = None
        if decision.checkpoint is not None:
            checkpoint_activity = decision.checkpoint.metadata.get("activity_name")
        self.navigation_recovery.execute_plan(
            plan=plan,
            driver=driver,
            package_name=self.package_name,
            activity_name=checkpoint_activity or self.launch_activity,
        )

        validation: RecoveryValidationResult | None = None
        if capture_state_fn is not None:
            state: DeviceState = capture_state_fn()
            validation = self.recovery_validator.validate(
                actual_state=state,
                expected_anchor_state=plan.anchor_state_id,
                candidate_state_ids=plan.candidate_state_ids,
                reason=plan.reason,
            )
        return RecoveryExecutionResult(
            plan=plan,
            validation=validation,
            checkpoint_activity=checkpoint_activity,
        )
