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
        detail["business"] = min(1.8, detail["business"] + self._pinch_context_bonus(action, state))
        detail["repeat_penalty"] = max(detail["repeat_penalty"], self._functional_page_penalty(action, state))
        detail["repeat_penalty"] = max(detail["repeat_penalty"], self._pinch_context_penalty(action, state))
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

    def _pinch_context_bonus(self, action: Action, state: DeviceState) -> float:
        if action.action_type.value not in {"pinch_in", "pinch_out"}:
            return 0.0
        if self._looks_like_zoom_context(state, action):
            boost = float(getattr(self.config.policy, "pinch_zoom_context_boost", 0.45))
            return max(0.0, min(1.0, boost))
        return 0.0

    def _pinch_context_penalty(self, action: Action, state: DeviceState) -> float:
        if action.action_type.value not in {"pinch_in", "pinch_out"}:
            return 0.0
        if self._looks_like_zoom_context(state, action):
            return 0.0
        penalty = float(getattr(self.config.policy, "pinch_non_zoom_penalty", 0.6))
        return max(0.0, min(2.0, penalty))

    @staticmethod
    def _looks_like_zoom_context(state: DeviceState, action: Action) -> bool:
        flags = {str(flag).lower() for flag in state.app_flags}
        if "webview" in flags:
            return True
        activity = str(state.activity_name or "").lower()
        activity_keywords = (
            "map",
            "image",
            "photo",
            "preview",
            "camera",
            "gallery",
            "album",
            "viewer",
            "pdf",
            "canvas",
            "chart",
            "webview",
        )
        if any(keyword in activity for keyword in activity_keywords):
            return True
        tokens = set()
        for element in state.elements:
            tokens.update(str(token).lower() for token in element.semantic_tokens())
        synthetic_gesture_tokens = {"zoom", "pinch", "pinch_in", "pinch_out", "scroll", "swipe", "gesture"}
        tokens.update(
            str(tag).lower()
            for tag in action.tags
            if str(tag).lower() not in synthetic_gesture_tokens
        )
        zoom_keywords = {
            "map",
            "地图",
            "image",
            "图片",
            "photo",
            "照片",
            "preview",
            "预览",
            "camera",
            "相机",
            "canvas",
            "画布",
            "chart",
            "图表",
            "graph",
            "pdf",
            "doc",
            "document",
            "viewer",
            "album",
            "gallery",
            "thumbnail",
            "zoom",
            "pinch",
        }
        return bool(tokens & zoom_keywords)
