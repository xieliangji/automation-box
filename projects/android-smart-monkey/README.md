# Android Smart Monkey

一个面向 Android App 的智能 Monkey 测试项目骨架。

它的目标不是简单随机发事件，而是围绕 **状态识别、候选动作提取、动作打分、UTG 状态图、回溯逃逸** 建一个可持续演进的智能探索框架。

## 当前范围

当前提交提供：

- 详细设计文档：`docs/design.md`
- Python 项目骨架：`smart_monkey/`
- 一个可直接继续编码的主循环骨架：`smart_monkey/runner.py`
- ADB/UiAutomator 风格的设备驱动接口骨架
- 状态指纹、候选动作提取、动作打分的第一版实现雏形

## 推荐实现路线

### 第一阶段

先把闭环跑通：

1. 获取当前前台包名与页面层级树
2. 解析为统一状态对象
3. 提取候选动作
4. 对动作打分
5. 选择并执行动作
6. 采集新状态
7. 更新状态图与运行轨迹

### 第二阶段

再补：

- 回溯与检查点
- 弹窗/权限页识别
- 列表页抽样点击
- 语义化输入
- crash / anr / out-of-app 监控

## 目录结构

```text
projects/android-smart-monkey/
├── docs/
│   └── design.md
├── smart_monkey/
│   ├── action/
│   │   ├── extractor.py
│   │   └── scorer.py
│   ├── device/
│   │   ├── adb_driver.py
│   │   └── base.py
│   ├── state/
│   │   └── fingerprint.py
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   └── runner.py
├── main.py
└── pyproject.toml
```

## 快速开始

```bash
cd projects/android-smart-monkey
python -m venv .venv
source .venv/bin/activate
pip install -e .
python main.py
```

## 当前注意事项

- `AdbDriver` 仍是骨架实现，部分方法需要你结合本机 adb / uiautomator2 环境补完。
- `ActionExtractor`、`ActionScorer` 和 `StateFingerprinter` 已可作为继续开发的基础，但还不是最终策略。
- 当前默认以 **Python 控制器 + adb** 为第一版落地方向，后续再考虑下沉到设备侧或引入模型策略。

## 下一步建议

1. 补齐 `dump_hierarchy()` 的真实能力
2. 接入 XML 解析，生成 `UIElement`
3. 将 `runner.py` 的 TODO 项逐步补齐
4. 先在一个简单 Demo App 上跑 300~500 步做验证
