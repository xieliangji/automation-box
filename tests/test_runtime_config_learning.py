from __future__ import annotations

from pathlib import Path

from smart_monkey.runtime_config import RuntimeConfig


def test_runtime_config_learning_defaults() -> None:
    cfg = RuntimeConfig()
    assert cfg.policy.enable_pinch is True
    assert cfg.learning.enabled is False
    assert cfg.learning.alpha == 0.8
    assert cfg.learning.ucb_exploration == 1.2
    assert cfg.learning.persistence_enabled is False
    assert cfg.learning.state_path == "output/learning_state.json"
    assert cfg.learning.min_observations_to_persist == 20
    assert cfg.learning.module_bucket_enabled is True
    assert cfg.learning.reward_novel_state == 0.3
    assert cfg.learning.penalty_recent_loop == 0.25
    assert cfg.learning.penalty_system_action == 0.15
    assert cfg.run.monkey_wait_ms == 400
    assert cfg.run.monkey_ios_wait_ms == 260
    assert cfg.policy.monkey_loop_streak_threshold == 3
    assert cfg.policy.monkey_diversity_state_repeat_threshold == 2
    assert cfg.policy.monkey_ios_permission_fastpath is True
    assert cfg.policy.monkey_ios_list_swipe_boost == 0.8
    assert cfg.policy.monkey_ios_static_text_click_penalty == 1.0
    assert cfg.policy.monkey_ios_cell_click_boost == 0.7
    assert cfg.policy.monkey_ios_back_like_click_penalty == 1.1
    assert cfg.policy.monkey_ios_external_jump_penalty == 2.0
    assert cfg.sidecar.monkey.enabled is False
    assert cfg.sidecar.monkey.step_interval == 15
    assert cfg.sidecar.monkey.max_batches == 4
    assert cfg.sidecar.monkey.events_per_batch == 35
    assert cfg.sidecar.monkey.throttle_ms == 20
    assert cfg.sidecar.monkey.seed_offset == 1000
    assert cfg.sidecar.monkey.pct_touch == 45
    assert cfg.sidecar.monkey.pct_motion == 15
    assert cfg.sidecar.monkey.pct_nav == 35
    assert cfg.sidecar.monkey.pct_syskeys == 5
    assert cfg.sidecar.monkey.ignore_crashes is True
    assert cfg.sidecar.monkey.ignore_timeouts is True
    assert cfg.sidecar.monkey.ignore_security_exceptions is True
    assert cfg.sidecar.monkey.adb_timeout_sec == 30.0


