from __future__ import annotations

from pathlib import Path
from typing import Any

from smart_monkey.services.recovery_audit_service import RecoveryAuditService


class OrchestrationService:
    def __init__(
        self,
        config: Any,
        runtime_hooks: Any,
        watchdog_service: Any,
        recovery_audit_service: RecoveryAuditService,
        login_bootstrap_service: Any | None = None,
    ) -> None:
        self.config = config
        self.runtime_hooks = runtime_hooks
        self.watchdog_service = watchdog_service
        self.recovery_audit_service = recovery_audit_service
        self.login_bootstrap_service = login_bootstrap_service

    def before_step(self, step: int, state: Any, driver: Any, recorder: Any) -> Any | None:
        if self.login_bootstrap_service is None:
            return None
        attempt = self.login_bootstrap_service.maybe_bootstrap(step=step, state=state, driver=driver)
        if attempt.status != "attempted":
            return attempt
        recorder.record_step(
            {
                "step": -1,
                "bootstrap_at_step": attempt.step,
                "bootstrap_status": attempt.status,
                "bootstrap_reason": attempt.reason,
            }
        )
        return attempt

    def after_transition(
        self,
        step: int,
        driver: Any,
        recorder: Any,
        previous_state: Any,
        current_state: Any,
        next_state: Any,
        action: Any,
        transition: Any,
    ) -> list[Path]:
        self.runtime_hooks.on_step_persist(step, driver, recorder, current_state, next_state, action, transition)
        return self.watchdog_service.handle(
            driver=driver,
            previous_state=previous_state,
            current_state=current_state,
            action=action,
            transition=transition,
            next_state=next_state,
        )

    def record_recovery(
        self,
        recorder: Any,
        at_step: int,
        before_stuck_score: int,
        after_stuck_score: int,
        recovery_result: Any,
    ) -> None:
        self.recovery_audit_service.record(
            recorder=recorder,
            at_step=at_step,
            before_stuck_score=before_stuck_score,
            after_stuck_score=after_stuck_score,
            recovery_result=recovery_result,
        )

    def finish_run(self, recorder: Any, utg: Any) -> dict[str, str]:
        return self.runtime_hooks.on_run_finish(recorder, utg)
