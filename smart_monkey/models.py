from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


Bounds = tuple[int, int, int, int]


class ActionType(str, Enum):
    CLICK = "click"
    LONG_CLICK = "long_click"
    INPUT = "input"
    SWIPE = "swipe"
    PINCH_IN = "pinch_in"
    PINCH_OUT = "pinch_out"
    BACK = "back"
    HOME = "home"
    WAIT = "wait"
    RESTART_APP = "restart_app"


@dataclass(slots=True)
class UIElement:
    element_id: str
    class_name: str
    resource_id: str | None = None
    text: str | None = None
    content_desc: str | None = None
    package_name: str | None = None
    clickable: bool = False
    long_clickable: bool = False
    scrollable: bool = False
    checkable: bool = False
    checked: bool = False
    enabled: bool = True
    focusable: bool = False
    focused: bool = False
    editable: bool = False
    visible_bounds: Bounds = (0, 0, 0, 0)
    depth: int = 0
    xpath: str = ""
    parent_id: str | None = None
    child_ids: list[str] = field(default_factory=list)

    @property
    def center(self) -> tuple[int, int]:
        left, top, right, bottom = self.visible_bounds
        return ((left + right) // 2, (top + bottom) // 2)

    def semantic_tokens(self) -> set[str]:
        values = [self.resource_id or "", self.text or "", self.content_desc or "", self.class_name or ""]
        tokens: set[str] = set()
        for value in values:
            for token in value.replace("/", " ").replace("_", " ").replace("-", " ").split():
                cleaned = token.strip().lower()
                if cleaned:
                    tokens.add(cleaned)
        return tokens


@dataclass(slots=True)
class DeviceState:
    state_id: str
    raw_hash: str
    stable_hash: str
    package_name: str
    activity_name: str | None
    screen_size: tuple[int, int] = (0, 0)
    elements: list[UIElement] = field(default_factory=list)
    screenshot_path: str | None = None
    hierarchy_path: str | None = None
    popup_flags: set[str] = field(default_factory=set)
    system_flags: set[str] = field(default_factory=set)
    app_flags: set[str] = field(default_factory=set)
    timestamp_ms: int = 0


@dataclass(slots=True)
class Action:
    action_id: str
    action_type: ActionType
    target_element_id: str | None
    params: dict[str, Any]
    source_state_id: str
    score: float = 0.0
    score_detail: dict[str, float] = field(default_factory=dict)
    tags: set[str] = field(default_factory=set)


@dataclass(slots=True)
class ExecuteResult:
    success: bool
    message: str = ""


@dataclass(slots=True)
class Transition:
    transition_id: str
    from_state_id: str
    to_state_id: str
    action_id: str
    success: bool
    changed: bool
    crash: bool = False
    anr: bool = False
    out_of_app: bool = False
    duration_ms: int = 0
    timestamp_ms: int = 0


@dataclass(slots=True)
class ActionHistory:
    execute_count: int = 0
    new_state_count: int = 0
    unchanged_count: int = 0


@dataclass(slots=True)
class RunStats:
    visited_states: dict[str, int] = field(default_factory=dict)
    action_histories: dict[str, ActionHistory] = field(default_factory=dict)
    recent_state_ids: list[str] = field(default_factory=list)
    recent_action_keys: list[str] = field(default_factory=list)
    stuck_score: int = 0
