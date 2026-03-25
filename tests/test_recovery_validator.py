from __future__ import annotations

from pathlib import Path

from smart_monkey.graph.recovery_validator import RecoveryValidator
from smart_monkey.models import DeviceState


def make_state(state_id: str, package_name: str = "com.demo.app") -> DeviceState:
    return DeviceState(
        state_id=state_id,
        raw_hash="",
        stable_hash="",
        package_name=package_name,
        activity_name=".MainActivity",
        screen_size=(1080, 1920),
        elements=[],
    )


def test_validator_records_exact_anchor_hit(tmp_path: Path) -> None:
    validator = RecoveryValidator(tmp_path, target_package="com.demo.app")
    state = make_state("state-anchor")

    result = validator.validate(
        actual_state=state,
        expected_anchor_state="state-anchor",
        candidate_state_ids=["state-anchor", "state-alt"],
        reason="unit test",
    )

    assert result.exact_anchor_hit is True
    assert result.candidate_hit is True
    assert result.in_target_app is True


def test_validator_summary_counts_rows(tmp_path: Path) -> None:
    validator = RecoveryValidator(tmp_path, target_package="com.demo.app")
    validator.validate(
        actual_state=make_state("state-1"),
        expected_anchor_state="state-1",
        candidate_state_ids=["state-1"],
        reason="case 1",
    )
    validator.validate(
        actual_state=make_state("state-2", package_name="com.other.app"),
        expected_anchor_state="state-1",
        candidate_state_ids=["state-3"],
        reason="case 2",
    )

    summary = validator.summary()

    assert summary["count"] == 2
    assert summary["exact_anchor_hits"] == 1
    assert summary["candidate_hits"] == 1
    assert summary["in_target_app_hits"] == 1
