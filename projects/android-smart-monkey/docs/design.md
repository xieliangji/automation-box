# Android Smart Monkey 详细设计

## 1. 目标

本项目用于构建一个面向 Android App 的智能 Monkey 测试框架。

与系统 Monkey 相比，它的核心差异不是“发更多随机事件”，而是：

- 能识别当前页面状态
- 能提取更合理的候选动作
- 能基于历史收益为动作打分
- 能维护页面状态图（UTG）
- 能在卡住时回溯或逃逸
- 能记录完整轨迹用于复现问题

第一版目标是做出 **可跑、可解释、可扩展** 的 MVP。

---

## 2. MVP 范围

### 2.1 要实现

1. 设备驱动抽象
2. 页面层级树抓取
3. 统一 UIElement / DeviceState 建模
4. 稳定状态指纹生成
5. 候选动作提取
6. 动作评分与选择
7. 主循环执行
8. 运行轨迹记录

### 2.2 暂不实现

1. 强化学习
2. 代码覆盖率插桩
3. 大模型在线决策
4. iOS 支持
5. 设备侧高性能执行器

---

## 3. 总体架构

```text
Runner
 ├─ DeviceDriver
 ├─ StateCapturer
 │   ├─ HierarchyParser
 │   └─ StateFingerprinter
 ├─ ActionExtractor
 ├─ ActionScorer
 ├─ ActionSelector
 ├─ TransitionRecorder
 └─ Recovery / Escape
```

### 3.1 模块职责

#### Runner
负责主循环：采集状态、提取动作、打分、执行、记录、恢复。

#### DeviceDriver
负责设备交互：

- 获取前台包名 / activity
- dump hierarchy
- 截图
- click / long click / swipe / back / home
- start app / stop app

#### StateFingerprinter
负责把页面层级树归一化，生成稳定状态 ID。

#### ActionExtractor
负责从当前状态提取候选动作。

#### ActionScorer
负责综合新颖度、收益、风险、重复度给动作打分。

#### Recorder
负责记录：

- action
- transition
- state snapshot
- score detail
- issue artifact

---

## 4. 数据模型

### 4.1 UIElement

统一表示页面上的可见节点。

核心字段：

- class_name
- resource_id
- text
- content_desc
- clickable / long_clickable / editable / scrollable
- bounds
- depth
- xpath

### 4.2 DeviceState

统一表示某个时刻的页面状态。

核心字段：

- state_id
- raw_hash
- stable_hash
- package_name
- activity_name
- elements
- popup_flags
- system_flags
- app_flags
- timestamp_ms

### 4.3 Action

表示一个可执行动作。

核心字段：

- action_type
- target_element_id
- params
- source_state_id
- score
- score_detail
- tags

### 4.4 Transition

表示一次动作执行导致的状态迁移。

核心字段：

- from_state_id
- to_state_id
- action_id
- success
- changed
- crash
- anr
- out_of_app
- duration_ms

---

## 5. 状态建模设计

### 5.1 为什么不能只看 Activity

因为同一个 Activity 内可能存在：

- 不同 Tab
- 不同弹窗态
- 不同登录态
- 不同列表位置
- 不同 WebView 内容

所以状态最少要由以下信息共同决定：

- package/activity
- 可交互元素集合
- 关键文本与结构摘要
- 弹窗 / 系统页标签

### 5.2 状态指纹

设计两套 hash：

#### raw_hash
用于完整调试，尽量保真。

#### stable_hash
用于去重，需要归一化处理。

### 5.3 归一化规则

1. 文本数字归一化：
   - 数字替换成 `<NUM>`
   - 时间替换成 `<TIME>`
2. 坐标归一化：
   - 使用相对比例，避免像素抖动影响
3. 列表项抽样：
   - 同构 item 只保留前几个代表节点
4. 仅选关键节点：
   - clickable
   - editable
   - scrollable
   - checkable

---

## 6. 候选动作提取

### 6.1 动作类型

- click
- long_click
- input
- swipe
- back
- home
- wait
- restart_app

### 6.2 提取规则

#### 元素点击
对 clickable 元素生成 click。

