from __future__ import annotations

import json
from pathlib import Path

from smart_monkey.graph.utg_path_planner import UtgPathPlanner


def test_planner_ranks_reachable_states_by_edge_stats(tmp_path: Path) -> None:
    utg = {
        "nodes": {},
        "edges": [
            {
                "from_state_id": "cp",
                "to_state_id": "s1",
                "stats": {"changed_count": 3, "execute_count": 5, "unchanged_count": 1},
            },
            {
                "from_state_id": "cp",
                "to_state_id": "s2",
                "stats": {"changed_count": 1, "execute_count": 10, "unchanged_count": 0},
            },
            {
                "from_state_id": "s1",
                "to_state_id": "s3",
                "stats": {"changed_count": 2, "execute_count": 2, "unchanged_count": 0},
            },
        ],
    }
    (tmp_path / "utg.json").write_text(json.dumps(utg), encoding="utf-8")

    planner = UtgPathPlanner(tmp_path)
    plan = planner.plan_from_checkpoint("cp", max_depth=2, top_k=3)

    assert plan.from_state_id == "cp"
    assert plan.candidate_state_ids[0] == "s1"
    assert "s2" in plan.candidate_state_ids
    assert "s3" in plan.candidate_state_ids


def test_planner_returns_empty_candidates_when_utg_missing(tmp_path: Path) -> None:
    planner = UtgPathPlanner(tmp_path)
    plan = planner.plan_from_checkpoint("missing")

    assert plan.from_state_id == "missing"
    assert plan.candidate_state_ids == []
