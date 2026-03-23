from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smart_monkey.graph.backtrack import BacktrackDecision
from smart_monkey.graph.checkpoint import Checkpoint


@dataclass(slots=True)
class RecoveryPlan:
    strategy: str
    checkpoint_id: str | None
    actions: list[dict[str, Any]]
    reason: str


class NavigationRecovery:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.replay_file = self.output_dir / "replay" / "actions_replay.jsonl"
        self.recovery_dir = self.output_dir / "recovery"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)

    def build_plan(self, decision: BacktrackDecision, max_actions: int = 3) -> RecoveryPlan:
        if decision.checkpoint is None or decision.strategy != "restart_to_checkpoint":
            return RecoveryPlan(
                strategy=decision.strategy,
                checkpoint_id=decision.checkpoint.checkpoint_id if decision.checkpoint else None,
                actions=[],
                reason=decision.reason,
            )

        replay_rows = self._read_jsonl(self.replay_file)
        actions = self._extract_following_actions(replay_rows, decision.checkpoint, max_actions=max_actions)
        plan = RecoveryPlan(
            strategy=decision.strategy,
            checkpoint_id=decision.checkpoint.checkpoint_id,
            actions=actions,
            reason=decision.reason,
        )
        self._write_plan(plan)
        return plan

    def execute_plan(self, plan: RecoveryPlan, driver: Any, package_name: str, activity_name: str | None) -> None:
        driver.stop_app(package_name)
        driver.wait_idle(500)
        driver.start_app(package_name, activity_name)
        driver.wait_idle(1500)

        for item in plan.actions:
            action = item.get("action", {})
            action_type = action.get("action_type")
            params = action.get("params", {})
            if action_type == "click":
                driver.click(params.get("x", 0), params.get("y", 0))
            elif action_type == "long_click":
                driver.long_click(params.get("x", 0), params.get("y", 0), params.get("duration_ms", 800))
            elif action_type == "input":
                driver.click(params.get("x", 0), params.get("y", 0))
                driver.input_text(params.get("text", "tester"))
            elif action_type == "swipe":
                driver.swipe(
                    params.get("x1", 0),
                    params.get("y1", 0),
                    params.get("x2", 0),
                    params.get("y2", 0),
                    params.get("duration_ms", 300),
                )
            elif action_type == "back":
                driver.press_back()
            else:
                continue
            driver.wait_idle(800)

    def _extract_following_actions(
        self,
        replay_rows: list[dict[str, Any]],
        checkpoint: Checkpoint,
        max_actions: int,
    ) -> list[dict[str, Any]]:
        matched_index = -1
        for index in range(len(replay_rows) - 1, -1, -1):
            if replay_rows[index].get("state_id") == checkpoint.state_id:
                matched_index = index
                break
        if matched_index < 0:
            return []

        selected: list[dict[str, Any]] = []
        for row in replay_rows[matched_index : matched_index + max_actions]:
            action = row.get("action", {})
            if action.get("action_type") in {"click", "long_click", "input", "swipe", "back"}:
                selected.append(row)
        return selected

    def _write_plan(self, plan: RecoveryPlan) -> None:
        target = self.recovery_dir / f"plan_{plan.checkpoint_id or 'generic'}.json"
        target.write_text(json.dumps({
            "strategy": plan.strategy,
            "checkpoint_id": plan.checkpoint_id,
            "reason": plan.reason,
            "actions": plan.actions,
        }, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows
