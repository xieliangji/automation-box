from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from smart_monkey.platform_profiles import normalize_platform


@dataclass(frozen=True, slots=True)
class DriverCapabilities:
    platform: str = "android"
    supports_launch_target: bool = True
    supports_press_back: bool = True
    supports_press_home: bool = True
    supports_stop_app: bool = True
    supports_log_stream: bool = False


def resolve_driver_capabilities(driver: Any) -> DriverCapabilities:
    provider = getattr(driver, "capabilities", None)
    if callable(provider):
        caps = provider()
        if isinstance(caps, DriverCapabilities):
            return DriverCapabilities(
                platform=normalize_platform(caps.platform),
                supports_launch_target=bool(caps.supports_launch_target),
                supports_press_back=bool(caps.supports_press_back),
                supports_press_home=bool(caps.supports_press_home),
                supports_stop_app=bool(caps.supports_stop_app),
                supports_log_stream=bool(caps.supports_log_stream),
            )
    return DriverCapabilities()
