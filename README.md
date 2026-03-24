# Android Smart Monkey

一个面向 Android App 的智能 Monkey 测试项目。

项目目标不是简单随机发事件，而是围绕 **状态识别、候选动作提取、动作打分、UTG 状态图、回溯恢复** 建立可持续演进的智能探索框架。

## 单一路径说明

当前仓库已收敛为 **唯一运行路径**：

- 统一入口：`main.py`
- 统一运行主类：`smart_monkey/app_runtime.py::SmartMonkeyAppRuntime`
- 统一输出目录：`output/run/`

历史并行入口/运行变体已清理，不再维护多入口执行路径。

## 快速开始

1. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
./.venv/bin/python -m pip install -e .
./.venv/bin/python -m pip install pytest
```

2. 复制配置并修改目标应用

```bash
cp config.example.yaml config.yaml
```

必改字段：

- `app.package_name`
- `app.launch_activity`

建议保留默认：

- `policy.enable_session_guardrails: true`（会话护栏，减少登录/账号页循环）
- `policy.enable_login_bootstrap: false`（默认关闭；需要账号密码时可开启自动登录引导）
- `policy.prefer_functional_pages: true`（默认偏向功能页探索；如需专测登录/账号链路可关闭）
- `run.benchmark_baseline_dir: ""`（可选；填写历史 run 目录可在报告中生成 A/B KPI 对比）

3. 启动运行

```bash
python main.py
```

建议先验证启动页是否正确：

```bash
adb shell cmd package resolve-activity --brief <package>/<activity>
```

若输出 `No activity found`，请先修正 `config.yaml` 中的 `app.launch_activity`。

## 测试

```bash
./.venv/bin/python -m pytest -q
```

单文件：

```bash
./.venv/bin/python -m pytest -q tests/test_parser.py
```

单用例：

```bash
./.venv/bin/python -m pytest -q tests/test_parser.py::test_parser_marks_permission_and_list_page
```

## 架构概览

运行链路（`SmartMonkeyAppRuntime`）：

1. `RobustAdbDriver` 负责设备交互与前台识别
2. `HierarchyParser` 解析 XML 为 `UIElement` 与页面语义 flags
3. `StateFingerprinter` 生成 `raw_hash/stable_hash/state_id`
4. `RuntimeActionExtractor` 提取候选动作（含列表抽样与高风险过滤）
5. `RuntimeActionScorer` 打分并选择动作
6. `UTG` / `RunStats` 更新状态迁移与历史收益
7. `RunRecorder` / `TelemetryService` 落盘动作与轨迹
8. `WatchdogService` 记录 crash/anr/越界等 issue
9. `RecoveryService` 执行回溯恢复并由 `RecoveryValidator` 校验
10. `ReportService` 生成 HTML/Markdown/metrics 报告

详细设计参考：`docs/design.md`  
使用指南（非自动化同学）：`docs/USER_GUIDE_CN.md`

## 日志

运行日志会输出到终端，并同时写入：

- `output/run/runtime.log`

日志包含每一步执行动作（action_type/action_id/state/score）、状态迁移、out_of_app 触发与恢复结果，便于快速回溯问题。
