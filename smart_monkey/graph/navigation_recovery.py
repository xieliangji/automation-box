from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from smart_monkey.graph.backtrack import BacktrackDecision
from smart_monkey.graph.utg_path_planner import UtgPathPlanner
from smart_monkey.storage.replay_lookup import ReplayLookup


@dataclass(slots=True)
class RecoveryPlan:
    strategy: str
    checkpoint_id: str | None
    anchor_state_id: str | None
    candidate_state_ids: list[str]
    actions: list[dict[str, Any]]
    reason: str


class NavigationRecovery:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.recovery_dir = self.output_dir / "recovery"
        self.recovery_dir.mkdir(parents=True, exist_ok=True)
        self.path_planner = UtgPathPlanner(self.output_dir)
        self.replay_lookup = ReplayLookup(self.output_dir)

    def build_plan(self, decision: BacktrackDecision, max_actions: int = 4) -> RecoveryPlan:
        if decision.checkpoint is None or decision.strategy != "restart_to_checkpoint":
            return RecoveryPlan(
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

        plan = RecoveryPlan(
            strategy=decision.strategy,
            checkpoint_id=decision.checkpoint.checkpoint_id,
            anchor_state_id=anchor_state_id,
            candidate_state_ids=candidate_state_ids,
            actions=actions,
            reason=f"{decision.reason}; {path.reason}",
        )
        self._write_plan(plan)
        return plan

    def execute_plan(self, plan: RecoveryPlan, driver: Any, package_name: str, activity_name: str | None) -> None:
        self._ensure_target_foreground(
            driver=driver,
            package_name=package_name,
            activity_name=activity_name,
            context=f"navigation_recovery:{plan.strategy}",
        )

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
            elif action_type in {"pinch_in", "pinch_out"}:
                driver.pinch(
                    params.get("x1_start", 0),
                    params.get("y1_start", 0),
                    params.get("x1_end", 0),
                    params.get("y1_end", 0),
                    params.get("x2_start", 0),
                    params.get("y2_start", 0),
                    params.get("x2_end", 0),
                    params.get("y2_end", 0),
                    params.get("duration_ms", 280),
                )
            elif action_type == "back":
                driver.press_back()
            else:
                continue
            driver.wait_idle(800)

    @staticmethod
    def _ensure_target_foreground(
        driver: Any,
        package_name: str,
        activity_name: str | None,
        context: str,
        max_attempts: int = 3,
    ) -> None:
        for attempt in range(1, max_attempts + 1):
            if driver.get_foreground_package() == package_name:
                return
            if attempt > 1:
                driver.stop_app(package_name)
                driver.wait_idle(500)
            launch_activity = activity_name if attempt == 1 and activity_name else None
            driver.start_app(package_name, launch_activity)
            driver.wait_idle(1500)

        current_package = driver.get_foreground_package() or "<unknown>"
        raise RuntimeError(
            f"{context}: failed to foreground target app '{package_name}' "
            f"after {max_attempts} attempts (current package: {current_package})."
        )

    def _filter_actions(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        selected: list[dict[str, Any]] = []
        for row in rows:
            action = row.get("action", {})
            if action.get("action_type") not in {"click", "long_click", "input", "swipe", "pinch_in", "pinch_out", "back"}:
                continue
            if self._is_login_regressive(action):
                continue
            selected.append(row)
        return selected

    @staticmethod
    def _is_login_regressive(action: dict[str, Any]) -> bool:
        joined = " ".join(
            [
                str(action.get("action_type") or "").lower(),
                str(action.get("target_element_id") or "").lower(),
                json.dumps(action.get("params", {}), ensure_ascii=False).lower(),
                " ".join(str(tag).lower() for tag in action.get("tags", []) if tag is not None),
            ]
        )
        patterns = (
            "logout",
            "log_out",
            "signout",
            "退出登录",
            "注销",
            "cancel_account",
            "delete_account",
            "btn_log_out",
            "ivback",
            "back_to_login",
        )
        return any(pattern in joined for pattern in patterns)

    def _write_plan(self, plan: RecoveryPlan) -> None:
        target = self.recovery_dir / f"plan_{plan.checkpoint_id or 'generic'}.json"
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
