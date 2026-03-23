from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class PlannedPath:
    from_state_id: str
    candidate_state_ids: list[str]
    reason: str


class UtgPathPlanner:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.utg_file = self.output_dir / "utg.json"

    def plan_from_checkpoint(self, checkpoint_state_id: str, max_depth: int = 2, top_k: int = 3) -> PlannedPath:
        utg = self._read_json(self.utg_file)
        edges = utg.get("edges", []) if isinstance(utg, dict) else []
        adjacency: dict[str, list[dict[str, Any]]] = {}
        for edge in edges:
            adjacency.setdefault(edge.get("from_state_id", ""), []).append(edge)

        queue: deque[tuple[str, int]] = deque([(checkpoint_state_id, 0)])
        visited = {checkpoint_state_id}
        scored: list[tuple[str, int]] = []

        while queue:
            state_id, depth = queue.popleft()
            if depth >= max_depth:
                continue
            for edge in adjacency.get(state_id, []):
                to_state_id = edge.get("to_state_id")
                if not to_state_id or to_state_id in visited:
                    continue
                visited.add(to_state_id)
                stats = edge.get("stats", {})
                score = int(stats.get("changed_count", 0)) * 3 + int(stats.get("execute_count", 0)) - int(stats.get("unchanged_count", 0))
                scored.append((to_state_id, score))
                queue.append((to_state_id, depth + 1))

        scored.sort(key=lambda item: item[1], reverse=True)
        return PlannedPath(
            from_state_id=checkpoint_state_id,
            candidate_state_ids=[state_id for state_id, _ in scored[:top_k]],
            reason="utg reachable states ranked by changed_count and execute_count",
        )

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
