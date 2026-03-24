from __future__ import annotations

from pathlib import Path

from smart_monkey.app_orchestrated_v2 import SmartMonkeyAppOrchestratedV2
from smart_monkey.config_v2 import ProjectConfigV2
from smart_monkey.device.base import DeviceDriver
from smart_monkey.services.recovery_audit_service import RecoveryAuditService
from smart_monkey.services.recovery_service import RecoveryExecutionResult


class SmartMonkeyAppRecommended(SmartMonkeyAppOrchestratedV2):
    """Current recommended orchestration-based app entry.

    This class keeps the orchestrated-v2 service layout while adding
    structured recovery audit logging, so downstream analysis can compare
    recovery attempts against stuck-score changes and validation outcomes.
    """

    def __init__(self, driver: DeviceDriver, config: ProjectConfigV2, output_dir: str | Path = "output") -> None:
        super().__init__(driver=driver, config=config, output_dir=output_dir)
        self.recovery_audit_service = RecoveryAuditService(self.output_dir)

    def _recover_orchestrated(self, step: int, current_state_id: str, out_of_app: bool) -> None:
        self._recovery_capture_no += 1
        before_stuck_score = self.runtime.stats.stuck_score
        recovery_result: RecoveryExecutionResult = self.recovery_service.recover(
            current_state_id=current_state_id,
            stuck_score=self.runtime.stats.stuck_score,
            out_of_app=out_of_app,
            driver=self.driver,
            capture_state_fn=lambda: self.capture_state(step_no=900000 + self._recovery_capture_no, suffix="recovery"),
        )
        self.runtime.stats.stuck_score = max(0, self.runtime.stats.stuck_score - 5)
        self.recovery_audit_service.record(
            recorder=self.recorder,
            at_step=step,
            before_stuck_score=before_stuck_score,
            after_stuck_score=self.runtime.stats.stuck_score,
            recovery_result=recovery_result,
        )
