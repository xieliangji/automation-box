from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


class ReplayLookup:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.replay_file = self.output_dir / "replay" / "actions_replay.jsonl"

    def by_state(self) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in self._read_jsonl(self.replay_file):
            state_id = row.get("state_id")
            if state_id:
                grouped[str(state_id)].append(row)
        return dict(grouped)

    def recent_from_state(self, state_id: str, tail: int = 5) -> list[dict[str, Any]]:
        grouped = self.by_state()
        rows = grouped.get(state_id, [])
        if not rows:
            return []
        return rows[-tail:]

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
