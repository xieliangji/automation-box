from __future__ import annotations

from smart_monkey.models import DeviceState, UIElement
from smart_monkey.state.fingerprint import StateFingerprinter


def make_state(text: str) -> DeviceState:
    return DeviceState(
        state_id="",
        raw_hash="",
        stable_hash="",
        package_name="com.demo.app",
        activity_name=".MainActivity",
        screen_size=(1080, 1920),
        elements=[
            UIElement(
                element_id="e0001",
                class_name="android.widget.TextView",
                resource_id="com.demo:id/title",
                text=text,
                clickable=True,
                visible_bounds=(100, 200, 400, 260),
                xpath="/hierarchy/node[0]",
            )
        ],
    )


def test_stable_hash_normalizes_time_and_numbers() -> None:
    fingerprinter = StateFingerprinter()
    state_a = make_state("Order 123 at 12:34")
    state_b = make_state("Order 456 at 18:59")

    assert fingerprinter.build_raw_hash(state_a) != fingerprinter.build_raw_hash(state_b)
    assert fingerprinter.build_stable_hash(state_a) == fingerprinter.build_stable_hash(state_b)


def test_state_id_uses_stable_hash_prefix() -> None:
    fingerprinter = StateFingerprinter()
    state = make_state("Hello 100")
    stable_hash = fingerprinter.build_stable_hash(state)

    assert fingerprinter.build_state_id(state) == stable_hash[:16]
