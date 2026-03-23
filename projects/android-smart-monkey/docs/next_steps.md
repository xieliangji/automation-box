# 下一步实现建议

当前项目已经具备：

- 统一状态模型
- 层级树 XML 解析器
- 状态指纹
- 候选动作提取
- 动作评分
- UTG 图结构
- JSONL 落盘记录器
- 一个可继续扩展的 stateful 主程序入口

## 现在最应该补的三件事

### 1. 优化 `AdbDriver.get_foreground_package()` 与 `get_current_activity()`

当前实现使用：

- `dumpsys window | grep mCurrentFocus`

这个方案可用，但在不同 Android 版本上可能不稳定。

建议增加兜底：

- `dumpsys activity activities | grep mResumedActivity`
- `dumpsys window windows | grep -E 'mCurrentFocus|mFocusedApp'`

### 2. 为列表页做抽样点击增强

当前 `ActionExtractor` 会为所有 clickable 元素生成动作，后面应改成：

- 相同 class/resource-id/text 模板的 item 去重
- 大列表只保留头部/中部/尾部代表节点
- 对重复点击无收益的 item 降权

### 3. 补充异常与 issue 落盘

建议新增：

- `watchdog.py`
- `issue_recorder.py`

至少要记录：

- crash 发生前最后 30 步
- 当前 screenshot
- 当前 hierarchy xml
- 当前 state json
- 当前 action

## 接下来的推荐编码顺序

1. 修 driver
2. 给 `HierarchyParser` 增加更多页面识别标签
3. 增强 `ActionExtractor` 的列表抽样能力
4. 为 `ActionScorer` 加入历史收益和短环惩罚
5. 加入 crash / anr / permission dialog 监控
6. 导出更完整的 UTG 可视化

## 推荐验证方式

先选一个结构简单的 Demo App：

- 登录页
- 列表页
- 详情页
- 表单页

让它先跑 300~500 步，重点观察：

- 是否一直卡在少数页面循环
- 是否容易跳出 app
- 是否能从首页推进到详情/表单
- 是否能稳定记录状态与动作轨迹
