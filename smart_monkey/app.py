from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

from loguru import logger

from smart_monkey.action.extractor import ActionExtractor
from smart_monkey.action.scorer import ActionScorer
from smart_monkey.config import ProjectConfig
from smart_monkey.device.base import DeviceDriver
from smart_monkey.graph.utg import UTG
from smart_monkey.logging_utils import setup_logger
from smart_monkey.models import Action, ActionHistory, DeviceState, ExecuteResult, RunStats, Transition
from smart_monkey.state.fingerprint import StateFingerprinter
from smart_monkey.state.parser import HierarchyParser
from smart_monkey.storage.recorder import RunRecorder


@dataclass(slots=True)
class Runtime:
    config: ProjectConfig
    stats: RunStats = field(default_factory=RunStats)
    utg: UTG = field(default_factory=UTG)


class SmartMonkeyApp:
    def __init__(self, driver: DeviceDriver, config: ProjectConfig, output_dir: str | Path = "output") -> None:
        self.driver = driver
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = setup_logger(self.output_dir)

        self.runtime = Runtime(config=config)
        self.fingerprinter = StateFingerprinter()
        self.parser = HierarchyParser()
        self.extractor = ActionExtractor(config)
        self.scorer = ActionScorer(config)
        self.recorder = RunRecorder(self.output_dir)

        random.seed(config.run.seed)
        logger.info(
            "app initialized output_dir={} target_package={} launch_activity={} seed={}",
            self.output_dir,
            self.config.app.package_name,
            self.config.app.launch_activity,
            self.config.run.seed,
        )

    def run(self) -> None:
        self._ensure_app_started()
        previous_state: DeviceState | None = None

        for step in range(self.config.run.max_steps):
            current_state = self.capture_state(step_no=step, suffix="before")
            self._mark_visited(current_state.state_id)
            self.runtime.utg.add_state(
                current_state.state_id,
                {
                    "package_name": current_state.package_name,
                    "activity_name": current_state.activity_name,
                    "app_flags": sorted(current_state.app_flags),
                    "popup_flags": sorted(current_state.popup_flags),
                },
            )

            actions = self.extractor.extract(current_state)
            scored_actions = self.scorer.score(current_state, actions, self.runtime.stats)
            action = self.select_action(scored_actions)
            logger.info(
                "step={} action={} id={} from={} score={:.3f} tags={}",
                step,
                action.action_type.value,
                action.action_id,
                current_state.state_id,
                action.score,
                sorted(action.tags),
            )
            action_started_at = time.time()
            result = self.execute_action(action)
            self.driver.wait_idle(self.config.run.post_action_wait_ms)
            next_state = self.capture_state(step_no=step, suffix="after")

            transition = Transition(
                transition_id=uuid4().hex[:16],
                from_state_id=current_state.state_id,
                to_state_id=next_state.state_id,
                action_id=action.action_id,
                success=result.success,
                changed=current_state.state_id != next_state.state_id,
                crash=False,
                anr=False,
                out_of_app=next_state.package_name != self.config.app.package_name,
                duration_ms=int((time.time() - action_started_at) * 1000),
                timestamp_ms=int(time.time() * 1000),
            )

            self.update_runtime(current_state, action, transition)
            self.persist_step(step, current_state, action, transition, next_state)
            logger.info(
                "step={} transition={} changed={} out_of_app={} stuck_score={}",
                step,
                transition.transition_id,
                transition.changed,
                transition.out_of_app,
                self.runtime.stats.stuck_score,
            )

            if transition.out_of_app:
                logger.warning("step={} detected out_of_app, triggering recovery", step)
                self.recover_from_out_of_app()
            elif self.should_escape(previous_state, current_state, next_state, transition):
                logger.warning("step={} detected stuck/escape condition, triggering escape", step)
                self.escape()

            previous_state = next_state

        self.recorder.record_utg(self.runtime.utg)
        logger.info("run completed steps={} utg_nodes={}", self.config.run.max_steps, len(self.runtime.utg.nodes))

    def capture_state(self, step_no: int, suffix: str) -> DeviceState:
        package_name = self.driver.get_foreground_package()
        activity_name = self.driver.get_current_activity()
        hierarchy = self.driver.dump_hierarchy()

        hierarchy_path = self.output_dir / "states" / f"step_{step_no:04d}_{suffix}.xml"
        hierarchy_path.parent.mkdir(parents=True, exist_ok=True)
        hierarchy_path.write_text(hierarchy, encoding="utf-8")

        parsed = self.parser.parse(hierarchy)
        state = DeviceState(
            state_id="",
            raw_hash="",
            stable_hash="",
            package_name=package_name,
            activity_name=activity_name,
            screen_size=(1080, 1920),
            elements=parsed.elements,
            hierarchy_path=str(hierarchy_path),
            popup_flags=parsed.popup_flags,
            system_flags=parsed.system_flags,
            app_flags=parsed.app_flags,
            timestamp_ms=int(time.time() * 1000),
        )
        state.raw_hash = self.fingerprinter.build_raw_hash(state)
        state.stable_hash = self.fingerprinter.build_stable_hash(state)
        state.state_id = self.fingerprinter.build_state_id(state)
        return state

    def select_action(self, actions: list[Action]) -> Action:
        if not actions:
            raise RuntimeError("No candidate actions available.")

        candidates = actions[: max(1, self.config.policy.top_k)]
        if random.random() < self.config.policy.epsilon:
            return random.choice(candidates)

        total = sum(max(item.score, 0.01) for item in candidates)
        threshold = random.random() * total
        current = 0.0
        for item in candidates:
            current += max(item.score, 0.01)
            if current >= threshold:
                return item
        return candidates[0]

    def execute_action(self, action: Action) -> ExecuteResult:
        action_type = action.action_type.value
        if action_type == "click":
            success = self.driver.click(action.params["x"], action.params["y"])
        elif action_type == "long_click":
            success = self.driver.long_click(action.params["x"], action.params["y"], action.params.get("duration_ms", 800))
        elif action_type == "input":
            self.driver.click(action.params["x"], action.params["y"])
            success = self.driver.input_text(action.params["text"])
        elif action_type == "swipe":
            success = self.driver.swipe(
                action.params["x1"],
                action.params["y1"],
                action.params["x2"],
                action.params["y2"],
                action.params.get("duration_ms", 300),
            )
        elif action_type in {"pinch_in", "pinch_out"}:
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
        elif action_type == "back":
            success = self.driver.press_back()
        elif action_type == "home":
            success = self.driver.press_home()
        elif action_type == "restart_app":
            self.driver.stop_app(self.config.app.package_name)
            self.driver.wait_idle(500)
            self._ensure_target_foreground(context="restart action")
            success = True
        else:
            time.sleep(action.params.get("duration_ms", 1000) / 1000)
            success = True
        return ExecuteResult(success=success)

    def update_runtime(self, current_state: DeviceState, action: Action, transition: Transition) -> None:
        action_key = self._action_key(current_state.state_id, action)
        history = self.runtime.stats.action_histories.setdefault(action_key, ActionHistory())
        history.execute_count += 1
        if transition.changed:
            history.new_state_count += 1
        else:
            history.unchanged_count += 1

        self.runtime.stats.recent_state_ids.append(transition.to_state_id)
        self.runtime.stats.recent_state_ids = self.runtime.stats.recent_state_ids[-10:]
        self.runtime.stats.recent_action_keys.append(action_key)
        self.runtime.stats.recent_action_keys = self.runtime.stats.recent_action_keys[-10:]
        self.runtime.stats.stuck_score = max(0, self.runtime.stats.stuck_score - 3) if transition.changed else self.runtime.stats.stuck_score + 2
        self.runtime.utg.add_transition(transition, action)

    def persist_step(
        self,
        step: int,
        current_state: DeviceState,
        action: Action,
        transition: Transition,
        next_state: DeviceState,
        extra_step_fields: dict[str, Any] | None = None,
    ) -> None:
        self.recorder.record_state(current_state)
        self.recorder.record_state(next_state)
        self.recorder.record_action(action)
        self.recorder.record_transition(transition)
        step_payload: dict[str, Any] = {
            "step": step,
            "current_state_id": current_state.state_id,
            "next_state_id": next_state.state_id,
            "action_type": action.action_type.value,
            "action_id": action.action_id,
            "score": action.score,
            "score_detail": action.score_detail,
            "changed": transition.changed,
            "crash": transition.crash,
            "anr": transition.anr,
            "out_of_app": transition.out_of_app,
            "timestamp_ms": transition.timestamp_ms,
            "stuck_score": self.runtime.stats.stuck_score,
        }
        if extra_step_fields:
            step_payload.update(extra_step_fields)
        self.recorder.record_step(step_payload)
        self.recorder.record_utg(self.runtime.utg)

    def should_escape(
        self,
        previous_state: DeviceState | None,
        current_state: DeviceState,
        next_state: DeviceState,
        transition: Transition,
    ) -> bool:
        if self.runtime.stats.stuck_score >= 10:
            return True
        if not transition.changed and current_state.state_id == next_state.state_id:
            return self.runtime.stats.stuck_score >= self.config.policy.no_progress_threshold
        if previous_state and previous_state.state_id == current_state.state_id == next_state.state_id:
            return True
        return False

    def escape(self) -> None:
        self.driver.press_back()
        self.driver.wait_idle(800)
        if self.driver.get_foreground_package() != self.config.app.package_name:
            self._ensure_target_foreground(context="escape recovery")
        self.runtime.stats.stuck_score = max(0, self.runtime.stats.stuck_score - 5)

    def recover_from_out_of_app(self) -> None:
        self.driver.press_back()
        self.driver.wait_idle(800)
        if self.driver.get_foreground_package() != self.config.app.package_name:
            self._ensure_target_foreground(context="out-of-app recovery")

    def _ensure_app_started(self) -> None:
        self._ensure_target_foreground(context="initial launch")

    def _ensure_target_foreground(self, context: str, max_attempts: int = 3) -> None:
        target_package = self.config.app.package_name
        launch_activity = self.config.app.launch_activity
        for attempt in range(1, max_attempts + 1):
            if self.driver.get_foreground_package() == target_package:
                logger.info("foreground ensured context={} attempt={} package={}", context, attempt, target_package)
                return
            if attempt > 1:
                self.driver.stop_app(target_package)
                self.driver.wait_idle(500)
            activity = launch_activity if attempt == 1 and launch_activity else None
            logger.warning(
                "foreground mismatch context={} attempt={} target={} launch_activity={}",
                context,
                attempt,
                target_package,
                activity,
            )
            self.driver.start_app(target_package, activity)
            self.driver.wait_idle(1500)

        current_package = self.driver.get_foreground_package() or "<unknown>"
        logger.error(
            "foreground failed context={} target={} current={} attempts={}",
            context,
            target_package,
            current_package,
            max_attempts,
        )
        raise RuntimeError(
            f"{context}: failed to foreground target app '{target_package}' "
            f"after {max_attempts} attempts (current package: {current_package}). "
            "Please verify app.package_name and app.launch_activity."
        )

    def _mark_visited(self, state_id: str) -> None:
        self.runtime.stats.visited_states[state_id] = self.runtime.stats.visited_states.get(state_id, 0) + 1

    @staticmethod
    def _action_key(state_id: str, action: Action) -> str:
        params = ",".join(f"{key}={value}" for key, value in sorted(action.params.items()))
        return f"{state_id}|{action.action_type.value}|{action.target_element_id}|{params}"
