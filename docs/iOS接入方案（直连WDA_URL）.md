# iOS（直连 WDA URL）接入方案

> 目标：在不引入 Appium 的前提下，基于用户提供的 WDA URL，把当前 monkey 框架扩展到 iOS。  
> 当前阶段：已完成主线接入与最小闭环验证（持续迭代中）。

---

## 1. 背景与决策

### 1.1 背景

当前框架运行在 Android，设备动作由 `AdbDriver/RobustAdbDriver` 提供，上层（状态建模、动作提取、评分、恢复、报告）已相对独立。

### 1.2 决策

- 不引入 Appium
- 直接消费 WDA REST 接口
- 用户侧负责通过 `go-ios` 启动并维护 WDA 服务
- 框架侧只要求可访问的 `wda_url`

### 1.3 核心收益

- 依赖更少（无 Appium Server）
- 架构更直（驱动层直接对接平台能力）
- 与当前 `DeviceDriver` 分层一致，便于复用上层逻辑

---

## 2. 边界与非目标

## 2.1 本期目标

- 在现有运行主链路下，增加 iOS 驱动接入设计
- 明确配置、会话、动作映射、恢复与可观测性方案

## 2.2 非目标

- 本文不展开代码逐行解读（仅说明主线设计与落地结果）
- 本文不负责 WDA 安装、签名、部署细节
- 本文不引入 Appium 兼容层

---

## 3. 外部依赖与用户约定

## 3.1 用户侧前置条件

- iOS 设备上可运行 WDA
- 通过 `go-ios` 启动 WDA 并暴露可访问 URL（例如 `http://127.0.0.1:8100`）
- 用户提供：
  - `wda_url`
  - `bundle_id`（目标应用）

## 3.2 框架侧承诺

- 只使用 `wda_url` 进行 REST 通讯
- 不接管 WDA 进程生命周期（启动/停止由用户负责）

---

## 4. 配置模型（当前主线）

在现有配置基础上，当前主线已支持如下配置：

```yaml
app:
  platform: ios
  target_app_id: "com.example.app"
  launch_target: ""

ios:
  wda_url: "http://127.0.0.1:8100"
  session_create_timeout_sec: 30
  command_timeout_sec: 20
  request_retry: 2
  keep_session: true
  auto_recreate_session: true
  udid: ""
```

说明：

- Android 继续兼容 `app.package_name/launch_activity`，并优先推荐使用平台中性字段 `app.target_app_id/launch_target`
- iOS 入口使用 `app.platform=ios` + `app.target_app_id` + `ios.wda_url`
- 为兼容历史配置，仍接受 `platform: ios`（根级）和 `ios.bundle_id`，运行时会自动映射

---

## 5. 架构落位

## 5.1 驱动抽象保持不变

继续沿用 `DeviceDriver` 协议，新增 `WdaDriver` 实现该协议。

## 5.2 新增模块建议

- `smart_monkey/device/wda_driver.py`
  - 面向上层的设备驱动实现
- `smart_monkey/device/wda_client.py`
  - 纯 HTTP 封装（会话、请求、重试、错误归类）
- `smart_monkey/device/driver_factory.py`（可选）
  - 按 `platform` 选择 Android/iOS 驱动

## 5.3 上层改动控制

- `app_runtime.py` 主流程尽量不改
- parser / extractor / scorer 仅做 iOS 适配增强，不破坏 Android 路径

---

## 6. DeviceDriver 能力映射（Android -> iOS/WDA）

| 现有能力 | iOS/WDA 对应能力 | 说明 |
|---|---|---|
| `get_foreground_package()` | active app info 的 `bundleId` | 用于 out_of_app 判定 |
| `get_current_activity()` | 无等价 activity | 可返回前台 app name 或 `None` |
| `dump_hierarchy()` | page source(XML) | 供状态解析 |
| `take_screenshot()` | screenshot(base64) | 落盘后与 Android 一致 |
| `click(x,y)` | tap | 坐标点击 |
| `long_click(...)` | touch and hold | 按压时长映射 |
| `input_text(text)` | send keys / element value | 依赖焦点或元素定位 |
| `swipe(...)` | drag/swipe | 参数映射 |
| `pinch(...)` | actions(双指 pointer) | 缩放手势统一走 W3C actions |
| `press_back()` | 导航返回策略 | 导航栏返回按钮优先，边缘返回兜底 |
| `press_home()` | 无稳定等价 | 建议 iOS 下禁用该动作 |
| `start_app(bundle)` | activate/launch app | 用 `bundle_id` |
| `stop_app(bundle)` | terminate app | 用 `bundle_id` |
| `wait_idle(ms)` | sleep + 轮询稳定态 | 与 Android 语义一致 |

