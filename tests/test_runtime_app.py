from __future__ import annotations

import json
from pathlib import Path

import pytest

from smart_monkey.app_runtime import SmartMonkeyAppRuntime
from smart_monkey.runtime_config import RuntimeConfig
from smart_monkey.device.capabilities import DriverCapabilities
from smart_monkey.models import Action, ActionType, DeviceState, ExecuteResult, UIElement


class FakeDriver:
    def __init__(self) -> None:
        self.started = False
        self.actions: list[tuple[str, tuple]] = []
        self.target_package = "com.demo.app"
        self.wait_idle_calls: list[int] = []

    def get_foreground_package(self) -> str:
        return self.target_package if self.started else ""

    def get_current_activity(self) -> str | None:
        return ".MainActivity" if self.started else None

    def dump_hierarchy(self) -> str:
        return "<hierarchy />"

    def take_screenshot(self, path) -> None:
        Path(path).write_bytes(b"fake")

    def click(self, x: int, y: int) -> bool:
        self.actions.append(("click", (x, y)))
        return True

    def long_click(self, x: int, y: int, duration_ms: int = 800) -> bool:
        self.actions.append(("long_click", (x, y, duration_ms)))
        return True

    def input_text(self, text: str) -> bool:
        self.actions.append(("input", (text,)))
        return True

    def clear_text(self) -> bool:
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        self.actions.append(("swipe", (x1, y1, x2, y2, duration_ms)))
        return True

    def pinch(
        self,
        x1_start: int,
        y1_start: int,
        x1_end: int,
        y1_end: int,
        x2_start: int,
        y2_start: int,
        x2_end: int,
        y2_end: int,
        duration_ms: int = 280,
    ) -> bool:
        self.actions.append(
            (
                "pinch",
                (x1_start, y1_start, x1_end, y1_end, x2_start, y2_start, x2_end, y2_end, duration_ms),
            )
        )
        return True

    def press_back(self) -> bool:
        self.actions.append(("back", ()))
        return True

    def press_home(self) -> bool:
        self.actions.append(("home", ()))
        return True

    def start_app(self, package_name: str, activity: str | None = None) -> bool:
        self.started = True
        self.actions.append(("start_app", (package_name, activity)))
        return True

    def stop_app(self, package_name: str) -> bool:
        self.actions.append(("stop_app", (package_name,)))
        return True

    def wait_idle(self, timeout_ms: int = 1500) -> None:
        self.wait_idle_calls.append(timeout_ms)
        return None

    def read_logcat_tail(self, max_lines: int = 200) -> str:
        return ""

    def clear_logcat(self) -> None:
        return None

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            platform="android",
            supports_launch_target=True,
            supports_press_back=True,
            supports_press_home=True,
            supports_stop_app=True,
            supports_log_stream=True,
        )


class StubExtractor:
    def extract(self, state):
        return [
            Action(
                action_id="a1",
                action_type=ActionType.WAIT,
                target_element_id=None,
                params={"duration_ms": 1},
                source_state_id=state.state_id,
                tags={"wait"},
            )
        ]


class StubScorer:
    def score(self, state, actions, stats):
        return actions


class StubCrashStressScorer:
    def score(self, state, actions, stats):
        for action in actions:
            if action.action_type == ActionType.WAIT:
                action.score = 10.0
            else:
                action.score = 0.1
        return list(actions)


class StubLearningScorer:
    def score(self, state, actions, stats):
        for idx, action in enumerate(actions):
            action.score = 1.0 + idx
        return list(actions)


