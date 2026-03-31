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
from smart_monkey.services.sidecar_monkey_service import SidecarMonkeyService
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
            target_app_id=self.config.app.target_app_id,
            launch_target=self.config.app.launch_target,
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
        self.sidecar_monkey_service = SidecarMonkeyService(config=config)
        self._recovery_capture_no = 0
        self._crash_stress_burst_left = 0
        self._learning_bandit = LearningBandit(exploration=config.learning.ucb_exploration)
        self._out_of_app_streak = 0
        self._same_state_streak = 0
        self._last_risky_step = -10**9
        self._last_permission_like_step = -10**9
        self._current_step_no = -1
        self._load_learning_state()

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
        if self.sidecar_monkey_service.enabled(self.config.app.platform):
            self.telemetry_service.set_runtime_metric("sidecar_monkey", self.sidecar_monkey_service.summary())

        for step in range(self.config.run.max_steps):
            self._current_step_no = step
            current_state = self.capture_state(step_no=step, suffix="before")
            visit_count = self._mark_visited(current_state.state_id)
            self.runtime_hooks.on_state_captured(current_state, visit_count, self.runtime.utg)
            if current_state.package_name != self.config.app.target_app_id:
                logger.warning(
                    "step={} pre-action state out_of_app package={} expected={} triggering recovery",
                    step,
                    current_state.package_name,
                    self.config.app.target_app_id,
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

            permission_like_state = self._is_permission_like_state(current_state)
            if permission_like_state:
                self._last_permission_like_step = step
            actions = self.extractor.extract(current_state)
            scored_actions = self.scorer.score(current_state, actions, self.runtime.stats)
            scored_actions = self._apply_learning_score_tuning(current_state, scored_actions)
            scored_actions, burst_active, monkey_meta = self._apply_profile_score_tuning(
                scored_actions,
                state=current_state,
            )
            action = self.select_action(scored_actions)
            started_at = time.time()
            result = self.execute_action(action)
            wait_ms = self._effective_post_action_wait_ms()
            self.driver.wait_idle(wait_ms)
            next_state = self.capture_state(step_no=step, suffix="after")
            if self._is_permission_like_state(next_state):
                self._last_permission_like_step = step
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
                out_of_app=next_state.package_name != self.config.app.target_app_id,
                duration_ms=int((time.time() - started_at) * 1000),
                timestamp_ms=next_state.timestamp_ms,
            )
            if self._is_high_risk_action(action):
                self._last_risky_step = step
            self._update_monkey_runtime_signals(transition)

            reward = self._compute_learning_reward(current_state, action, next_state, transition)
            self._learning_bandit.observe_last(reward)
            self.telemetry_service.set_runtime_metric(
                "learning",
                self._learning_bandit.summary(limit=self.config.learning.top_arms_report_limit),
            )

            self.update_runtime(current_state, action, transition)
            ios_recovery_grace_active = self._is_ios_permission_recovery_grace_active()
            super().persist_step(
                step,
                current_state,
                action,
                transition,
                next_state,
                extra_step_fields={
                    "platform": self.config.app.platform,
                    "run_profile": self._run_profile(),
                    "post_action_wait_ms": wait_ms,
                    "crash_stress_mode": crash_stress_mode,
                    "crash_stress_burst_active": burst_active,
                    "monkey_mode": monkey_meta["enabled"],
                    "monkey_escape_boosted": monkey_meta["escape_boosted"],
                    "monkey_risk_cooldown_applied": monkey_meta["risk_cooldown_applied"],
                    "monkey_diversity_boosted": monkey_meta["diversity_boosted"],
                    "monkey_ios_tuning_applied": monkey_meta["ios_tuning_applied"],
                    "monkey_ios_permission_fastpath_applied": monkey_meta["permission_fastpath_applied"],
                    "monkey_out_of_app_streak": self._out_of_app_streak,
                    "monkey_same_state_streak": self._same_state_streak,
                    "permission_like_state": permission_like_state,
                    "monkey_ios_recovery_grace_active": ios_recovery_grace_active,
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

            recovery_needed = self._should_trigger_recovery(previous_state, current_state, next_state, transition)
            if recovery_needed:
                logger.warning(
                    "step={} recovery trigger out_of_app={} stuck_score={}",
                    step,
                    transition.out_of_app,
                    self.runtime.stats.stuck_score,
                )
                self._recover_runtime(step, current_state.state_id, transition.out_of_app)

            sidecar_triggered = self._maybe_run_sidecar_monkey(step)
            previous_state = None if sidecar_triggered else next_state

        if self.sidecar_monkey_service.enabled(self.config.app.platform):
            self.telemetry_service.set_runtime_metric("sidecar_monkey", self.sidecar_monkey_service.summary())
        artifacts = self.orchestration_service.finish_run(self.recorder, self.runtime.utg)
        self._persist_learning_state()
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
        if profile in {"functional", "crash_stress", "monkey_compatible"}:
            return profile
        return "functional"

    def _is_crash_stress(self) -> bool:
        return self._run_profile() == "crash_stress"

    def _is_monkey_compatible(self) -> bool:
        return self._run_profile() == "monkey_compatible"

    def _effective_post_action_wait_ms(self) -> int:
        default_wait = int(getattr(self.config.run, "post_action_wait_ms", 1200))
        if self._is_monkey_compatible():
            if self._is_ios_platform():
                monkey_wait = int(
                    getattr(
                        self.config.run,
                        "monkey_ios_wait_ms",
                        getattr(self.config.run, "monkey_wait_ms", default_wait),
                    )
                )
            else:
                monkey_wait = int(getattr(self.config.run, "monkey_wait_ms", default_wait))
            return max(50, monkey_wait)
        if not self._is_crash_stress():
            return max(50, default_wait)
        stress_wait = int(getattr(self.config.run, "crash_stress_wait_ms", default_wait))
        return max(50, stress_wait)

    def _apply_profile_score_tuning(
        self,
        actions: list[Action],
        state: DeviceState | None = None,
    ) -> tuple[list[Action], bool, dict[str, bool]]:
        monkey_meta = {
            "enabled": self._is_monkey_compatible(),
            "escape_boosted": False,
            "risk_cooldown_applied": False,
            "diversity_boosted": False,
            "ios_tuning_applied": False,
            "permission_fastpath_applied": False,
        }
        if not actions:
            return actions, False, monkey_meta
        if self._is_monkey_compatible():
            actions, monkey_meta = self._apply_monkey_compatible_tuning(actions, state=state)
        if not self._is_crash_stress():
            return sorted(actions, key=lambda item: item.score, reverse=True), False, monkey_meta
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
        return sorted(actions, key=lambda item: item.score, reverse=True), burst_active, monkey_meta

    def _apply_monkey_compatible_tuning(
        self,
        actions: list[Action],
        state: DeviceState | None = None,
    ) -> tuple[list[Action], dict[str, bool]]:
        loop_threshold = int(getattr(self.config.policy, "monkey_loop_streak_threshold", 3))
        out_threshold = int(getattr(self.config.policy, "monkey_out_of_app_streak_threshold", 2))
        perturb_boost = float(getattr(self.config.policy, "monkey_perturb_boost", 2.0))
        risk_cooldown = int(getattr(self.config.policy, "monkey_risk_cooldown_steps", 3))
        risk_penalty = float(getattr(self.config.policy, "monkey_risk_penalty", 2.5))
        jitter = max(0.0, float(getattr(self.config.policy, "monkey_score_jitter", 0.35)))
        repeat_threshold = int(getattr(self.config.policy, "monkey_diversity_state_repeat_threshold", 2))
        repeat_penalty = float(getattr(self.config.policy, "monkey_diversity_state_repeat_penalty", 0.6))
        novel_action_boost = float(getattr(self.config.policy, "monkey_diversity_novel_action_boost", 0.8))
        frontier_boost = float(getattr(self.config.policy, "monkey_diversity_frontier_boost", 0.6))
        ios_permission_fastpath = bool(getattr(self.config.policy, "monkey_ios_permission_fastpath", True))
        ios_permission_boost = float(getattr(self.config.policy, "monkey_ios_permission_boost", 2.2))
        ios_restart_penalty = float(getattr(self.config.policy, "monkey_ios_restart_penalty", 1.8))
        ios_back_penalty = float(getattr(self.config.policy, "monkey_ios_back_penalty", 0.5))
        ios_swipe_boost = float(getattr(self.config.policy, "monkey_ios_swipe_boost", 0.6))
        ios_list_swipe_boost = float(getattr(self.config.policy, "monkey_ios_list_swipe_boost", 0.8))
        ios_pinch_boost = float(getattr(self.config.policy, "monkey_ios_pinch_boost", 0.5))
        ios_static_text_click_penalty = float(getattr(self.config.policy, "monkey_ios_static_text_click_penalty", 1.0))
        ios_cell_click_boost = float(getattr(self.config.policy, "monkey_ios_cell_click_boost", 0.7))
        ios_back_like_click_penalty = float(getattr(self.config.policy, "monkey_ios_back_like_click_penalty", 1.1))
        ios_external_jump_penalty = float(getattr(self.config.policy, "monkey_ios_external_jump_penalty", 2.0))
        perturb_active = self._same_state_streak >= max(1, loop_threshold) or self._out_of_app_streak >= max(1, out_threshold)
        cooldown_active = (self._current_step_no - self._last_risky_step) <= max(0, risk_cooldown)
        permission_like_state = self._is_permission_like_state(state)
        ios_platform = self._is_ios_platform()
        elements_by_id = {element.element_id: element for element in (state.elements if state is not None else [])}
        state_flags = {str(flag).lower() for flag in state.app_flags} if state is not None else set()
        exploration_types = {"click", "swipe", "input", "long_click", "pinch_in", "pinch_out"}
        exploration_bias = max(0.0, frontier_boost * 0.5)
        wait_penalty = max(0.2, repeat_penalty * 0.5)
        restart_penalty = max(0.4, risk_penalty * 0.4)
        back_penalty = max(0.2, risk_penalty * 0.2)
        meta = {
            "enabled": True,
            "escape_boosted": False,
            "risk_cooldown_applied": False,
            "diversity_boosted": False,
            "ios_tuning_applied": False,
            "permission_fastpath_applied": False,
        }
        source_state_id = state.state_id if state is not None else (actions[0].source_state_id if actions else "")
        for action in actions:
            action_type = action.action_type.value
            if perturb_active and action_type in {"back", "swipe", "restart_app", "wait"}:
                action.score += perturb_boost
                meta["escape_boosted"] = True
            if not perturb_active:
                if action_type in exploration_types:
                    action.score += exploration_bias
                    meta["diversity_boosted"] = True
                elif action_type == "wait":
                    action.score -= wait_penalty
                elif action_type == "restart_app":
                    action.score -= restart_penalty
                elif action_type == "back":
                    action.score -= back_penalty
            if cooldown_active and self._is_high_risk_action(action):
                action.score -= risk_penalty
                meta["risk_cooldown_applied"] = True
            if self._same_state_streak >= max(1, repeat_threshold):
                action_key = self._action_key(source_state_id, action)
                history = self.runtime.stats.action_histories.get(action_key)
                execute_count = history.execute_count if history is not None else 0
                unchanged_count = history.unchanged_count if history is not None else 0
                if execute_count == 0:
                    action.score += novel_action_boost
                    meta["diversity_boosted"] = True
                else:
                    penalty_scale = min(2.0, 0.5 + unchanged_count * 0.4)
                    action.score -= repeat_penalty * penalty_scale
                    meta["diversity_boosted"] = True
                frontier_gain = max(0.0, 1.0 - min(1.0, execute_count * 0.2))
                if frontier_gain > 0.0:
                    action.score += frontier_boost * frontier_gain
                    meta["diversity_boosted"] = True
            if ios_platform:
                if action_type == "restart_app":
                    action.score -= max(0.0, ios_restart_penalty)
                    meta["ios_tuning_applied"] = True
                elif action_type == "back":
                    action.score -= max(0.0, ios_back_penalty)
                    meta["ios_tuning_applied"] = True
                elif action_type == "swipe":
                    action.score += max(0.0, ios_swipe_boost)
                    if "list_page" in state_flags:
                        action.score += max(0.0, ios_list_swipe_boost)
                        meta["diversity_boosted"] = True
                    meta["ios_tuning_applied"] = True
                elif action_type in {"pinch_in", "pinch_out"}:
                    action.score += max(0.0, ios_pinch_boost)
                    meta["ios_tuning_applied"] = True
                elif action_type == "click" and action.target_element_id:
                    target_element = elements_by_id.get(str(action.target_element_id))
                    target_class = str(getattr(target_element, "class_name", "") or "").lower()
                    if target_class == "xcuielementtypestatictext":
                        action.score -= max(0.0, ios_static_text_click_penalty)
                        meta["ios_tuning_applied"] = True
                    elif target_class == "xcuielementtypecell":
                        action.score += max(0.0, ios_cell_click_boost)
                        meta["ios_tuning_applied"] = True
                    if target_element is not None and self._is_ios_back_like_element(target_element):
                        action.score -= max(0.0, ios_back_like_click_penalty)
                        meta["ios_tuning_applied"] = True
                    if target_element is not None and self._is_ios_external_jump_element(target_element):
                        action.score -= max(0.0, ios_external_jump_penalty)
                        meta["risk_cooldown_applied"] = True
                        meta["ios_tuning_applied"] = True
                if permission_like_state and ios_permission_fastpath:
                    if self._is_permission_accept_action(action):
                        action.score += max(0.0, ios_permission_boost)
                        meta["permission_fastpath_applied"] = True
                    elif action_type in {"wait", "restart_app", "back"}:
                        action.score -= max(0.6, ios_permission_boost * 0.6)
                        meta["ios_tuning_applied"] = True
            if jitter > 0.0:
                action.score += random.uniform(-jitter, jitter)
        return actions, meta

    def _update_monkey_runtime_signals(self, transition: Transition) -> None:
        if transition.out_of_app:
            self._out_of_app_streak += 1
        else:
            self._out_of_app_streak = 0
        if transition.changed:
            self._same_state_streak = 0
        else:
            self._same_state_streak += 1

    def _is_high_risk_action(self, action: Action) -> bool:
        tags = {str(tag).lower() for tag in action.tags}
        risk_tokens = {item.lower() for item in self.config.safety.blacklist_keywords}
        if tags & risk_tokens:
            return True
        return any(token in tags for token in ("logout", "signout", "删除", "付款", "购买", "退出登录"))

    def _is_permission_accept_action(self, action: Action) -> bool:
        tokens = {str(tag).lower() for tag in action.tags}
        target = str(action.target_element_id or "").lower()
        params_blob = " ".join(f"{key}={value}" for key, value in sorted(action.params.items())).lower()
        blob = " ".join([target, params_blob, " ".join(sorted(tokens))]).strip()
        allow_tokens = (
            "allow",
            "允许",
            "继续",
            "confirm",
            "ok",
            "while using",
            "仅在使用期间",
            "始终允许",
        )
        deny_tokens = ("don't allow", "拒绝", "不允许", "deny", "cancel", "稍后")
        if any(token in blob for token in deny_tokens):
            return False
        return any(token in blob for token in allow_tokens)

    @staticmethod
    def _is_ios_back_like_element(element: object) -> bool:
        text = str(getattr(element, "text", "") or "").lower()
        desc = str(getattr(element, "content_desc", "") or "").lower()
        resource_id = str(getattr(element, "resource_id", "") or "").lower()
        class_name = str(getattr(element, "class_name", "") or "").lower()
        blob = " ".join([text, desc, resource_id, class_name])
        back_tokens = ("back", "返回", "arrow back", "navclose", "close", "ic_close")
        return any(token in blob for token in back_tokens)

    @staticmethod
    def _is_ios_external_jump_element(element: object) -> bool:
        text = str(getattr(element, "text", "") or "").lower()
        desc = str(getattr(element, "content_desc", "") or "").lower()
        resource_id = str(getattr(element, "resource_id", "") or "").lower()
        blob = " ".join([text, desc, resource_id])
        external_tokens = ("相册", "拍照", "camera", "photo", "gallery", "album")
        return any(token in blob for token in external_tokens)

    def _is_permission_like_state(self, state: DeviceState | None) -> bool:
        if state is None:
            return False
        popup_flags = {str(flag).lower() for flag in state.popup_flags}
        system_flags = {str(flag).lower() for flag in state.system_flags}
        if "permission_like" in popup_flags or "permission_controller" in system_flags:
            return True
        text_blob = self._state_text_blob(state)
        permission_tokens = ("allow", "don't allow", "允许", "拒绝", "访问", "访问权限", "仅在使用期间")
        return any(token in text_blob for token in permission_tokens)

    def _is_ios_platform(self) -> bool:
        return str(getattr(self.config.app, "platform", "android")).strip().lower() == "ios"

    def _is_ios_permission_recovery_grace_active(self) -> bool:
        if not (self._is_monkey_compatible() and self._is_ios_platform()):
            return False
        grace_steps = int(getattr(self.config.policy, "monkey_ios_permission_recovery_grace_steps", 3))
        return (self._current_step_no - self._last_permission_like_step) <= max(0, grace_steps)

    def _should_trigger_recovery(
        self,
        previous_state: DeviceState | None,
        current_state: DeviceState,
        next_state: DeviceState,
        transition: Transition,
    ) -> bool:
        if transition.out_of_app:
            return True
        if not self.should_escape(previous_state, current_state, next_state, transition):
            return False
        if not (self._is_monkey_compatible() and self._is_ios_platform()):
            return True
        if self._is_ios_permission_recovery_grace_active():
            return False
        stuck_threshold = int(getattr(self.config.policy, "monkey_ios_recovery_stuck_threshold", 10))
        same_state_threshold = int(getattr(self.config.policy, "monkey_ios_same_state_recovery_threshold", 3))
        return self.runtime.stats.stuck_score >= max(0, stuck_threshold) or self._same_state_streak >= max(1, same_state_threshold)

    def _maybe_run_sidecar_monkey(self, step: int) -> bool:
        if not self.sidecar_monkey_service.enabled(self.config.app.platform):
            return False
        result = self.sidecar_monkey_service.run_batch(
            step=step,
            driver=self.driver,
            target_app_id=self.config.app.target_app_id,
        )
        if result is None:
            return False

        sidecar_recovery_error: str | None = None
        if self.driver.get_foreground_package() != self.config.app.target_app_id:
            try:
                self._ensure_target_foreground(context=f"sidecar monkey batch#{result.batch_no}")
                self.sidecar_monkey_service.mark_recovered(result)
            except RuntimeError as exc:
                sidecar_recovery_error = str(exc)
                logger.error(
                    "sidecar monkey foreground recovery failed batch={} step={} error={}",
                    result.batch_no,
                    step,
                    sidecar_recovery_error,
                )
        self.recorder.record_step(
            {
                "step": -1,
                "sidecar_monkey_batch": True,
                "sidecar_trigger_step": result.triggered_step,
                "sidecar_batch_no": result.batch_no,
                "sidecar_command": result.command,
                "sidecar_seed": result.seed,
                "sidecar_events_requested": result.events_requested,
                "sidecar_events_injected": result.events_injected,
                "sidecar_exit_code": result.exit_code,
                "sidecar_success": result.success,
                "sidecar_recovered_to_target": result.recovered_to_target,
                "sidecar_recovery_failed": sidecar_recovery_error is not None,
                "sidecar_recovery_error": sidecar_recovery_error,
                "sidecar_stdout_tail": result.stdout_tail,
                "sidecar_stderr_tail": result.stderr_tail,
                "sidecar_skipped_reason": result.skipped_reason,
            }
        )
        self.telemetry_service.set_runtime_metric("sidecar_monkey", self.sidecar_monkey_service.summary())
        # sidecar 扰动会改变页面上下文，重置主轨 streak 信号避免误触发偏置。
        self._out_of_app_streak = 0
        self._same_state_streak = 0
        return True

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

    def _learning_persistence_enabled(self) -> bool:
        return bool(getattr(self.config.learning, "persistence_enabled", False))

    def _learning_state_path(self) -> str:
        return str(getattr(self.config.learning, "state_path", "output/learning_state.json") or "output/learning_state.json")

    def _load_learning_state(self) -> None:
        if not (self._learning_enabled() and self._learning_persistence_enabled()):
            return
        state_path = self._learning_state_path()
        loaded = self._learning_bandit.load_from_path(state_path)
        if loaded:
            logger.info("learning state loaded path={} observations={}", state_path, self._learning_bandit.total_observations)

    def _persist_learning_state(self) -> None:
        if not (self._learning_enabled() and self._learning_persistence_enabled()):
            return
        min_obs = int(getattr(self.config.learning, "min_observations_to_persist", 20))
        if self._learning_bandit.total_observations < max(1, min_obs):
            return
        state_path = self._learning_state_path()
        saved = self._learning_bandit.save_to_path(state_path)
        if saved:
            logger.info("learning state saved path={} observations={}", state_path, self._learning_bandit.total_observations)

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
