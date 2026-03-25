from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from smart_monkey.config import ProjectConfig
from smart_monkey.models import Action, ActionType, DeviceState, UIElement


@dataclass(slots=True)
class ActionExtractor:
    config: ProjectConfig

    def extract(self, state: DeviceState) -> list[Action]:
        actions: list[Action] = []

        for element in state.elements:
            actions.extend(self._actions_from_element(state, element))

        actions.append(self._build_system_action(ActionType.BACK, state.state_id))
        actions.append(self._build_system_action(ActionType.WAIT, state.state_id, {"duration_ms": 1000}))
        if self.config.policy.enable_restart_app:
            actions.append(self._build_system_action(ActionType.RESTART_APP, state.state_id))

        return self._deduplicate(actions)

    def _actions_from_element(self, state: DeviceState, element: UIElement) -> list[Action]:
        actions: list[Action] = []

        if not element.enabled:
            return actions

        if element.clickable:
            x, y = element.center
            actions.append(
                Action(
                    action_id=self._new_id(),
                    action_type=ActionType.CLICK,
                    target_element_id=element.element_id,
                    params={"x": x, "y": y},
                    source_state_id=state.state_id,
                    tags=element.semantic_tokens(),
                )
            )

        if self.config.policy.enable_long_click and element.long_clickable:
            x, y = element.center
            actions.append(
                Action(
                    action_id=self._new_id(),
                    action_type=ActionType.LONG_CLICK,
                    target_element_id=element.element_id,
                    params={"x": x, "y": y, "duration_ms": 800},
                    source_state_id=state.state_id,
                    tags=element.semantic_tokens(),
                )
            )

        if self.config.policy.enable_text_input and element.editable:
            x, y = element.center
            actions.append(
                Action(
                    action_id=self._new_id(),
                    action_type=ActionType.INPUT,
                    target_element_id=element.element_id,
                    params={"x": x, "y": y, "text": self._guess_input_text(element)},
                    source_state_id=state.state_id,
                    tags=element.semantic_tokens(),
                )
            )

        if element.scrollable:
            left, top, right, bottom = element.visible_bounds
            center_x = (left + right) // 2
            actions.append(
                Action(
                    action_id=self._new_id(),
                    action_type=ActionType.SWIPE,
                    target_element_id=element.element_id,
                    params={
                        "x1": center_x,
                        "y1": int(bottom * 0.8),
                        "x2": center_x,
                        "y2": int(top + (bottom - top) * 0.2),
                        "duration_ms": 300,
                        "direction": "up",
                    },
                    source_state_id=state.state_id,
                    tags=element.semantic_tokens() | {"scroll"},
                )
            )
            if self.config.policy.enable_pinch:
                width = max(1, right - left)
                height = max(1, bottom - top)
                center_y = (top + bottom) // 2
                # 在当前可滚动区域内生成双指手势。
                delta_x = max(20, min(width // 4, 240))
                delta_y = max(20, min(height // 4, 240))
                pinch_in_params = {
                    "x1_start": max(left + 5, center_x - delta_x),
                    "y1_start": max(top + 5, center_y - delta_y),
                    "x1_end": center_x,
                    "y1_end": center_y,
                    "x2_start": min(right - 5, center_x + delta_x),
                    "y2_start": min(bottom - 5, center_y + delta_y),
                    "x2_end": center_x,
                    "y2_end": center_y,
                    "duration_ms": 280,
                    "gesture": "pinch_in",
                }
                pinch_out_params = {
                    "x1_start": center_x,
                    "y1_start": center_y,
                    "x1_end": max(left + 5, center_x - delta_x),
                    "y1_end": max(top + 5, center_y - delta_y),
                    "x2_start": center_x,
                    "y2_start": center_y,
                    "x2_end": min(right - 5, center_x + delta_x),
                    "y2_end": min(bottom - 5, center_y + delta_y),
                    "duration_ms": 280,
                    "gesture": "pinch_out",
                }
                actions.append(
                    Action(
                        action_id=self._new_id(),
                        action_type=ActionType.PINCH_IN,
                        target_element_id=element.element_id,
                        params=pinch_in_params,
                        source_state_id=state.state_id,
                        tags=element.semantic_tokens() | {"zoom", "pinch_in"},
                    )
                )
                actions.append(
                    Action(
                        action_id=self._new_id(),
                        action_type=ActionType.PINCH_OUT,
                        target_element_id=element.element_id,
                        params=pinch_out_params,
                        source_state_id=state.state_id,
                        tags=element.semantic_tokens() | {"zoom", "pinch_out"},
                    )
                )

        return actions

    def _guess_input_text(self, element: UIElement) -> str:
        tokens = element.semantic_tokens()
        if {"phone", "mobile", "tel", "手机号"} & tokens:
            return "13800138000"
        if {"email", "邮箱"} & tokens:
            return "test@example.com"
        if {"password", "pwd", "密码"} & tokens:
            return "Aa123456!"
        if {"search", "搜索"} & tokens:
            return "test"
        return "tester"

    def _build_system_action(self, action_type: ActionType, source_state_id: str, params: dict | None = None) -> Action:
        return Action(
            action_id=self._new_id(),
            action_type=action_type,
            target_element_id=None,
            params=params or {},
            source_state_id=source_state_id,
            tags={action_type.value},
        )

    def _deduplicate(self, actions: list[Action]) -> list[Action]:
        unique: dict[tuple, Action] = {}
        for action in actions:
            key = (
                action.action_type.value,
                action.target_element_id,
                tuple(sorted(action.params.items())),
            )
            unique[key] = action
        return list(unique.values())

    @staticmethod
    def _new_id() -> str:
        return uuid4().hex[:16]
