from __future__ import annotations

import math
from dataclasses import dataclass


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
