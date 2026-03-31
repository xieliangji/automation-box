from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

from smart_monkey.models import UIElement
from smart_monkey.platform_profiles import build_ui_parsing_rules


_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")
@dataclass(slots=True)
class ParsedHierarchy:
    elements: list[UIElement]
    popup_flags: set[str]
    system_flags: set[str]
    app_flags: set[str]


class HierarchyParser:
    def __init__(self, platform: str = "android") -> None:
        self.platform = platform
        self.rules = build_ui_parsing_rules(platform)

    def parse(self, xml_content: str) -> ParsedHierarchy:
        root = ET.fromstring(xml_content)
        elements: list[UIElement] = []
        popup_flags: set[str] = set()
        system_flags: set[str] = set()
        app_flags: set[str] = set()

        self._walk(
            node=root,
            elements=elements,
            parent_id=None,
            depth=0,
            xpath="/hierarchy",
            popup_flags=popup_flags,
            system_flags=system_flags,
            app_flags=app_flags,
        )

        if self._has_center_dialog(elements):
            popup_flags.add("center_dialog")
        if self._looks_like_login_page(elements):
            app_flags.add("login_page")
        if self._looks_like_list_page(elements):
            app_flags.add("list_page")
        if self._looks_like_form_page(elements):
            app_flags.add("form_page")
        if any("webview" in element.class_name.lower() for element in elements):
            app_flags.add("webview")

        return ParsedHierarchy(
            elements=elements,
            popup_flags=popup_flags,
            system_flags=system_flags,
            app_flags=app_flags,
        )

    def _walk(
        self,
        node: ET.Element,
        elements: list[UIElement],
        parent_id: str | None,
        depth: int,
        xpath: str,
        popup_flags: set[str],
        system_flags: set[str],
        app_flags: set[str],
    ) -> str | None:
        if not self._is_element_node(node):
            for index, child in enumerate(list(node)):
                self._walk(
                    node=child,
                    elements=elements,
                    parent_id=parent_id,
                    depth=depth,
                    xpath=f"{xpath}/{child.tag}[{index}]",
                    popup_flags=popup_flags,
                    system_flags=system_flags,
                    app_flags=app_flags,
                )
            return None

        node_index = len(elements)
        element_id = f"e{node_index:04d}"
        class_name = (node.attrib.get("class") or node.attrib.get("type") or node.tag or "").strip()
        package_name = node.attrib.get("package") or node.attrib.get("bundleId") or None
        text = self._first_non_empty(
            node.attrib.get("text"),
            node.attrib.get("label"),
            node.attrib.get("value"),
            node.attrib.get("name"),
        )
        content_desc = self._first_non_empty(
            node.attrib.get("content-desc"),
            node.attrib.get("name"),
            node.attrib.get("label"),
        )
        bounds = self._parse_visible_bounds(node)
        clickable = self._resolve_clickable(node.attrib, class_name)
        long_clickable = self._resolve_long_clickable(node.attrib, class_name)
        scrollable = self._resolve_scrollable(node.attrib, class_name)
        checkable = self._as_bool(node.attrib.get("checkable"))
        checked = self._as_bool(node.attrib.get("checked"))
        enabled = self._as_bool(node.attrib.get("enabled"), default=True)
        focusable = self._as_bool(node.attrib.get("focusable"))
        focused = self._as_bool(node.attrib.get("focused"))
        editable = self._is_editable(node.attrib, class_name)

        element = UIElement(
            element_id=element_id,
            class_name=class_name,
            resource_id=node.attrib.get("resource-id") or None,
            text=text,
            content_desc=content_desc,
            package_name=package_name,
            clickable=clickable,
            long_clickable=long_clickable,
            scrollable=scrollable,
            checkable=checkable,
            checked=checked,
            enabled=enabled,
            focusable=focusable,
            focused=focused,
            editable=editable,
            visible_bounds=bounds,
            depth=depth,
            xpath=xpath,
            parent_id=parent_id,
        )
        elements.append(element)

        package_lower = (package_name or "").lower()
        if package_lower in self.rules.permission_controller_packages:
            system_flags.add("permission_controller")
        if package_lower in self.rules.settings_packages:
            system_flags.add("settings")
        if text and any(token in text.lower() for token in self.rules.permission_like_tokens):
            popup_flags.add("permission_like")
        if text and any(token in text.lower() for token in self.rules.loading_tokens):
            app_flags.add("loading")

        for index, child in enumerate(list(node)):
            child_id = self._walk(
                node=child,
                elements=elements,
                parent_id=element_id,
                depth=depth + 1,
                xpath=f"{xpath}/node[{index}]",
                popup_flags=popup_flags,
                system_flags=system_flags,
                app_flags=app_flags,
            )
            if child_id:
                element.child_ids.append(child_id)

        return element_id

    @staticmethod
    def _parse_bounds(raw: str) -> tuple[int, int, int, int]:
        match = _BOUNDS_RE.match(raw)
        if not match:
            return (0, 0, 0, 0)
        return tuple(int(item) for item in match.groups())  # type: ignore[return-value]

    @staticmethod
    def _parse_ios_bounds(attrs: dict[str, str]) -> tuple[int, int, int, int]:
        try:
            left = int(float(attrs.get("x", "0")))
            top = int(float(attrs.get("y", "0")))
            width = int(float(attrs.get("width", "0")))
            height = int(float(attrs.get("height", "0")))
        except ValueError:
            return (0, 0, 0, 0)
        right = max(left, left + width)
        bottom = max(top, top + height)
        return (left, top, right, bottom)

    @staticmethod
    def _as_bool(value: str | None, default: bool = False) -> bool:
        if value is None:
            return default
        return value.lower() == "true"

    def _is_editable(self, attrs: dict[str, str], class_name: str) -> bool:
        class_name = class_name.lower()
        if class_name in self.rules.editable_classes:
            return True
        resource_id = (attrs.get("resource-id") or "").lower()
        text = (attrs.get("text") or "").lower()
        content_desc = (attrs.get("content-desc") or "").lower()
        tokens = " ".join([resource_id, text, content_desc])
        return any(token in tokens for token in ("input", "search", "phone", "email", "password", "编辑", "输入"))

    @staticmethod
    def _has_center_dialog(elements: list[UIElement]) -> bool:
        for element in elements:
            left, top, right, bottom = element.visible_bounds
            width = right - left
            height = bottom - top
            if 300 <= width <= 900 and 200 <= height <= 1200 and left > 50 and top > 100:
                if element.clickable or len(element.child_ids) >= 2:
                    return True
        return False

    @staticmethod
    def _looks_like_login_page(elements: list[UIElement]) -> bool:
        tokens = set()
        editable_count = 0
        for element in elements:
            tokens |= element.semantic_tokens()
            if element.editable:
                editable_count += 1
        return editable_count >= 1 and bool(tokens & {"login", "登录", "password", "密码", "验证码", "register", "注册"})

    @staticmethod
    def _looks_like_list_page(elements: list[UIElement]) -> bool:
        scrollables = [element for element in elements if element.scrollable]
        clickable_children = [element for element in elements if element.clickable and element.depth >= 2]
        return bool(scrollables) and len(clickable_children) >= 4

    @staticmethod
    def _looks_like_form_page(elements: list[UIElement]) -> bool:
        editable_count = sum(1 for element in elements if element.editable)
        clickable_tokens = set().union(*(element.semantic_tokens() for element in elements if element.clickable)) if elements else set()
        return editable_count >= 2 and bool(clickable_tokens & {"submit", "提交", "save", "保存", "完成", "done"})

    def _is_element_node(self, node: ET.Element) -> bool:
        if self.platform == "ios":
            return node.tag.lower().startswith("xcuielementtype")
        return node.tag == "node"

    def _parse_visible_bounds(self, node: ET.Element) -> tuple[int, int, int, int]:
        if self.platform == "ios":
            return self._parse_ios_bounds(node.attrib)
        return self._parse_bounds(node.attrib.get("bounds", ""))

    def _resolve_clickable(self, attrs: dict[str, str], class_name: str) -> bool:
        if self.platform != "ios":
            return self._as_bool(attrs.get("clickable"))
        if not self._as_bool(attrs.get("enabled"), default=True):
            return False
        if not self._as_bool(attrs.get("visible"), default=True):
            return False
        kind = class_name.lower()
        interactive_tokens = (
            "button",
            "cell",
            "link",
            "icon",
            "tabbarbutton",
            "menuitem",
            "switch",
        )
        if any(token in kind for token in interactive_tokens):
            return True
        if self._as_bool(attrs.get("accessible")) and self._first_non_empty(
            attrs.get("name"),
            attrs.get("label"),
            attrs.get("value"),
        ):
            return True
        return False

    def _resolve_long_clickable(self, attrs: dict[str, str], class_name: str) -> bool:
        if self.platform != "ios":
            return self._as_bool(attrs.get("long-clickable"))
        return False

    def _resolve_scrollable(self, attrs: dict[str, str], class_name: str) -> bool:
        if self.platform != "ios":
            return self._as_bool(attrs.get("scrollable"))
        kind = class_name.lower()
        return any(token in kind for token in ("scrollview", "table", "collectionview", "webview"))

    @staticmethod
    def _first_non_empty(*values: str | None) -> str | None:
        for value in values:
            if value is None:
                continue
            cleaned = str(value).strip()
            if cleaned:
                return cleaned
        return None