---

## 7. 会话与请求模型

## 7.1 启动阶段

1. `GET /status` 健康检查  
2. 创建或复用 session  
3. 读取前台 app，若不在目标 `bundle_id`，执行 activate/launch  
4. 进入主循环

## 7.2 运行阶段

- 所有 WDA 请求统一经过 `WdaClient`
- 每个请求具备：超时、有限重试、错误分类
- 若 session 失效且 `auto_recreate_session=true`：
  - 重建 session
  - 重新激活目标 app
  - 继续执行

## 7.3 结束阶段

- `keep_session=true`：保留 session（默认）
- `keep_session=false`：主动删除 session

---

## 8. 状态解析与动作策略适配

## 8.1 页面树解析

WDA source 与 Android UI XML 属性不同，需新增 iOS 归一化规则，把节点映射到现有 `UIElement`：

- class -> `XCUIElementType*`
- resource_id 映射为 `name/identifier`
- text 映射为 `label/value/name` 的优先级合并
- bounds 从 iOS 坐标信息归一化

## 8.2 动作提取策略

- 保留现有 Runtime extractor/scorer 主体
- 新增 iOS 平台差异规则：
  - 禁用 `home` 候选动作
  - `back` 使用 iOS 可回退元素/手势策略
  - 风险关键词与控件模式可追加 iOS 版本

---

## 9. 恢复、回放、报告联动

## 9.1 恢复

- out_of_app 判定从 `package_name` 切换为 `bundle_id`
- `restart_app/restart_to_checkpoint` 走 WDA activate/terminate/launch 组合

## 9.2 回放

- 保持当前策略：记录全量 replay，恢复场景局部执行 replay
- 建议在 replay 记录中增加 `platform` 字段，避免跨平台误回放

## 9.3 报告

- 报告结构不变
- 在 summary/index 中增加平台标识（android/ios）与会话信息（可选脱敏）

---

## 10. 可观测性与错误处理要求

## 10.1 日志要求

- 启动日志：`wda_url`、session 创建结果、目标 bundle 校验
- 每步动作日志：沿用现有 `runtime.log` 结构
- 恢复日志：触发原因、策略、结果

## 10.2 错误处理

- 连接错误：重试 + 明确报错（URL 不可达）
- 协议错误：记录 endpoint 与响应摘要
- 会话失效：按策略重建；失败则 fail-fast
- 严禁静默吞错

---

## 11. 分阶段实施计划（建议）

## 阶段 A：最小闭环（MVP）

- `WdaDriver` + `WdaClient`
- 支持：前台检测、source、screenshot、tap、swipe、pinch、input、activate/terminate
- 跑通主循环与基础报告

## 阶段 B：稳定性

- 会话重建
- 请求重试与超时治理
- iOS 返回动作策略完善

## 阶段 C：策略增强

- iOS parser/extractor/scorer 细化
- 恢复与回放平台隔离增强

---

## 12. 验收标准（DoD）

- 同一主入口可按配置切换 Android/iOS
- iOS 在给定 `wda_url + bundle_id` 下可完成 N 步稳定执行
- 日志、steps、actions、transitions、report 产物齐全
- out_of_app 判定与恢复可工作
- 不引入 Appium 依赖

---

## 13. 风险与对策

- WDA 不同构建版本端点差异  
  - 对策：在 `WdaClient` 做端点能力探测与 fallback
- iOS 返回语义弱于 Android  
  - 对策：平台化 `back` 策略（元素优先 + 手势兜底）
- 网络链路抖动（USB/Wi-Fi）  
  - 对策：统一重试、超时、会话重建与 fail-fast
