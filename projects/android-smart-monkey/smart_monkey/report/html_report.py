from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class HtmlReportGenerator:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.report_dir = self.output_dir / "report"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> Path:
        steps = self._read_jsonl(self.output_dir / "steps.jsonl")
        actions = self._read_jsonl(self.output_dir / "actions.jsonl")
        transitions = self._read_jsonl(self.output_dir / "transitions.jsonl")
        issue_dirs = sorted((self.output_dir / "issues").glob("*")) if (self.output_dir / "issues").exists() else []
        screenshots_dir = self.output_dir / "screenshots"
        replay_file = self.output_dir / "replay" / "actions_replay.jsonl"
        utg_file = self.output_dir / "utg.json"
        index_file = self.output_dir / "index" / "lookup.json"

        unique_states = self._count_unique_states(steps)
        latest_issues = [issue_dir.name for issue_dir in issue_dirs[-10:]]
        recent_steps = steps[-10:]

        html = f"""
<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\" />
  <title>Smart Monkey Run Report</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 24px; line-height: 1.5; }}
    h1, h2 {{ margin-top: 24px; }}
    .cards {{ display: flex; gap: 16px; flex-wrap: wrap; }}
    .card {{ border: 1px solid #ddd; border-radius: 10px; padding: 16px; min-width: 180px; }}
    code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 6px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f7f7f7; }}
    ul {{ padding-left: 20px; }}
  </style>
</head>
<body>
  <h1>Android Smart Monkey 运行报告</h1>
  <div class=\"cards\">
    <div class=\"card\"><strong>总步数</strong><div>{len(steps)}</div></div>
    <div class=\"card\"><strong>动作数</strong><div>{len(actions)}</div></div>
    <div class=\"card\"><strong>迁移数</strong><div>{len(transitions)}</div></div>
    <div class=\"card\"><strong>状态数</strong><div>{unique_states}</div></div>
    <div class=\"card\"><strong>Issue 数</strong><div>{len(issue_dirs)}</div></div>
  </div>

  <h2>产物索引</h2>
  <ul>
    <li><code>{utg_file.name}</code>{'（已生成）' if utg_file.exists() else '（未生成）'}</li>
    <li><code>{replay_file.name}</code>{'（已生成）' if replay_file.exists() else '（未生成）'}</li>
    <li><code>{index_file.name}</code>{'（已生成）' if index_file.exists() else '（未生成）'}</li>
    <li><code>screenshots/</code>{'（存在）' if screenshots_dir.exists() else '（未生成）'}</li>
  </ul>

  <h2>最近 Issue</h2>
  <ul>
    {''.join(f'<li>{name}</li>' for name in latest_issues) if latest_issues else '<li>暂无</li>'}
  </ul>

  <h2>最近 10 步</h2>
  <table>
    <thead>
      <tr><th>Step</th><th>Current State</th><th>Next State</th><th>Action</th><th>Changed</th><th>Out Of App</th></tr>
    </thead>
    <tbody>
      {''.join(self._render_step_row(step) for step in recent_steps)}
    </tbody>
  </table>
</body>
</html>
"""
        target = self.report_dir / "index.html"
        target.write_text(html, encoding="utf-8")
        return target

    def _render_step_row(self, step: dict[str, Any]) -> str:
        return (
            "<tr>"
            f"<td>{step.get('step', '')}</td>"
            f"<td>{step.get('current_state_id', '')}</td>"
            f"<td>{step.get('next_state_id', '')}</td>"
            f"<td>{step.get('action_type', '')}</td>"
            f"<td>{step.get('changed', '')}</td>"
            f"<td>{step.get('out_of_app', '')}</td>"
            "</tr>"
        )

    def _count_unique_states(self, steps: list[dict[str, Any]]) -> int:
        states = set()
        for step in steps:
            if step.get("current_state_id"):
                states.add(step["current_state_id"])
            if step.get("next_state_id"):
                states.add(step["next_state_id"])
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
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows
