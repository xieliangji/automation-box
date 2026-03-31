from __future__ import annotations

from dataclasses import dataclass


def normalize_platform(platform: str | None) -> str:
    value = str(platform or "android").strip().lower()
    if value in {"android", "ios"}:
        return value
    return "android"


@dataclass(frozen=True, slots=True)
class UiParsingRules:
    editable_classes: frozenset[str]
    permission_controller_packages: frozenset[str]
    settings_packages: frozenset[str]
    permission_like_tokens: tuple[str, ...]
    loading_tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WatchdogRules:
    crash_fatal_markers: tuple[str, ...]
    crash_runtime_markers: tuple[str, ...]
    anr_markers: tuple[str, ...]


def build_ui_parsing_rules(platform: str) -> UiParsingRules:
    normalized = normalize_platform(platform)
    if normalized == "ios":
        return UiParsingRules(
            editable_classes=frozenset(
                {
                    "xcuielementtypetextfield",
                    "xcuielementtypesecuretextfield",
                    "xcuielementtypesearchfield",
                }
            ),
            permission_controller_packages=frozenset({"com.apple.springboard"}),
            settings_packages=frozenset({"com.apple.preferences"}),
            permission_like_tokens=("allow", "don't allow", "允许", "拒绝", "始终允许", "仅在使用期间"),
            loading_tokens=("loading", "please wait", "加载中", "请稍候"),
        )

    return UiParsingRules(
        editable_classes=frozenset(
            {
                "android.widget.edittext",
                "androidx.appcompat.widget.appcompatedittext",
            }
        ),
        permission_controller_packages=frozenset({"com.android.permissioncontroller"}),
        settings_packages=frozenset({"com.android.settings"}),
        permission_like_tokens=("允许", "拒绝", "仅在使用期间", "while using the app", "allow", "don't allow"),
        loading_tokens=("loading", "加载中"),
    )


def build_watchdog_rules(platform: str) -> WatchdogRules:
    normalized = normalize_platform(platform)
    if normalized == "ios":
        return WatchdogRules(
            crash_fatal_markers=("termination reason", "uncaught exception", "crashed with", "fatal"),
            crash_runtime_markers=(),
            anr_markers=("isn't responding", "not responding", "stalled", "hang", "卡住", "无响应"),
        )

    return WatchdogRules(
        crash_fatal_markers=("fatal exception", "has crashed"),
        crash_runtime_markers=("androidruntime",),
        anr_markers=("anr in", "application not responding", "input dispatching timed out", "isn't responding"),
    )
