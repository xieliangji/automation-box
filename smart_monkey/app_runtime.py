from __future__ import annotations

import random
import time
from pathlib import Path

from loguru import logger

from smart_monkey.action.extractor_runtime import RuntimeActionExtractor
from smart_monkey.action.scorer_runtime import RuntimeActionScorer
from smart_monkey.app_watchdog import WatchdogSmartMonkeyApp
from smart_monkey.runtime_config import RuntimeConfig
from smart_monkey.device.base import DeviceDriver
from smart_monkey.graph.backtrack import BacktrackHelper
from smart_monkey.graph.checkpoint import CheckpointManager
from smart_monkey.models import Action, DeviceState, Transition
from smart_monkey.services.orchestration_service import OrchestrationService
from smart_monkey.services.learning_bandit import LearningBandit
from smart_monkey.services.login_bootstrap_service import LoginBootstrapService
from smart_monkey.services.recovery_audit_service import RecoveryAuditService
from smart_monkey.services.recovery_service import RecoveryExecutionResult, RecoveryService
from smart_monkey.services.report_service import ReportService
from smart_monkey.services.runtime_hooks import RuntimeHooks
from smart_monkey.services.telemetry_service import TelemetryService
from smart_monkey.services.watchdog_service import WatchdogService


class SmartMonkeyAppRuntime(WatchdogSmartMonkeyApp):
    """当前唯一维护的运行时主流程。"""

    def __init__(self, driver: DeviceDriver, config: RuntimeConfig, output_dir: str | Path = "output") -> None:
        super().__init__(driver=driver, config=config, output_dir=output_dir)
        if config.features.use_runtime_extractor:
            self.extractor = RuntimeActionExtractor(config)
        if config.features.use_runtime_scorer:
            self.scorer = RuntimeActionScorer(config)

        self.checkpoint_manager = CheckpointManager(self.output_dir)
        self.backtrack_helper = BacktrackHelper(self.checkpoint_manager, self.output_dir)
        self.telemetry_service = TelemetryService(
            output_dir=self.output_dir,
            snapshot_every_n_steps=config.snapshot.every_n_steps,
            snapshot_enabled=config.snapshot.enabled,
            export_replay=config.features.export_replay,
        )
        self.recovery_service = RecoveryService(
            output_dir=self.output_dir,
            package_name=self.config.app.package_name,
            launch_activity=self.config.app.launch_activity,
            checkpoint_manager=self.checkpoint_manager,
            backtrack_helper=self.backtrack_helper,
        )
        baseline_dir = config.run.benchmark_baseline_dir.strip() if getattr(config.run, "benchmark_baseline_dir", "") else ""
        self.report_service = ReportService(self.output_dir, baseline_dir=baseline_dir or None)
        self.runtime_hooks = RuntimeHooks(
            config=config,
            checkpoint_manager=self.checkpoint_manager,
            telemetry_service=self.telemetry_service,
            report_service=self.report_service,
        )
        self.watchdog_service = WatchdogService(config=config, watchdog=self.watchdog, telemetry_service=self.telemetry_service)
        self.recovery_audit_service = RecoveryAuditService(self.output_dir)
        self.login_bootstrap_service = LoginBootstrapService(config=config)
        self.orchestration_service = OrchestrationService(
            config=config,
            runtime_hooks=self.runtime_hooks,
            watchdog_service=self.watchdog_service,
            recovery_audit_service=self.recovery_audit_service,
            login_bootstrap_service=self.login_bootstrap_service,
        )
        self._recovery_capture_no = 0
        self._crash_stress_burst_left = 0
        self._learning_bandit = LearningBandit(exploration=config.learning.ucb_exploration)

    def run(self) -> None:
        self.runtime_hooks.on_run_start(self.driver, self.watchdog)
        self._ensure_app_started()
        previous_state = None
        logger.info(
            "runtime run started max_steps={} profile={} wait_ms={}",
            self.config.run.max_steps,
            self._run_profile(),
            self._effective_post_action_wait_ms(),
        )

        for step in range(self.config.run.max_steps):
            current_state = self.capture_state(step_no=step, suffix="before")
            visit_count = self._mark_visited(current_state.state_id)
            self.runtime_hooks.on_state_captured(current_state, visit_count, self.runtime.utg)
            if current_state.package_name != self.config.app.package_name:
                logger.warning(
                    "step={} pre-action state out_of_app package={} expected={} triggering recovery",
                    step,
                    current_state.package_name,
                    self.config.app.package_name,
                )
                self._recover_runtime(step, current_state.state_id, True)
                previous_state = current_state
                continue
            bootstrap_attempt = self.orchestration_service.before_step(
                step=step,
                state=current_state,
                driver=self.driver,
                recorder=self.recorder,
            )
            if bootstrap_attempt is not None and bootstrap_attempt.status == "attempted":
                self.driver.wait_idle(self._effective_post_action_wait_ms())
                current_state = self.capture_state(step_no=step, suffix="bootstrap")
                visit_count = self._mark_visited(current_state.state_id)
                self.runtime_hooks.on_state_captured(current_state, visit_count, self.runtime.utg)

            actions = self.extractor.extract(current_state)
            scored_actions = self.scorer.score(current_state, actions, self.runtime.stats)
            scored_actions = self._apply_learning_score_tuning(current_state, scored_actions)
            scored_actions, burst_active = self._apply_profile_score_tuning(scored_actions)
            action = self.select_action(scored_actions)
            started_at = time.time()
            result = self.execute_action(action)
            wait_ms = self._effective_post_action_wait_ms()
            self.driver.wait_idle(wait_ms)
            next_state = self.capture_state(step_no=step, suffix="after")
            crash_stress_mode = self._is_crash_stress()
            crash_signal = self._looks_like_crash_signal(next_state)
            anr_signal = self._looks_like_anr_signal(next_state)

            transition = Transition(
                transition_id=action.action_id,
                from_state_id=current_state.state_id,
                to_state_id=next_state.state_id,
                action_id=action.action_id,
                success=result.success,
                changed=current_state.state_id != next_state.state_id,
                crash=crash_signal,
                anr=anr_signal,
                out_of_app=next_state.package_name != self.config.app.package_name,
                duration_ms=int((time.time() - started_at) * 1000),
                timestamp_ms=next_state.timestamp_ms,
            )

            reward = self._compute_learning_reward(current_state, action, next_state, transition)
            self._learning_bandit.observe_last(reward)
            self.telemetry_service.set_runtime_metric(
                "learning",
                self._learning_bandit.summary(limit=self.config.learning.top_arms_report_limit),
            )

            self.update_runtime(current_state, action, transition)
            super().persist_step(
                step,
                current_state,
                action,
                transition,
                next_state,
                extra_step_fields={
                    "run_profile": self._run_profile(),
                    "post_action_wait_ms": wait_ms,
                    "crash_stress_mode": crash_stress_mode,
                    "crash_stress_burst_active": burst_active,
                    "crash_signal": crash_signal,
                    "anr_signal": anr_signal,
                    "learning_enabled": self._learning_enabled(),
                    "learning_reward": round(reward, 4),
                    "learning_arm_key": self._learning_arm_key(
                        current_state,
                        action,
                        use_module_bucket=bool(getattr(self.config.learning, "module_bucket_enabled", True)),
                    ),
                },
            )
            self.orchestration_service.after_transition(
                step=step,
                driver=self.driver,
                recorder=self.recorder,
                previous_state=previous_state,
                current_state=current_state,
                next_state=next_state,
                action=action,
                transition=transition,
            )

            if transition.out_of_app or self.should_escape(previous_state, current_state, next_state, transition):
                logger.warning(
                    "step={} recovery trigger out_of_app={} stuck_score={}",
                    step,
                    transition.out_of_app,
                    self.runtime.stats.stuck_score,
                )
                self._recover_runtime(step, current_state.state_id, transition.out_of_app)

            previous_state = next_state

        artifacts = self.orchestration_service.finish_run(self.recorder, self.runtime.utg)
        logger.info("runtime run finished artifacts={}", artifacts)

    def _recover_runtime(self, step: int, current_state_id: str, out_of_app: bool) -> None:
        self._recovery_capture_no += 1
        before_stuck_score = self.runtime.stats.stuck_score
        logger.warning(
            "recovery start step={} state={} out_of_app={} stuck_score={}",
            step,
            current_state_id,
            out_of_app,
            before_stuck_score,
        )
        recovery_result: RecoveryExecutionResult = self.recovery_service.recover(
            current_state_id=current_state_id,
            stuck_score=self.runtime.stats.stuck_score,
            out_of_app=out_of_app,
            driver=self.driver,
            capture_state_fn=lambda: self.capture_state(step_no=900000 + self._recovery_capture_no, suffix="recovery"),
            avoid_login_checkpoint=self.config.policy.prefer_functional_pages,
        )
        self.runtime.stats.stuck_score = max(0, self.runtime.stats.stuck_score - 5)
        self.orchestration_service.record_recovery(
            recorder=self.recorder,
            at_step=step,
            before_stuck_score=before_stuck_score,
            after_stuck_score=self.runtime.stats.stuck_score,
            recovery_result=recovery_result,
        )
        logger.warning(
            "recovery done step={} strategy={} in_target_app={} after_stuck_score={}",
            step,
            recovery_result.plan.strategy,
            recovery_result.validation.in_target_app if recovery_result.validation else None,
            self.runtime.stats.stuck_score,
        )

    def _mark_visited(self, state_id: str) -> int:
        count = self.runtime.stats.visited_states.get(state_id, 0) + 1
        self.runtime.stats.visited_states[state_id] = count
        return count

    def _run_profile(self) -> str:
        profile = str(getattr(self.config.run, "profile", "functional") or "functional").strip().lower()
        if profile in {"functional", "crash_stress"}:
            return profile
        return "functional"

    def _is_crash_stress(self) -> bool:
        return self._run_profile() == "crash_stress"

    def _effective_post_action_wait_ms(self) -> int:
        default_wait = int(getattr(self.config.run, "post_action_wait_ms", 1200))
        if not self._is_crash_stress():
            return max(50, default_wait)
        stress_wait = int(getattr(self.config.run, "crash_stress_wait_ms", default_wait))
        return max(50, stress_wait)

    def _apply_profile_score_tuning(self, actions: list[Action]) -> tuple[list[Action], bool]:
        if not self._is_crash_stress() or not actions:
            return actions, False
        self._maybe_start_crash_burst(actions)
        burst_active = self._crash_stress_burst_left > 0
        for action in actions:
            if burst_active and action.action_type.value in {"click", "swipe", "input", "pinch_in", "pinch_out"}:
                action.score += 2.5
            if burst_active and action.action_type.value in {"restart_app", "back"}:
                action.score -= 1.5
            if action.action_type.value == "wait":
                action.score -= 0.8
            elif action.action_type.value in {"click", "swipe", "input", "long_click", "pinch_in", "pinch_out"}:
                action.score += 0.6
        if burst_active:
            self._crash_stress_burst_left -= 1
        return sorted(actions, key=lambda item: item.score, reverse=True), burst_active

    def _apply_learning_score_tuning(self, state: DeviceState, actions: list[Action]) -> list[Action]:
        if not self._learning_enabled() or not actions:
            return actions
        alpha = self._learning_alpha()
        scored_arms: list[tuple[str, float]] = []
        for action in actions:
            arm_key = self._learning_arm_key(
                state,
                action,
                use_module_bucket=bool(getattr(self.config.learning, "module_bucket_enabled", True)),
            )
            learned_score = self._learning_bandit.score(arm_key)
            action.score_detail["learned_ucb"] = round(learned_score, 4)
            action.score_detail["rule_score_before_learning"] = round(action.score, 4)
            action.score_detail["learning_arm_key"] = arm_key
            action.score = alpha * action.score + (1.0 - alpha) * learned_score
            action.score_detail["score_after_learning"] = round(action.score, 4)
            scored_arms.append((arm_key, action.score))
        self._learning_bandit.select(scored_arms)
        return sorted(actions, key=lambda item: item.score, reverse=True)

    def _compute_learning_reward(
        self,
        current_state: DeviceState,
        action: Action,
        next_state: DeviceState,
        transition: Transition,
    ) -> float:
        if not self._learning_enabled():
            return 0.0
        reward = 0.0
        if transition.changed:
            reward += float(self.config.learning.reward_changed_state)
        else:
            reward -= float(self.config.learning.penalty_unchanged)
        if transition.out_of_app:
            reward -= float(self.config.learning.penalty_out_of_app)
        flags = {str(flag).lower() for flag in next_state.app_flags}
        if {"list_page", "form_page", "webview"} & flags:
            reward += float(self.config.learning.reward_functional_page)
        if transition.crash or transition.anr:
            reward += float(self.config.learning.reward_issue_signal)
        if next_state.state_id not in self.runtime.stats.visited_states:
            reward += float(self.config.learning.reward_novel_state)
        if action.action_type.value in {"wait", "back", "restart_app", "home"}:
            reward -= float(self.config.learning.penalty_system_action)
        if current_state.state_id == next_state.state_id:
            reward -= float(self.config.learning.penalty_recent_loop)
        return reward

    def _learning_enabled(self) -> bool:
        return bool(getattr(self.config.learning, "enabled", False))

    def _learning_alpha(self) -> float:
        alpha = float(getattr(self.config.learning, "alpha", 0.8))
        return max(0.0, min(1.0, alpha))

    @staticmethod
    def _learning_arm_key(state: DeviceState, action: Action, use_module_bucket: bool = True) -> str:
        flags = {str(flag).lower() for flag in state.app_flags}
        page_bucket = SmartMonkeyAppRuntime._page_bucket(flags, state, action, use_module_bucket=use_module_bucket)
        action_bucket = action.action_type.value
        target_bucket = SmartMonkeyAppRuntime._target_bucket(action)
        tag_bucket = SmartMonkeyAppRuntime._tag_bucket(action.tags)
        return f"{page_bucket}|{action_bucket}|{target_bucket}|{tag_bucket}"

    @staticmethod
    def _page_bucket(flags: set[str], state: DeviceState, action: Action, use_module_bucket: bool = True) -> str:
        if "login_page" in flags:
            return "login"
        if use_module_bucket:
            module_bucket = SmartMonkeyAppRuntime._module_bucket(state, action)
            if module_bucket:
                return module_bucket
        if "form_page" in flags:
            return "form"
        if "list_page" in flags:
            return "list"
        if "webview" in flags:
            return "webview"
        return "generic"

    @staticmethod
    def _module_bucket(state: DeviceState, action: Action) -> str:
        activity = str(state.activity_name or "").lower()
        tokens = set()
        for element in state.elements:
            for token in element.semantic_tokens():
                tokens.add(str(token).lower())
        tokens.update(str(tag).lower() for tag in action.tags)
        if "device" in activity or tokens & {"device", "设备"}:
            return "module_device"
        if "setting" in activity or tokens & {"setting", "settings", "设置"}:
            return "module_settings"
        if "account" in activity or tokens & {"account", "账号", "profile", "我的"}:
            return "module_account"
        if "message" in activity or tokens & {"message", "消息", "通知", "notification"}:
            return "module_message"
        if "scene" in activity or tokens & {"scene", "场景", "automation", "自动化"}:
            return "module_scene"
        if "home" in activity or tokens & {"home", "首页", "tab_home"}:
            return "module_home"
        return ""

    @staticmethod
    def _target_bucket(action: Action) -> str:
        target = str(action.target_element_id or "").lower()
        if not target:
            return "system"
        if "btn" in target or "button" in target:
            return "button"
        if "input" in target or "edit" in target:
            return "input"
        if "tab" in target:
            return "tab"
        return "element"

    @staticmethod
    def _tag_bucket(tags: set[str]) -> str:
        lowered = {str(tag).lower() for tag in tags}
        if lowered & {"login", "登录", "password", "密码", "account", "账号"}:
            return "auth"
        if lowered & {"detail", "details", "详情", "next", "下一步"}:
            return "detail"
        if lowered & {"save", "保存", "submit", "提交", "done"}:
            return "submit"
        if lowered & {"scroll", "swipe", "pinch", "zoom", "pinch_in", "pinch_out"}:
            return "scroll"
        return "generic"

    def _maybe_start_crash_burst(self, actions: list[Action]) -> None:
        if self._crash_stress_burst_left > 0:
            return
        probability = float(getattr(self.config.run, "crash_stress_burst_probability", 0.25))
        probability = max(0.0, min(1.0, probability))
        if probability <= 0.0:
            return
        if random.random() > probability:
            return
        burst_candidates = [
            action for action in actions if action.action_type.value in {"click", "swipe", "input", "pinch_in", "pinch_out"}
        ]
        if not burst_candidates:
            return
        min_steps = int(getattr(self.config.run, "crash_stress_burst_min_steps", 2))
        max_steps = int(getattr(self.config.run, "crash_stress_burst_max_steps", 5))
        min_steps = max(1, min_steps)
        max_steps = max(min_steps, max_steps)
        self._crash_stress_burst_left = random.randint(min_steps, max_steps)

    @staticmethod
    def _looks_like_crash_signal(state: DeviceState) -> bool:
        flags = {str(flag).lower() for flag in state.system_flags}
        if "crash_dialog" in flags:
            return True
        text_blob = SmartMonkeyAppRuntime._state_text_blob(state)
        return any(
            token in text_blob
            for token in (
                "has stopped",
                "keeps stopping",
                "is crashing",
                "已停止运行",
                "停止运行",
                "崩溃",
                "闪退",
            )
        )

    @staticmethod
    def _looks_like_anr_signal(state: DeviceState) -> bool:
        flags = {str(flag).lower() for flag in state.system_flags}
        if "app_not_responding" in flags or "anr_dialog" in flags:
            return True
        text_blob = SmartMonkeyAppRuntime._state_text_blob(state)
        return any(token in text_blob for token in ("isn't responding", "not responding", "无响应", "没有响应"))

    @staticmethod
    def _state_text_blob(state: DeviceState) -> str:
        return " ".join(
            f"{element.text or ''} {element.content_desc or ''}".lower() for element in state.elements if element is not None
        )
