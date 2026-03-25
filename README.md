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

环境要求：

- Python `3.11+`
- ADB 已安装并加入 PATH

1. 创建虚拟环境并安装依赖

```bash
python -m venv .venv
source .venv/bin/activate
./.venv/bin/python -m pip install -e .
./.venv/bin/python -m pip install pytest
```

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m pip install pytest
```

2. 复制配置并修改目标应用

```bash
cp config.example.yaml config.yaml
```

Windows PowerShell：

```powershell
copy config.example.yaml config.yaml
```

必改字段：

- `app.package_name`
- `app.launch_activity`

建议保留默认：

- `policy.enable_session_guardrails: true`（会话护栏，减少登录/账号页循环）
- `policy.enable_login_bootstrap: false`（默认关闭；需要账号密码时可开启自动登录引导）
- `policy.prefer_functional_pages: true`（默认偏向功能页探索；如需专测登录/账号链路可关闭）
- `policy.enable_pinch: true`（默认开启双指缩放手势：`pinch_in/pinch_out`）
- `run.benchmark_baseline_dir: ""`（可选；填写历史 run 目录可在报告中生成 A/B KPI 对比）
- `run.profile: "functional"`（默认功能覆盖模式）

Crash 专项模式（Android）可选配置：

- `run.profile: "crash_stress"`
- `run.crash_stress_wait_ms: 200`（动作后等待时长，默认更激进）
- `run.crash_stress_burst_probability: 0.25`（触发 burst 的概率）
- `run.crash_stress_burst_min_steps: 2`
- `run.crash_stress_burst_max_steps: 5`

学习型策略（UCB）可选配置（默认关闭）：

- `learning.enabled: false`
- `learning.alpha: 0.8`（规则分与学习分混合系数）
- `learning.ucb_exploration: 1.2`
- `learning.module_bucket_enabled: true`（按页面模块聚类 arm）
- `learning.reward_changed_state: 1.0`
- `learning.reward_novel_state: 0.3`
- `learning.reward_functional_page: 0.4`
- `learning.reward_issue_signal: 0.8`
- `learning.penalty_out_of_app: 1.0`
- `learning.penalty_unchanged: 0.2`
- `learning.penalty_recent_loop: 0.25`
- `learning.penalty_system_action: 0.15`

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

Windows PowerShell：

```powershell
python -m pytest -q
```

单文件：

```bash
./.venv/bin/python -m pytest -q tests/test_parser.py
```

Windows PowerShell：

```powershell
python -m pytest -q tests/test_parser.py
```

单用例：

```bash
./.venv/bin/python -m pytest -q tests/test_parser.py::test_parser_marks_permission_and_list_page
```

Windows PowerShell：

```powershell
python -m pytest -q tests/test_parser.py::test_parser_marks_permission_and_list_page
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

详细设计参考：`docs/详细设计.md`  
使用指南（非自动化同学）：`docs/使用指南（非自动化）.md`

iOS 直连 WDA URL 接入方案：`docs/iOS直连WDA_URL接入方案.md`
算法优化与 crash 专项方案：`docs/算法优化与Crash专项增强方案.md`
当前主线算法与策略详解：`docs/主线算法与策略详解.md`
参数调优手册（按目标）：`docs/参数调优手册（按目标）.md`
能力补齐总设计：`docs/能力补齐总设计.md`

## 日志

运行日志会输出到终端，并同时写入：

- `output/run/runtime.log`

日志包含每一步执行动作（action_type/action_id/state/score）、状态迁移、out_of_app 触发与恢复结果，便于快速回溯问题。

`report/coverage_benchmark.json` 中新增 KPI：

- crash 专项：`actions_per_minute`、`crash_per_1k_actions`、`burst_step_ratio`、`time_to_first_crash_steps`
- learning 专项：`learning_step_ratio`、`learning_exploration_rate`、`learning_average_reward`、`learning_top_arms`

查看报告（Windows PowerShell）：

```powershell
start .\output\run\report\index.html
```
