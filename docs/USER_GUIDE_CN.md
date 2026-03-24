# Android Smart Monkey 使用指南（面向非自动化测试开发工程师）

这份文档给**业务开发工程师**或**普通测试同学**使用，目标是让你在不读源码的情况下，也能独立完成一次 Android App 的智能 Monkey 测试，并读懂结果。

---

## 1. 这套工具是什么

它不是系统自带的纯随机 Monkey。

它会先识别当前页面，再挑选更“像人”的操作（点击、输入、返回、滚动），同时记录完整轨迹，最后输出可阅读报告，方便定位问题。

主入口固定为：

- `main.py`

输出目录固定为：

- `output/run/`

---

## 2. 你需要准备什么

### 2.1 本机环境

- macOS / Linux（Windows 也可，但命令略有差异）
- Python 3.11+
- ADB 可用（`adb devices` 能看到手机）

### 2.2 手机环境

- 已开启开发者选项和 USB 调试
- 首次连接时，手机上点“允许 USB 调试”
- 建议关闭省电策略，避免测试过程中 App 被系统强杀

### 2.3 目标应用信息

你需要知道两项：

- `package_name`（包名），例如：`com.ugreen.iot`
- `launch_activity`（启动页 Activity），例如：`.ui.SplashActivity`

如果你不确定启动页，可用：

```bash
adb shell cmd package resolve-activity --brief com.ugreen.iot/.MainActivity
```

或让同事提供。

---

## 3. 第一次使用（一步一步）

### 3.1 安装依赖

在项目根目录执行：

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

### 3.2 生成配置文件

```bash
cp config.example.yaml config.yaml
```

Windows PowerShell：

```powershell
copy config.example.yaml config.yaml
```

### 3.3 修改配置（最少改这几个）

打开 `config.yaml`，重点改：

- `app.package_name`
- `app.launch_activity`
- `run.max_steps`

建议开启会话护栏（默认已开启）：

- `policy.enable_session_guardrails: true`

作用：在登录/表单等高风险会话页抑制部分高风险系统动作（如 `back/restart_app`），减少回登录循环。

如测试需要自动保持登录态，可开启登录引导：

- `policy.enable_login_bootstrap: true`
- `policy.bootstrap_username: "你的账号"`
- `policy.bootstrap_password: "你的密码"`
- `policy.bootstrap_max_attempts: 3`
- `policy.bootstrap_retry_interval_steps: 20`

作用：当检测到登录页时，自动尝试填充账号密码并点击登录按钮，避免长时间停留登录流程。

如你要专门测试登录/账号相关页面（小范围 Monkey），可关闭功能页优先策略：

- `policy.prefer_functional_pages: false`

作用：关闭后不再对登录页的“非认证动作”做额外打分惩罚，更容易停留在登录/账号相关页做细粒度探索。

与该开关联动的恢复策略说明：

- 当 `prefer_functional_pages: true` 时，恢复会优先回到非登录 checkpoint，并尽量过滤会把路径带回登录链路的历史动作。
- 当 `prefer_functional_pages: false` 时，恢复可使用登录 checkpoint，适合登录/账号链路小范围测试。

如你要做策略优化前后效果对比（A/B），可配置 baseline：

- `run.benchmark_baseline_dir: "output/你的历史run目录"`

作用：报告会生成 `coverage_benchmark.json`，包含功能覆盖率、登录页停留比例、越界比例、恢复成功率、综合评分及与 baseline 的 delta。

建议起步值：

- 冒烟：`run.max_steps: 20`
- 中等回归：`run.max_steps: 100`
- 相对完整：`run.max_steps: 200~500`（按设备稳定性调整）

### 3.4 启动测试

```bash
./.venv/bin/python main.py
```

Windows PowerShell：

```powershell
python main.py
```

运行过程中手机会被自动点击/输入/返回，这是正常行为。

---

## 4. 推荐执行策略（避免一上来跑太猛）

### 阶段 A：冒烟确认（1~20 步）

目的：验证环境和配置都正常。

### 阶段 B：中等覆盖（100 步左右）

目的：快速发现明显稳定性问题（闪退、ANR、跳系统页等）。

### 阶段 C：相对完整（200~500 步）

目的：拉长探索深度，观察复杂页面与回退恢复能力。

---

## 5. 测试完成后看哪里

产物目录：`output/run/`

你最关心：

- `report/summary.md`：人类可读摘要
- `report/index.html`：可视化报告
- `runtime.log`：运行日志（含每步动作埋点）
- `issues/*/summary.json`：异常详情（如果有）
- `steps.jsonl`：每一步执行记录
- `transitions.jsonl`：状态迁移记录
- `utg.json`：页面状态图（UTG）

---

## 6. 如何判断“这次跑得好不好”

可以用下面的简单标准：

- 是否跑到预期步数（例如配置 300，实际接近 300）
- `Issue 数` 是否为 0（或可接受）
- 是否长期卡在同一页面（看 `steps.jsonl` 的 state 是否重复）
- 是否频繁跳出目标 App（`out_of_app` 比例是否偏高）

如果你只看一个文件，先看：

- `output/run/report/summary.md`

---

## 7. 常见问题与排查

### Q1：运行后没反应 / 很慢

先看设备连通：

```bash
adb devices
```

确认手机在线（`device` 状态）。

### Q2：报找不到包名或拉不起应用

检查 `config.yaml`：

- 包名拼写是否正确
- `launch_activity` 是否正确

建议先用以下命令确认启动页可解析：

```bash
adb shell cmd package resolve-activity --brief com.ugreen.iot/.ui.SplashActivity
```

如果输出 `No activity found`，请先修正 `launch_activity` 再执行 monkey。

### Q3：测试中途被系统打断

常见原因：

- 权限弹窗未授权
- 系统省电或后台限制
- 手机锁屏

建议：

- 关闭自动锁屏
- 保持亮屏与常亮供电
- 首次先人工把关键权限放开

### Q4：看不懂 JSONL

先看 `report/summary.md` 与 `report/index.html`，再回头按需查 JSONL 细节。

---

## 8. 给非自动化同学的建议

- 不要追求“一次跑很久”，先小步快跑
- 每次改动后先跑 20 步冒烟，再上 200+ 步
- 遇到问题优先保存 `output/run/` 目录再反馈
- 反馈时附上：
  - 使用的 `config.yaml`
  - `report/summary.md`
  - 相关 `issues/*/summary.json`

---

## 9. 一条龙命令模板（可直接改包名后执行）

```bash
cp config.example.yaml config.yaml
./.venv/bin/python - <<'PY'
import yaml
from pathlib import Path
p = Path("config.yaml")
data = yaml.safe_load(p.read_text(encoding="utf-8"))
data["app"]["package_name"] = "com.ugreen.iot"
data["app"]["launch_activity"] = ".ui.SplashActivity"
data["run"]["max_steps"] = 200
p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print("config.yaml updated")
PY
./.venv/bin/python main.py
```

完成后查看：

```bash
open output/run/report/index.html
```

Windows PowerShell：

```powershell
copy config.example.yaml config.yaml
python -c "import yaml;from pathlib import Path;p=Path('config.yaml');d=yaml.safe_load(p.read_text(encoding='utf-8'));d['app']['package_name']='com.ugreen.iot';d['app']['launch_activity']='.ui.SplashActivity';d['run']['max_steps']=200;p.write_text(yaml.safe_dump(d,allow_unicode=True,sort_keys=False),encoding='utf-8')"
python main.py
start .\output\run\report\index.html
```
