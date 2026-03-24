from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class RecoveryMetricsGenerator:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.report_dir = self.output_dir / "report"
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self) -> Path:
        steps = self._read_jsonl(self.output_dir / "steps.jsonl")
        checkpoints = self._read_json(self.output_dir / "checkpoints.json")
        recovery_dir = self.output_dir / "recovery"
        recovery_plans = sorted(recovery_dir.glob("*.json")) if recovery_dir.exists() else []

        recovery_rows = [row for row in steps if row.get("recovery_strategy")]
        bootstrap_rows = [row for row in steps if row.get("bootstrap_status")]
        strategy_counter: dict[str, int] = {}
        checkpoint_counter: dict[str, int] = {}
        bootstrap_counter: dict[str, int] = {}
        for row in recovery_rows:
            strategy = str(row.get("recovery_strategy") or "unknown")
            strategy_counter[strategy] = strategy_counter.get(strategy, 0) + 1
            checkpoint_id = row.get("checkpoint_id")
            if checkpoint_id:
                checkpoint_counter[str(checkpoint_id)] = checkpoint_counter.get(str(checkpoint_id), 0) + 1
        for row in bootstrap_rows:
            status = str(row.get("bootstrap_status") or "unknown")
            bootstrap_counter[status] = bootstrap_counter.get(status, 0) + 1

        payload = {
            "recovery_events": len(recovery_rows),
            "bootstrap_events": len(bootstrap_rows),
            "checkpoint_count": len(checkpoints) if isinstance(checkpoints, list) else 0,
            "recovery_plan_count": len(recovery_plans),
            "strategy_counter": strategy_counter,
            "checkpoint_counter": checkpoint_counter,
            "bootstrap_counter": bootstrap_counter,
            "latest_bootstrap_rows": bootstrap_rows[-20:],
            "latest_recovery_rows": recovery_rows[-20:],
        }
        target = self.report_dir / "recovery_metrics.json"
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
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
