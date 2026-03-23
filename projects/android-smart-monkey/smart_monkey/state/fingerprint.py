from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from smart_monkey.models import DeviceState, UIElement


_NUM_RE = re.compile(r"\d+")
_TIME_RE = re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b")


@dataclass(slots=True)
class StateFingerprinter:
    """Build raw and stable hashes for a device state."""

    def build_raw_hash(self, state: DeviceState) -> str:
        payload = "\n".join(self._raw_element_signature(element) for element in state.elements)
        payload = f"{state.package_name}|{state.activity_name}|{payload}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def build_stable_hash(self, state: DeviceState) -> str:
        signatures = [self._stable_element_signature(element, state.screen_size) for element in state.elements]
        signatures.sort()
        payload = "\n".join(signatures)
        payload = f"{state.package_name}|{state.activity_name}|{sorted(state.popup_flags)}|{payload}"
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def build_state_id(self, state: DeviceState) -> str:
        return self.build_stable_hash(state)[:16]

    def _raw_element_signature(self, element: UIElement) -> str:
        return "|".join(
            [
                element.class_name,
                element.resource_id or "",
                element.text or "",
                element.content_desc or "",
                str(element.visible_bounds),
                str(element.clickable),
                str(element.editable),
                str(element.scrollable),
                element.xpath,
            ]
        )

    def _stable_element_signature(self, element: UIElement, screen_size: tuple[int, int]) -> str:
        width, height = screen_size
        left, top, right, bottom = element.visible_bounds
        x_bucket = self._bucket(left, width)
        y_bucket = self._bucket(top, height)
        w_bucket = self._bucket(max(right - left, 0), width)
        h_bucket = self._bucket(max(bottom - top, 0), height)
        return "|".join(
            [
                element.class_name,
                element.resource_id or "",
                self._normalize_text(element.text or ""),
                self._normalize_text(element.content_desc or ""),
                str(element.clickable),
                str(element.editable),
                str(element.scrollable),
                f"{x_bucket}:{y_bucket}:{w_bucket}:{h_bucket}",
            ]
        )

    def _normalize_text(self, value: str) -> str:
        value = value.strip().lower()
        value = _TIME_RE.sub("<TIME>", value)
        value = _NUM_RE.sub("<NUM>", value)
        return value[:32]

    @staticmethod
    def _bucket(value: int, total: int) -> int:
        if total <= 0:
            return 0
        ratio = max(0.0, min(1.0, value / total))
        return int(ratio * 10)
