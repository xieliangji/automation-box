from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ArmStats:
    count: int = 0
    reward_sum: float = 0.0

    @property
    def avg_reward(self) -> float:
        if self.count <= 0:
            return 0.0
        return self.reward_sum / self.count


class LearningBandit:
    def __init__(self, exploration: float = 1.2) -> None:
        self.exploration = max(0.0, float(exploration))
        self.total_observations = 0
        self._arms: dict[str, ArmStats] = {}
        self._last_selected_arm: str | None = None
        self._explore_count = 0
        self._reward_sum = 0.0

    def score(self, arm_key: str) -> float:
        stats = self._arms.get(arm_key)
        if stats is None or stats.count == 0:
            return 1.0
        confidence = self.exploration * math.sqrt(math.log(max(1, self.total_observations)) / stats.count)
        return stats.avg_reward + confidence

    def select(self, scored_arms: list[tuple[str, float]]) -> str | None:
        if not scored_arms:
            self._last_selected_arm = None
            return None
        ranked = sorted(scored_arms, key=lambda item: item[1], reverse=True)
        selected = ranked[0][0]
        known = self._arms.get(selected)
        if known is None or known.count == 0:
            self._explore_count += 1
        self._last_selected_arm = selected
        return selected

    def update(self, arm_key: str, reward: float) -> None:
        stats = self._arms.setdefault(arm_key, ArmStats())
        stats.count += 1
        stats.reward_sum += float(reward)
        self._reward_sum += float(reward)
        self.total_observations += 1

    def observe_last(self, reward: float) -> None:
        if self._last_selected_arm is None:
            return
        self.update(self._last_selected_arm, reward)

    def summary(self, limit: int = 5) -> dict:
        ranked = sorted(
            (
                (arm, stats.count, round(stats.avg_reward, 4))
                for arm, stats in self._arms.items()
                if stats.count > 0
            ),
            key=lambda item: (item[2], item[1]),
            reverse=True,
        )
        obs = max(1, self.total_observations)
        return {
            "total_observations": self.total_observations,
            "exploration_rate": round(self._explore_count / obs, 4),
            "average_reward": round(self._reward_sum / obs, 4),
            "top_arms": [
                {"arm_key": arm, "count": count, "avg_reward": avg_reward} for arm, count, avg_reward in ranked[: max(1, limit)]
            ],
        }

    def dump_state(self) -> dict:
        return {
            "exploration": self.exploration,
            "total_observations": self.total_observations,
            "explore_count": self._explore_count,
            "reward_sum": self._reward_sum,
            "arms": {
                arm_key: {"count": arm.count, "reward_sum": arm.reward_sum}
                for arm_key, arm in self._arms.items()
                if arm.count > 0
            },
        }

    def load_state(self, payload: dict) -> bool:
        if not isinstance(payload, dict):
            return False
        arms_payload = payload.get("arms")
        if not isinstance(arms_payload, dict):
            return False
        self._arms = {}
        for arm_key, arm_payload in arms_payload.items():
            if not isinstance(arm_key, str) or not isinstance(arm_payload, dict):
                continue
            count = int(arm_payload.get("count", 0) or 0)
            reward_sum = float(arm_payload.get("reward_sum", 0.0) or 0.0)
            if count <= 0:
                continue
            self._arms[arm_key] = ArmStats(count=count, reward_sum=reward_sum)
        self.total_observations = int(payload.get("total_observations", sum(arm.count for arm in self._arms.values())) or 0)
        if self.total_observations < 0:
            self.total_observations = 0
        self._explore_count = int(payload.get("explore_count", 0) or 0)
        if self._explore_count < 0:
            self._explore_count = 0
        self._reward_sum = float(payload.get("reward_sum", sum(arm.reward_sum for arm in self._arms.values())) or 0.0)
        self._last_selected_arm = None
        return True

    def save_to_path(self, path: str | Path) -> bool:
        target = Path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(self.dump_state(), ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            return False
        return True

    def load_from_path(self, path: str | Path) -> bool:
        target = Path(path)
        if not target.exists():
            return False
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return False
        return self.load_state(payload)
