from __future__ import annotations

from pathlib import Path

from smart_monkey.runtime_config import RuntimeConfig


def test_runtime_config_learning_defaults() -> None:
    cfg = RuntimeConfig()
    assert cfg.policy.enable_pinch is True
    assert cfg.learning.enabled is False
    assert cfg.learning.alpha == 0.8
    assert cfg.learning.ucb_exploration == 1.2
    assert cfg.learning.module_bucket_enabled is True
    assert cfg.learning.reward_novel_state == 0.3
    assert cfg.learning.penalty_recent_loop == 0.25
    assert cfg.learning.penalty_system_action == 0.15


def test_runtime_config_learning_from_yaml(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
app:
  package_name: com.demo.app
policy:
  enable_pinch: false
learning:
  enabled: true
  alpha: 0.6
  ucb_exploration: 2.0
  module_bucket_enabled: false
  reward_changed_state: 1.5
  reward_novel_state: 0.9
  penalty_recent_loop: 0.5
  penalty_system_action: 0.4
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = RuntimeConfig.from_yaml(cfg_path)
    assert cfg.policy.enable_pinch is False
    assert cfg.learning.enabled is True
    assert cfg.learning.alpha == 0.6
    assert cfg.learning.ucb_exploration == 2.0
    assert cfg.learning.module_bucket_enabled is False
    assert cfg.learning.reward_changed_state == 1.5
    assert cfg.learning.reward_novel_state == 0.9
    assert cfg.learning.penalty_recent_loop == 0.5
    assert cfg.learning.penalty_system_action == 0.4
