from __future__ import annotations

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
