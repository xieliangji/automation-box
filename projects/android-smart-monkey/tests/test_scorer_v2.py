from __future__ import annotations

from smart_monkey.action.scorer_v2 import ActionScorerV2
from smart_monkey.config import ProjectConfig
from smart_monkey.models import Action, ActionHistory, ActionType, DeviceState, RunStats


def make_state() -> DeviceState:
    return DeviceState(
        state_id="state-1",
        raw_hash="",
        stable_hash="",
        package_name="com.demo.app",
        activity_name=".MainActivity",
        screen_size=(1080, 1920),
        elements=[],
        app_flags={"list_page"},
    )


def make_action() -> Action:
    return Action(
        action_id="a1",
        action_type=ActionType.CLICK,
        target_element_id="e1",
        params={"x": 100, "y": 200},
        source_state_id="state-1",
        tags={"item", "详情"},
    )


def test_scorer_v2_adds_list_bonus_and_penalties() -> None:
    config = ProjectConfig()
    scorer = ActionScorerV2(config)
    state = make_state()
    action = make_action()
    stats = RunStats(
        recent_state_ids=["x", "y", "x", "y", "x", "y"],
        recent_action_keys=["other", "state-1|click|e1|x=100,y=200"] * 3,
    )
    action_key = scorer._action_key(state.state_id, action)
    stats.action_histories[action_key] = ActionHistory(execute_count=4, new_state_count=1, unchanged_count=5)

    detail = scorer._score_one(state, action, stats)

    assert detail["depth"] >= 1.3
    assert detail["repeat_penalty"] >= 1.0
    assert detail["stuck_penalty"] >= 1.0
    assert detail["transition"] < 1.0


def test_scorer_v2_transition_gain_defaults_to_one_for_new_action() -> None:
    config = ProjectConfig()
    scorer = ActionScorerV2(config)
    state = make_state()
    action = make_action()
    stats = RunStats()

    detail = scorer._score_one(state, action, stats)

    assert detail["transition"] == 1.0
