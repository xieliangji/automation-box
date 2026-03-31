# Smart Monkey

一个面向 Android + iOS 双平台的智能 Monkey 测试项目。

项目目标不是简单随机发事件，而是围绕 **状态识别、候选动作提取、动作打分、UTG 状态图、回溯恢复** 建立可持续演进的智能探索框架。

## 运行入口

- 入口：`main.py`
- 运行主类：`smart_monkey/app_runtime.py::SmartMonkeyAppRuntime`
- 默认输出目录：`output/run/`

打包元数据说明：

- 仓库包名为 `smart-monkey`。
- `*.egg-info/` 为本地构建产物，仓库已统一忽略，不再提交平台专属 egg-info 目录。

## 快速开始

环境要求：

- Python `3.11+`
- Android 场景：ADB 已安装并加入 PATH
- iOS 场景：WebDriverAgent 已启动并可访问（默认 `http://localhost:8100`）

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

如需快速切平台，建议直接切换预置配置：

```bash
cp config.android.yaml config.yaml   # Android
cp config.ios.yaml config.yaml       # iOS
```

必改字段：

- `app.platform`（默认 `android`）
- `app.target_app_id`
- `app.launch_target`
- `app.package_name`
- `app.launch_activity`

说明：`app.target_app_id/launch_target` 为平台中性主字段；`app.package_name/launch_activity` 继续保留并向后兼容。

iOS 运行时参数统一通过 `ios.*` 配置段注入（例如 `ios.wda_url`、`ios.keep_session`、`ios.auto_recreate_session`），`main.py` 不再手工读取原始 YAML。

建议保留默认：

- `policy.enable_session_guardrails: true`（会话护栏，减少登录/账号页循环）
- `policy.enable_login_bootstrap: false`（默认关闭；需要账号密码时可开启自动登录引导）
- `policy.prefer_functional_pages: true`（默认偏向功能页探索；如需专测登录/账号链路可关闭）
- `policy.enable_pinch: true`（默认开启双指缩放手势：`pinch_in/pinch_out`）
- `run.benchmark_baseline_dir: ""`（可选；填写历史 run 目录可在报告中生成 A/B KPI 对比）
- `run.profile: "functional"`（默认功能覆盖模式）
- `ios.wda_url: "http://localhost:8100"`（仅 `app.platform=ios` 时生效）

Crash 专项模式（当前 Android 驱动）可选配置：

- `run.profile: "crash_stress"`
- `run.crash_stress_wait_ms: 200`（动作后等待时长，默认更激进）
- `run.crash_stress_burst_probability: 0.25`（触发 burst 的概率）
- `run.crash_stress_burst_min_steps: 2`
- `run.crash_stress_burst_max_steps: 5`

Monkey 兼容增强模式（Android 先行）可选配置：

- `run.profile: "monkey_compatible"`
- `run.monkey_wait_ms: 350`
- `run.monkey_ios_wait_ms: 260`（仅 iOS + monkey_compatible 生效）
- `policy.monkey_out_of_app_streak_threshold: 2`
- `policy.monkey_loop_streak_threshold: 3`
- `policy.monkey_perturb_boost: 2.0`
- `policy.monkey_risk_cooldown_steps: 3`
- `policy.monkey_risk_penalty: 2.5`
- `policy.monkey_score_jitter: 0.35`
- `policy.monkey_diversity_state_repeat_threshold: 2`
- `policy.monkey_diversity_state_repeat_penalty: 0.6`
- `policy.monkey_diversity_novel_action_boost: 0.8`
- `policy.monkey_diversity_frontier_boost: 0.6`
- `policy.monkey_ios_permission_fastpath: true`
- `policy.monkey_ios_permission_boost: 2.2`
- `policy.monkey_ios_restart_penalty: 1.8`
- `policy.monkey_ios_back_penalty: 0.5`
- `policy.monkey_ios_swipe_boost: 0.6`
- `policy.monkey_ios_list_swipe_boost: 0.8`（iOS list_page 额外 swipe 探索加权）
- `policy.monkey_ios_pinch_boost: 0.5`
- `policy.monkey_ios_static_text_click_penalty: 1.0`（抑制 iOS 静态文本无效点击）
- `policy.monkey_ios_cell_click_boost: 0.7`（提升 iOS Cell 入口点击权重）
- `policy.monkey_ios_back_like_click_penalty: 1.1`（抑制 iOS 返回/关闭类点击）
- `policy.monkey_ios_external_jump_penalty: 2.0`（抑制跳转相册/拍照等外部路径）
- `policy.monkey_ios_recovery_stuck_threshold: 10`
- `policy.monkey_ios_same_state_recovery_threshold: 3`
- `policy.monkey_ios_permission_recovery_grace_steps: 3`

