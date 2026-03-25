from __future__ import annotations

import json
from pathlib import Path

import pytest

from smart_monkey.app_runtime import SmartMonkeyAppRuntime
from smart_monkey.runtime_config import RuntimeConfig
from smart_monkey.models import Action, ActionType, DeviceState, ExecuteResult


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
