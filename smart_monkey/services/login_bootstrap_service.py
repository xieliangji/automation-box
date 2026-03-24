from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LoginBootstrapAttempt:
    step: int
    status: str
    reason: str


class LoginBootstrapService:
    """Deterministic login bootstrap and keep-alive checks."""

    _USERNAME_KEYS: tuple[str, ...] = ("phone", "email", "user", "account", "username", "账号", "手机号", "邮箱")
    _PASSWORD_KEYS: tuple[str, ...] = ("password", "pwd", "pass", "密码")
    _LOGIN_KEYS: tuple[str, ...] = ("login", "登录", "立即登录", "登录账号")

    def __init__(self, config: Any) -> None:
        self.config = config
        self._attempts = 0
        self._last_attempt_step = -10**9

    def maybe_bootstrap(self, step: int, state: Any, driver: Any) -> LoginBootstrapAttempt:
        if not self.config.policy.enable_login_bootstrap:
            return LoginBootstrapAttempt(step=step, status="skipped", reason="disabled")
        if "login_page" not in state.app_flags:
            return LoginBootstrapAttempt(step=step, status="skipped", reason="not_login_page")
        if self._attempts >= max(1, self.config.policy.bootstrap_max_attempts):
            return LoginBootstrapAttempt(step=step, status="skipped", reason="max_attempts_reached")
        if step - self._last_attempt_step < max(1, self.config.policy.bootstrap_retry_interval_steps):
            return LoginBootstrapAttempt(step=step, status="skipped", reason="retry_cooldown")
        if not self._credentials_configured():
            return LoginBootstrapAttempt(step=step, status="skipped", reason="missing_credentials")

        username = self.config.policy.bootstrap_username.strip()
        password = self.config.policy.bootstrap_password.strip()

        username_input = self._find_editable(state, self._USERNAME_KEYS)
        password_input = self._find_editable(state, self._PASSWORD_KEYS)
        login_button = self._find_clickable(state, self._LOGIN_KEYS)

        if username_input is None or password_input is None or login_button is None:
            return LoginBootstrapAttempt(step=step, status="skipped", reason="missing_login_controls")

        self._attempts += 1
        self._last_attempt_step = step

        ux, uy = username_input.center
        driver.click(ux, uy)
        driver.wait_idle(200)
        driver.input_text(username)
        driver.wait_idle(200)

        px, py = password_input.center
        driver.click(px, py)
        driver.wait_idle(200)
        driver.input_text(password)
        driver.wait_idle(200)

        lx, ly = login_button.center
        driver.click(lx, ly)
        driver.wait_idle(800)
        return LoginBootstrapAttempt(step=step, status="attempted", reason="submitted_login_form")

    def _credentials_configured(self) -> bool:
        return bool(self.config.policy.bootstrap_username.strip() and self.config.policy.bootstrap_password.strip())

    def _find_editable(self, state: Any, keys: tuple[str, ...]) -> Any | None:
        candidates = [element for element in state.elements if element.enabled and element.editable]
        return self._best_match(candidates, keys)

    def _find_clickable(self, state: Any, keys: tuple[str, ...]) -> Any | None:
        candidates = [element for element in state.elements if element.enabled and element.clickable]
        return self._best_match(candidates, keys)

    def _best_match(self, elements: list[Any], keys: tuple[str, ...]) -> Any | None:
        for element in elements:
            joined = " ".join(
                [
                    (element.resource_id or "").lower(),
                    (element.text or "").lower(),
                    (element.content_desc or "").lower(),
                    (element.class_name or "").lower(),
                ]
            )
            if any(key in joined for key in keys):
                return element
        return elements[0] if elements else None
