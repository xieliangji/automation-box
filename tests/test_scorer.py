from __future__ import annotations

from smart_monkey.action.scorer_runtime import RuntimeActionScorer
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


def make_login_state() -> DeviceState:
    return DeviceState(
        state_id="login-state",
        raw_hash="",
        stable_hash="",
        package_name="com.demo.app",
        activity_name=".LoginActivity",
        screen_size=(1080, 1920),
        elements=[],
        app_flags={"login_page"},
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


def test_runtime_scorer_adds_list_bonus_and_penalties() -> None:
    config = ProjectConfig()
    scorer = RuntimeActionScorer(config)
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


def test_runtime_scorer_transition_gain_defaults_to_one_for_new_action() -> None:
    config = ProjectConfig()
    scorer = RuntimeActionScorer(config)
    state = make_state()
    action = make_action()
    stats = RunStats()

    detail = scorer._score_one(state, action, stats)

    assert detail["transition"] == 1.0


def test_runtime_scorer_functional_page_switch_affects_login_penalty() -> None:
    stats = RunStats()
    login_state = make_login_state()
    wait_action = Action(
        action_id="wait-1",
        action_type=ActionType.WAIT,
        target_element_id=None,
        params={"duration_ms": 1000},
        source_state_id="login-state",
        tags={"wait"},
    )

    prefer_config = ProjectConfig()
    prefer_config.policy.prefer_functional_pages = True
    prefer_detail = RuntimeActionScorer(prefer_config)._score_one(login_state, wait_action, stats)

    auth_config = ProjectConfig()
    auth_config.policy.prefer_functional_pages = False
    auth_detail = RuntimeActionScorer(auth_config)._score_one(login_state, wait_action, stats)

    assert prefer_detail["repeat_penalty"] >= 1.0
    assert auth_detail["repeat_penalty"] == 0.0


def test_runtime_scorer_functional_page_switch_affects_business_bonus() -> None:
    state = make_state()
    action = Action(
        action_id="click-1",
        action_type=ActionType.CLICK,
        target_element_id="e100",
        params={"x": 300, "y": 500},
        source_state_id="state-1",
        tags={"item"},
    )
    stats = RunStats()

    prefer_config = ProjectConfig()
    prefer_config.policy.prefer_functional_pages = True
    prefer_detail = RuntimeActionScorer(prefer_config)._score_one(state, action, stats)

    auth_config = ProjectConfig()
    auth_config.policy.prefer_functional_pages = False
    auth_detail = RuntimeActionScorer(auth_config)._score_one(state, action, stats)

    assert prefer_detail["business"] > auth_detail["business"]


def test_runtime_scorer_treats_pinch_as_escape_candidate_when_stuck() -> None:
    config = ProjectConfig()
    scorer = RuntimeActionScorer(config)
    state = make_state()
    action = Action(
        action_id="pinch-1",
        action_type=ActionType.PINCH_OUT,
        target_element_id="scroll-1",
        params={
            "x1_start": 500,
            "y1_start": 900,
            "x1_end": 350,
            "y1_end": 750,
            "x2_start": 500,
            "y2_start": 900,
            "x2_end": 650,
            "y2_end": 1050,
        },
        source_state_id="state-1",
        tags={"zoom", "pinch_out"},
    )
    stats = RunStats(stuck_score=8)

    detail = scorer._score_one(state, action, stats)

    assert detail["escape"] == 1.0
    assert detail["depth"] >= 0.5


def test_runtime_scorer_boosts_pinch_on_zoom_context() -> None:
    config = ProjectConfig()
    config.policy.pinch_zoom_context_boost = 0.5
    scorer = RuntimeActionScorer(config)
    state = DeviceState(
        state_id="s-zoom",
        raw_hash="",
        stable_hash="",
        package_name="com.demo.app",
        activity_name=".MapActivity",
        screen_size=(1080, 1920),
        elements=[],
        app_flags={"list_page"},
    )
    action = Action(
        action_id="pinch-2",
        action_type=ActionType.PINCH_IN,
        target_element_id="map",
        params={},
        source_state_id="s-zoom",
        tags={"map"},
    )
    detail = scorer._score_one(state, action, RunStats())
    assert detail["business"] >= 0.5
    assert detail["repeat_penalty"] == 0.0


def test_runtime_scorer_penalizes_pinch_on_non_zoom_context() -> None:
    config = ProjectConfig()
    config.policy.pinch_non_zoom_penalty = 0.7
    scorer = RuntimeActionScorer(config)
    state = DeviceState(
        state_id="s-plain",
        raw_hash="",
        stable_hash="",
        package_name="com.demo.app",
        activity_name=".MainActivity",
        screen_size=(1080, 1920),
        elements=[],
        app_flags={"list_page"},
    )
    action = Action(
        action_id="pinch-3",
        action_type=ActionType.PINCH_OUT,
        target_element_id="list",
        params={},
        source_state_id="s-plain",
        tags={"list"},
    )
    detail = scorer._score_one(state, action, RunStats())
    assert detail["repeat_penalty"] >= 0.7
