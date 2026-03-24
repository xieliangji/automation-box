# 推荐入口 V2 说明

如果你准备继续把当前项目作为**后续默认开发主线**推进，建议优先从下面这个入口启动：

```bash
python main_recommended_v2.py
```

## 当前推荐入口 V2 指向

当前 `main_recommended_v2.py` 指向：

- `SmartMonkeyAppRecommendedV2`

它是在此前推荐主线基础上，进一步把运行编排职责收敛到下列服务层后的版本：

- `RecoveryService`
- `ReportService`
- `TelemetryService`
- `WatchdogService`
- `RuntimeHooks`
- `RecoveryAuditService`
- `OrchestrationService`

## 为什么现在更推荐 V2

相比 `main_recommended.py` 对应的上一版推荐主线，V2 更适合作为继续演进的基础，原因是：

1. 运行编排逻辑进一步向 `OrchestrationService` 收口
2. `watchdog / telemetry / recovery audit / report` 的职责边界更清晰
3. app 类本身更接近 orchestration shell，便于后续继续拆分 runtime flow
4. 更适合作为后续补完整集成测试与回归测试的基线

## 推荐运行方式

1. 复制配置文件

```bash
cp config.v3.example.yaml config.yaml
```

2. 修改：

- `app.package_name`
- `app.launch_activity`

3. 执行：

```bash
python main_recommended_v2.py
```

## 默认输出目录

```text
output/recommended_v2_run/
```

## 与其他入口的关系

- `main_current.py`：当前稳定默认入口
- `main_mainline.py`：服务化收敛主线入口
- `main_orchestrated.py`：orchestration 主线入口
- `main_recommended.py`：上一版推荐主线入口
- `main_recommended_v2.py`：当前更推荐的后续默认开发主线入口

## 后续建议

如果你准备继续收敛内部结构，建议优先围绕下面这些文件继续演进：

- `main_recommended_v2.py`
- `smart_monkey/app_recommended_v2.py`
- `smart_monkey/services/`
