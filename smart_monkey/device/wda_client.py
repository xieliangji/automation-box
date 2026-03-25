from __future__ import annotations

import base64
import json
import socket
from typing import Any
from urllib import error, request


class WdaClient:
    """用于直连设备代理服务的轻量接口封装。"""

    def __init__(
        self,
        base_url: str,
        request_timeout_sec: float = 20.0,
        session_create_timeout_sec: float = 30.0,
        request_retry: int = 2,
    ) -> None:
        if not base_url or not base_url.strip():
            raise ValueError("WDA base_url must not be empty.")
        self.base_url = base_url.rstrip("/")
        self.request_timeout_sec = request_timeout_sec
        self.session_create_timeout_sec = session_create_timeout_sec
        self.request_retry = max(0, request_retry)
        self.session_id: str | None = None

    def status(self) -> dict[str, Any]:
        return self._request_json(
            method="GET",
            path="/status",
            payload=None,
            timeout_sec=self.request_timeout_sec,
            retry=self.request_retry,
        )

    def healthcheck(self) -> bool:
        try:
            self.status()
            return True
        except RuntimeError:
            return False

    def create_session(self, capabilities: dict[str, Any] | None = None) -> str:
        caps = dict(capabilities or {})
        payload = {
            "capabilities": {"alwaysMatch": caps, "firstMatch": [{}]},
            "desiredCapabilities": caps,
        }
        response = self._request_json(
            method="POST",
            path="/session",
            payload=payload,
            timeout_sec=self.session_create_timeout_sec,
            retry=self.request_retry,
        )
        session_id = self._extract_session_id(response)
        if not session_id:
            raise RuntimeError(f"Failed to create WDA session: {response}")
        self.session_id = session_id
        return session_id

    def ensure_session(self, capabilities: dict[str, Any] | None = None) -> str:
        if self.session_id:
            return self.session_id
        return self.create_session(capabilities=capabilities)

    def delete_session(self, session_id: str | None = None) -> bool:
        sid = session_id or self.session_id
        if not sid:
            return False
        try:
            self._request_json(
                method="DELETE",
                path=f"/session/{sid}",
                payload=None,
                timeout_sec=self.request_timeout_sec,
                retry=self.request_retry,
            )
        finally:
            if self.session_id == sid:
                self.session_id = None
        return True

    def source(self, session_id: str | None = None) -> str:
        sid = self._resolve_session_id(session_id)
        response = self._request_json(
            method="GET",
            path=f"/session/{sid}/source",
            payload=None,
            timeout_sec=self.request_timeout_sec,
            retry=self.request_retry,
        )
        value = response.get("value")
        if not isinstance(value, str):
            raise RuntimeError(f"Unexpected WDA source payload: {response}")
        return value

    def screenshot(self, session_id: str | None = None) -> bytes:
        sid = self._resolve_session_id(session_id)
        response = self._request_json(
            method="GET",
            path=f"/session/{sid}/screenshot",
            payload=None,
            timeout_sec=self.request_timeout_sec,
            retry=self.request_retry,
        )
        encoded = response.get("value")
        if not isinstance(encoded, str):
            raise RuntimeError(f"Unexpected WDA screenshot payload: {response}")
        try:
            return base64.b64decode(encoded, validate=False)
        except Exception as exc:  # pragma: no cover - 异常兜底：防御畸形返回数据
            raise RuntimeError("Failed to decode WDA screenshot payload.") from exc

    def active_app_info(self, session_id: str | None = None) -> dict[str, Any]:
        sid = self._resolve_session_id(session_id)
        response = self._request_json(
            method="GET",
            path=f"/session/{sid}/wda/activeAppInfo",
            payload=None,
            timeout_sec=self.request_timeout_sec,
            retry=self.request_retry,
        )
        value = response.get("value")
        if isinstance(value, dict):
            return value
        return {}

    def get_foreground_bundle_id(self, session_id: str | None = None) -> str:
        info = self.active_app_info(session_id=session_id)
        bundle_id = info.get("bundleId")
        return bundle_id if isinstance(bundle_id, str) else ""

    def is_app_foreground(self, bundle_id: str, session_id: str | None = None) -> bool:
        return self.get_foreground_bundle_id(session_id=session_id) == bundle_id

    def tap(self, x: int, y: int, session_id: str | None = None) -> bool:
        sid = self._resolve_session_id(session_id)
        self._call_with_fallback(
            candidates=[
                ("POST", f"/session/{sid}/wda/tap/0", {"x": x, "y": y}),
                ("POST", f"/session/{sid}/actions", self._tap_actions_payload(x, y)),
            ]
        )
        return True

    def long_press(self, x: int, y: int, duration_ms: int = 800, session_id: str | None = None) -> bool:
        sid = self._resolve_session_id(session_id)
        duration_sec = max(0.1, duration_ms / 1000.0)
        self._call_with_fallback(
            candidates=[
                ("POST", f"/session/{sid}/wda/touchAndHold", {"x": x, "y": y, "duration": duration_sec}),
                ("POST", f"/session/{sid}/actions", self._long_press_actions_payload(x, y, duration_ms)),
            ]
        )
        return True

    def swipe(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
        session_id: str | None = None,
    ) -> bool:
        sid = self._resolve_session_id(session_id)
        duration_sec = max(0.05, duration_ms / 1000.0)
        self._call_with_fallback(
            candidates=[
                (
                    "POST",
                    f"/session/{sid}/wda/dragfromtoforduration",
                    {
                        "fromX": x1,
                        "fromY": y1,
                        "toX": x2,
                        "toY": y2,
                        "duration": duration_sec,
                    },
                ),
                ("POST", f"/session/{sid}/actions", self._swipe_actions_payload(x1, y1, x2, y2, duration_ms)),
            ]
        )
        return True

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
        session_id: str | None = None,
    ) -> bool:
        sid = self._resolve_session_id(session_id)
        self._request_json(
            method="POST",
            path=f"/session/{sid}/actions",
            payload=self._pinch_actions_payload(
                x1_start=x1_start,
                y1_start=y1_start,
                x1_end=x1_end,
                y1_end=y1_end,
                x2_start=x2_start,
                y2_start=y2_start,
                x2_end=x2_end,
                y2_end=y2_end,
                duration_ms=duration_ms,
            ),
            timeout_sec=self.request_timeout_sec,
            retry=self.request_retry,
        )
        return True

    def send_keys(self, text: str, session_id: str | None = None) -> bool:
        sid = self._resolve_session_id(session_id)
        values = list(text)
        self._call_with_fallback(
            candidates=[
                ("POST", f"/session/{sid}/wda/keys", {"value": values}),
                ("POST", f"/session/{sid}/keys", {"text": text, "value": values}),
            ]
        )
        return True

    def activate_app(self, bundle_id: str, session_id: str | None = None) -> bool:
        sid = self._resolve_session_id(session_id)
        self._call_with_fallback(
            candidates=[
                ("POST", f"/session/{sid}/wda/apps/activate", {"bundleId": bundle_id}),
                ("POST", f"/session/{sid}/wda/apps/launch", {"bundleId": bundle_id}),
            ]
        )
        return True

    def terminate_app(self, bundle_id: str, session_id: str | None = None) -> bool:
        sid = self._resolve_session_id(session_id)
        self._call_with_fallback(
            candidates=[
                ("POST", f"/session/{sid}/wda/apps/terminate", {"bundleId": bundle_id}),
                ("POST", f"/session/{sid}/wda/apps/terminate", {"appId": bundle_id}),
            ]
        )
        return True

    def _call_with_fallback(self, candidates: list[tuple[str, str, dict[str, Any] | None]]) -> None:
        errors: list[str] = []
        for method, path, payload in candidates:
            try:
                self._request_json(
                    method=method,
                    path=path,
                    payload=payload,
                    timeout_sec=self.request_timeout_sec,
                    retry=self.request_retry,
                )
                return
            except RuntimeError as exc:
                errors.append(f"{method} {path} -> {exc}")
        raise RuntimeError("All WDA candidate endpoints failed. " + " | ".join(errors))

    def _resolve_session_id(self, session_id: str | None) -> str:
        sid = session_id or self.session_id
        if not sid:
            raise RuntimeError("WDA session_id is required. Call create_session() first.")
        return sid

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None,
        timeout_sec: float,
        retry: int,
    ) -> dict[str, Any]:
        url = self._build_url(path)
        attempts = max(0, retry) + 1
        last_error: RuntimeError | None = None
        for attempt in range(1, attempts + 1):
            try:
                status_code, raw_body = self._send(method, url, payload, timeout_sec)
            except RuntimeError as exc:
                last_error = exc
                if attempt < attempts:
                    continue
                raise

            parsed = self._parse_json(raw_body)
            if 200 <= status_code < 400:
                return parsed

            http_error = self._build_http_error(
                method=method,
                url=url,
                status_code=status_code,
                parsed=parsed,
                raw_body=raw_body,
            )
            last_error = http_error
            if status_code >= 500 and attempt < attempts:
                continue
            raise http_error

        raise RuntimeError(f"WDA request failed after {attempts} attempts: {last_error}")

    def _send(
        self,
        method: str,
        url: str,
        payload: dict[str, Any] | None,
        timeout_sec: float,
    ) -> tuple[int, str]:
        headers = {"Accept": "application/json"}
        data: bytes | None = None
        if payload is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        req = request.Request(url=url, data=data, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=timeout_sec) as response:
                body = response.read().decode("utf-8", errors="replace")
                return response.getcode(), body
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            return exc.code, body
        except (error.URLError, socket.timeout, TimeoutError) as exc:
            raise RuntimeError(f"WDA network request failed: {method} {url} ({exc})") from exc

    def _build_url(self, path: str) -> str:
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    @staticmethod
    def _parse_json(raw_body: str) -> dict[str, Any]:
        text = raw_body.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {"raw": raw_body}
        if isinstance(parsed, dict):
            return parsed
        return {"value": parsed}

    @staticmethod
    def _extract_session_id(response: dict[str, Any]) -> str | None:
        top_level = response.get("sessionId")
        if isinstance(top_level, str) and top_level:
            return top_level
        value = response.get("value")
        if isinstance(value, dict):
            sid = value.get("sessionId")
            if isinstance(sid, str) and sid:
                return sid
        return None

    @staticmethod
    def _build_http_error(
        method: str,
        url: str,
        status_code: int,
        parsed: dict[str, Any],
        raw_body: str,
    ) -> RuntimeError:
        message = WdaClient._extract_error_message(parsed, raw_body)
        return RuntimeError(f"WDA HTTP {status_code} for {method} {url}: {message}")

    @staticmethod
    def _extract_error_message(parsed: dict[str, Any], raw_body: str) -> str:
        value = parsed.get("value")
        if isinstance(value, dict):
            error_name = value.get("error")
            error_msg = value.get("message")
            if error_name or error_msg:
                return f"{error_name or 'error'}: {error_msg or ''}".strip()
        if isinstance(value, str) and value.strip():
            return value
        if parsed.get("raw"):
            return str(parsed["raw"])
        return raw_body.strip() or "<empty body>"

    @staticmethod
    def _tap_actions_payload(x: int, y: int) -> dict[str, Any]:
        return {
            "actions": [
                {
                    "type": "pointer",
                    "id": "finger1",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pause", "duration": 50},
                        {"type": "pointerUp", "button": 0},
                    ],
                }
            ]
        }

    @staticmethod
    def _long_press_actions_payload(x: int, y: int, duration_ms: int) -> dict[str, Any]:
        return {
            "actions": [
                {
                    "type": "pointer",
                    "id": "finger1",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pause", "duration": max(100, duration_ms)},
                        {"type": "pointerUp", "button": 0},
                    ],
                }
            ]
        }

    @staticmethod
    def _swipe_actions_payload(
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int,
    ) -> dict[str, Any]:
        return {
            "actions": [
                {
                    "type": "pointer",
                    "id": "finger1",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": x1, "y": y1},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pointerMove", "duration": max(50, duration_ms), "x": x2, "y": y2},
                        {"type": "pointerUp", "button": 0},
                    ],
                }
            ]
        }

    @staticmethod
    def _pinch_actions_payload(
        x1_start: int,
        y1_start: int,
        x1_end: int,
        y1_end: int,
        x2_start: int,
        y2_start: int,
        x2_end: int,
        y2_end: int,
        duration_ms: int,
    ) -> dict[str, Any]:
        duration = max(60, duration_ms)
        return {
            "actions": [
                {
                    "type": "pointer",
                    "id": "finger1",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": x1_start, "y": y1_start},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pointerMove", "duration": duration, "x": x1_end, "y": y1_end},
                        {"type": "pointerUp", "button": 0},
                    ],
                },
                {
                    "type": "pointer",
                    "id": "finger2",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": x2_start, "y": y2_start},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pointerMove", "duration": duration, "x": x2_end, "y": y2_end},
                        {"type": "pointerUp", "button": 0},
                    ],
                },
            ]
        }
