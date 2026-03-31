from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from smart_monkey.config import AppConfig, IOSConfig, PolicyConfig, RunConfig, SafetyConfig, ScoreWeights
from smart_monkey.platform_profiles import normalize_platform


@dataclass(slots=True)
class SnapshotPolicy:
    enabled: bool = True
    every_n_steps: int = 10
    on_issue: bool = True


@dataclass(slots=True)
class FeatureFlags:
    use_runtime_extractor: bool = True
    use_runtime_scorer: bool = True
    enable_watchdog: bool = True
    export_replay: bool = True


@dataclass(slots=True)
class LearningPolicy:
    enabled: bool = False
    alpha: float = 0.8
    ucb_exploration: float = 1.2
    persistence_enabled: bool = False
    state_path: str = "output/learning_state.json"
    min_observations_to_persist: int = 20
    module_bucket_enabled: bool = True
    reward_changed_state: float = 1.0
    reward_novel_state: float = 0.3
    reward_functional_page: float = 0.4
    reward_issue_signal: float = 0.8
    penalty_out_of_app: float = 1.0
    penalty_unchanged: float = 0.2
    penalty_recent_loop: float = 0.25
    penalty_system_action: float = 0.15
    top_arms_report_limit: int = 5


@dataclass(slots=True)
class SidecarMonkeyPolicy:
    enabled: bool = False
    step_interval: int = 15
    max_batches: int = 4
    events_per_batch: int = 35
    throttle_ms: int = 20
    seed_offset: int = 1000
    pct_touch: int = 45
    pct_motion: int = 15
    pct_nav: int = 35
    pct_syskeys: int = 5
    ignore_crashes: bool = True
    ignore_timeouts: bool = True
    ignore_security_exceptions: bool = True
    adb_timeout_sec: float = 30.0


@dataclass(slots=True)
class SidecarPolicy:
    monkey: SidecarMonkeyPolicy = field(default_factory=SidecarMonkeyPolicy)


@dataclass(slots=True)
class RuntimeConfig:
    app: AppConfig = field(default_factory=AppConfig)
    ios: IOSConfig = field(default_factory=IOSConfig)
    run: RunConfig = field(default_factory=RunConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    snapshot: SnapshotPolicy = field(default_factory=SnapshotPolicy)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    learning: LearningPolicy = field(default_factory=LearningPolicy)
    sidecar: SidecarPolicy = field(default_factory=SidecarPolicy)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RuntimeConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        app_raw = dict(raw.get("app", {}))
        if "platform" not in app_raw and raw.get("platform") is not None:
            app_raw["platform"] = raw.get("platform")
        target_app_id = app_raw.pop("target_app_id", None)
        launch_target = app_raw.pop("launch_target", None)
        if target_app_id is not None and "package_name" not in app_raw:
            app_raw["package_name"] = target_app_id
        if launch_target is not None and "launch_activity" not in app_raw:
            app_raw["launch_activity"] = launch_target
        app_raw["platform"] = normalize_platform(app_raw.get("platform"))
        ios_raw = dict(raw.get("ios", {}))
        legacy_bundle_id = ios_raw.pop("bundle_id", None)
        if legacy_bundle_id is not None and "package_name" not in app_raw:
            app_raw["package_name"] = legacy_bundle_id
        feature_raw = dict(raw.get("features", {}))
        # 向后兼容历史配置键名。
        if "use_runtime_extractor" not in feature_raw and "use_extractor_v2" in feature_raw:
            feature_raw["use_runtime_extractor"] = feature_raw.get("use_extractor_v2")
        if "use_runtime_scorer" not in feature_raw and "use_scorer_v2" in feature_raw:
            feature_raw["use_runtime_scorer"] = feature_raw.get("use_scorer_v2")
        sidecar_raw = dict(raw.get("sidecar", {}))
        sidecar_monkey_raw = dict(sidecar_raw.get("monkey", {}))
        return cls(
            app=AppConfig(**app_raw),
            ios=IOSConfig(**ios_raw),
            run=RunConfig(**raw.get("run", {})),
            policy=PolicyConfig(**raw.get("policy", {})),
            score_weights=ScoreWeights(**raw.get("score_weights", {})),
            safety=SafetyConfig(**raw.get("safety", {})),
            snapshot=SnapshotPolicy(**raw.get("snapshot", {})),
            features=FeatureFlags(**feature_raw),
            learning=LearningPolicy(**raw.get("learning", {})),
            sidecar=SidecarPolicy(monkey=SidecarMonkeyPolicy(**sidecar_monkey_raw)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "app": self.app.__dict__,
            "ios": self.ios.__dict__,
            "run": self.run.__dict__,
            "policy": self.policy.__dict__,
            "score_weights": self.score_weights.__dict__,
            "safety": self.safety.__dict__,
            "snapshot": self.snapshot.__dict__,
            "features": self.features.__dict__,
            "learning": self.learning.__dict__,
            "sidecar": {"monkey": self.sidecar.monkey.__dict__},
        }
