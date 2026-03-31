from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from smart_monkey.action.extractor import ActionExtractor
from smart_monkey.action.scorer import ActionScorer
from smart_monkey.config import ProjectConfig
from smart_monkey.device.base import DeviceDriver
from smart_monkey.models import Action, ActionHistory, DeviceState, ExecuteResult, RunStats, Transition
from smart_monkey.state.fingerprint import StateFingerprinter


@dataclass(slots=True)
class RunContext:
    config: ProjectConfig
    output_dir: Path
    stats: RunStats = field(default_factory=RunStats)


class SmartMonkeyRunner:
    def __init__(self, driver: DeviceDriver, config: ProjectConfig, output_dir: str | Path = "output") -> None:
        self.driver = driver
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.context = RunContext(config=config, output_dir=self.output_dir)
        self.fingerprinter = StateFingerprinter()
        self.extractor = ActionExtractor(config)
        self.scorer = ActionScorer(config)
        random.seed(config.run.seed)

    def run(self) -> None:
        self._ensure_app_started()
        previous_state: DeviceState | None = None

        for step in range(self.config.run.max_steps):
            state = self.capture_state(step)
            self._mark_visited(state.state_id)

            if previous_state is not None and state.state_id == previous_state.state_id:
                self.context.stats.stuck_score += 2
            else:
                self.context.stats.stuck_score = max(0, self.context.stats.stuck_score - 4)

            actions = self.extractor.extract(state)
            scored_actions = self.scorer.score(state, actions, self.context.stats)
            action = self.select_action(scored_actions)
            started_at = time.time()
            result = self.execute_action(action)
            self.driver.wait_idle(self.config.run.post_action_wait_ms)
            next_state = self.capture_state(step, suffix="after")
            duration_ms = int((time.time() - started_at) * 1000)

            transition = Transition(
                transition_id=uuid4().hex[:16],
                from_state_id=state.state_id,
                to_state_id=next_state.state_id,
                action_id=action.action_id,
                success=result.success,
                changed=state.state_id != next_state.state_id,
                out_of_app=next_state.package_name != self.config.app.target_app_id,
                duration_ms=duration_ms,
                timestamp_ms=int(time.time() * 1000),
            )
            self.update_stats(state, action, transition)
            self.write_step_log(step, state, action, transition)

            if transition.out_of_app:
                self.recover_from_out_of_app()

            previous_state = next_state

    def capture_state(self, step: int, suffix: str = "before") -> DeviceState:
        package_name = self.driver.get_foreground_package()
        activity_name = self.driver.get_current_activity()
        hierarchy = self.driver.dump_hierarchy()
        hierarchy_path = self.output_dir / f"step_{step:04d}_{suffix}.xml"
        hierarchy_path.write_text(hierarchy, encoding="utf-8")

        state = DeviceState(
            state_id="",
            raw_hash="",
            stable_hash="",
            package_name=package_name,
            activity_name=activity_name,
            hierarchy_path=str(hierarchy_path),
            screen_size=(1080, 1920),
            elements=[],
            timestamp_ms=int(time.time() * 1000),
        )
        # 待办：解析层级结构并生成元素列表。
        state.raw_hash = self.fingerprinter.build_raw_hash(state)
        state.stable_hash = self.fingerprinter.build_stable_hash(state)
        state.state_id = self.fingerprinter.build_state_id(state)
        return state

    def select_action(self, actions: list[Action]) -> Action:
        if not actions:
            raise RuntimeError("No action generated for current state.")

        top_k = max(1, self.config.policy.top_k)
        candidates = actions[:top_k]
        if random.random() < self.config.policy.epsilon:
            return random.choice(candidates)

        scores = [max(item.score, 0.01) for item in candidates]
        total = sum(scores)
        target = random.random() * total
        current = 0.0
        for item, score in zip(candidates, scores):
            current += score
            if current >= target:
                return item
        return candidates[0]

    def execute_action(self, action: Action) -> ExecuteResult:
        if action.action_type.value == "click":
            success = self.driver.click(action.params["x"], action.params["y"])
        elif action.action_type.value == "long_click":
            success = self.driver.long_click(
                action.params["x"],
                action.params["y"],
                action.params.get("duration_ms", 800),
            )
        elif action.action_type.value == "input":
            self.driver.click(action.params["x"], action.params["y"])
            success = self.driver.input_text(action.params["text"])
        elif action.action_type.value == "swipe":
            success = self.driver.swipe(
                action.params["x1"],
                action.params["y1"],
                action.params["x2"],
                action.params["y2"],
                action.params.get("duration_ms", 300),
            )
        elif action.action_type.value in {"pinch_in", "pinch_out"}:
            success = self.driver.pinch(
                action.params["x1_start"],
                action.params["y1_start"],
                action.params["x1_end"],
                action.params["y1_end"],
                action.params["x2_start"],
                action.params["y2_start"],
                action.params["x2_end"],
                action.params["y2_end"],
                action.params.get("duration_ms", 280),
            )
        elif action.action_type.value == "back":
            success = self.driver.press_back()
        elif action.action_type.value == "home":
            success = self.driver.press_home()
        elif action.action_type.value == "restart_app":
            self.driver.stop_app(self.config.app.target_app_id)
            success = self.driver.start_app(self.config.app.target_app_id, self.config.app.launch_target)
        else:
            time.sleep(action.params.get("duration_ms", 1000) / 1000)
            success = True

        return ExecuteResult(success=success)

    def update_stats(self, state: DeviceState, action: Action, transition: Transition) -> None:
        history_key = self._action_key(state.state_id, action)
        history = self.context.stats.action_histories.setdefault(history_key, ActionHistory())
        history.execute_count += 1
        if transition.changed:
            history.new_state_count += 1
        else:
            history.unchanged_count += 1

        self.context.stats.recent_state_ids.append(transition.to_state_id)
        self.context.stats.recent_state_ids = self.context.stats.recent_state_ids[-10:]
        self.context.stats.recent_action_keys.append(history_key)
        self.context.stats.recent_action_keys = self.context.stats.recent_action_keys[-10:]

        if transition.changed:
            self.context.stats.stuck_score = max(0, self.context.stats.stuck_score - 4)
        else:
            self.context.stats.stuck_score += 2

    def write_step_log(self, step: int, state: DeviceState, action: Action, transition: Transition) -> None:
        line = (
            f"step={step} "
            f"from={state.state_id} "
            f"action={action.action_type.value} "
            f"score={action.score:.2f} "
            f"to={transition.to_state_id} "
            f"changed={transition.changed} "
            f"out_of_app={transition.out_of_app}"
        )
        log_file = self.output_dir / "run.log"
        with log_file.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def recover_from_out_of_app(self) -> None:
        self.driver.press_back()
        self.driver.wait_idle(800)
        if self.driver.get_foreground_package() != self.config.app.target_app_id:
            self.driver.start_app(self.config.app.target_app_id, self.config.app.launch_target)
            self.driver.wait_idle(1500)

    def _ensure_app_started(self) -> None:
        if self.driver.get_foreground_package() != self.config.app.target_app_id:
            self.driver.start_app(self.config.app.target_app_id, self.config.app.launch_target)
            self.driver.wait_idle(1500)

    def _mark_visited(self, state_id: str) -> None:
        self.context.stats.visited_states[state_id] = self.context.stats.visited_states.get(state_id, 0) + 1

    @staticmethod
    def _action_key(state_id: str, action: Action) -> str:
        params = ",".join(f"{key}={value}" for key, value in sorted(action.params.items()))
        return f"{state_id}|{action.action_type.value}|{action.target_element_id}|{params}"
