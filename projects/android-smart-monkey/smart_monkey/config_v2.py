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
    use_extractor_v2: bool = True
    use_scorer_v2: bool = True
    enable_watchdog: bool = True
    export_replay: bool = True


@dataclass(slots=True)
class ProjectConfigV2:
    app: AppConfig = field(default_factory=AppConfig)
    run: RunConfig = field(default_factory=RunConfig)
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    score_weights: ScoreWeights = field(default_factory=ScoreWeights)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    snapshot: SnapshotPolicy = field(default_factory=SnapshotPolicy)
    features: FeatureFlags = field(default_factory=FeatureFlags)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "ProjectConfigV2":
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        return cls(
            app=AppConfig(**raw.get("app", {})),
            run=RunConfig(**raw.get("run", {})),
            policy=PolicyConfig(**raw.get("policy", {})),
            score_weights=ScoreWeights(**raw.get("score_weights", {})),
            safety=SafetyConfig(**raw.get("safety", {})),
            snapshot=SnapshotPolicy(**raw.get("snapshot", {})),
            features=FeatureFlags(**raw.get("features", {})),
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
        }
