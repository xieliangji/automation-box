from __future__ import annotations

import json
from pathlib import Path

from smart_monkey.report.coverage_benchmark import CoverageBenchmarkGenerator


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")


def _write_state(path: Path, state_id: str, app_flags: list[str], elements: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state_id": state_id,
        "app_flags": app_flags,
        "elements": elements,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_coverage_benchmark_generates_current_and_comparison(tmp_path: Path) -> None:
    current = tmp_path / "current"
    baseline = tmp_path / "baseline"
    for run in (current, baseline):
        (run / "report").mkdir(parents=True, exist_ok=True)
        (run / "states").mkdir(parents=True, exist_ok=True)
        (run / "issues").mkdir(parents=True, exist_ok=True)
        _write_jsonl(
            run / "steps.jsonl",
            [
                {
                    "step": 0,
                    "current_state_id": "s_login",
                    "next_state_id": "s_home",
                    "action_type": "click",
                    "changed": True,
                    "out_of_app": False,
                    "timestamp_ms": 1_000,
                    "platform": "android",
                    "run_profile": "monkey_compatible",
                    "crash_stress_mode": True,
                    "crash_stress_burst_active": True,
                    "crash_signal": True,
                    "monkey_mode": True,
                    "monkey_escape_boosted": True,
                    "monkey_risk_cooldown_applied": False,
                    "monkey_diversity_boosted": True,
                    "monkey_ios_tuning_applied": False,
                    "monkey_ios_permission_fastpath_applied": False,
                    "permission_like_state": False,
                    "monkey_ios_recovery_grace_active": False,
                    "monkey_out_of_app_streak": 0,
                    "monkey_same_state_streak": 0,
                },
                {
                    "step": 1,
                    "current_state_id": "s_home",
                    "next_state_id": "s_feature",
                    "action_type": "click",
                    "changed": True,
                    "out_of_app": False,
                    "timestamp_ms": 31_000,
                    "platform": "android",
                    "run_profile": "monkey_compatible",
                    "crash_stress_mode": True,
                    "crash_stress_burst_active": False,
                    "crash_signal": False,
                    "monkey_mode": True,
                    "monkey_escape_boosted": False,
                    "monkey_risk_cooldown_applied": True,
                    "monkey_diversity_boosted": False,
                    "monkey_ios_tuning_applied": False,
                    "monkey_ios_permission_fastpath_applied": False,
                    "permission_like_state": False,
                    "monkey_ios_recovery_grace_active": False,
                    "monkey_out_of_app_streak": 0,
                    "monkey_same_state_streak": 1,
                },
                {
                    "step": -1,
                    "recovery_strategy": "restart_to_checkpoint",
                    "recovery_validation_in_target_app": True,
                },
                {
                    "step": -1,
                    "runtime_metrics": {
                        "learning": {
                            "exploration_rate": 0.4,
                            "average_reward": 0.6,
                            "top_arms": [{"arm_key": "x", "count": 3, "avg_reward": 0.7}],
                        },
                        "sidecar_monkey": {
                            "enabled": True,
                            "last_exit_code": 0,
                        },
                    },
                },
                {
                    "step": -1,
                    "sidecar_monkey_batch": True,
                    "sidecar_success": True,
                    "sidecar_recovered_to_target": False,
                    "sidecar_recovery_failed": False,
                    "sidecar_events_injected": 20,
                },
            ],
        )
        _write_jsonl(
            run / "transitions.jsonl",
            [
                {"from_state_id": "s_login", "to_state_id": "s_home"},
                {"from_state_id": "s_home", "to_state_id": "s_feature"},
            ],
        )
        _write_state(
            run / "states" / "s_login.json",
            "s_login",
            ["login_page"],
            [{"resource_id": "com.demo:id/btn_login", "text": "登录"}],
        )
        _write_state(
            run / "states" / "s_home.json",
            "s_home",
            ["list_page"],
            [{"resource_id": "com.demo:id/home_tab", "text": "首页"}],
        )
        _write_state(
            run / "states" / "s_feature.json",
            "s_feature",
            ["form_page"],
            [{"resource_id": "com.demo:id/save", "text": "保存"}],
        )
        issue_dir = run / "issues" / "out_of_app_1"
        issue_dir.mkdir(parents=True, exist_ok=True)
        (issue_dir / "summary.json").write_text(
            json.dumps({"issue_type": "out_of_app"}, ensure_ascii=False), encoding="utf-8"
        )

    # 让基线数据略差一些，便于验证对比指标变化。
    _write_jsonl(
        baseline / "steps.jsonl",
        [
            {
                "step": 0,
                "current_state_id": "s_login",
                "next_state_id": "s_login",
                "action_type": "wait",
                "changed": False,
                "out_of_app": True,
                "timestamp_ms": 1_000,
                "platform": "android",
                "run_profile": "monkey_compatible",
                "crash_stress_mode": False,
                "crash_stress_burst_active": False,
                "crash_signal": False,
                "monkey_mode": True,
                "monkey_escape_boosted": False,
                "monkey_risk_cooldown_applied": False,
                "monkey_diversity_boosted": False,
                "monkey_ios_tuning_applied": False,
                "monkey_ios_permission_fastpath_applied": False,
                "permission_like_state": False,
                "monkey_ios_recovery_grace_active": False,
            },
            {"step": -1, "recovery_strategy": "restart_app", "recovery_validation_in_target_app": False},
        ],
    )

    generator = CoverageBenchmarkGenerator(current, baseline_dir=baseline)
    path = generator.generate()
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert "current_run" in payload
    assert "comparison" in payload
    assert payload["current_run"]["runtime_steps"] >= 1
    assert "composite_score" in payload["current_run"]
    assert "composite_score" in payload["comparison"]
    assert payload["current_run"]["actions_per_minute"] == 4.0
    assert payload["current_run"]["crash_per_1k_actions"] == 500.0
    assert payload["current_run"]["burst_step_ratio"] == 0.5
    assert payload["current_run"]["time_to_first_crash_steps"] == 0
    assert payload["current_run"]["monkey_step_ratio"] == 1.0
    assert payload["current_run"]["monkey_escape_boosted_ratio"] == 0.5
    assert payload["current_run"]["monkey_risk_cooldown_ratio"] == 0.5
    assert payload["current_run"]["monkey_diversity_boosted_ratio"] == 0.5
    assert payload["current_run"]["monkey_ios_permission_fastpath_ratio"] == 0.0
    assert payload["current_run"]["monkey_max_same_state_streak"] == 1
    assert payload["current_run"]["learning_exploration_rate"] == 0.4
    assert payload["current_run"]["learning_average_reward"] == 0.6
    assert payload["current_run"]["learning_top_arms"][0]["arm_key"] == "x"
    assert payload["targets"]["unique_states_growth_vs_baseline"] == 1.25
    assert payload["targets"]["sidecar_batch_count_min"] == 1
    assert payload["targets"]["sidecar_success_rate_min"] == 0.95
    assert payload["targets"]["sidecar_recovery_failure_rate_max"] == 0.2
    assert payload["gates"]["results"]["sidecar_batch_count_min"]["passed"] is True
    assert payload["gates"]["results"]["sidecar_success_rate_min"]["passed"] is True
    assert payload["gates"]["results"]["sidecar_recovery_failure_rate_max"]["passed"] is True
    assert payload["gates"]["passed"] is True
