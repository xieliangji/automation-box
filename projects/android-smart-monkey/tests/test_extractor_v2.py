from __future__ import annotations

from smart_monkey.action.extractor_v2 import ActionExtractorV2
from smart_monkey.config import ProjectConfig
from smart_monkey.models import DeviceState, UIElement


def make_element(
    element_id: str,
    *,
    text: str = "",
    resource_id: str = "",
    clickable: bool = True,
    scrollable: bool = False,
    parent_id: str | None = None,
    y: int = 0,
) -> UIElement:
    return UIElement(
        element_id=element_id,
        class_name="android.widget.TextView",
        resource_id=resource_id or f"com.demo:id/{element_id}",
        text=text,
        clickable=clickable,
        scrollable=scrollable,
        visible_bounds=(0, y, 100, y + 50),
        parent_id=parent_id,
        xpath=f"/hierarchy/node[{element_id}]",
    )


def make_state(elements: list[UIElement]) -> DeviceState:
    return DeviceState(
        state_id="state-1",
        raw_hash="",
        stable_hash="",
        package_name="com.demo.app",
        activity_name=".MainActivity",
        screen_size=(1080, 1920),
        elements=elements,
    )


def test_extractor_filters_high_risk_element_when_safe_candidates_exist() -> None:
    config = ProjectConfig()
    extractor = ActionExtractorV2(config)
    safe = make_element("safe_btn", text="下一步", y=10)
    risky = make_element("danger_btn", text="删除", y=80)
    state = make_state([safe, risky])

    selected = extractor._select_interactive_elements(state)

    assert any(item.element_id == "safe_btn" for item in selected)
    assert all(item.element_id != "danger_btn" for item in selected)


def test_extractor_keeps_list_sampling_bounded() -> None:
    config = ProjectConfig()
    extractor = ActionExtractorV2(config)
    items = [
        make_element(f"item_{idx}", text=f"item {idx}", resource_id="com.demo:id/item", parent_id="list_parent", y=idx * 60)
        for idx in range(8)
    ]
    state = make_state(items)

    selected = extractor._sample_list_items(items)

    assert len(selected) <= 5
    assert selected[0].element_id == "item_0"
    assert selected[-1].element_id == "item_7"


def test_extract_always_adds_system_actions() -> None:
    config = ProjectConfig()
    extractor = ActionExtractorV2(config)
    state = make_state([make_element("safe_btn", text="进入")])

    actions = extractor.extract(state)
    action_types = {action.action_type.value for action in actions}

    assert "back" in action_types
    assert "wait" in action_types
    assert "restart_app" in action_types
