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

        lines: list[str] = []
        lines.append("# Android Smart Monkey 运行摘要")
        lines.append("")
        lines.append(f"- 总步数：{len(steps)}")
        lines.append(f"- 动作数：{len(actions)}")
        lines.append(f"- 迁移数：{len(transitions)}")
        lines.append(f"- 状态数：{unique_states}")
        lines.append(f"- Issue 数：{len(issue_dirs)}")
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
        for step in steps[-10:]:
            lines.append(
                f"- step={step.get('step')} action={step.get('action_type')} changed={step.get('changed')} out_of_app={step.get('out_of_app')}"
            )

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
