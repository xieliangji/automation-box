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
        payload: dict[str, Any] = {
            "current_run": current,
            "baseline_run": baseline,
            "comparison": self._compare(current, baseline) if baseline else {},
        }
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
        login_rows = [row for row in runtime_steps if self._is_login_related_row(row, states_dir)]
        functional_rows = [row for row in runtime_steps if not self._is_login_related_row(row, states_dir)]
        crash_stress_rows = [row for row in runtime_steps if row.get("crash_stress_mode") is True]

        changed_count = sum(1 for row in runtime_steps if row.get("changed") is True)
        out_of_app_count = sum(1 for row in runtime_steps if row.get("out_of_app") is True)
        unique_states = self._count_unique_states(runtime_steps)
        unique_functional_states = self._count_unique_states(functional_rows)
        crash_count = self._count_crash_signals(runtime_steps)
        burst_active_count = sum(1 for row in runtime_steps if row.get("crash_stress_burst_active") is True)
        duration_minutes = self._duration_minutes(runtime_steps)
        first_crash_step = self._first_crash_step(runtime_steps)

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

        total_runtime = max(1, len(runtime_steps))
        payload: dict[str, Any] = {
            "run_dir": str(run_dir),
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
            "learning_step_ratio": round(len(learning_rows) / total_runtime, 4),
            "learning_avg_reward_per_step": round(learning_reward_sum / max(1, len(learning_rows)), 4),
            "learning_exploration_rate": learning_metrics.get("exploration_rate"),
            "learning_average_reward": learning_metrics.get("average_reward"),
            "learning_top_arms": learning_metrics.get("top_arms", []),
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
            "learning_step_ratio",
            "learning_avg_reward_per_step",
            "learning_exploration_rate",
            "learning_average_reward",
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
        # score in [0, 100], higher is better
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
        score -= out_of_app_ratio * 10.0
        score -= login_step_ratio * 5.0
        return round(max(0.0, min(100.0, score)), 2)

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
