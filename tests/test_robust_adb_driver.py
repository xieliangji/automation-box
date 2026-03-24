from __future__ import annotations

from smart_monkey.device.robust_adb_driver import RobustAdbDriver


class _ProbeDriver(RobustAdbDriver):
    def __init__(self, outputs: dict[str, str]) -> None:
        super().__init__(serial=None)
        self.outputs = outputs

    def _shell(self, command: str, check: bool = True, timeout_sec: float | None = None) -> str:  # noqa: ARG002
        return self.outputs.get(command, "")


def test_foreground_parsing_works_without_grep() -> None:
    outputs = {
        "dumpsys activity activities": "\n".join(
            [
                "Some historical lines",
                "mResumedActivity: ActivityRecord{abc u0 com.ugreen.iot/.ui.SplashActivity t12}",
            ]
        )
    }
    driver = _ProbeDriver(outputs)

    assert driver.get_foreground_package() == "com.ugreen.iot"
    assert driver.get_current_activity() == "com.ugreen.iot.ui.SplashActivity"


def test_foreground_parsing_fallback_to_window_dump() -> None:
    outputs = {
        "dumpsys activity activities": "",
        "dumpsys window windows": "mCurrentFocus=Window{afc u0 com.android.settings/.Settings}",
    }
    driver = _ProbeDriver(outputs)

    assert driver.get_foreground_package() == "com.android.settings"
    assert driver.get_current_activity() == "com.android.settings.Settings"
