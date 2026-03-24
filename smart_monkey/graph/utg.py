from __future__ import annotations

from dataclasses import asdict, dataclass, field

from smart_monkey.models import Action, Transition


@dataclass(slots=True)
class EdgeStats:
    execute_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    crash_count: int = 0
    out_of_app_count: int = 0


@dataclass(slots=True)
class GraphEdge:
    from_state_id: str
    to_state_id: str
    action_type: str
    target_element_id: str | None
    stats: EdgeStats = field(default_factory=EdgeStats)


@dataclass(slots=True)
class UTG:
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: dict[str, GraphEdge] = field(default_factory=dict)

    def add_state(self, state_id: str, meta: dict | None = None) -> None:
        self.nodes.setdefault(state_id, meta or {})

    def add_transition(self, transition: Transition, action: Action) -> None:
        self.add_state(transition.from_state_id)
        self.add_state(transition.to_state_id)
        edge_key = self._edge_key(
            transition.from_state_id,
            transition.to_state_id,
            action.action_type.value,
            action.target_element_id,
        )
        edge = self.edges.setdefault(
            edge_key,
            GraphEdge(
                from_state_id=transition.from_state_id,
                to_state_id=transition.to_state_id,
                action_type=action.action_type.value,
                target_element_id=action.target_element_id,
            ),
        )
        edge.stats.execute_count += 1
        if transition.changed:
            edge.stats.changed_count += 1
        else:
            edge.stats.unchanged_count += 1
        if transition.crash:
            edge.stats.crash_count += 1
        if transition.out_of_app:
            edge.stats.out_of_app_count += 1

    def outgoing_edges(self, state_id: str) -> list[GraphEdge]:
        return [edge for edge in self.edges.values() if edge.from_state_id == state_id]

    def to_dict(self) -> dict:
        return {
            "nodes": self.nodes,
            "edges": [
                {
                    "from_state_id": edge.from_state_id,
                    "to_state_id": edge.to_state_id,
                    "action_type": edge.action_type,
                    "target_element_id": edge.target_element_id,
                    "stats": asdict(edge.stats),
                }
                for edge in self.edges.values()
            ],
        }

    @staticmethod
    def _edge_key(from_state_id: str, to_state_id: str, action_type: str, target_element_id: str | None) -> str:
        return f"{from_state_id}|{to_state_id}|{action_type}|{target_element_id}"
