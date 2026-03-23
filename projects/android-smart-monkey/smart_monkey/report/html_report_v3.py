from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class HtmlReportGeneratorV3:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.report_dir = self.output_dir / "report"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> Path:
        steps = self._read_jsonl(self.output_dir / "steps.jsonl")
        checkpoints = self._read_json(self.output_dir / "checkpoints.json")
        recovery_metrics = self._read_json(self.output_dir / "report" / "recovery_metrics.json")
        validation_rows = self._read_jsonl(self.output_dir / "recovery" / "recovery_validation.jsonl")

        checkpoint_count = len(checkpoints) if isinstance(checkpoints, list) else 0
        recovery_events = len([row for row in steps if row.get("recovery_strategy")])
        exact_hits = sum(1 for row in validation_rows if row.get("exact_anchor_hit"))
        candidate_hits = sum(1 for row in validation_rows if row.get("candidate_hit"))

        parts: list[str] = []
        parts.append("<!DOCTYPE html><html lang='zh-CN'><head><meta charset='UTF-8'><title>Smart Monkey Report V3</title>")
        parts.append("<style>body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:24px;line-height:1.55}table{border-collapse:collapse;width:100%;margin-top:12px}th,td{border:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}th{background:#f7f7f7}.cards{display:flex;gap:16px;flex-wrap:wrap}.card{border:1px solid #ddd;border-radius:10px;padding:16px;min-width:180px}.mono{font-family:ui-monospace,Menlo,Consolas,monospace}</style></head><body>")
        parts.append("<h1>Android Smart Monkey 运行报告 V3</h1>")
        parts.append("<div class='cards'>")
        parts.append(self._card("总步数", str(len([row for row in steps if row.get('step', -1) >= 0]))))
        parts.append(self._card("Checkpoint 数", str(checkpoint_count)))
        parts.append(self._card("恢复事件数", str(recovery_events)))
        parts.append(self._card("Exact Anchor Hit", str(exact_hits)))
        parts.append(self._card("Candidate Hit", str(candidate_hits)))
        parts.append("</div>")

        parts.append("<h2>恢复指标</h2><table><thead><tr><th>Metric</th><th>Value</th></tr></thead><tbody>")
        if isinstance(recovery_metrics, dict):
            for key, value in recovery_metrics.items():
                if isinstance(value, (dict, list)):
                    continue
                parts.append(f"<tr><td>{key}</td><td>{value}</td></tr>")
        parts.append("</tbody></table>")

        parts.append("<h2>最近恢复事件</h2><table><thead><tr><th>Strategy</th><th>Reason</th><th>Checkpoint</th><th>Plan Actions</th></tr></thead><tbody>")
        recovery_rows = [row for row in steps if row.get("recovery_strategy")]
        if recovery_rows:
            for row in recovery_rows[-10:]:
                parts.append(
                    "<tr>"
                    f"<td>{row.get('recovery_strategy', '')}</td>"
                    f"<td>{row.get('recovery_reason', '')}</td>"
                    f"<td class='mono'>{row.get('checkpoint_id', '')}</td>"
                    f"<td>{row.get('recovery_plan_actions', '')}</td>"
                    "</tr>"
                )
        else:
            parts.append("<tr><td colspan='4'>暂无</td></tr>")
        parts.append("</tbody></table>")

        parts.append("<h2>恢复校验</h2><table><thead><tr><th>Actual State</th><th>Exact Anchor Hit</th><th>Candidate Hit</th><th>In Target App</th></tr></thead><tbody>")
        if validation_rows:
            for row in validation_rows[-10:]:
                parts.append(
                    "<tr>"
                    f"<td class='mono'>{row.get('actual_state_id', '')}</td>"
                    f"<td>{row.get('exact_anchor_hit', '')}</td>"
                    f"<td>{row.get('candidate_hit', '')}</td>"
                    f"<td>{row.get('in_target_app', '')}</td>"
                    "</tr>"
                )
        else:
            parts.append("<tr><td colspan='4'>暂无</td></tr>")
        parts.append("</tbody></table></body></html>")

        target = self.report_dir / "index_v3.html"
        target.write_text("".join(parts), encoding="utf-8")
        return target

    def _card(self, title: str, value: str) -> str:
        return f"<div class='card'><strong>{title}</strong><div>{value}</div></div>"

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

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
