from __future__ import annotations

import time
from pathlib import Path
from urllib.parse import urlparse

from smart_monkey.device.capabilities import DriverCapabilities
from smart_monkey.device.wda_client import WdaClient


class WdaDriver:
    def __init__(
        self,
        wda_url: str,
        target_bundle_id: str,
        serial: str | None = None,
        launch_target: str | None = None,
        request_timeout_sec: float = 20.0,
        session_create_timeout_sec: float = 30.0,
        request_retry: int = 2,
        keep_session: bool = True,
        auto_recreate_session: bool = True,
    ) -> None:
        if not wda_url.strip():
            raise ValueError("WDA URL must not be empty.")
        if not target_bundle_id.strip():
            raise ValueError("target_bundle_id must not be empty.")
        self.serial = serial
        self.wda_url = wda_url.strip()
        self.target_bundle_id = target_bundle_id.strip()
        self.launch_target = launch_target
        self.keep_session = keep_session
        self.auto_recreate_session = auto_recreate_session
        self.client = WdaClient(
            base_url=self.wda_url,
            request_timeout_sec=request_timeout_sec,
            session_create_timeout_sec=session_create_timeout_sec,
            request_retry=request_retry,
        )

    @property
    def _host(self) -> str:
        host = urlparse(self.wda_url).hostname
        return host or "ios-device"

    def _ensure_session(self) -> str:
        if self.client.session_id:
            return self.client.session_id
        return self.client.ensure_session()

    def _call(self, fn, *args, **kwargs):
        self._ensure_session()
        try:
            return fn(*args, **kwargs)
        except RuntimeError:
            if not self.auto_recreate_session:
                raise
            self.client.session_id = None
            self._ensure_session()
            return fn(*args, **kwargs)

    @staticmethod
    def _session_bundle_capabilities(bundle_id: str) -> dict[str, str]:
        return {"bundleId": bundle_id, "appium:bundleId": bundle_id}

    def capabilities(self) -> DriverCapabilities:
        return DriverCapabilities(
            platform="ios",
            supports_launch_target=False,
            supports_press_back=True,
            supports_press_home=False,
            supports_stop_app=False,
            supports_log_stream=False,
        )

    def get_foreground_package(self) -> str:
        return self._call(self.client.get_foreground_bundle_id)

    def get_current_activity(self) -> str | None:
        info = self._call(self.client.active_app_info)
        app_name = info.get("name")
        if isinstance(app_name, str) and app_name.strip():
            return app_name
        return None

    def dump_hierarchy(self) -> str:
        return self._call(self.client.source)

    def take_screenshot(self, path: str | Path) -> None:
        data = self._call(self.client.screenshot)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    def click(self, x: int, y: int) -> bool:
        return bool(self._call(self.client.tap, x, y))

    def long_click(self, x: int, y: int, duration_ms: int = 800) -> bool:
        return bool(self._call(self.client.long_press, x, y, duration_ms))

    def input_text(self, text: str) -> bool:
        return bool(self._call(self.client.send_keys, text))

    def clear_text(self) -> bool:
        return True

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> bool:
        return bool(self._call(self.client.swipe, x1, y1, x2, y2, duration_ms))

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
        return bool(
            self._call(
                self.client.pinch,
                x1_start,
                y1_start,
                x1_end,
                y1_end,
                x2_start,
                y2_start,
                x2_end,
                y2_end,
                duration_ms,
            )
        )

    def press_back(self) -> bool:
        self._call(self.client.swipe, 20, 300, 260, 300, 200)
        return True

    def press_home(self) -> bool:
        self._call(self.client.tap, 210, 900)
        return True

    def start_app(self, package_name: str, activity: str | None = None) -> bool:
        bundle_id = package_name or self.target_bundle_id
        self._call(self.client.activate_app, bundle_id)
        self.wait_idle(400)
        if self.get_foreground_package() == bundle_id:
            return True

        # 部分设备上 activate API 会返回成功但未切前台，回退到重建会话并带 bundle 能力。
        self.client.delete_session()
        self.client.ensure_session(capabilities=self._session_bundle_capabilities(bundle_id))
        self.wait_idle(700)
        if self.get_foreground_package() == bundle_id:
            return True

        # 最后再尝试一次激活，确保在 WDA session 刚重建后仍可拉起。
        self._call(self.client.activate_app, bundle_id)
        self.wait_idle(400)
        return self.get_foreground_package() == bundle_id

    def stop_app(self, package_name: str) -> bool:
        bundle_id = package_name or self.target_bundle_id
        return bool(self._call(self.client.terminate_app, bundle_id))

    def wait_idle(self, timeout_ms: int = 1500) -> None:
        time.sleep(max(0, timeout_ms) / 1000.0)

    def read_logcat_tail(self, max_lines: int = 200) -> str:
        return ""

    def clear_logcat(self) -> None:
        return None

    def close(self) -> None:
        if self.keep_session:
            return
        self.client.delete_session()
