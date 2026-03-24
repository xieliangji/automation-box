# 推荐入口说明

当前项目如果你要继续作为**默认开发入口**和**默认运行入口**来使用，建议优先从下面这个文件启动：

```bash
python main_recommended.py
```

## 推荐入口指向

当前 `main_recommended.py` 指向：

- `SmartMonkeyAppRecommended`

它建立在以下收敛主线之上：

- `SmartMonkeyAppOrchestratedV2`
- `RecoveryService`
- `ReportService`
- `TelemetryService`
- `WatchdogService`
- `RuntimeHooks`
- `RecoveryAuditService`

## 为什么现在推荐这个入口

相比历史入口，这个入口更适合作为后续演进主线，原因是：

1. 运行编排逻辑已经明显服务化
2. watchdog / telemetry / recovery / report 已开始解耦
3. 恢复事件有了更结构化的审计记录
4. 更适合作为后续继续做 runtime orchestration 收敛的基础

## 当前推荐运行方式

1. 复制配置文件

```bash
cp config.v3.example.yaml config.yaml
```

2. 修改：

- `app.package_name`
- `app.launch_activity`

3. 执行：

```bash
python main_recommended.py
```

## 默认输出目录

```text
output/recommended_run/
```

## 与其他入口的关系

- `main_current.py`：当前稳定默认入口
- `main_mainline.py`：服务化收敛主线入口
- `main_orchestrated.py`：orchestration 主线入口
- `main_recommended.py`：当前建议作为后续默认开发主线的入口

## 后续建议

如果你准备继续推进结构收敛，建议优先围绕下面这些文件继续演进：

- `main_recommended.py`
- `smart_monkey/app_recommended.py`
- `smart_monkey/services/`
