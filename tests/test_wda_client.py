from __future__ import annotations

import json

from smart_monkey.device.wda_client import WdaClient


class _FakeResponse:
    def __init__(self, code: int, payload: dict | list | str | None) -> None:
        self._code = code
        self._payload = payload

    def getcode(self) -> int:
        return self._code

    def read(self) -> bytes:
        if self._payload is None:
            return b""
        if isinstance(self._payload, str):
            return self._payload.encode("utf-8")
        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


class _FakeUrlopen:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = list(responses)
        self.requests: list[dict[str, object]] = []

    def __call__(self, req, timeout):  # noqa: ANN001 - 通过补丁注入的可调用对象
        payload = req.data.decode("utf-8") if req.data else ""
        self.requests.append(
            {
                "method": req.get_method(),
                "url": req.full_url,
                "timeout": timeout,
                "payload": payload,
            }
        )
        if not self.responses:
            raise RuntimeError("No fake response prepared.")
        return self.responses.pop(0)


def test_create_session_and_status(monkeypatch) -> None:
    fake = _FakeUrlopen(
        responses=[
            _FakeResponse(200, {"value": {"ready": True}}),
            _FakeResponse(200, {"sessionId": "sess-1", "value": {"capabilities": {}}}),
        ]
    )
    monkeypatch.setattr("smart_monkey.device.wda_client.request.urlopen", fake)
    client = WdaClient("http://127.0.0.1:8100")

    status = client.status()
    sid = client.create_session({"bundleId": "com.demo.app"})

    assert status["value"]["ready"] is True
    assert sid == "sess-1"
    assert client.session_id == "sess-1"
    assert fake.requests[0]["url"] == "http://127.0.0.1:8100/status"
    assert fake.requests[1]["url"] == "http://127.0.0.1:8100/session"


def test_activate_app_with_fallback(monkeypatch) -> None:
    fake = _FakeUrlopen(
        responses=[
            _FakeResponse(404, {"value": {"error": "unknown command", "message": "not found"}}),
            _FakeResponse(200, {"value": {}}),
        ]
    )
    monkeypatch.setattr("smart_monkey.device.wda_client.request.urlopen", fake)
    client = WdaClient("http://127.0.0.1:8100")
    client.session_id = "sess-1"

    assert client.activate_app("com.demo.app") is True
    assert len(fake.requests) == 2
    assert fake.requests[0]["url"].endswith("/session/sess-1/wda/apps/activate")
    assert fake.requests[1]["url"].endswith("/session/sess-1/wda/apps/launch")


def test_screenshot_decodes_base64(monkeypatch) -> None:
    fake = _FakeUrlopen(
        responses=[
            _FakeResponse(200, {"value": "ZmFrZS1pbWFnZS1ieXRlcw=="}),
        ]
    )
    monkeypatch.setattr("smart_monkey.device.wda_client.request.urlopen", fake)
    client = WdaClient("http://127.0.0.1:8100")
    client.session_id = "sess-1"

    data = client.screenshot()

    assert data == b"fake-image-bytes"
    assert fake.requests[0]["url"].endswith("/session/sess-1/screenshot")


def test_tap_fallback_to_actions(monkeypatch) -> None:
    fake = _FakeUrlopen(
        responses=[
            _FakeResponse(404, {"value": {"error": "unknown command", "message": "tap endpoint missing"}}),
            _FakeResponse(200, {"value": {}}),
        ]
    )
    monkeypatch.setattr("smart_monkey.device.wda_client.request.urlopen", fake)
    client = WdaClient("http://127.0.0.1:8100")
    client.session_id = "sess-1"

    assert client.tap(100, 200) is True
    assert fake.requests[0]["url"].endswith("/session/sess-1/wda/tap/0")
    assert fake.requests[1]["url"].endswith("/session/sess-1/actions")


def test_pinch_uses_actions_payload(monkeypatch) -> None:
    fake = _FakeUrlopen(
        responses=[
            _FakeResponse(200, {"value": {}}),
        ]
    )
    monkeypatch.setattr("smart_monkey.device.wda_client.request.urlopen", fake)
    client = WdaClient("http://127.0.0.1:8100")
    client.session_id = "sess-1"

    assert client.pinch(100, 200, 90, 190, 200, 300, 210, 310, duration_ms=240) is True
    assert fake.requests[0]["url"].endswith("/session/sess-1/actions")
    payload = json.loads(str(fake.requests[0]["payload"]))
    assert len(payload["actions"]) == 2
    assert payload["actions"][0]["id"] == "finger1"
    assert payload["actions"][1]["id"] == "finger2"
