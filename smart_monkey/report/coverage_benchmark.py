from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CoverageBenchmarkGenerator:
    def __init__(self, output_dir: str | Path, baseline_dir: str | Path | None = None) -> None:
        self.output_dir = Path(output_dir)
        self.report_dir = self.output_dir / "report"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.baseline_dir = Path(baseline_dir) if baseline_dir else None

    def generate(self) -> Path:
        current = self._collect_metrics(self.output_dir)
        baseline = self._collect_metrics(self.baseline_dir) if self.baseline_dir else None
        targets = self._targets_for(current)
        gates = self._evaluate_gates(current, baseline, targets)
        payload: dict[str, Any] = {
            "current_run": current,
            "baseline_run": baseline,
            "comparison": self._compare(current, baseline) if baseline else {},
            "targets": targets,
            "gates": gates,
        }
        current["benchmark_gate_passed"] = gates.get("passed")
        target = self.report_dir / "coverage_benchmark.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return target

    def _collect_metrics(self, run_dir: Path | None) -> dict[str, Any]:
        if run_dir is None or not run_dir.exists():
            return {}
        steps = self._read_jsonl(run_dir / "steps.jsonl")
        transitions = self._read_jsonl(run_dir / "transitions.jsonl")
        states_dir = run_dir / "states"
        issue_dirs = sorted((run_dir / "issues").glob("*")) if (run_dir / "issues").exists() else []

        runtime_steps = [row for row in steps if isinstance(row.get("step"), int) and row.get("step", -1) >= 0]
        recovery_rows = [row for row in steps if row.get("recovery_strategy")]
        bootstrap_rows = [row for row in steps if row.get("bootstrap_status")]
        sidecar_rows = [row for row in steps if row.get("sidecar_monkey_batch") is True]
        monkey_rows = [row for row in runtime_steps if row.get("monkey_mode") is True]
        login_rows = [row for row in runtime_steps if self._is_login_related_row(row, states_dir)]
        functional_rows = [row for row in runtime_steps if not self._is_login_related_row(row, states_dir)]
        crash_stress_rows = [row for row in runtime_steps if row.get("crash_stress_mode") is True]

        changed_count = sum(1 for row in runtime_steps if row.get("changed") is True)
        out_of_app_count = sum(1 for row in runtime_steps if row.get("out_of_app") is True)
        unique_states = self._count_unique_states(runtime_steps)
        unique_functional_states = self._count_unique_states(functional_rows)
        crash_count = self._count_crash_signals(runtime_steps)
        burst_active_count = sum(1 for row in runtime_steps if row.get("crash_stress_burst_active") is True)
        monkey_escape_boosted_count = sum(1 for row in runtime_steps if row.get("monkey_escape_boosted") is True)
        monkey_risk_cooldown_count = sum(1 for row in runtime_steps if row.get("monkey_risk_cooldown_applied") is True)
        monkey_diversity_boosted_count = sum(1 for row in runtime_steps if row.get("monkey_diversity_boosted") is True)
        monkey_ios_tuning_applied_count = sum(1 for row in runtime_steps if row.get("monkey_ios_tuning_applied") is True)
        monkey_ios_permission_fastpath_count = sum(
            1 for row in runtime_steps if row.get("monkey_ios_permission_fastpath_applied") is True
        )
        permission_like_step_count = sum(1 for row in runtime_steps if row.get("permission_like_state") is True)
        monkey_ios_recovery_grace_step_count = sum(
            1 for row in runtime_steps if row.get("monkey_ios_recovery_grace_active") is True
        )
        duration_minutes = self._duration_minutes(runtime_steps)
        first_crash_step = self._first_crash_step(runtime_steps)
        max_monkey_out_of_app_streak = max((int(row.get("monkey_out_of_app_streak", 0) or 0) for row in monkey_rows), default=0)
        max_monkey_same_state_streak = max((int(row.get("monkey_same_state_streak", 0) or 0) for row in monkey_rows), default=0)
        platform = self._infer_platform(runtime_steps)
        run_profile = self._infer_run_profile(runtime_steps)

        issue_type_counter: dict[str, int] = {}
        for issue_dir in issue_dirs:
            summary = self._read_json(issue_dir / "summary.json")
            issue_type = str(summary.get("issue_type") or issue_dir.name.split("_")[0]) if isinstance(summary, dict) else issue_dir.name
            issue_type_counter[issue_type] = issue_type_counter.get(issue_type, 0) + 1

        issue_precision = self._issue_precision_score(issue_type_counter)
        recovery_success_rate = self._recovery_success_rate(recovery_rows)
        learning_rows = [row for row in runtime_steps if row.get("learning_enabled") is True]
        learning_reward_sum = sum(float(row.get("learning_reward", 0.0) or 0.0) for row in learning_rows)
        learning_metrics = self._extract_learning_metrics(steps)
        sidecar_metrics = self._extract_sidecar_metrics(steps)
        sidecar_success_count = sum(1 for row in sidecar_rows if row.get("sidecar_success") is True)
        sidecar_recovery_count = sum(1 for row in sidecar_rows if row.get("sidecar_recovered_to_target") is True)
        sidecar_recovery_failure_count = sum(1 for row in sidecar_rows if row.get("sidecar_recovery_failed") is True)
        sidecar_events_total = sum(int(row.get("sidecar_events_injected", 0) or 0) for row in sidecar_rows)

        total_runtime = max(1, len(runtime_steps))
        payload: dict[str, Any] = {
            "run_dir": str(run_dir),
            "platform": platform,
            "run_profile": run_profile,
            "runtime_steps": len(runtime_steps),
            "transitions": len(transitions),
            "changed_count": changed_count,
            "changed_ratio": round(changed_count / total_runtime, 4),
            "out_of_app_count": out_of_app_count,
            "out_of_app_ratio": round(out_of_app_count / total_runtime, 4),
            "recovery_events": len(recovery_rows),
            "bootstrap_events": len(bootstrap_rows),
            "unique_states": unique_states,
            "unique_functional_states": unique_functional_states,
            "functional_step_ratio": round(len(functional_rows) / total_runtime, 4),
            "login_step_ratio": round(len(login_rows) / total_runtime, 4),
            "issue_count": len(issue_dirs),
            "issue_type_counter": issue_type_counter,
            "issue_precision_score": issue_precision,
            "recovery_success_rate": recovery_success_rate,
            "crash_count": crash_count,
            "actions_per_minute": round(len(runtime_steps) / max(duration_minutes, 1e-6), 2),
            "crash_per_1k_actions": round((crash_count * 1000.0) / max(1, len(runtime_steps)), 2),
            "burst_step_ratio": round(burst_active_count / total_runtime, 4),
            "time_to_first_crash_steps": first_crash_step,
            "crash_stress_step_ratio": round(len(crash_stress_rows) / total_runtime, 4),
            "monkey_step_ratio": round(len(monkey_rows) / total_runtime, 4),
            "monkey_escape_boosted_ratio": round(monkey_escape_boosted_count / total_runtime, 4),
            "monkey_risk_cooldown_ratio": round(monkey_risk_cooldown_count / total_runtime, 4),
            "monkey_diversity_boosted_ratio": round(monkey_diversity_boosted_count / total_runtime, 4),
            "monkey_ios_tuning_applied_ratio": round(monkey_ios_tuning_applied_count / total_runtime, 4),
            "monkey_ios_permission_fastpath_ratio": round(monkey_ios_permission_fastpath_count / total_runtime, 4),
            "permission_like_step_ratio": round(permission_like_step_count / total_runtime, 4),
            "monkey_ios_recovery_grace_step_ratio": round(monkey_ios_recovery_grace_step_count / total_runtime, 4),
            "monkey_max_out_of_app_streak": max_monkey_out_of_app_streak,
            "monkey_max_same_state_streak": max_monkey_same_state_streak,
            "learning_step_ratio": round(len(learning_rows) / total_runtime, 4),
            "learning_avg_reward_per_step": round(learning_reward_sum / max(1, len(learning_rows)), 4),
            "learning_exploration_rate": learning_metrics.get("exploration_rate"),
            "learning_average_reward": learning_metrics.get("average_reward"),
            "learning_top_arms": learning_metrics.get("top_arms", []),
            "sidecar_batch_count": len(sidecar_rows),
            "sidecar_success_count": sidecar_success_count,
            "sidecar_success_rate": round(sidecar_success_count / max(1, len(sidecar_rows)), 4) if sidecar_rows else None,
            "sidecar_recovery_count": sidecar_recovery_count,
            "sidecar_recovery_failure_count": sidecar_recovery_failure_count,
            "sidecar_recovery_failure_rate": (
                round(sidecar_recovery_failure_count / max(1, len(sidecar_rows)), 4) if sidecar_rows else None
            ),
            "sidecar_events_injected_total": sidecar_events_total,
            "sidecar_batch_step_ratio": round(len(sidecar_rows) / total_runtime, 4),
            "sidecar_enabled": sidecar_metrics.get("enabled"),
            "sidecar_last_exit_code": sidecar_metrics.get("last_exit_code"),
        }
        payload["composite_score"] = self._composite_score(payload)
        return payload

    def _compare(self, current: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any]:
        if not baseline:
            return {}
        keys = [
            "runtime_steps",
            "unique_states",
            "unique_functional_states",
            "functional_step_ratio",
            "login_step_ratio",
            "out_of_app_ratio",
            "issue_precision_score",
            "recovery_success_rate",
            "actions_per_minute",
            "crash_per_1k_actions",
            "burst_step_ratio",
            "time_to_first_crash_steps",
            "monkey_step_ratio",
            "monkey_escape_boosted_ratio",
            "monkey_risk_cooldown_ratio",
            "monkey_diversity_boosted_ratio",
            "monkey_ios_tuning_applied_ratio",
            "monkey_ios_permission_fastpath_ratio",
            "permission_like_step_ratio",
            "monkey_ios_recovery_grace_step_ratio",
            "monkey_max_out_of_app_streak",
            "monkey_max_same_state_streak",
            "learning_step_ratio",
            "learning_avg_reward_per_step",
            "learning_exploration_rate",
            "learning_average_reward",
            "sidecar_batch_count",
            "sidecar_success_count",
            "sidecar_success_rate",
            "sidecar_recovery_count",
            "sidecar_recovery_failure_count",
            "sidecar_recovery_failure_rate",
            "sidecar_events_injected_total",
            "sidecar_batch_step_ratio",
            "sidecar_last_exit_code",
            "composite_score",
        ]
        comparison: dict[str, Any] = {}
        for key in keys:
            current_value = current.get(key)
            baseline_value = baseline.get(key)
            if isinstance(current_value, (int, float)) and isinstance(baseline_value, (int, float)):
                comparison[key] = {
                    "current": current_value,
                    "baseline": baseline_value,
                    "delta": round(current_value - baseline_value, 4),
                }
        return comparison

    def _composite_score(self, metrics: dict[str, Any]) -> float:
        # 分数范围 [0, 100]，越高越好。
        unique_states = float(metrics.get("unique_states", 0))
        unique_functional_states = float(metrics.get("unique_functional_states", 0))
        functional_step_ratio = float(metrics.get("functional_step_ratio", 0.0))
        out_of_app_ratio = float(metrics.get("out_of_app_ratio", 0.0))
        login_step_ratio = float(metrics.get("login_step_ratio", 0.0))
        issue_precision_score = float(metrics.get("issue_precision_score", 0.0))
        recovery_success_rate = float(metrics.get("recovery_success_rate", 0.0))
        crash_per_1k_actions = float(metrics.get("crash_per_1k_actions", 0.0))
        burst_step_ratio = float(metrics.get("burst_step_ratio", 0.0))
        learning_step_ratio = float(metrics.get("learning_step_ratio", 0.0))
        learning_avg_reward_per_step = float(metrics.get("learning_avg_reward_per_step", 0.0))
        sidecar_success_rate = metrics.get("sidecar_success_rate")
        sidecar_success_rate_value = float(sidecar_success_rate) if isinstance(sidecar_success_rate, (int, float)) else 0.0

        score = 0.0
        score += min(25.0, unique_states * 0.8)
        score += min(25.0, unique_functional_states * 1.0)
        score += functional_step_ratio * 20.0
        score += issue_precision_score * 15.0
        score += recovery_success_rate * 10.0
        score += min(5.0, crash_per_1k_actions * 0.5)
        score += burst_step_ratio * 3.0
        score += learning_step_ratio * 2.0
        score += min(2.0, max(0.0, learning_avg_reward_per_step))
        score += sidecar_success_rate_value * 1.5
        score -= out_of_app_ratio * 10.0
        score -= login_step_ratio * 5.0
        return round(max(0.0, min(100.0, score)), 2)

    def _targets_for(self, current: dict[str, Any]) -> dict[str, Any]:
        platform = str(current.get("platform") or "android").lower()
        run_profile = str(current.get("run_profile") or "").lower()
        if platform == "android" and run_profile == "monkey_compatible":
            targets: dict[str, Any] = {
                "unique_states_growth_vs_baseline": 1.25,
                "out_of_app_ratio_delta_max": 0.02,
                "recovery_success_rate_min": 0.95,
            }
            if current.get("sidecar_enabled") is True:
                targets.update(
                    {
                        "sidecar_batch_count_min": 1,
                        "sidecar_success_rate_min": 0.95,
                        "sidecar_recovery_failure_rate_max": 0.2,
                    }
                )
            return targets
        if platform == "ios":
            return {
                "unique_states_growth_vs_baseline": 2.0,
                "out_of_app_ratio_max": 0.03,
                "recovery_success_rate_min": 0.95,
                "permission_like_step_ratio_delta_max": 0.0,
            }
        return {}

    def _evaluate_gates(
        self,
        current: dict[str, Any],
        baseline: dict[str, Any] | None,
        targets: dict[str, Any],
    ) -> dict[str, Any]:
        if not targets:
            return {"passed": None, "results": {}}
        results: dict[str, dict[str, Any]] = {}
        baseline = baseline or {}
        has_baseline = bool(baseline)
        unique_growth_target = targets.get("unique_states_growth_vs_baseline")
        if isinstance(unique_growth_target, (int, float)):
            if has_baseline:
                current_unique = float(current.get("unique_states", 0) or 0)
                baseline_unique = float(baseline.get("unique_states", 0) or 0)
                ratio = current_unique / baseline_unique if baseline_unique > 0 else None
                passed = ratio is not None and ratio >= float(unique_growth_target)
            else:
                ratio = None
                passed = None
            results["unique_states_growth_vs_baseline"] = {
                "target": round(float(unique_growth_target), 4),
                "actual": round(float(ratio), 4) if ratio is not None else None,
                "passed": passed,
            }

        out_delta_target = targets.get("out_of_app_ratio_delta_max")
        if isinstance(out_delta_target, (int, float)):
            if has_baseline:
                current_ratio = float(current.get("out_of_app_ratio", 0.0) or 0.0)
                baseline_ratio = float(baseline.get("out_of_app_ratio", 0.0) or 0.0)
                delta = current_ratio - baseline_ratio
                passed = delta <= float(out_delta_target)
                actual: float | None = round(delta, 4)
            else:
                actual = None
                passed = None
            results["out_of_app_ratio_delta_max"] = {
                "target": round(float(out_delta_target), 4),
                "actual": actual,
                "passed": passed,
            }

        out_max_target = targets.get("out_of_app_ratio_max")
        if isinstance(out_max_target, (int, float)):
            current_ratio = float(current.get("out_of_app_ratio", 0.0) or 0.0)
            results["out_of_app_ratio_max"] = {
                "target": round(float(out_max_target), 4),
                "actual": round(current_ratio, 4),
                "passed": current_ratio <= float(out_max_target),
            }

        recovery_target = targets.get("recovery_success_rate_min")
        if isinstance(recovery_target, (int, float)):
            current_rate = float(current.get("recovery_success_rate", 0.0) or 0.0)
            results["recovery_success_rate_min"] = {
                "target": round(float(recovery_target), 4),
                "actual": round(current_rate, 4),
                "passed": current_rate >= float(recovery_target),
            }

        sidecar_batch_target = targets.get("sidecar_batch_count_min")
        if isinstance(sidecar_batch_target, (int, float)):
            current_count = int(current.get("sidecar_batch_count", 0) or 0)
            results["sidecar_batch_count_min"] = {
                "target": int(sidecar_batch_target),
                "actual": current_count,
                "passed": current_count >= int(sidecar_batch_target),
            }

        sidecar_success_target = targets.get("sidecar_success_rate_min")
        if isinstance(sidecar_success_target, (int, float)):
            current_rate_raw = current.get("sidecar_success_rate")
            current_rate = float(current_rate_raw) if isinstance(current_rate_raw, (int, float)) else None
            results["sidecar_success_rate_min"] = {
                "target": round(float(sidecar_success_target), 4),
                "actual": round(current_rate, 4) if current_rate is not None else None,
                "passed": current_rate is not None and current_rate >= float(sidecar_success_target),
            }

        sidecar_recovery_failure_target = targets.get("sidecar_recovery_failure_rate_max")
        if isinstance(sidecar_recovery_failure_target, (int, float)):
            current_rate_raw = current.get("sidecar_recovery_failure_rate")
            current_rate = float(current_rate_raw) if isinstance(current_rate_raw, (int, float)) else None
            results["sidecar_recovery_failure_rate_max"] = {
                "target": round(float(sidecar_recovery_failure_target), 4),
                "actual": round(current_rate, 4) if current_rate is not None else None,
                "passed": current_rate is not None and current_rate <= float(sidecar_recovery_failure_target),
            }

        permission_delta_target = targets.get("permission_like_step_ratio_delta_max")
        if isinstance(permission_delta_target, (int, float)):
            if has_baseline:
                current_ratio = float(current.get("permission_like_step_ratio", 0.0) or 0.0)
                baseline_ratio = float(baseline.get("permission_like_step_ratio", 0.0) or 0.0)
                delta = current_ratio - baseline_ratio
                passed = delta <= float(permission_delta_target)
                actual: float | None = round(delta, 4)
            else:
                actual = None
                passed = None
            results["permission_like_step_ratio_delta_max"] = {
                "target": round(float(permission_delta_target), 4),
                "actual": actual,
                "passed": passed,
            }

        decision_values = [item.get("passed") for item in results.values()]
        if any(value is False for value in decision_values):
            overall = False
        elif any(value is None for value in decision_values):
            overall = None
        else:
            overall = True
        return {"passed": overall, "results": results}

    def _issue_precision_score(self, issue_type_counter: dict[str, int]) -> float:
        if not issue_type_counter:
            return 1.0
        high_signal = {"crash", "anr", "out_of_app"}
        total = sum(issue_type_counter.values())
        good = sum(count for key, count in issue_type_counter.items() if key in high_signal)
        return round(good / max(1, total), 4)

    def _recovery_success_rate(self, recovery_rows: list[dict[str, Any]]) -> float:
        if not recovery_rows:
            return 1.0
        success = sum(1 for row in recovery_rows if row.get("recovery_validation_in_target_app") is True)
        return round(success / max(1, len(recovery_rows)), 4)

    def _is_login_related_row(self, row: dict[str, Any], states_dir: Path) -> bool:
        current_state_id = row.get("current_state_id")
        next_state_id = row.get("next_state_id")
        action_type = str(row.get("action_type") or "").lower()
        if action_type in {"restart_app", "back"} and row.get("out_of_app") is True:
            return True
        for state_id in (current_state_id, next_state_id):
            if not state_id:
                continue
            if self._is_login_related_state(str(state_id), states_dir):
                return True
        return False

    def _is_login_related_state(self, state_id: str, states_dir: Path) -> bool:
        path = states_dir / f"{state_id}.json"
        payload = self._read_json(path)
        if not isinstance(payload, dict):
            return False
        app_flags = {str(flag).lower() for flag in payload.get("app_flags", []) if flag is not None}
        if "login_page" in app_flags:
            return True
        elements = payload.get("elements", [])
        if not isinstance(elements, list):
            return False
        joined = " ".join(
            (
                f"{element.get('resource_id', '')} {element.get('text', '')} {element.get('content_desc', '')}"
                for element in elements
                if isinstance(element, dict)
            )
        ).lower()
        return any(token in joined for token in ("login", "登录", "密码", "password", "账号", "account"))

    def _count_unique_states(self, steps: list[dict[str, Any]]) -> int:
        states = set()
        for step in steps:
            current_state_id = step.get("current_state_id")
            next_state_id = step.get("next_state_id")
            if current_state_id:
                states.add(str(current_state_id))
            if next_state_id:
                states.add(str(next_state_id))
        return len(states)

    @staticmethod
    def _count_crash_signals(runtime_steps: list[dict[str, Any]]) -> int:
        return sum(1 for row in runtime_steps if row.get("crash_signal") is True or row.get("crash") is True)

    @staticmethod
    def _first_crash_step(runtime_steps: list[dict[str, Any]]) -> int | None:
        for row in runtime_steps:
            if row.get("crash_signal") is True or row.get("crash") is True:
                step = row.get("step")
                if isinstance(step, int):
                    return step
        return None

    @staticmethod
    def _duration_minutes(runtime_steps: list[dict[str, Any]]) -> float:
        if len(runtime_steps) < 2:
            return 1.0 / 60.0
        timestamp_values = [int(row.get("timestamp_ms")) for row in runtime_steps if isinstance(row.get("timestamp_ms"), int)]
        if len(timestamp_values) < 2:
            return 1.0 / 60.0
        elapsed_ms = max(1, max(timestamp_values) - min(timestamp_values))
        return elapsed_ms / 60000.0

    @staticmethod
    def _extract_learning_metrics(steps: list[dict[str, Any]]) -> dict[str, Any]:
        for row in reversed(steps):
            metrics = row.get("runtime_metrics")
            if not isinstance(metrics, dict):
                continue
            learning = metrics.get("learning")
            if isinstance(learning, dict):
                return {
                    "exploration_rate": learning.get("exploration_rate"),
                    "average_reward": learning.get("average_reward"),
                    "top_arms": learning.get("top_arms", []),
                }
        return {"exploration_rate": None, "average_reward": None, "top_arms": []}

    @staticmethod
    def _extract_sidecar_metrics(steps: list[dict[str, Any]]) -> dict[str, Any]:
        for row in reversed(steps):
            metrics = row.get("runtime_metrics")
            if not isinstance(metrics, dict):
                continue
            sidecar = metrics.get("sidecar_monkey")
            if isinstance(sidecar, dict):
                return {
                    "enabled": sidecar.get("enabled"),
                    "last_exit_code": sidecar.get("last_exit_code"),
                }
        return {"enabled": None, "last_exit_code": None}

    @staticmethod
    def _infer_platform(runtime_steps: list[dict[str, Any]]) -> str:
        for row in runtime_steps:
            platform = row.get("platform")
            if platform in {"android", "ios"}:
                return str(platform)
        return "android"

    @staticmethod
    def _infer_run_profile(runtime_steps: list[dict[str, Any]]) -> str:
        for row in runtime_steps:
            profile = row.get("run_profile")
            if isinstance(profile, str) and profile.strip():
                return profile.strip().lower()
        return "functional"

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
        return rows

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
