from __future__ import annotations

from pathlib import Path
from typing import Any

from smart_monkey.services.recovery_service import RecoveryExecutionResult


class RecoveryAuditService:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)

    def record(
        self,
        recorder: Any,
        at_step: int,
        before_stuck_score: int,
        after_stuck_score: int,
        recovery_result: RecoveryExecutionResult,
    ) -> None:
        recorder.record_step(
            {
                "step": -1,
                "recovery_at_step": at_step,
                "recovery_strategy": recovery_result.plan.strategy,
                "recovery_reason": recovery_result.plan.reason,
                "checkpoint_id": recovery_result.plan.checkpoint_id,
                "recovery_plan_actions": len(recovery_result.plan.actions),
                "recovery_anchor_state": recovery_result.plan.anchor_state_id,
                "recovery_candidate_state_ids": recovery_result.plan.candidate_state_ids,
                "recovery_before_stuck_score": before_stuck_score,
                "recovery_after_stuck_score": after_stuck_score,
                "recovery_validation_exact_anchor_hit": recovery_result.validation.exact_anchor_hit if recovery_result.validation else None,
                "recovery_validation_candidate_hit": recovery_result.validation.candidate_hit if recovery_result.validation else None,
                "recovery_validation_in_target_app": recovery_result.validation.in_target_app if recovery_result.validation else None,
            }
        )
