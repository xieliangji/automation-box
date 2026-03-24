from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from smart_monkey.action.extractor import ActionExtractor
from smart_monkey.config import ProjectConfig
from smart_monkey.models import Action, ActionType, DeviceState, UIElement


@dataclass(slots=True)
class ActionExtractorV3(ActionExtractor):
    config: ProjectConfig

    def extract(self, state: DeviceState) -> list[Action]:
        selected_elements = self._select_interactive_elements(state)
        actions: list[Action] = []
        for element in selected_elements:
            actions.extend(self._actions_from_element(state, element))

        actions.append(self._build_system_action(ActionType.BACK, state.state_id))
        actions.append(self._build_system_action(ActionType.WAIT, state.state_id, {"duration_ms": 1000}))
        if self.config.policy.enable_restart_app:
            actions.append(self._build_system_action(ActionType.RESTART_APP, state.state_id))
        return self._deduplicate(actions)

    def _select_interactive_elements(self, state: DeviceState) -> list[UIElement]:
        candidates = [
            element
            for element in state.elements
            if element.enabled and (element.clickable or element.long_clickable or element.editable or element.scrollable)
        ]

        safe_candidates = [element for element in candidates if not self._is_high_risk(element)]
        if not safe_candidates:
            safe_candidates = candidates

        grouped: dict[str, list[UIElement]] = defaultdict(list)
        for element in safe_candidates:
            grouped[self._template_signature(element)].append(element)

        selected: list[UIElement] = []
        for group in grouped.values():
            ordered = sorted(group, key=lambda item: (item.depth, item.visible_bounds[1], item.visible_bounds[0]))
            if len(ordered) <= 3:
                selected.extend(ordered)
                continue
            selected.extend([ordered[0], ordered[len(ordered) // 2], ordered[-1]])

        selected = self._sample_list_items(selected)
        selected.sort(key=lambda item: (item.depth, item.visible_bounds[1], item.visible_bounds[0]))
        return selected

    def _sample_list_items(self, elements: list[UIElement]) -> list[UIElement]:
        if len(elements) <= 5:
            return elements

        ordered = sorted(elements, key=lambda item: (item.visible_bounds[1], item.visible_bounds[0]))
        picks = [ordered[0], ordered[1], ordered[len(ordered) // 2], ordered[-2], ordered[-1]]

        seen: set[str] = set()
        result: list[UIElement] = []
        for element in picks:
            if element.element_id in seen:
                continue
            seen.add(element.element_id)
            result.append(element)
        return result

    def _template_signature(self, element: UIElement) -> str:
        text = (element.text or "")[:12]
        resource_id = element.resource_id or ""
        return f"{element.class_name}|{resource_id}|{text}|{element.clickable}|{element.editable}|{element.scrollable}"

    def _is_high_risk(self, element: UIElement) -> bool:
        tokens = {token.lower() for token in element.semantic_tokens()}
        blacklist = {item.lower() for item in self.config.safety.blacklist_keywords}
        return bool(tokens & blacklist)
