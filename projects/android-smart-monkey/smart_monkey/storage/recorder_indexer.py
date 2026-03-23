from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


class RecorderIndexer:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.index_dir = self.output_dir / "index"
        self.index_dir.mkdir(parents=True, exist_ok=True)

    def build(self) -> dict[str, Any]:
        steps = self._read_jsonl(self.output_dir / "steps.jsonl")
        actions = self._read_jsonl(self.output_dir / "actions.jsonl")
        transitions = self._read_jsonl(self.output_dir / "transitions.jsonl")

        step_to_rows: dict[str, list[int]] = defaultdict(list)
        state_to_steps: dict[str, list[int]] = defaultdict(list)
        action_type_to_steps: dict[str, list[int]] = defaultdict(list)

        for index, row in enumerate(steps):
            step = row.get("step")
            if step is None:
                continue
            step_to_rows[str(step)].append(index)
            current_state_id = row.get("current_state_id")
            next_state_id = row.get("next_state_id")
            action_type = row.get("action_type")
            if current_state_id:
                state_to_steps[str(current_state_id)].append(step)
            if next_state_id:
                state_to_steps[str(next_state_id)].append(step)
            if action_type:
                action_type_to_steps[str(action_type)].append(step)

        summary = {
            "steps_count": len(steps),
            "actions_count": len(actions),
            "transitions_count": len(transitions),
            "unique_states": len(state_to_steps),
            "action_types": sorted(action_type_to_steps.keys()),
        }

        payload = {
            "summary": summary,
            "step_to_rows": dict(step_to_rows),
            "state_to_steps": {key: sorted(set(value)) for key, value in state_to_steps.items()},
            "action_type_to_steps": {key: sorted(set(value)) for key, value in action_type_to_steps.items()},
        }
        (self.index_dir / "lookup.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return payload

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
