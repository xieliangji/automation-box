from __future__ import annotations

from pathlib import Path
from typing import Protocol


class DeviceDriver(Protocol):
    serial: str | None

    def get_foreground_package(self) -> str:
        ...

    def get_current_activity(self) -> str | None:
        ...

    def dump_hierarchy(self) -> str:
        ...

    def take_screenshot(self, path: str | Path) -> None:
        ...

    def click(self, x: int, y: int) -> bool:
        ...

    def long_click(self, x: int, y: int, duration_ms: int = 800) -> bool:
        ...

    def input_text(self, text: str) -> bool:
        ...

    def clear_text(self) -> bool:
        ...

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        ...

    def pinch(
        self,
        x1_start: int,
        y1_start: int,
        x1_end: int,
        y1_end: int,
        x2_start: int,
        y2_start: int,
        x2_end: int,
        y2_end: int,
        duration_ms: int = 280,
    ) -> bool:
        ...

    def press_back(self) -> bool:
        ...

    def press_home(self) -> bool:
        ...

    def start_app(self, package_name: str, activity: str | None = None) -> bool:
        ...

    def stop_app(self, package_name: str) -> bool:
        ...

    def wait_idle(self, timeout_ms: int = 1500) -> None:
        ...
