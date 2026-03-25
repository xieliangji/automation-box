from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from smart_monkey.config import AppConfig, PolicyConfig, RunConfig, SafetyConfig, ScoreWeights


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
class RuntimeConfig:
    app: AppConfig = field(default_factory=AppConfig)
    run: RunConfig = field(default_factory=RunConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    snapshot: SnapshotPolicy = field(default_factory=SnapshotPolicy)
    features: FeatureFlags = field(default_factory=FeatureFlags)
    learning: LearningPolicy = field(default_factory=LearningPolicy)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "RuntimeConfig":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        feature_raw = dict(raw.get("features", {}))
        # Backward compatibility for historical config keys.
        if "use_runtime_extractor" not in feature_raw and "use_extractor_v2" in feature_raw:
            feature_raw["use_runtime_extractor"] = feature_raw.get("use_extractor_v2")
        if "use_runtime_scorer" not in feature_raw and "use_scorer_v2" in feature_raw:
            feature_raw["use_runtime_scorer"] = feature_raw.get("use_scorer_v2")
        return cls(
            app=AppConfig(**raw.get("app", {})),
            run=RunConfig(**raw.get("run", {})),
            policy=PolicyConfig(**raw.get("policy", {})),
            score_weights=ScoreWeights(**raw.get("score_weights", {})),
            safety=SafetyConfig(**raw.get("safety", {})),
            snapshot=SnapshotPolicy(**raw.get("snapshot", {})),
            features=FeatureFlags(**feature_raw),
            learning=LearningPolicy(**raw.get("learning", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "app": self.app.__dict__,
            "run": self.run.__dict__,
            "policy": self.policy.__dict__,
            "score_weights": self.score_weights.__dict__,
            "safety": self.safety.__dict__,
            "snapshot": self.snapshot.__dict__,
            "features": self.features.__dict__,
            "learning": self.learning.__dict__,
        }
