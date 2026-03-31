from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class AppConfig:
    platform: str = "android"
    package_name: str = "com.demo.app"
    launch_activity: str | None = None

    @property
    def target_app_id(self) -> str:
        return self.package_name

    @target_app_id.setter
    def target_app_id(self, value: str) -> None:
        self.package_name = value

    @property
    def launch_target(self) -> str | None:
        return self.launch_activity

    @launch_target.setter
    def launch_target(self, value: str | None) -> None:
        self.launch_activity = value


@dataclass(slots=True)
class RunConfig:
    max_steps: int = 200
    post_action_wait_ms: int = 1200
    seed: int = 12345
    benchmark_baseline_dir: str = ""
    profile: str = "functional"
    crash_stress_wait_ms: int = 200
    crash_stress_burst_probability: float = 0.25
    crash_stress_burst_min_steps: int = 2
    crash_stress_burst_max_steps: int = 5
    monkey_wait_ms: int = 400
    monkey_ios_wait_ms: int = 260


@dataclass(slots=True)
class IOSConfig:
    wda_url: str = "http://localhost:8100"
    session_create_timeout_sec: float = 30.0
    command_timeout_sec: float = 20.0
    request_retry: int = 2
    keep_session: bool = True
    auto_recreate_session: bool = True
    udid: str = ""


@dataclass(slots=True)
class PolicyConfig:
    epsilon: float = 0.2
    top_k: int = 5
    no_progress_threshold: int = 8
    same_state_threshold: int = 5
    out_of_app_threshold: int = 2
    enable_text_input: bool = True
    enable_long_click: bool = True
    enable_pinch: bool = True
    pinch_zoom_context_boost: float = 0.45
    pinch_non_zoom_penalty: float = 0.6
    enable_restart_app: bool = True
    enable_session_guardrails: bool = True
    enable_login_bootstrap: bool = False
    bootstrap_username: str = ""
    bootstrap_password: str = ""
    bootstrap_max_attempts: int = 3
    bootstrap_retry_interval_steps: int = 20
    prefer_functional_pages: bool = True
    monkey_out_of_app_streak_threshold: int = 2
    monkey_loop_streak_threshold: int = 3
    monkey_perturb_boost: float = 2.0
    monkey_risk_cooldown_steps: int = 3
    monkey_risk_penalty: float = 2.5
    monkey_score_jitter: float = 0.35
    monkey_diversity_state_repeat_threshold: int = 2
    monkey_diversity_state_repeat_penalty: float = 0.6
    monkey_diversity_novel_action_boost: float = 0.8
    monkey_diversity_frontier_boost: float = 0.6
    monkey_ios_permission_fastpath: bool = True
    monkey_ios_permission_boost: float = 2.2
    monkey_ios_restart_penalty: float = 1.8
    monkey_ios_back_penalty: float = 0.5
    monkey_ios_swipe_boost: float = 0.6
    monkey_ios_list_swipe_boost: float = 0.8
    monkey_ios_pinch_boost: float = 0.5
    monkey_ios_static_text_click_penalty: float = 1.0
    monkey_ios_cell_click_boost: float = 0.7
    monkey_ios_back_like_click_penalty: float = 1.1
    monkey_ios_external_jump_penalty: float = 2.0
    monkey_ios_recovery_stuck_threshold: int = 10
    monkey_ios_same_state_recovery_threshold: int = 3
    monkey_ios_permission_recovery_grace_steps: int = 3


@dataclass(slots=True)
class ScoreWeights:
    novelty: float = 2.0
    transition: float = 2.5
    depth: float = 1.8
    business: float = 1.4
    escape: float = 2.2
    input: float = 1.2
    repeat: float = 2.4
    risk: float = 3.0
    stuck: float = 2.6


@dataclass(slots=True)
class SafetyConfig:
    blacklist_keywords: list[str] = field(
        default_factory=lambda: ["删除", "恢复出厂", "付款", "购买", "退出登录"]
    )
    whitelist_keywords: list[str] = field(
        default_factory=lambda: ["下一步", "继续", "允许", "确定", "进入", "登录", "保存"]
    )


@dataclass(slots=True)
class ProjectConfig:
    app: AppConfig = field(default_factory=AppConfig)
    ios: IOSConfig = field(default_factory=IOSConfig)
    run: RunConfig = field(default_factory=RunConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    safety: SafetyConfig = field(default_factory=SafetyConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ProjectConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        app_raw = dict(raw.get("app", {}))
        if "platform" not in app_raw and raw.get("platform") is not None:
            app_raw["platform"] = raw.get("platform")
        ios_raw = dict(raw.get("ios", {}))
        legacy_bundle_id = ios_raw.pop("bundle_id", None)
        if legacy_bundle_id is not None and "package_name" not in app_raw:
            app_raw["package_name"] = legacy_bundle_id
        return cls(
            app=AppConfig(**app_raw),
            ios=IOSConfig(**ios_raw),
            run=RunConfig(**raw.get("run", {})),
            policy=PolicyConfig(**raw.get("policy", {})),
            score_weights=ScoreWeights(**raw.get("score_weights", {})),
            safety=SafetyConfig(**raw.get("safety", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "app": self.app.__dict__,
            "ios": self.ios.__dict__,
            "run": self.run.__dict__,
            "policy": self.policy.__dict__,
            "score_weights": self.score_weights.__dict__,
            "safety": self.safety.__dict__,
        }
