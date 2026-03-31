from __future__ import annotations

from pathlib import Path

from smart_monkey.services.learning_bandit import LearningBandit


def test_learning_bandit_prefers_higher_ucb_arm() -> None:
    bandit = LearningBandit(exploration=1.2)
    bandit.update("a", 1.0)
    bandit.update("a", 1.0)
    bandit.update("b", 0.2)

    score_a = bandit.score("a")
    score_b = bandit.score("b")
    assert score_a >= score_b


def test_learning_bandit_summary_contains_expected_fields() -> None:
    bandit = LearningBandit(exploration=1.0)
    bandit.select([("arm-x", 0.5)])
    bandit.observe_last(0.8)
    payload = bandit.summary(limit=3)

    assert "exploration_rate" in payload
    assert "average_reward" in payload
    assert "top_arms" in payload
    assert payload["top_arms"][0]["arm_key"] == "arm-x"


def test_learning_bandit_dump_and_load_state() -> None:
    bandit = LearningBandit(exploration=1.0)
    bandit.update("arm-a", 1.2)
    bandit.update("arm-a", 0.8)
    bandit.update("arm-b", 0.5)
    payload = bandit.dump_state()

    restored = LearningBandit(exploration=2.0)
    assert restored.load_state(payload) is True
    summary = restored.summary(limit=3)
    assert summary["total_observations"] == 3
    assert summary["top_arms"][0]["arm_key"] in {"arm-a", "arm-b"}


def test_learning_bandit_persistence_roundtrip(tmp_path: Path) -> None:
    state_path = tmp_path / "learning_state.json"
    bandit = LearningBandit(exploration=1.0)
    bandit.update("arm-a", 1.0)
    bandit.update("arm-b", 0.4)
    assert bandit.save_to_path(state_path) is True

    restored = LearningBandit(exploration=1.0)
    assert restored.load_from_path(state_path) is True
    summary = restored.summary(limit=3)
    assert summary["total_observations"] == 2
    assert any(item["arm_key"] == "arm-a" for item in summary["top_arms"])
