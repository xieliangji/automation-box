from __future__ import annotations

from smart_monkey.state.parser import HierarchyParser


def test_parser_marks_permission_and_list_page() -> None:
    xml = '''
    <hierarchy>
      <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.demo.app" clickable="false" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="false" focused="false" bounds="[0,0][1080,1920]">
        <node index="0" text="允许" resource-id="com.android.permissioncontroller:id/permission_allow_button" class="android.widget.Button" package="com.android.permissioncontroller" clickable="true" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="true" focused="false" bounds="[700,1500][1000,1600]" />
        <node index="1" text="" resource-id="com.demo:id/list" class="androidx.recyclerview.widget.RecyclerView" package="com.demo.app" clickable="false" long-clickable="false" scrollable="true" checkable="false" checked="false" enabled="true" focusable="false" focused="false" bounds="[0,200][1080,1800]">
          <node index="0" text="item 1" resource-id="com.demo:id/item" class="android.widget.TextView" package="com.demo.app" clickable="true" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="false" focused="false" bounds="[0,300][1080,400]" />
          <node index="1" text="item 2" resource-id="com.demo:id/item" class="android.widget.TextView" package="com.demo.app" clickable="true" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="false" focused="false" bounds="[0,410][1080,510]" />
          <node index="2" text="item 3" resource-id="com.demo:id/item" class="android.widget.TextView" package="com.demo.app" clickable="true" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="false" focused="false" bounds="[0,520][1080,620]" />
          <node index="3" text="item 4" resource-id="com.demo:id/item" class="android.widget.TextView" package="com.demo.app" clickable="true" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="false" focused="false" bounds="[0,630][1080,730]" />
        </node>
      </node>
    </hierarchy>
    '''
    parser = HierarchyParser()
    parsed = parser.parse(xml)

    assert "permission_controller" in parsed.system_flags
    assert "permission_like" in parsed.popup_flags
    assert "list_page" in parsed.app_flags


def test_parser_ios_rules_detect_permission_controller_and_settings() -> None:
    xml = '''
    <XCUIElementTypeApplication type="XCUIElementTypeApplication" bundleId="com.apple.springboard" x="0" y="0" width="1170" height="2532" enabled="true" visible="true">
      <XCUIElementTypeWindow type="XCUIElementTypeWindow" bundleId="com.apple.springboard" x="0" y="0" width="1170" height="2532" enabled="true" visible="true">
        <XCUIElementTypeButton type="XCUIElementTypeButton" label="Allow" bundleId="com.apple.springboard" x="700" y="1800" width="300" height="100" enabled="true" visible="true" />
        <XCUIElementTypeStaticText type="XCUIElementTypeStaticText" label="Loading" bundleId="com.apple.preferences" x="100" y="300" width="800" height="60" enabled="true" visible="true" />
      </XCUIElementTypeWindow>
    </XCUIElementTypeApplication>
    '''
    parser = HierarchyParser(platform="ios")
    parsed = parser.parse(xml)

    assert "permission_controller" in parsed.system_flags
    assert "settings" in parsed.system_flags
    assert "permission_like" in parsed.popup_flags
    assert "loading" in parsed.app_flags


def test_parser_ios_reads_standard_xcui_attributes() -> None:
    xml = '''
    <XCUIElementTypeApplication type="XCUIElementTypeApplication" bundleId="com.demo.ios" x="0" y="0" width="420" height="912" enabled="true" visible="true">
      <XCUIElementTypeWindow type="XCUIElementTypeWindow" x="0" y="0" width="420" height="912" enabled="true" visible="true">
        <XCUIElementTypeTextField type="XCUIElementTypeTextField" name="手机号" label="手机号" x="20" y="200" width="380" height="44" enabled="true" visible="true" />
        <XCUIElementTypeButton type="XCUIElementTypeButton" name="登录" label="登录" x="20" y="280" width="380" height="44" enabled="true" visible="true" />
      </XCUIElementTypeWindow>
    </XCUIElementTypeApplication>
    '''
    parser = HierarchyParser(platform="ios")
    parsed = parser.parse(xml)

    assert len(parsed.elements) >= 3
    text_field = next(item for item in parsed.elements if "textfield" in item.class_name.lower())
    button = next(item for item in parsed.elements if "button" in item.class_name.lower())
    assert text_field.editable is True
    assert button.clickable is True
    assert text_field.visible_bounds == (20, 200, 400, 244)


def test_parser_marks_form_page_from_editable_fields() -> None:
    xml = '''
    <hierarchy>
      <node index="0" text="" resource-id="" class="android.widget.FrameLayout" package="com.demo.app" clickable="false" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="false" focused="false" bounds="[0,0][1080,1920]">
        <node index="0" text="" resource-id="com.demo:id/phone_input" class="android.widget.EditText" package="com.demo.app" clickable="true" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="true" focused="false" bounds="[100,300][900,400]" />
        <node index="1" text="" resource-id="com.demo:id/password_input" class="android.widget.EditText" package="com.demo.app" clickable="true" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="true" focused="false" bounds="[100,420][900,520]" />
        <node index="2" text="保存" resource-id="com.demo:id/save_btn" class="android.widget.Button" package="com.demo.app" clickable="true" long-clickable="false" scrollable="false" checkable="false" checked="false" enabled="true" focusable="true" focused="false" bounds="[100,620][900,720]" />
      </node>
    </hierarchy>
    '''
    parser = HierarchyParser()
    parsed = parser.parse(xml)

    assert "form_page" in parsed.app_flags
