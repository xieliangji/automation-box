from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smart_monkey.graph.backtrack import BacktrackDecision
from smart_monkey.graph.utg_path_planner import UtgPathPlanner
from smart_monkey.storage.replay_lookup import ReplayLookup


@dataclass(slots=True)
class RecoveryPlanV2:
    strategy: str
    checkpoint_id: str | None
    anchor_state_id: str | None
    candidate_state_ids: list[str]
    actions: list[dict[str, Any]]
    reason: str


class NavigationRecoveryV2:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.recovery_dir = self.output_dir / "recovery"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        self.path_planner = UtgPathPlanner(self.output_dir)
        self.replay_lookup = ReplayLookup(self.output_dir)

    def build_plan(self, decision: BacktrackDecision, max_actions: int = 4) -> RecoveryPlanV2:
        if decision.checkpoint is None or decision.strategy != "restart_to_checkpoint":
            return RecoveryPlanV2(
                strategy=decision.strategy,
                checkpoint_id=decision.checkpoint.checkpoint_id if decision.checkpoint else None,
                anchor_state_id=decision.checkpoint.state_id if decision.checkpoint else None,
                candidate_state_ids=[],
                actions=[],
                reason=decision.reason,
            )

        path = self.path_planner.plan_from_checkpoint(decision.checkpoint.state_id, max_depth=2, top_k=3)
        candidate_state_ids = path.candidate_state_ids or [decision.checkpoint.state_id]
        actions: list[dict[str, Any]] = []
        anchor_state_id = decision.checkpoint.state_id

        for state_id in candidate_state_ids:
            rows = self.replay_lookup.recent_from_state(state_id, tail=max_actions)
            filtered = self._filter_actions(rows)
            if filtered:
                anchor_state_id = state_id
                actions = filtered
                break

        if not actions:
            rows = self.replay_lookup.recent_from_state(decision.checkpoint.state_id, tail=max_actions)
            actions = self._filter_actions(rows)

        plan = RecoveryPlanV2(
            strategy=decision.strategy,
            checkpoint_id=decision.checkpoint.checkpoint_id,
            anchor_state_id=anchor_state_id,
            candidate_state_ids=candidate_state_ids,
            actions=actions,
            reason=f"{decision.reason}; {path.reason}",
        )
        self._write_plan(plan)
        return plan

    def execute_plan(self, plan: RecoveryPlanV2, driver: Any, package_name: str, activity_name: str | None) -> None:
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

    def _filter_actions(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for row in rows:
            action = row.get("action", {})
            if action.get("action_type") in {"click", "long_click", "input", "swipe", "back"}:
                selected.append(row)
        return selected

    def _write_plan(self, plan: RecoveryPlanV2) -> None:
        target = self.recovery_dir / f"plan_v2_{plan.checkpoint_id or 'generic'}.json"
        target.write_text(
            json.dumps(
                {
                    "strategy": plan.strategy,
                    "checkpoint_id": plan.checkpoint_id,
                    "anchor_state_id": plan.anchor_state_id,
                    "candidate_state_ids": plan.candidate_state_ids,
                    "reason": plan.reason,
                    "actions": plan.actions,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
