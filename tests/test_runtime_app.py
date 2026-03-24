from __future__ import annotations

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
