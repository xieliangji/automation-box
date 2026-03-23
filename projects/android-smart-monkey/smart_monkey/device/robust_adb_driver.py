from __future__ import annotations

import re
from dataclasses import dataclass

from smart_monkey.device.adb_driver import AdbDriver


_COMPONENT_RE = re.compile(r"(?P<pkg>[A-Za-z0-9_.$]+)\/(?P<act>[A-Za-z0-9_.$]+)")


@dataclass(slots=True)
class ForegroundInfo:
    package_name: str = ""
    activity_name: str | None = None
    raw_source: str = ""


class RobustAdbDriver(AdbDriver):
    """ADB driver with more resilient foreground parsing and logcat helpers."""

    def get_foreground_package(self) -> str:
        return self._read_foreground_info().package_name

    def get_current_activity(self) -> str | None:
        return self._read_foreground_info().activity_name

    def read_logcat_tail(self, max_lines: int = 200) -> str:
        result = self._run("logcat", "-d", "-t", str(max_lines), check=False)
        return result.stdout

    def clear_logcat(self) -> None:
        self._run("logcat", "-c", check=False)

    def _read_foreground_info(self) -> ForegroundInfo:
        commands = [
            "dumpsys activity activities | grep mResumedActivity",
            "dumpsys window windows | grep mCurrentFocus",
            "dumpsys window windows | grep mFocusedApp",
            "dumpsys window | grep mCurrentFocus",
        ]
        for command in commands:
            raw = self._shell(command, check=False)
            info = self._parse_foreground_info(raw)
            if info.package_name:
                return info
        return ForegroundInfo()

    def _parse_foreground_info(self, raw: str) -> ForegroundInfo:
        if not raw:
            return ForegroundInfo(raw_source=raw)

        match = _COMPONENT_RE.search(raw)
        if not match:
            return ForegroundInfo(raw_source=raw)

        package_name = match.group("pkg")
        activity_name = match.group("act")
        if activity_name.startswith("."):
            activity_name = f"{package_name}{activity_name}"
        return ForegroundInfo(
            package_name=package_name,
            activity_name=activity_name,
            raw_source=raw,
        )