#### 长按
对 long_clickable 元素生成 long_click。

#### 输入
对 editable 元素生成 input。

#### 滚动
对 scrollable 元素生成 swipe up / swipe down。

#### 系统动作
额外补充：

- back
- wait
- restart_app

### 6.3 列表抽样

列表页不应对全部 item 都生成动作，否则会导致动作爆炸。

建议策略：

- 前 3 个
- 中间 1 个
- 后 2 个
- 对模板重复项去重

---

## 7. 动作评分

建议公式：

```text
score =
  + novelty
  + transition_gain
  + depth_potential
  + business_value
  + escape_value
  + input_value
  - repeat_penalty
  - risk_penalty
  - stuck_penalty
```

### 7.1 Novelty
该动作是否新鲜。

### 7.2 TransitionGain
历史上是否经常带来新状态。

### 7.3 DepthPotential
是否更可能进入更深页面。

### 7.4 BusinessValue
是否命中高价值语义，如：

- 登录
- 下一步
- 详情
- 添加
- 保存
- 配置

### 7.5 RepeatPenalty
最近是否重复太多次。

### 7.6 RiskPenalty
是否存在高风险语义，如：

- 删除
- 支付
- 恢复出厂
- 退出登录

---

## 8. 选择策略

第一版建议使用 **epsilon-greedy + top-k**：

- 大部分时间从 top-k 高分动作中按权重抽样
- 少量时间随机探索

默认建议：

- epsilon = 0.2
- top_k = 5

这样比纯贪心更稳，也比纯随机更容易向深处探索。

---

## 9. 回溯与逃逸

### 9.1 卡住判定

可基于以下信号累计 stuck_score：

- 连续状态不变
- 连续重复动作
- 短环 A→B→A→B
- 应用退到后台

### 9.2 恢复优先级

1. 处理明显弹窗
2. back
3. 连续 back
4. 回到最近检查点
5. force-stop + restart app

---

## 10. 落盘设计

建议每次运行输出到独立目录：

```text
output/run_xxx/
├── config.json
├── actions.jsonl
├── transitions.jsonl
├── states/
│   ├── *.json
│   ├── *.xml
│   └── *.png
└── issues/
```

### 每步记录

- step_no
- prev_state_id
- action
- score
- score_detail
- curr_state_id
- changed / unchanged
- duration
- foreground package/activity

---

## 11. 编码顺序建议

### 第一阶段

1. DeviceDriver
2. models.py
3. fingerprint.py
4. extractor.py
5. scorer.py
6. runner.py

### 第二阶段

1. XML 解析到 UIElement
2. issue artifact
3. checkpoint / backtrack
4. popup / permission 识别

### 第三阶段

1. 语义化输入
2. 黑白名单增强
3. UTG 可视化
4. replay 生成

---

## 12. 第一版关键决策

### 决策一：先用 Python 控制器

原因：

- 开发快
- 易调试
- 易看日志
- 易快速试错

### 决策二：元素执行前重定位

不要长期持有 driver 元素对象。

更稳的做法是：

1. 先存元素摘要
2. 执行动作前重新匹配
3. 匹配不到再退化到坐标点击

### 决策三：先做强启发式，不做强化学习

在绝大多数工程场景下：

**状态图 + 启发式打分 + 回溯**
比一上来引入 RL 更适合落地。

---

## 13. 当前代码骨架与设计关系

当前代码骨架已经提供：

- 统一模型对象
- 基础驱动接口
- 动作提取器
- 动作评分器
- 主运行器骨架

还缺的部分主要是：

- hierarchy XML 真实解析
- 更完整的状态相似度比较
- 运行数据持久化
- 异常监控与 issue 落盘

---

## 14. 下一步建议

你接下来可以直接按下面顺序编码：

1. 让 `AdbDriver.dump_hierarchy()` 真正拿到 XML
2. 加一个 `parser.py`，把 XML 转成 `UIElement`
3. 在 `runner.py` 中接入 parser + fingerprinter
4. 先对一个简单 Demo App 跑 300~500 步
5. 观察是否出现明显循环，再补 stuck / backtrack
