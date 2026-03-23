from __future__ import annotations

from dataclasses import dataclass

from smart_monkey.action.scorer import ActionScorer
from smart_monkey.config import ProjectConfig
from smart_monkey.models import Action, ActionHistory, DeviceState, RunStats


@dataclass(slots=True)
class ActionScorerV2(ActionScorer):
    config: ProjectConfig

    def _score_one(self, state: DeviceState, action: Action, stats: RunStats) -> dict[str, float]:
        detail = super()._score_one(state, action, stats)
        action_key = self._action_key(state.state_id, action)
        history = stats.action_histories.get(action_key, ActionHistory())

        detail["transition"] = self._decayed_transition_gain(history)
        detail["repeat_penalty"] = max(detail["repeat_penalty"], self._short_loop_penalty(stats, state.state_id, action_key))
        detail["stuck_penalty"] = max(detail["stuck_penalty"], self._history_stuck_penalty(history))
        detail["depth"] = min(1.5, detail["depth"] + self._list_depth_bonus(action, state))
        return detail

    @staticmethod
    def _decayed_transition_gain(history: ActionHistory) -> float:
        if history.execute_count == 0:
            return 1.0
        base = (history.new_state_count + 1) / (history.execute_count + 2)
        decay = max(0.4, 1.0 - history.execute_count * 0.05)
        return base * decay

    @staticmethod
    def _short_loop_penalty(stats: RunStats, state_id: str, action_key: str) -> float:
        recent_states = stats.recent_state_ids[-6:]
        recent_actions = stats.recent_action_keys[-6:]
        penalty = 0.0
        if len(recent_states) >= 4 and recent_states[-4:] in ([state_id, recent_states[-3], state_id, recent_states[-1]],):
            penalty = max(penalty, 1.0)
        if recent_actions.count(action_key) >= 3:
            penalty = max(penalty, 1.0)
        return penalty

    @staticmethod
    def _history_stuck_penalty(history: ActionHistory) -> float:
        if history.unchanged_count >= 5:
            return 1.2
        if history.unchanged_count >= 3:
            return 0.8
        return 0.0

    @staticmethod
    def _list_depth_bonus(action: Action, state: DeviceState) -> float:
        tags = {tag.lower() for tag in action.tags}
        if "list_page" in state.app_flags and action.action_type.value == "click":
            return 0.5
        if {"detail", "详情", "next", "下一步", "item"} & tags:
            return 0.3
        return 0.0
