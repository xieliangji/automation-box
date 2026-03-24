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

        changed_count = sum(1 for row in runtime_steps if row.get("changed") is True)
        out_of_app_count = sum(1 for row in runtime_steps if row.get("out_of_app") is True)
        unique_states = self._count_unique_states(runtime_steps)
        unique_functional_states = self._count_unique_states(functional_rows)

        issue_type_counter: dict[str, int] = {}
        for issue_dir in issue_dirs:
            summary = self._read_json(issue_dir / "summary.json")
            issue_type = str(summary.get("issue_type") or issue_dir.name.split("_")[0]) if isinstance(summary, dict) else issue_dir.name
            issue_type_counter[issue_type] = issue_type_counter.get(issue_type, 0) + 1

        issue_precision = self._issue_precision_score(issue_type_counter)
        recovery_success_rate = self._recovery_success_rate(recovery_rows)

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

        score = 0.0
        score += min(25.0, unique_states * 0.8)
        score += min(25.0, unique_functional_states * 1.0)
        score += functional_step_ratio * 20.0
        score += issue_precision_score * 15.0
        score += recovery_success_rate * 10.0
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
