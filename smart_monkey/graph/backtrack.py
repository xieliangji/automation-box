from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smart_monkey.graph.checkpoint import Checkpoint, CheckpointManager


@dataclass(slots=True)
class BacktrackDecision:
    strategy: str
    checkpoint: Checkpoint | None = None
    reason: str = ""


class BacktrackHelper:
    def __init__(self, checkpoint_manager: CheckpointManager, output_dir: str | Path) -> None:
        self.checkpoint_manager = checkpoint_manager
        self.output_dir = Path(output_dir)

    def choose(
        self,
        current_state_id: str,
        stuck_score: int,
        out_of_app: bool,
        avoid_login_checkpoint: bool = False,
    ) -> BacktrackDecision:
        if out_of_app:
            return BacktrackDecision(strategy="restart_app", reason="应用已经跳出目标包")
        if stuck_score < 8:
            return BacktrackDecision(strategy="press_back", reason="轻度卡住，先尝试返回")
        checkpoint = self.checkpoint_manager.best_checkpoint(
            exclude_state_id=current_state_id,
            include_login=not avoid_login_checkpoint,
        )
        if checkpoint is None and avoid_login_checkpoint:
            checkpoint = self.checkpoint_manager.best_checkpoint(
                exclude_state_id=current_state_id,
                include_login=True,
            )
        if checkpoint is not None:
            return BacktrackDecision(strategy="restart_to_checkpoint", checkpoint=checkpoint, reason="使用最近稳定检查点恢复")
        return BacktrackDecision(strategy="restart_app", reason="没有可用检查点，执行应用重启")

    def execute(self, decision: BacktrackDecision, driver: Any, package_name: str, activity_name: str | None) -> None:
        if decision.strategy == "press_back":
            driver.press_back()
            driver.wait_idle(800)
            return
        self._ensure_target_foreground(
            driver=driver,
            package_name=package_name,
            activity_name=activity_name,
            context=f"backtrack:{decision.strategy}",
        )

    @staticmethod
    def _ensure_target_foreground(
        driver: Any,
        package_name: str,
        activity_name: str | None,
        context: str,
        max_attempts: int = 3,
    ) -> None:
        for attempt in range(1, max_attempts + 1):
            current = driver.get_foreground_package()
            if current == package_name:
                return
            if attempt > 1:
                driver.stop_app(package_name)
                driver.wait_idle(500)
            launch_activity = activity_name if attempt == 1 and activity_name else None
            driver.start_app(package_name, launch_activity)
            driver.wait_idle(1500)

        current = driver.get_foreground_package() or "<unknown>"
        raise RuntimeError(
            f"{context}: unable to foreground target app '{package_name}' "
            f"after {max_attempts} attempts (current package: {current})."
        )
