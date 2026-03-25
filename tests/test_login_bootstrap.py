from __future__ import annotations

from smart_monkey.config import ProjectConfig
from smart_monkey.models import DeviceState, UIElement
from smart_monkey.services.login_bootstrap_service import LoginBootstrapService


class FakeDriver:
    def __init__(self) -> None:
        self.actions: list[tuple[str, tuple]] = []

    def click(self, x: int, y: int) -> bool:
        self.actions.append(("click", (x, y)))
        return True

    def input_text(self, text: str) -> bool:
        self.actions.append(("input", (text,)))
        return True

    def wait_idle(self, timeout_ms: int = 1500) -> None:
        self.actions.append(("wait_idle", (timeout_ms,)))

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
        self.actions.append(
            (
                "pinch",
                (x1_start, y1_start, x1_end, y1_end, x2_start, y2_start, x2_end, y2_end, duration_ms),
            )
        )
        return True


def make_login_state() -> DeviceState:
    elements = [
        UIElement(
            element_id="username",
            class_name="android.widget.EditText",
            resource_id="com.demo:id/phone_input",
            editable=True,
            clickable=True,
            visible_bounds=(100, 300, 900, 400),
        ),
        UIElement(
            element_id="password",
            class_name="android.widget.EditText",
            resource_id="com.demo:id/password_input",
            editable=True,
            clickable=True,
            visible_bounds=(100, 420, 900, 520),
        ),
        UIElement(
            element_id="login_button",
            class_name="android.widget.Button",
            resource_id="com.demo:id/btn_login",
            text="登录",
            clickable=True,
            visible_bounds=(100, 620, 900, 720),
        ),
    ]
    return DeviceState(
        state_id="login-state",
        raw_hash="raw",
        stable_hash="stable",
        package_name="com.demo.app",
        activity_name=".LoginActivity",
        elements=elements,
        app_flags={"login_page"},
    )


def test_login_bootstrap_attempts_with_credentials() -> None:
    config = ProjectConfig()
    config.policy.enable_login_bootstrap = True
    config.policy.bootstrap_username = "13000000000"
    config.policy.bootstrap_password = "abc123"
    config.policy.bootstrap_retry_interval_steps = 1
    service = LoginBootstrapService(config)
    driver = FakeDriver()

    result = service.maybe_bootstrap(step=0, state=make_login_state(), driver=driver)

    assert result.status == "attempted"
    assert ("input", ("13000000000",)) in driver.actions
    assert ("input", ("abc123",)) in driver.actions


def test_login_bootstrap_respects_retry_and_max_attempts() -> None:
    config = ProjectConfig()
    config.policy.enable_login_bootstrap = True
    config.policy.bootstrap_username = "13000000000"
    config.policy.bootstrap_password = "abc123"
    config.policy.bootstrap_max_attempts = 2
    config.policy.bootstrap_retry_interval_steps = 10
    service = LoginBootstrapService(config)
    driver = FakeDriver()
    state = make_login_state()

    first = service.maybe_bootstrap(step=0, state=state, driver=driver)
    cooldown = service.maybe_bootstrap(step=1, state=state, driver=driver)
    second = service.maybe_bootstrap(step=20, state=state, driver=driver)
    exhausted = service.maybe_bootstrap(step=40, state=state, driver=driver)

    assert first.status == "attempted"
    assert cooldown.reason == "retry_cooldown"
    assert second.status == "attempted"
    assert exhausted.reason == "max_attempts_reached"