class TestableRecommendedApp(SmartMonkeyAppRuntime):
    def __init__(self, *args, states: list[DeviceState], **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._states = list(states)
        self._captured = 0
        self.extractor = StubExtractor()
        self.scorer = StubScorer()

    def capture_state(self, step_no: int, suffix: str) -> DeviceState:
        state = self._states[min(self._captured, len(self._states) - 1)]
        self._captured += 1
        return state

    def select_action(self, actions):
        return actions[0]

    def execute_action(self, action) -> ExecuteResult:
        return ExecuteResult(success=True)


def make_state(state_id: str) -> DeviceState:
    return DeviceState(
        state_id=state_id,
        raw_hash=state_id,
        stable_hash=state_id,
        package_name="com.demo.app",
        activity_name=".MainActivity",
        screen_size=(1080, 1920),
        elements=[],
        app_flags={"list_page"},
    )


def test_runtime_app_executes_pinch_action_via_driver(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    action = Action(
        action_id="pinch-1",
        action_type=ActionType.PINCH_OUT,
        target_element_id="e-scroll",
        params={
            "x1_start": 500,
            "y1_start": 900,
            "x1_end": 350,
            "y1_end": 750,
            "x2_start": 500,
            "y2_start": 900,
            "x2_end": 650,
            "y2_end": 1050,
            "duration_ms": 260,
        },
        source_state_id="state-a",
        tags={"zoom", "pinch_out"},
    )

    result = SmartMonkeyAppRuntime.execute_action(app, action)

    assert result.success is True
    assert driver.actions[-1][0] == "pinch"


def test_runtime_app_generates_artifacts(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )

    app.run()

    assert (tmp_path / "steps.jsonl").exists()
    assert (tmp_path / "replay" / "actions_replay.jsonl").exists()
    assert (tmp_path / "report" / "summary.md").exists()
    assert (tmp_path / "report" / "recovery_metrics.json").exists()
    assert (tmp_path / "report" / "coverage_benchmark.json").exists()


def test_runtime_app_fails_fast_when_target_package_cannot_be_foregrounded(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.package_name = "com.other.app"
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )

    with pytest.raises(RuntimeError) as exc_info:
        app.run()
    message = str(exc_info.value)
    assert "failed to foreground target app" in message
    assert "com.other.app" in message


def test_runtime_app_uses_platform_neutral_target_fields(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.target_app_id = "com.other.app"
    config.app.launch_target = ".OtherActivity"
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )

    with pytest.raises(RuntimeError):
        app.run()


def test_runtime_app_uses_crash_stress_wait_when_profile_enabled(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.run.profile = "crash_stress"
    config.run.crash_stress_wait_ms = 123
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )

    app.run()

    assert 123 in driver.wait_idle_calls
    steps = [json.loads(line) for line in (tmp_path / "steps.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    runtime_rows = [row for row in steps if isinstance(row.get("step"), int) and row.get("step", -1) >= 0]
    assert runtime_rows
    assert runtime_rows[0]["run_profile"] == "crash_stress"
    assert runtime_rows[0]["post_action_wait_ms"] == 123
    assert runtime_rows[0]["crash_stress_mode"] is True


def test_runtime_app_uses_monkey_wait_when_profile_enabled(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.run.profile = "monkey_compatible"
    config.run.monkey_wait_ms = 333
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )

    app.run()

    assert 333 in driver.wait_idle_calls
    steps = [json.loads(line) for line in (tmp_path / "steps.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    runtime_rows = [row for row in steps if isinstance(row.get("step"), int) and row.get("step", -1) >= 0]
    assert runtime_rows
    assert runtime_rows[0]["run_profile"] == "monkey_compatible"
    assert runtime_rows[0]["post_action_wait_ms"] == 333
    assert runtime_rows[0]["monkey_mode"] is True
    assert "monkey_same_state_streak" in runtime_rows[0]
    assert "monkey_out_of_app_streak" in runtime_rows[0]


def test_runtime_app_uses_ios_monkey_wait_when_profile_enabled(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.platform = "ios"
    config.run.profile = "monkey_compatible"
    config.run.monkey_wait_ms = 333
    config.run.monkey_ios_wait_ms = 222
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )

    app.run()

    assert 222 in driver.wait_idle_calls
    steps = [json.loads(line) for line in (tmp_path / "steps.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    runtime_rows = [row for row in steps if isinstance(row.get("step"), int) and row.get("step", -1) >= 0]
    assert runtime_rows
    assert runtime_rows[0]["run_profile"] == "monkey_compatible"
    assert runtime_rows[0]["post_action_wait_ms"] == 222
    assert runtime_rows[0]["platform"] == "ios"


def test_runtime_app_crash_stress_penalizes_wait_action(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.run.profile = "crash_stress"
    config.run.crash_stress_burst_probability = 0.0
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    app.extractor = StubExtractor()
    app.scorer = StubCrashStressScorer()

    app.run()

    steps = [json.loads(line) for line in (tmp_path / "steps.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    runtime_rows = [row for row in steps if isinstance(row.get("step"), int) and row.get("step", -1) >= 0]
    assert runtime_rows
    assert runtime_rows[0]["action_type"] == "wait"
    assert runtime_rows[0]["score"] < 10.0


def test_runtime_app_monkey_profile_boosts_escape_when_stuck(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.run.profile = "monkey_compatible"
    config.policy.monkey_loop_streak_threshold = 1
    config.policy.monkey_perturb_boost = 3.0
    config.policy.monkey_score_jitter = 0.0
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-a")],
    )
    escape_action = Action(
        action_id="back-1",
        action_type=ActionType.BACK,
        target_element_id=None,
        params={},
        source_state_id="state-a",
        tags={"back"},
        score=1.0,
    )
    app.extractor = StubExtractor()
    app.scorer = StubScorer()

    app._same_state_streak = 2
    tuned, _, meta = app._apply_profile_score_tuning([escape_action])
    assert tuned[0].score >= 4.0
    assert meta["enabled"] is True
    assert meta["escape_boosted"] is True


def test_runtime_app_monkey_profile_applies_diversity_boost(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.run.profile = "monkey_compatible"
    config.policy.monkey_diversity_state_repeat_threshold = 1
    config.policy.monkey_score_jitter = 0.0
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-a")],
    )
    app._same_state_streak = 3
    action = Action(
        action_id="click-1",
        action_type=ActionType.CLICK,
        target_element_id="e-1",
        params={"x": 1, "y": 1},
        source_state_id="state-a",
        tags={"detail"},
        score=1.0,
    )

    tuned, _, meta = app._apply_profile_score_tuning([action], state=make_state("state-a"))

    assert meta["diversity_boosted"] is True
    assert tuned[0].score > 1.0


def test_runtime_app_monkey_profile_prefers_exploration_even_without_perturb(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.run.profile = "monkey_compatible"
    config.policy.monkey_diversity_frontier_boost = 0.8
    config.policy.monkey_diversity_state_repeat_threshold = 5
    config.policy.monkey_score_jitter = 0.0
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    wait_action = Action(
        action_id="wait-bias",
        action_type=ActionType.WAIT,
        target_element_id=None,
        params={"duration_ms": 1000},
        source_state_id="state-a",
        tags={"wait"},
        score=1.0,
    )
    click_action = Action(
        action_id="click-bias",
        action_type=ActionType.CLICK,
        target_element_id="e-1",
        params={"x": 10, "y": 10},
        source_state_id="state-a",
        tags={"detail"},
        score=1.0,
    )

    tuned, _, meta = app._apply_profile_score_tuning([wait_action, click_action], state=make_state("state-a"))

    assert meta["diversity_boosted"] is True
    assert tuned[0].action_id == "click-bias"


def test_runtime_app_monkey_ios_permission_fastpath_boosts_allow_action(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.platform = "ios"
    config.run.profile = "monkey_compatible"
    config.policy.monkey_score_jitter = 0.0
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    permission_state = make_state("state-a")
    permission_state.popup_flags = {"permission_like"}
    allow_action = Action(
        action_id="allow-1",
        action_type=ActionType.CLICK,
        target_element_id="allow_button",
        params={"x": 1, "y": 1},
        source_state_id="state-a",
        tags={"allow", "允许"},
        score=1.0,
    )
    wait_action = Action(
        action_id="wait-1",
        action_type=ActionType.WAIT,
        target_element_id=None,
        params={"duration_ms": 1000},
        source_state_id="state-a",
        tags={"wait"},
        score=1.0,
    )

    tuned, _, meta = app._apply_profile_score_tuning([wait_action, allow_action], state=permission_state)

    assert meta["permission_fastpath_applied"] is True
    assert tuned[0].action_id == "allow-1"


def test_runtime_app_monkey_ios_static_text_click_is_penalized(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.platform = "ios"
    config.run.profile = "monkey_compatible"
    config.policy.monkey_score_jitter = 0.0
    config.policy.monkey_ios_static_text_click_penalty = 1.3
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    state = make_state("state-a")
    static_text = UIElement(
        element_id="label-1",
        class_name="XCUIElementTypeStaticText",
        text="个人信息",
        clickable=True,
        enabled=True,
        visible_bounds=(0, 0, 100, 40),
    )
    state.elements = [static_text]
    click_action = Action(
        action_id="click-static",
        action_type=ActionType.CLICK,
        target_element_id="label-1",
        params={"x": 10, "y": 10},
        source_state_id="state-a",
        tags={"个人信息"},
        score=4.0,
    )

    tuned, _, meta = app._apply_profile_score_tuning([click_action], state=state)

    assert meta["ios_tuning_applied"] is True
    assert tuned[0].score < 4.0


def test_runtime_app_monkey_ios_cell_click_gets_boost(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.platform = "ios"
    config.run.profile = "monkey_compatible"
    config.policy.monkey_score_jitter = 0.0
    config.policy.monkey_ios_cell_click_boost = 0.9
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    state = make_state("state-a")
    cell = UIElement(
        element_id="cell-1",
        class_name="XCUIElementTypeCell",
        clickable=True,
        enabled=True,
        visible_bounds=(0, 100, 200, 200),
    )
    state.elements = [cell]
    click_action = Action(
        action_id="click-cell",
        action_type=ActionType.CLICK,
        target_element_id="cell-1",
        params={"x": 20, "y": 120},
        source_state_id="state-a",
        tags={"详情"},
        score=3.0,
    )

    tuned, _, meta = app._apply_profile_score_tuning([click_action], state=state)

    assert meta["ios_tuning_applied"] is True
    assert tuned[0].score > 3.0


def test_runtime_app_monkey_ios_list_swipe_gets_extra_boost(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.platform = "ios"
    config.run.profile = "monkey_compatible"
    config.policy.monkey_score_jitter = 0.0
    config.policy.monkey_ios_swipe_boost = 0.0
    config.policy.monkey_ios_list_swipe_boost = 1.1
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    state = make_state("state-a")
    state.app_flags = {"list_page"}
    swipe_action = Action(
        action_id="swipe-list",
        action_type=ActionType.SWIPE,
        target_element_id="list-1",
        params={"x1": 10, "y1": 20, "x2": 10, "y2": 5, "duration_ms": 200},
        source_state_id="state-a",
        tags={"scroll"},
        score=2.0,
    )

    tuned, _, meta = app._apply_profile_score_tuning([swipe_action], state=state)

    assert meta["ios_tuning_applied"] is True
    assert meta["diversity_boosted"] is True
    assert tuned[0].score > 3.0


def test_runtime_app_monkey_ios_back_like_click_is_penalized(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.platform = "ios"
    config.run.profile = "monkey_compatible"
    config.policy.monkey_score_jitter = 0.0
    config.policy.monkey_ios_back_like_click_penalty = 1.5
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    state = make_state("state-a")
    back_like = UIElement(
        element_id="btn-back",
        class_name="XCUIElementTypeButton",
        text="icon arrow back",
        clickable=True,
        enabled=True,
        visible_bounds=(0, 0, 100, 40),
    )
    state.elements = [back_like]
    click_action = Action(
        action_id="click-back-like",
        action_type=ActionType.CLICK,
        target_element_id="btn-back",
        params={"x": 10, "y": 10},
        source_state_id="state-a",
        tags={"back"},
        score=5.0,
    )

    tuned, _, meta = app._apply_profile_score_tuning([click_action], state=state)

    assert meta["ios_tuning_applied"] is True
    assert tuned[0].score < 5.0


def test_runtime_app_monkey_ios_external_jump_click_is_penalized(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.platform = "ios"
    config.run.profile = "monkey_compatible"
    config.policy.monkey_score_jitter = 0.0
    config.policy.monkey_ios_external_jump_penalty = 2.4
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    state = make_state("state-a")
    external_jump = UIElement(
        element_id="btn-gallery",
        class_name="XCUIElementTypeButton",
        text="相册",
        clickable=True,
        enabled=True,
        visible_bounds=(0, 0, 120, 50),
    )
    state.elements = [external_jump]
    click_action = Action(
        action_id="click-gallery",
        action_type=ActionType.CLICK,
        target_element_id="btn-gallery",
        params={"x": 20, "y": 20},
        source_state_id="state-a",
        tags={"gallery"},
        score=6.0,
    )

    tuned, _, meta = app._apply_profile_score_tuning([click_action], state=state)

    assert meta["ios_tuning_applied"] is True
    assert meta["risk_cooldown_applied"] is True
    assert tuned[0].score < 6.0


def test_runtime_app_ios_permission_grace_can_skip_recovery_trigger(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.platform = "ios"
    config.run.profile = "monkey_compatible"
    config.policy.monkey_ios_recovery_stuck_threshold = 10
    config.policy.monkey_ios_same_state_recovery_threshold = 3
    config.policy.monkey_ios_permission_recovery_grace_steps = 3
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-a")],
    )
    current = make_state("state-a")
    next_state = make_state("state-a")
    previous = make_state("state-a")
    transition = app._build_transition(current, Action(
        action_id="wait-recovery",
        action_type=ActionType.WAIT,
        target_element_id=None,
        params={"duration_ms": 10},
        source_state_id="state-a",
        tags={"wait"},
    ), next_state, ExecuteResult(success=True))
    app._current_step_no = 10
    app._last_permission_like_step = 9
    app._same_state_streak = 3
    app.runtime.stats.stuck_score = 12

    assert app._should_trigger_recovery(previous, current, next_state, transition) is False

def test_runtime_app_learning_fields_are_recorded(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.learning.enabled = True
    config.learning.alpha = 0.5
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    app.extractor = StubExtractor()
    app.scorer = StubLearningScorer()

    app.run()

    steps = [json.loads(line) for line in (tmp_path / "steps.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    runtime_rows = [row for row in steps if isinstance(row.get("step"), int) and row.get("step", -1) >= 0]
    assert runtime_rows
    row = runtime_rows[0]
    assert row["learning_enabled"] is True
    assert isinstance(row["learning_reward"], float)
    assert row["score_detail"]["learned_ucb"] >= 0.0
    assert row["score_detail"]["score_after_learning"] >= 0.0
    assert "learning_arm_key" in row
    assert row["learning_arm_key"].count("|") == 3

    metrics_rows = [row for row in steps if row.get("runtime_metrics")]
    assert metrics_rows
    assert "learning" in metrics_rows[-1]["runtime_metrics"]


def test_runtime_app_sidecar_monkey_batch_is_recorded(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 2
    config.snapshot.enabled = False
    config.run.profile = "monkey_compatible"
    config.sidecar.monkey.enabled = True
    config.sidecar.monkey.step_interval = 1
    config.sidecar.monkey.max_batches = 1
    config.sidecar.monkey.events_per_batch = 20
    config.sidecar.monkey.throttle_ms = 10
    driver = FakeDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b"), make_state("state-c")],
    )
    app.extractor = StubExtractor()
    app.scorer = StubLearningScorer()

    app.run()

    steps = [json.loads(line) for line in (tmp_path / "steps.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    sidecar_rows = [row for row in steps if row.get("sidecar_monkey_batch") is True]
    assert sidecar_rows
    sidecar_row = sidecar_rows[0]
    assert sidecar_row["sidecar_batch_no"] == 1
    assert sidecar_row["sidecar_events_requested"] == 20
    assert sidecar_row["sidecar_success"] is False
    assert sidecar_row["sidecar_skipped_reason"] == "driver_not_supported"

    metrics_rows = [row for row in steps if row.get("runtime_metrics")]
    assert metrics_rows
    assert "sidecar_monkey" in metrics_rows[-1]["runtime_metrics"]
    sidecar_summary = metrics_rows[-1]["runtime_metrics"]["sidecar_monkey"]
    assert sidecar_summary["batches_run"] == 1
    assert sidecar_summary["failure_count"] == 1


def test_runtime_learning_arm_key_normalization_reduces_state_specificity() -> None:
    state = make_state("state-x")
    state.app_flags = {"list_page"}
    action1 = Action(
        action_id="a1",
        action_type=ActionType.CLICK,
        target_element_id="e001",
        params={"x": 1, "y": 2},
        source_state_id="s1",
        tags={"detail"},
    )
    action2 = Action(
        action_id="a2",
        action_type=ActionType.CLICK,
        target_element_id="e999",
        params={"x": 9, "y": 9},
        source_state_id="s2",
        tags={"details"},
    )
    key1 = SmartMonkeyAppRuntime._learning_arm_key(state, action1)
    key2 = SmartMonkeyAppRuntime._learning_arm_key(state, action2)
    assert key1 == key2
    assert key1 == "list|click|element|detail"


def test_runtime_learning_arm_key_uses_module_bucket_by_activity() -> None:
    state = make_state("state-y")
    state.app_flags = {"list_page"}
    state.activity_name = ".DeviceListActivity"
    action = Action(
        action_id="a3",
        action_type=ActionType.CLICK,
        target_element_id="e333",
        params={"x": 3, "y": 3},
        source_state_id="s3",
        tags={"generic"},
    )
    key = SmartMonkeyAppRuntime._learning_arm_key(state, action, use_module_bucket=True)
    assert key.startswith("module_device|click|")


def test_runtime_learning_arm_key_can_disable_module_bucket() -> None:
    state = make_state("state-z")
    state.app_flags = {"list_page"}
    state.activity_name = ".DeviceListActivity"
    action = Action(
        action_id="a4",
        action_type=ActionType.CLICK,
        target_element_id="e444",
        params={"x": 4, "y": 4},
        source_state_id="s4",
        tags={"generic"},
    )
    key = SmartMonkeyAppRuntime._learning_arm_key(state, action, use_module_bucket=False)
    assert key.startswith("list|click|")


class CapabilityLimitedDriver(FakeDriver):
    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            platform="ios",
            supports_launch_target=False,
            supports_press_back=False,
            supports_press_home=False,
            supports_stop_app=False,
            supports_log_stream=False,
        )


class RetryNeedsLaunchTargetDriver(FakeDriver):
    def __init__(self) -> None:
        super().__init__()
        self.started = False
        self._launch_attempts = 0

    def get_foreground_package(self) -> str:
        return self.target_package if self.started else "com.motorola.launcher3"

    def start_app(self, package_name: str, activity: str | None = None) -> bool:
        self._launch_attempts += 1
        self.actions.append(("start_app", (package_name, activity)))
        # 模拟首启失败，要求重试时仍使用 launch_target 才能拉回目标 App。
        self.started = bool(activity) and self._launch_attempts >= 2
        return True


class SidecarRecoveryFailingDriver(FakeDriver):
    def __init__(self) -> None:
        super().__init__()
        self.started = False
        self._start_calls = 0
        self._force_out_of_app = False

    def get_foreground_package(self) -> str:
        if self._force_out_of_app:
            return "com.android.settings"
        return self.target_package if self.started else ""

    def _run(self, *args, **kwargs):
        self._force_out_of_app = True
        return type(
            "_Completed",
            (),
            {"returncode": 0, "stdout": "Events injected: 20", "stderr": ""},
        )()

    def start_app(self, package_name: str, activity: str | None = None) -> bool:
        self._start_calls += 1
        self.actions.append(("start_app", (package_name, activity)))
        self.started = self._start_calls == 1
        return True


def test_runtime_app_foreground_retry_reuses_launch_target(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.app.launch_target = ".MainActivity"
    driver = RetryNeedsLaunchTargetDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )

    app.run()

    start_calls = [item for item in driver.actions if item[0] == "start_app"]
    assert len(start_calls) >= 2
    assert start_calls[0][1][1] == ".MainActivity"
    assert start_calls[1][1][1] == ".MainActivity"


def test_runtime_app_sidecar_recovery_failure_is_audited(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    config.run.profile = "monkey_compatible"
    config.sidecar.monkey.enabled = True
    config.sidecar.monkey.step_interval = 1
    config.sidecar.monkey.max_batches = 1
    driver = SidecarRecoveryFailingDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    app.extractor = StubExtractor()
    app.scorer = StubLearningScorer()

    app.run()

    steps = [json.loads(line) for line in (tmp_path / "steps.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    sidecar_rows = [row for row in steps if row.get("sidecar_monkey_batch") is True]
    assert sidecar_rows
    row = sidecar_rows[0]
    assert row["sidecar_recovery_failed"] is True
    assert isinstance(row["sidecar_recovery_error"], str)
    metrics_rows = [row for row in steps if row.get("runtime_metrics")]
    assert metrics_rows
    sidecar_summary = metrics_rows[-1]["runtime_metrics"]["sidecar_monkey"]
    assert sidecar_summary["batches_run"] == 1


def test_runtime_app_home_action_falls_back_when_driver_has_no_home(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    driver = CapabilityLimitedDriver()
    driver.started = False
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    action = Action(
        action_id="home-1",
        action_type=ActionType.HOME,
        target_element_id=None,
        params={},
        source_state_id="state-a",
        tags={"home"},
    )

    result = SmartMonkeyAppRuntime.execute_action(app, action)

    assert result.success is True
    assert ("home", ()) not in driver.actions
    assert any(item[0] == "start_app" for item in driver.actions)


def test_runtime_app_skips_back_when_driver_has_no_back(tmp_path: Path) -> None:
    config = RuntimeConfig()
    config.run.max_steps = 1
    config.snapshot.enabled = False
    driver = CapabilityLimitedDriver()
    app = TestableRecommendedApp(
        driver=driver,
        config=config,
        output_dir=tmp_path,
        states=[make_state("state-a"), make_state("state-b")],
    )
    action = Action(
        action_id="back-1",
        action_type=ActionType.BACK,
        target_element_id=None,
        params={},
        source_state_id="state-a",
        tags={"back"},
    )

    result = SmartMonkeyAppRuntime.execute_action(app, action)

    assert result.success is False
    assert ("back", ()) not in driver.actions
