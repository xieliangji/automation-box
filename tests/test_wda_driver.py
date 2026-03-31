from __future__ import annotations

from pathlib import Path

from smart_monkey.device.capabilities import DriverCapabilities
from smart_monkey.device.wda_driver import WdaDriver


class StubClient:
    def __init__(self) -> None:
        self.session_id = None
        self.calls: list[tuple[str, tuple]] = []
        self._bundle = "com.demo.app"

    def ensure_session(self):
        self.session_id = "sess-1"
        self.calls.append(("ensure_session", ()))
        return self.session_id

    def get_foreground_bundle_id(self):
        self.calls.append(("get_foreground_bundle_id", ()))
        return self._bundle

    def active_app_info(self):
        self.calls.append(("active_app_info", ()))
        return {"name": "DemoApp"}

    def source(self):
        self.calls.append(("source", ()))
        return "<XCUIElementTypeApplication />"

    def screenshot(self):
        self.calls.append(("screenshot", ()))
        return b"png-bytes"

    def tap(self, x: int, y: int):
        self.calls.append(("tap", (x, y)))
        return True

    def long_press(self, x: int, y: int, duration_ms: int):
        self.calls.append(("long_press", (x, y, duration_ms)))
        return True

    def send_keys(self, text: str):
        self.calls.append(("send_keys", (text,)))
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int):
        self.calls.append(("swipe", (x1, y1, x2, y2, duration_ms)))
        return True

    def pinch(self, *args):
        self.calls.append(("pinch", args))
        return True

    def activate_app(self, bundle_id: str):
        self.calls.append(("activate_app", (bundle_id,)))
        self._bundle = bundle_id
        return True

    def terminate_app(self, bundle_id: str):
        self.calls.append(("terminate_app", (bundle_id,)))
        return True

    def delete_session(self):
        self.calls.append(("delete_session", ()))
        self.session_id = None
        return True


def test_wda_driver_basic_actions(tmp_path: Path) -> None:
    driver = WdaDriver("http://localhost:8100", target_bundle_id="com.demo.app")
    stub = StubClient()
    driver.client = stub  # type: ignore[assignment]

    assert driver.get_foreground_package() == "com.demo.app"
    assert driver.get_current_activity() == "DemoApp"
    assert driver.dump_hierarchy().startswith("<XCUI")
    assert driver.click(10, 20) is True
    assert driver.long_click(10, 20, 700) is True
    assert driver.input_text("abc") is True
    assert driver.swipe(1, 2, 3, 4, 150) is True
    assert driver.pinch(1, 2, 3, 4, 5, 6, 7, 8, 260) is True
    assert driver.start_app("com.demo.app", None) is True
    assert driver.stop_app("com.demo.app") is True

    shot = tmp_path / "shot.png"
    driver.take_screenshot(shot)
    assert shot.read_bytes() == b"png-bytes"


def test_wda_driver_close_deletes_session_when_keep_session_false() -> None:
    driver = WdaDriver("http://localhost:8100", target_bundle_id="com.demo.app", keep_session=False)
    stub = StubClient()
    driver.client = stub  # type: ignore[assignment]
    stub.session_id = "sess-1"

    driver.close()

    assert ("delete_session", ()) in stub.calls


def test_wda_driver_capabilities_are_ios_friendly() -> None:
    driver = WdaDriver("http://localhost:8100", target_bundle_id="com.demo.app")
    caps = driver.capabilities()
    assert isinstance(caps, DriverCapabilities)
    assert caps.platform == "ios"
    assert caps.supports_launch_target is False
    assert caps.supports_press_back is True
    assert caps.supports_press_home is False
    assert caps.supports_stop_app is False
