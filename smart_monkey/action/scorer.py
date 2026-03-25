from __future__ import annotations

from dataclasses import dataclass

from smart_monkey.config import ProjectConfig
from smart_monkey.models import Action, ActionHistory, DeviceState, RunStats


@dataclass(slots=True)
class ActionScorer:
    config: ProjectConfig

    def score(self, state: DeviceState, actions: list[Action], stats: RunStats) -> list[Action]:
        for action in actions:
            detail = self._score_one(state, action, stats)
            action.score_detail = detail
            action.score = (
                self.config.score_weights.novelty * detail["novelty"]
                + self.config.score_weights.transition * detail["transition"]
                + self.config.score_weights.depth * detail["depth"]
                + self.config.score_weights.business * detail["business"]
                + self.config.score_weights.escape * detail["escape"]
                + self.config.score_weights.input * detail["input"]
                - self.config.score_weights.repeat * detail["repeat_penalty"]
                - self.config.score_weights.risk * detail["risk_penalty"]
                - self.config.score_weights.stuck * detail["stuck_penalty"]
            )
        return sorted(actions, key=lambda item: item.score, reverse=True)

    def _score_one(self, state: DeviceState, action: Action, stats: RunStats) -> dict[str, float]:
        action_key = self._action_key(state.state_id, action)
        history = stats.action_histories.get(action_key, ActionHistory())

        novelty = 1.0 if history.execute_count == 0 else max(0.1, 1.0 - history.execute_count * 0.2)
        transition = (history.new_state_count + 1) / (history.execute_count + 2)
        depth = self._depth_value(action)
        business = self._business_value(action)
        escape = (
            1.0
            if stats.stuck_score >= 6 and action.action_type.value in {"back", "restart_app", "swipe", "pinch_in", "pinch_out"}
            else 0.0
        )
        input_value = 1.0 if action.action_type.value == "input" else 0.0
        repeat_penalty = 1.0 if action_key in stats.recent_action_keys[-3:] else 0.0
        risk_penalty = self._risk_value(action)
        stuck_penalty = 1.0 if history.unchanged_count >= 3 else 0.0

        return {
            "novelty": novelty,
            "transition": transition,
            "depth": depth,
            "business": business,
            "escape": escape,
            "input": input_value,
            "repeat_penalty": repeat_penalty,
            "risk_penalty": risk_penalty,
            "stuck_penalty": stuck_penalty,
        }

    def _business_value(self, action: Action) -> float:
        tags = {tag.lower() for tag in action.tags}
        value = 0.0
        whitelist = {item.lower() for item in self.config.safety.whitelist_keywords}
        if tags & whitelist:
            value += 1.0
        if {"detail", "details", "详情", "config", "配置", "next", "下一步"} & tags:
            value += 0.6
        return min(value, 1.5)

    def _risk_value(self, action: Action) -> float:
        tags = {tag.lower() for tag in action.tags}
        blacklist = {item.lower() for item in self.config.safety.blacklist_keywords}
        return 1.0 if tags & blacklist else 0.0

    @staticmethod
    def _depth_value(action: Action) -> float:
        tags = {tag.lower() for tag in action.tags}
        if {"详情", "detail", "next", "下一步", "高级", "advanced", "add", "添加"} & tags:
            return 1.0
        if action.action_type.value == "click":
            return 0.6
        if action.action_type.value == "swipe":
            return 0.5
        if action.action_type.value in {"pinch_in", "pinch_out"}:
            return 0.5
        return 0.1

    @staticmethod
    def _action_key(state_id: str, action: Action) -> str:
        params = ",".join(f"{key}={value}" for key, value in sorted(action.params.items()))
        return f"{state_id}|{action.action_type.value}|{action.target_element_id}|{params}"
