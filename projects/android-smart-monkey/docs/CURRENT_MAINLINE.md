# 当前 Mainline 入口说明

如果你希望使用当前收敛后的服务化主线，建议从下面这个入口启动：

```bash
python main_mainline.py
```

## 当前 Mainline 指向

当前 `main_mainline.py` 指向：

- `SmartMonkeyAppCurrent`

它是在前面版本能力基础上，进一步把以下逻辑下沉为服务层后的主线：

- `RecoveryService`
- `ReportService`
- `TelemetryService`

## 当前 Mainline 已包含能力

- 状态建模与层级树解析
- 候选动作提取 v2
- 动作评分 v2
- watchdog 监控
- issue 落盘
- periodic screenshot
- replay 导出与 issue replay
- checkpoint 管理
- backtrack 恢复
- navigation recovery v2
- recovery validation
- recorder index
- html / markdown 报告
- recovery metrics
- 服务化拆分（recovery / report / telemetry）

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
python main_mainline.py
```

## 当前输出目录

默认输出到：

```text
output/current_mainline_run/
```

## 与 main_current.py 的关系

- `main_current.py`：当前稳定默认入口，便于直接运行
- `main_mainline.py`：当前服务化收敛主线，便于后续继续重构和扩展

如果你后面准备继续收敛内部结构，建议优先围绕 `main_mainline.py` 对应的 `SmartMonkeyAppCurrent` 继续演进。
