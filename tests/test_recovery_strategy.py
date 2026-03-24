from __future__ import annotations

from smart_monkey.graph.backtrack import BacktrackHelper
from smart_monkey.graph.checkpoint import Checkpoint
from smart_monkey.graph.navigation_recovery import NavigationRecovery


class StubCheckpointManager:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []
        self.login_checkpoint = Checkpoint(
            checkpoint_id="login_cp",
            state_id="state-login",
            name="login_checkpoint",
            priority=40,
            created_at_ms=1,
            metadata={"app_flags": ["login_page"]},
        )
        self.home_checkpoint = Checkpoint(
            checkpoint_id="home_cp",
            state_id="state-home",
            name="home_checkpoint",
            priority=100,
            created_at_ms=2,
            metadata={"app_flags": ["list_page"]},
        )

    def best_checkpoint(self, exclude_state_id=None, include_login=True):
        self.calls.append(
            {"exclude_state_id": exclude_state_id, "include_login": include_login}
        )
        if include_login:
            return self.login_checkpoint
        return self.home_checkpoint


def test_backtrack_prefers_non_login_checkpoint_when_requested(tmp_path) -> None:
    manager = StubCheckpointManager()
    helper = BacktrackHelper(manager, tmp_path)

    decision = helper.choose(
        current_state_id="state-stuck",
        stuck_score=10,
        out_of_app=False,
        avoid_login_checkpoint=True,
    )

    assert decision.strategy == "restart_to_checkpoint"
    assert decision.checkpoint is not None
    assert decision.checkpoint.name == "home_checkpoint"
    assert manager.calls[0]["include_login"] is False


def test_backtrack_falls_back_to_login_checkpoint_when_no_non_login_checkpoint(tmp_path) -> None:
    class LoginOnlyCheckpointManager(StubCheckpointManager):
        def best_checkpoint(self, exclude_state_id=None, include_login=True):
            self.calls.append(
                {"exclude_state_id": exclude_state_id, "include_login": include_login}
            )
            if include_login:
                return self.login_checkpoint
            return None

    manager = LoginOnlyCheckpointManager()
    helper = BacktrackHelper(manager, tmp_path)

    decision = helper.choose(
        current_state_id="state-stuck",
        stuck_score=10,
        out_of_app=False,
        avoid_login_checkpoint=True,
    )

    assert decision.strategy == "restart_to_checkpoint"
    assert decision.checkpoint is not None
    assert decision.checkpoint.name == "login_checkpoint"
    assert [call["include_login"] for call in manager.calls] == [False, True]


def test_navigation_recovery_filters_login_regressive_actions(tmp_path) -> None:
    recovery = NavigationRecovery(tmp_path)
    rows = [
        {
            "action": {
                "action_type": "click",
                "target_element_id": "logout_btn",
                "params": {"x": 1, "y": 1},
                "tags": ["logout", "退出登录"],
            }
        },
        {
            "action": {
                "action_type": "click",
                "target_element_id": "safe_btn",
                "params": {"x": 2, "y": 2},
                "tags": ["detail"],
            }
        },
    ]

    filtered = recovery._filter_actions(rows)

    assert len(filtered) == 1
    assert filtered[0]["action"]["target_element_id"] == "safe_btn"

