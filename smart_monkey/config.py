from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class AppConfig:
    package_name: str = "com.demo.app"
    launch_activity: str | None = None


@dataclass(slots=True)
class RunConfig:
    max_steps: int = 200
    post_action_wait_ms: int = 1200
    seed: int = 12345
    benchmark_baseline_dir: str = ""


@dataclass(slots=True)
class PolicyConfig:
    epsilon: float = 0.2
    top_k: int = 5
    no_progress_threshold: int = 8
    same_state_threshold: int = 5
    out_of_app_threshold: int = 2
    enable_text_input: bool = True
    enable_long_click: bool = True
    enable_restart_app: bool = True
    enable_session_guardrails: bool = True
    enable_login_bootstrap: bool = False
    bootstrap_username: str = ""
    bootstrap_password: str = ""
    bootstrap_max_attempts: int = 3
    bootstrap_retry_interval_steps: int = 20
    prefer_functional_pages: bool = True


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
    run: RunConfig = field(default_factory=RunConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    safety: SafetyConfig = field(default_factory=SafetyConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ProjectConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(
            app=AppConfig(**raw.get("app", {})),
            run=RunConfig(**raw.get("run", {})),
            policy=PolicyConfig(**raw.get("policy", {})),
            score_weights=ScoreWeights(**raw.get("score_weights", {})),
            safety=SafetyConfig(**raw.get("safety", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "app": self.app.__dict__,
            "run": self.run.__dict__,
            "policy": self.policy.__dict__,
            "score_weights": self.score_weights.__dict__,
            "safety": self.safety.__dict__,
        }