策略组合关系（建议同步给相关方）：

- `run.profile` 在一次运行中只能选择一个：`functional` / `crash_stress` / `monkey_compatible`。
- `crash_stress` 与 `monkey_compatible` 互斥，不能同一轮同时启用。
- `learning.enabled` 是独立增强层，可与任一 profile 叠加。
- `monkey_compatible` 不是独立引擎，而是在主线动作提取与打分之上叠加调分（防脱、防卡、风险冷却、随机扰动）。

模式对结果的主要影响：

- `functional`：更偏覆盖质量与恢复稳定性。
- `crash_stress`：更偏 crash 暴露效率（吞吐、burst、首崩步数）。
- `monkey_compatible`：更偏防脱/防卡与随机探索平衡（越界比例、streak、冷却命中率）。
- iOS + `monkey_compatible`：额外启用权限弹窗 fast-path、动作权重与恢复缓冲调优（目标是提覆盖同时抑制过度恢复）。

学习型策略（UCB）可选配置（默认关闭）：

- `learning.enabled: false`
- `learning.alpha: 0.8`（规则分与学习分混合系数）
- `learning.ucb_exploration: 1.2`
- `learning.persistence_enabled: false`（开启后跨运行保存/加载学习状态）
- `learning.state_path: "output/learning_state.json"`（学习状态文件）
- `learning.min_observations_to_persist: 20`（达到最小观测数后才落盘）
- `learning.module_bucket_enabled: true`（按页面模块聚类 arm）
- `learning.reward_changed_state: 1.0`
- `learning.reward_novel_state: 0.3`
- `learning.reward_functional_page: 0.4`
- `learning.reward_issue_signal: 0.8`
- `learning.penalty_out_of_app: 1.0`
- `learning.penalty_unchanged: 0.2`
- `learning.penalty_recent_loop: 0.25`
- `learning.penalty_system_action: 0.15`

官方 monkey sidecar（Android 双轨）可选配置（默认关闭）：

- `sidecar.monkey.enabled: false`
- `sidecar.monkey.step_interval: 15`（每 N 个主轨 step 触发一次 sidecar 批次）
- `sidecar.monkey.max_batches: 4`（单次 run 最多 sidecar 批次数）
- `sidecar.monkey.events_per_batch: 35`（每批官方 monkey 事件数）
- `sidecar.monkey.throttle_ms: 20`
- `sidecar.monkey.seed_offset: 1000`
- `sidecar.monkey.pct_touch: 45`
- `sidecar.monkey.pct_motion: 15`
- `sidecar.monkey.pct_nav: 35`
- `sidecar.monkey.pct_syskeys: 5`
- `sidecar.monkey.ignore_crashes: true`
- `sidecar.monkey.ignore_timeouts: true`
- `sidecar.monkey.ignore_security_exceptions: true`
- `sidecar.monkey.adb_timeout_sec: 30`

sidecar 观测指标（`coverage_benchmark.json`）：

- `sidecar_batch_count`
- `sidecar_success_count`
- `sidecar_success_rate`
- `sidecar_recovery_count`
- `sidecar_events_injected_total`
- `sidecar_batch_step_ratio`
- `sidecar_last_exit_code`

3. 启动运行

```bash
python main.py
```

给普通测试工程师的快捷入口：

```bash
python main_android.py   # 自动使用 config.android.yaml
python main_ios.py       # 自动使用 config.ios.yaml
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

详细设计参考：`docs/主线详细设计.md`  
使用指南（非自动化同学）：`docs/使用指南（当前主线）.md`

iOS 直连 WDA URL 接入方案：`docs/iOS接入方案（直连WDA_URL）.md`
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
- monkey 专项：`monkey_diversity_boosted_ratio`、`monkey_ios_tuning_applied_ratio`、`monkey_ios_permission_fastpath_ratio`、`permission_like_step_ratio`、`monkey_ios_recovery_grace_step_ratio`
- learning 专项：`learning_step_ratio`、`learning_exploration_rate`、`learning_average_reward`、`learning_top_arms`
- gate 判定：`gates.passed` 与 `gates.results.*`（按平台和 profile 给出目标阈值对比）
  - 当 Android `run.profile=monkey_compatible` 且 `sidecar.monkey.enabled=true` 时，额外 gate：`sidecar_batch_count >= 1`、`sidecar_success_rate >= 0.95`、`sidecar_recovery_failure_rate <= 0.2`

查看报告（Windows PowerShell）：

```powershell
start .\output\run\report\index.html
```
