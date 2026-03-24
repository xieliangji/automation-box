# 统一运行说明

## 唯一路径

仓库已收敛为唯一路径，后续开发和问题修复统一基于：

- 入口：`main.py`
- 主类：`smart_monkey/app_runtime.py::SmartMonkeyAppRuntime`
- 输出：`output/run/`

历史分支入口已清理，后续统一通过 `main.py` 执行，不再维护并行入口脚本。

## 运行方式

1. 复制配置

```bash
cp config.example.yaml config.yaml
```

Windows PowerShell：

```powershell
copy config.example.yaml config.yaml
```

2. 修改目标应用

- `app.package_name`
- `app.launch_activity`

3. 运行

```bash
python main.py
```

Windows PowerShell：

```powershell
python main.py
```

查看报告（Windows PowerShell）：

```powershell
start .\output\run\report\index.html
```

## 当前能力

- 状态建模与层级树解析
- 候选动作提取与高风险过滤
- 动作评分与探索策略
- watchdog 监控与 issue 落盘
- periodic screenshot
- replay 导出与 issue replay
- checkpoint 管理与 backtrack
- navigation recovery + recovery validation
- recorder index
- html / markdown 报告
- recovery metrics
- 服务化编排（recovery / report / telemetry / watchdog / orchestration）
- 会话护栏（session guardrails）：在登录/表单等高风险会话状态下抑制 `back/restart_app`，降低回登录循环概率
- 登录引导（login bootstrap）：可选自动填充账号密码并触发登录，减少停留登录页的预算浪费
- 目标导向探索开关（goal-directed switch）：`prefer_functional_pages` 默认开启，优先功能页；关闭后可做登录/账号链路小范围 Monkey
- 恢复策略升级（recovery upgrade）：当 `prefer_functional_pages=true` 时，恢复优先选择非登录 checkpoint，并过滤会导致回登录链路的回放动作
- 覆盖率基准评估（coverage benchmarking）：支持读取 baseline run 并输出 KPI 对比（`coverage_benchmark.json`）

## 代码组织约定

- 运行编排职责优先收敛在 `smart_monkey/services/`。
- `app_runtime.py` 作为运行壳层，避免在此堆叠细碎实现。
- 新能力优先接入主线链路，不再新增并行 `main_*` 入口。
