# 当前主入口说明

当前项目建议统一从下面这个入口启动：

```bash
python main_current.py
```

## 当前主线版本

当前 `main_current.py` 指向：

- `SmartMonkeyAppV8`

也就是说，目前推荐把 `v8` 作为主开发线。

## 当前主线已包含能力

- 状态建模与层级树解析
- 候选动作提取 v2
- 动作评分 v2
- watchdog 监控
- issue 落盘
- periodic screenshot
- replay 导出
- checkpoint 管理
- backtrack 恢复
- navigation recovery v2
- recovery validation
- recorder index
- html / markdown 报告
- recovery metrics

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
python main_current.py
```

## 当前输出目录

默认输出到：

```text
output/current_run/
```

## 历史入口说明

仓库中仍保留：

- `main.py`
- `main_stateful.py`
- `main_watchdog.py`
- `main_v2.py`
- `main_v3.py`
- `main_v4.py`
- `main_v5.py`
- `main_v6.py`
- `main_v7.py`

这些文件主要用于保留演进过程与阶段性能力，不建议作为当前默认入口。
