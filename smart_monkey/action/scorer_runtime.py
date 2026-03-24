from __future__ import annotations

from dataclasses import dataclass

from smart_monkey.action.scorer import ActionScorer
from smart_monkey.config import ProjectConfig
from smart_monkey.models import Action, ActionHistory, DeviceState, RunStats


@dataclass
class RuntimeActionScorer(ActionScorer):
    config: ProjectConfig

    def _score_one(self, state: DeviceState, action: Action, stats: RunStats) -> dict[str, float]:
        detail = super()._score_one(state, action, stats)
        action_key = self._action_key(state.state_id, action)
        history = stats.action_histories.get(action_key, ActionHistory())

        detail["transition"] = self._decayed_transition_gain(history)
        detail["repeat_penalty"] = max(detail["repeat_penalty"], self._short_loop_penalty(stats, state.state_id, action_key))
        detail["stuck_penalty"] = max(detail["stuck_penalty"], self._history_stuck_penalty(history))
        detail["depth"] = min(1.5, detail["depth"] + self._list_depth_bonus(action, state))
        detail["business"] = min(1.8, detail["business"] + self._functional_page_bonus(action, state))
        detail["repeat_penalty"] = max(detail["repeat_penalty"], self._functional_page_penalty(action, state))
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

    def _functional_page_bonus(self, action: Action, state: DeviceState) -> float:
        if not self.config.policy.prefer_functional_pages:
            return 0.0
        flags = {flag.lower() for flag in state.app_flags}
        if "login_page" in flags:
            return 0.0
        tags = {tag.lower() for tag in action.tags}
        if {"list_page", "form_page", "webview"} & flags:
            return 0.35
        if {"detail", "details", "详情", "config", "配置", "add", "添加"} & tags:
            return 0.25
        return 0.0

    def _functional_page_penalty(self, action: Action, state: DeviceState) -> float:
        if not self.config.policy.prefer_functional_pages:
            return 0.0
        flags = {flag.lower() for flag in state.app_flags}
        if "login_page" not in flags:
            return 0.0
        tags = {tag.lower() for tag in action.tags}
        auth_like = {"login", "登录", "register", "注册", "password", "密码", "account", "账号"}
        if tags & auth_like:
            return 0.0
        if action.action_type.value in {"wait", "restart_app", "back"}:
            return 1.0
        return 0.6