def test_runtime_config_learning_from_yaml(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
app:
  package_name: com.demo.app
policy:
  enable_pinch: false
  monkey_loop_streak_threshold: 4
  monkey_risk_penalty: 3.2
  monkey_diversity_state_repeat_threshold: 3
  monkey_ios_permission_fastpath: false
  monkey_ios_permission_boost: 2.8
  monkey_ios_list_swipe_boost: 1.1
  monkey_ios_static_text_click_penalty: 1.4
  monkey_ios_cell_click_boost: 0.9
  monkey_ios_back_like_click_penalty: 1.6
  monkey_ios_external_jump_penalty: 2.3
run:
  monkey_wait_ms: 350
  monkey_ios_wait_ms: 240
learning:
  enabled: true
  alpha: 0.6
  ucb_exploration: 2.0
  persistence_enabled: true
  state_path: output/custom_learning_state.json
  min_observations_to_persist: 12
  module_bucket_enabled: false
  reward_changed_state: 1.5
  reward_novel_state: 0.9
  penalty_recent_loop: 0.5
  penalty_system_action: 0.4
sidecar:
  monkey:
    enabled: true
    step_interval: 9
    max_batches: 4
    events_per_batch: 80
    throttle_ms: 20
    seed_offset: 1500
    pct_touch: 50
    pct_motion: 25
    pct_nav: 15
    pct_syskeys: 10
    ignore_crashes: false
    ignore_timeouts: false
    ignore_security_exceptions: false
    adb_timeout_sec: 45
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = RuntimeConfig.from_yaml(cfg_path)
    assert cfg.policy.enable_pinch is False
    assert cfg.learning.enabled is True
    assert cfg.learning.alpha == 0.6
    assert cfg.learning.ucb_exploration == 2.0
    assert cfg.learning.persistence_enabled is True
    assert cfg.learning.state_path == "output/custom_learning_state.json"
    assert cfg.learning.min_observations_to_persist == 12
    assert cfg.learning.module_bucket_enabled is False
    assert cfg.learning.reward_changed_state == 1.5
    assert cfg.learning.reward_novel_state == 0.9
    assert cfg.learning.penalty_recent_loop == 0.5
    assert cfg.learning.penalty_system_action == 0.4
    assert cfg.run.monkey_wait_ms == 350
    assert cfg.run.monkey_ios_wait_ms == 240
    assert cfg.policy.monkey_loop_streak_threshold == 4
    assert cfg.policy.monkey_risk_penalty == 3.2
    assert cfg.policy.monkey_diversity_state_repeat_threshold == 3
    assert cfg.policy.monkey_ios_permission_fastpath is False
    assert cfg.policy.monkey_ios_permission_boost == 2.8
    assert cfg.policy.monkey_ios_list_swipe_boost == 1.1
    assert cfg.policy.monkey_ios_static_text_click_penalty == 1.4
    assert cfg.policy.monkey_ios_cell_click_boost == 0.9
    assert cfg.policy.monkey_ios_back_like_click_penalty == 1.6
    assert cfg.policy.monkey_ios_external_jump_penalty == 2.3
    assert cfg.sidecar.monkey.enabled is True
    assert cfg.sidecar.monkey.step_interval == 9
    assert cfg.sidecar.monkey.max_batches == 4
    assert cfg.sidecar.monkey.events_per_batch == 80
    assert cfg.sidecar.monkey.throttle_ms == 20
    assert cfg.sidecar.monkey.seed_offset == 1500
    assert cfg.sidecar.monkey.pct_touch == 50
    assert cfg.sidecar.monkey.pct_motion == 25
    assert cfg.sidecar.monkey.pct_nav == 15
    assert cfg.sidecar.monkey.pct_syskeys == 10
    assert cfg.sidecar.monkey.ignore_crashes is False
    assert cfg.sidecar.monkey.ignore_timeouts is False
    assert cfg.sidecar.monkey.ignore_security_exceptions is False
    assert cfg.sidecar.monkey.adb_timeout_sec == 45


def test_runtime_config_supports_platform_neutral_app_fields(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
app:
  platform: ios
  target_app_id: com.demo.ios
  launch_target: MainScreen
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = RuntimeConfig.from_yaml(cfg_path)
    assert cfg.app.platform == "ios"
    assert cfg.app.package_name == "com.demo.ios"
    assert cfg.app.launch_activity == "MainScreen"
    assert cfg.app.target_app_id == "com.demo.ios"
    assert cfg.app.launch_target == "MainScreen"


def test_runtime_config_supports_ios_section_and_legacy_root_fields(tmp_path: Path) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
platform: ios
ios:
  bundle_id: com.demo.legacy
  wda_url: http://127.0.0.1:8100
  request_retry: 4
  keep_session: false
  auto_recreate_session: false
""".strip()
        + "\n",
        encoding="utf-8",
    )

    cfg = RuntimeConfig.from_yaml(cfg_path)
    assert cfg.app.platform == "ios"
    assert cfg.app.target_app_id == "com.demo.legacy"
    assert cfg.ios.wda_url == "http://127.0.0.1:8100"
    assert cfg.ios.request_retry == 4
    assert cfg.ios.keep_session is False
    assert cfg.ios.auto_recreate_session is False
