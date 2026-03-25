from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MarkdownReportGenerator:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.report_dir = self.output_dir / "report"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> Path:
        steps = self._read_jsonl(self.output_dir / "steps.jsonl")
        actions = self._read_jsonl(self.output_dir / "actions.jsonl")
        transitions = self._read_jsonl(self.output_dir / "transitions.jsonl")
        issue_dirs = sorted((self.output_dir / "issues").glob("*")) if (self.output_dir / "issues").exists() else []
        unique_states = self._count_unique_states(steps)
        action_stats = self._count_action_types(steps)
        runtime_steps = [row for row in steps if isinstance(row.get("step"), int) and row.get("step", -1) >= 0]
        recovery_rows = [row for row in steps if row.get("recovery_strategy")]
        bootstrap_rows = [row for row in steps if row.get("bootstrap_status")]
        coverage_benchmark = self._read_json(self.output_dir / "report" / "coverage_benchmark.json")
        coverage_benchmark = coverage_benchmark if isinstance(coverage_benchmark, dict) else {}

        lines: list[str] = []
        lines.append("# Android Smart Monkey 运行摘要")
        lines.append("")
        lines.append(f"- 总记录行：{len(steps)}")
        lines.append(f"- 业务 Step 行：{len(runtime_steps)}")
        lines.append(f"- 动作数：{len(actions)}")
        lines.append(f"- 迁移数：{len(transitions)}")
        lines.append(f"- 状态数：{unique_states}")
        lines.append(f"- Issue 数：{len(issue_dirs)}")
        lines.append(f"- 恢复事件数：{len(recovery_rows)}")
        lines.append(f"- 登录引导事件数：{len(bootstrap_rows)}")
        lines.append("")
        lines.append("## Coverage Benchmark KPI")
        current_run = coverage_benchmark.get("current_run", {}) if isinstance(coverage_benchmark, dict) else {}
        comparison = coverage_benchmark.get("comparison", {}) if isinstance(coverage_benchmark, dict) else {}
        if isinstance(current_run, dict) and current_run:
            lines.append(f"- composite_score: {current_run.get('composite_score')}")
            lines.append(f"- unique_functional_states: {current_run.get('unique_functional_states')}")
            lines.append(f"- functional_step_ratio: {current_run.get('functional_step_ratio')}")
            lines.append(f"- login_step_ratio: {current_run.get('login_step_ratio')}")
            lines.append(f"- out_of_app_ratio: {current_run.get('out_of_app_ratio')}")
            lines.append(f"- issue_precision_score: {current_run.get('issue_precision_score')}")
            lines.append(f"- recovery_success_rate: {current_run.get('recovery_success_rate')}")
            lines.append(f"- actions_per_minute: {current_run.get('actions_per_minute')}")
            lines.append(f"- crash_per_1k_actions: {current_run.get('crash_per_1k_actions')}")
            lines.append(f"- burst_step_ratio: {current_run.get('burst_step_ratio')}")
            lines.append(f"- time_to_first_crash_steps: {current_run.get('time_to_first_crash_steps')}")
            lines.append(f"- learning_step_ratio: {current_run.get('learning_step_ratio')}")
            lines.append(f"- learning_exploration_rate: {current_run.get('learning_exploration_rate')}")
            lines.append(f"- learning_average_reward: {current_run.get('learning_average_reward')}")
        else:
            lines.append("- 暂无")
        if isinstance(comparison, dict) and comparison:
            lines.append("- 与 baseline 对比：")
            for key, payload in sorted(comparison.items()):
                if not isinstance(payload, dict):
                    continue
                lines.append(
                    f"  - {key}: current={payload.get('current')} baseline={payload.get('baseline')} delta={payload.get('delta')}"
                )
        lines.append("")
        lines.append("## 关键产物")
        for label, path in [
            ("UTG JSON", self.output_dir / "utg.json"),
            ("索引 JSON", self.output_dir / "index" / "lookup.json"),
            ("Replay JSONL", self.output_dir / "replay" / "actions_replay.jsonl"),
            ("Checkpoint JSON", self.output_dir / "checkpoints.json"),
        ]:
            lines.append(f"- {label}：{'已生成' if path.exists() else '未生成'} ({path.name})")
        lines.append("")
        lines.append("## Action Type 分布")
        for name, count in sorted(action_stats.items()):
            lines.append(f"- {name}: {count}")
        lines.append("")
        lines.append("## 最近 Issue")
        if issue_dirs:
            for issue_dir in issue_dirs[-10:]:
                lines.append(f"- {issue_dir.name}")
        else:
            lines.append("- 暂无")
        lines.append("")
        lines.append("## 最近 10 步")
        for step in runtime_steps[-10:]:
            lines.append(
                f"- step={step.get('step')} action={step.get('action_type')} changed={step.get('changed')} out_of_app={step.get('out_of_app')}"
            )
        lines.append("")
        lines.append("## 最近登录引导事件")
        if bootstrap_rows:
            for row in bootstrap_rows[-10:]:
                lines.append(
                    f"- at_step={row.get('bootstrap_at_step')} status={row.get('bootstrap_status')} reason={row.get('bootstrap_reason')}"
                )
        else:
            lines.append("- 暂无")

        target = self.report_dir / "summary.md"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target

    def _count_unique_states(self, steps: list[dict[str, Any]]) -> int:
        states = set()
        for step in steps:
            current_state_id = step.get("current_state_id")
            next_state_id = step.get("next_state_id")
            if current_state_id:
                states.add(current_state_id)
            if next_state_id:
                states.add(next_state_id)
        return len(states)

    def _count_action_types(self, steps: list[dict[str, Any]]) -> dict[str, int]:
        counter: dict[str, int] = {}
        for step in steps:
            action_type = step.get("action_type")
            if action_type:
                counter[action_type] = counter.get(action_type, 0) + 1
        return counter

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
