from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class MarkdownReportGeneratorV2:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.report_dir = self.output_dir / "report"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> Path:
        steps = self._read_jsonl(self.output_dir / "steps.jsonl")
        issues = sorted((self.output_dir / "issues").glob("*")) if (self.output_dir / "issues").exists() else []
        checkpoints = self._read_json(self.output_dir / "checkpoints.json")
        recovery_dir = self.output_dir / "recovery"
        recovery_plans = sorted(recovery_dir.glob("*.json")) if recovery_dir.exists() else []

        lines: list[str] = []
        lines.append("# Android Smart Monkey 运行摘要 V2")
        lines.append("")
        lines.append(f"- 总步数：{len([row for row in steps if row.get('step', -1) >= 0])}")
        lines.append(f"- 恢复事件数：{len([row for row in steps if row.get('recovery_strategy')])}")
        lines.append(f"- Checkpoint 数：{len(checkpoints) if isinstance(checkpoints, list) else 0}")
        lines.append(f"- Recovery Plan 数：{len(recovery_plans)}")
        lines.append(f"- Issue 数：{len(issues)}")
        lines.append("")
        lines.append("## 最近恢复事件")
        recovery_rows = [row for row in steps if row.get("recovery_strategy")]
        if recovery_rows:
            for row in recovery_rows[-10:]:
                lines.append(
                    f"- strategy={row.get('recovery_strategy')} reason={row.get('recovery_reason')} checkpoint={row.get('checkpoint_id')}"
                )
        else:
            lines.append("- 暂无")
        lines.append("")
        lines.append("## Checkpoint 概览")
        if isinstance(checkpoints, list) and checkpoints:
            for item in checkpoints[:10]:
                lines.append(
                    f"- {item.get('checkpoint_id')} name={item.get('name')} priority={item.get('priority')} state={item.get('state_id')}"
                )
        else:
            lines.append("- 暂无")
        lines.append("")
        lines.append("## Recovery Plans")
        if recovery_plans:
            for plan in recovery_plans[-10:]:
                lines.append(f"- {plan.name}")
        else:
            lines.append("- 暂无")
        lines.append("")
        lines.append("## 最近 Issue")
        if issues:
            for issue_dir in issues[-10:]:
                lines.append(f"- {issue_dir.name}")
        else:
            lines.append("- 暂无")

        target = self.report_dir / "summary_v2.md"
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return target

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
