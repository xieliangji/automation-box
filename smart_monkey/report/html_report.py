from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any


class HtmlReportGenerator:
    def __init__(self, output_dir: str | Path) -> None:
        self.output_dir = Path(output_dir)
        self.report_dir = self.output_dir / "report"
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._table_seq = 0

    def generate(self) -> Path:
        self._table_seq = 0
        steps = self._read_jsonl(self.output_dir / "steps.jsonl")
        actions = self._read_jsonl(self.output_dir / "actions.jsonl")
        transitions = self._read_jsonl(self.output_dir / "transitions.jsonl")
        issue_dirs = sorted((self.output_dir / "issues").glob("*")) if (self.output_dir / "issues").exists() else []
        issue_rows = self._load_issues(issue_dirs)
        checkpoints = self._read_json(self.output_dir / "checkpoints.json")
        utg = self._read_json(self.output_dir / "utg.json")
        lookup = self._read_json(self.output_dir / "index" / "lookup.json")
        recovery_metrics = self._read_json(self.output_dir / "report" / "recovery_metrics.json")
        coverage_benchmark = self._read_json(self.output_dir / "report" / "coverage_benchmark.json")
        replay_rows = self._read_jsonl(self.output_dir / "replay" / "actions_replay.jsonl")
        recovery_validation_rows = self._read_jsonl(self.output_dir / "recovery" / "recovery_validation.jsonl")

        checkpoints = checkpoints if isinstance(checkpoints, list) else []
        utg = utg if isinstance(utg, dict) else {}
        lookup = lookup if isinstance(lookup, dict) else {}
        recovery_metrics = recovery_metrics if isinstance(recovery_metrics, dict) else {}
        coverage_benchmark = coverage_benchmark if isinstance(coverage_benchmark, dict) else {}

        runtime_steps = [row for row in steps if isinstance(row.get("step"), int) and row.get("step", -1) >= 0]
        recovery_rows = [row for row in steps if row.get("recovery_strategy")]
        bootstrap_rows = [row for row in steps if row.get("bootstrap_status")]
        issue_counter = Counter(str(row.get("issue_type") or "unknown") for row in issue_rows)
        action_type_counter = Counter(str(row.get("action_type")) for row in runtime_steps if row.get("action_type"))
        bootstrap_counter = Counter(str(row.get("bootstrap_status") or "unknown") for row in bootstrap_rows)
        benchmark_current = coverage_benchmark.get("current_run", {}) if isinstance(coverage_benchmark, dict) else {}
        benchmark_current = benchmark_current if isinstance(benchmark_current, dict) else {}

        screenshots_dir = self.output_dir / "screenshots"
        replay_file = self.output_dir / "replay" / "actions_replay.jsonl"
        utg_file = self.output_dir / "utg.json"
        index_file = self.output_dir / "index" / "lookup.json"
        steps_file = self.output_dir / "steps.jsonl"
        actions_file = self.output_dir / "actions.jsonl"
        transitions_file = self.output_dir / "transitions.jsonl"
        checkpoints_file = self.output_dir / "checkpoints.json"
        recovery_validation_file = self.output_dir / "recovery" / "recovery_validation.jsonl"
        recovery_metrics_file = self.output_dir / "report" / "recovery_metrics.json"
        coverage_benchmark_file = self.output_dir / "report" / "coverage_benchmark.json"

        unique_states = self._count_unique_states(runtime_steps)
        out_of_app_count = sum(1 for row in runtime_steps if row.get("out_of_app") is True)
        changed_count = sum(1 for row in runtime_steps if row.get("changed") is True)
        recovery_event_count = len(recovery_rows)

        artifact_rows = [
            {
                "artifact": "Step 轨迹",
                "description": "每一步的动作、状态变化、分数与恢复审计",
                "exists": steps_file.exists(),
                "path": "../steps.jsonl",
            },
            {
                "artifact": "Action 明细",
                "description": "候选动作与最终执行动作明细",
                "exists": actions_file.exists(),
                "path": "../actions.jsonl",
            },
            {
                "artifact": "Transition 明细",
                "description": "状态迁移及 out_of_app/crash/anr 标记",
                "exists": transitions_file.exists(),
                "path": "../transitions.jsonl",
            },
            {
                "artifact": "UTG 状态图",
                "description": "状态节点和边统计、动作类型分布",
                "exists": utg_file.exists(),
                "path": "../utg.json",
            },
            {
                "artifact": "索引查找",
                "description": "基于 step/state/action 的快速索引",
                "exists": index_file.exists(),
                "path": "../index/lookup.json",
            },
            {
                "artifact": "Checkpoint",
                "description": "恢复检查点快照与优先级",
                "exists": checkpoints_file.exists(),
                "path": "../checkpoints.json",
            },
            {
                "artifact": "Recovery Metrics",
                "description": "恢复事件汇总与策略分布",
                "exists": recovery_metrics_file.exists(),
                "path": "./recovery_metrics.json",
            },
            {
                "artifact": "Coverage Benchmark",
                "description": "覆盖率 KPI 与 baseline 对比",
                "exists": coverage_benchmark_file.exists(),
                "path": "./coverage_benchmark.json",
            },
            {
                "artifact": "Recovery Validation",
                "description": "恢复结果校验明细",
                "exists": recovery_validation_file.exists(),
                "path": "../recovery/recovery_validation.jsonl",
            },
            {
                "artifact": "Replay",
                "description": "回放动作流（按 step 输出）",
                "exists": replay_file.exists(),
                "path": "../replay/actions_replay.jsonl",
            },
            {
                "artifact": "Screenshots",
                "description": "周期快照与 issue 截图",
                "exists": screenshots_dir.exists(),
                "path": "../screenshots/",
            },
        ]

        checkpoints_rows = []
        for item in checkpoints:
            if not isinstance(item, dict):
                continue
            checkpoints_rows.append(
                {
                    "checkpoint_id": item.get("checkpoint_id"),
                    "name": item.get("name"),
                    "priority": item.get("priority"),
                    "state_id": item.get("state_id"),
                    "created_at_ms": item.get("created_at_ms"),
                    "metadata": item.get("metadata"),
                }
            )

        utg_nodes_rows: list[dict[str, Any]] = []
        utg_nodes = utg.get("nodes", {})
        if isinstance(utg_nodes, dict):
            for state_id, meta in sorted(utg_nodes.items(), key=lambda item: item[0]):
                utg_nodes_rows.append({"state_id": state_id, "meta": meta})
        utg_edges_rows: list[dict[str, Any]] = []
        utg_edges = utg.get("edges", [])
        if isinstance(utg_edges, list):
            for index, edge in enumerate(utg_edges):
                if isinstance(edge, dict):
                    utg_edges_rows.append(
                        {
                            "edge_no": index + 1,
                            "from_state_id": edge.get("from_state_id"),
                            "to_state_id": edge.get("to_state_id"),
                            "action_type": edge.get("action_type"),
                            "target_element_id": edge.get("target_element_id"),
                            "stats": edge.get("stats"),
                        }
                    )

        navigation_entries = [
            ("overview", "概览"),
            ("artifacts", "产物索引"),
            ("issues", "Issue 详情"),
            ("recovery", "恢复数据"),
            ("benchmark", "覆盖率KPI"),
            ("bootstrap", "登录引导"),
            ("checkpoints", "Checkpoint"),
            ("steps", "Steps"),
            ("actions", "Actions"),
            ("transitions", "Transitions"),
            ("utg", "UTG"),
            ("raw", "原始 JSON"),
        ]

        issue_badges = "".join(
            f"<span class='pill'>{escape(name)}: {count}</span>" for name, count in sorted(issue_counter.items())
        )
        action_badges = "".join(
            f"<span class='pill'>{escape(name)}: {count}</span>" for name, count in sorted(action_type_counter.items())
        )
        bootstrap_badges = "".join(
            f"<span class='pill'>{escape(name)}: {count}</span>" for name, count in sorted(bootstrap_counter.items())
        )

        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        page_title = "Smart Monkey 运行报告（全量数据视图）"
        interaction_script = """
<script>
(function () {
  function parseComparable(text) {
    var normalized = String(text || '').replace(/,/g, '').trim();
    if (/^-?\\d+(\\.\\d+)?$/.test(normalized)) {
      return { type: 'number', value: parseFloat(normalized) };
    }
    return { type: 'text', value: String(text || '').toLowerCase() };
  }

  function compareValues(a, b, kind) {
    if (kind === 'bool') {
      var map = { 'true': 1, 'false': 0 };
      var av = map[String(a || '').trim().toLowerCase()];
      var bv = map[String(b || '').trim().toLowerCase()];
      if (av === undefined && bv === undefined) return 0;
      if (av === undefined) return -1;
      if (bv === undefined) return 1;
      return av - bv;
    }

    var pa = parseComparable(a);
    var pb = parseComparable(b);
    if (pa.type === 'number' && pb.type === 'number') {
      return pa.value - pb.value;
    }
    return pa.value.localeCompare(pb.value, 'zh-Hans-CN', { numeric: true, sensitivity: 'base' });
  }

  function getCellText(row, colIndex) {
    var cell = row.cells[colIndex];
    if (!cell) return '';
    return cell.innerText || cell.textContent || '';
  }

  function bindTable(table) {
    var tableId = table.id;
    var controls = document.querySelector(".table-controls[data-table='" + tableId + "']");
    if (!controls) return;

    var searchInput = controls.querySelector('.table-search');
    var resetBtn = controls.querySelector('.table-reset');
    var clearSortBtn = controls.querySelector('.table-clear-sort');
    var meta = controls.querySelector('.table-meta');
    var tbody = table.tBodies[0];
    if (!tbody) return;

    var originalRows = Array.prototype.slice.call(tbody.rows).map(function (row) {
      return row.cloneNode(true);
    });
    var sortState = { col: null, dir: 1 };

    function allRows() {
      return Array.prototype.slice.call(tbody.rows);
    }

    function restoreRows() {
      tbody.innerHTML = '';
      originalRows.forEach(function (row) {
        tbody.appendChild(row.cloneNode(true));
      });
    }

    function updateMeta() {
      var visible = allRows().filter(function (row) {
        return row.style.display !== 'none';
      }).length;
      var total = parseInt(table.dataset.totalRows || String(allRows().length), 10);
      if (meta) {
        meta.textContent = '显示 ' + visible + ' / ' + total;
      }
    }

    function applyFilter() {
      var query = String((searchInput && searchInput.value) || '').trim().toLowerCase();
      allRows().forEach(function (row) {
        if (!query) {
          row.style.display = '';
          return;
        }
        var text = (row.innerText || row.textContent || '').toLowerCase();
        row.style.display = text.indexOf(query) >= 0 ? '' : 'none';
      });
      updateMeta();
    }

    function updateIndicators() {
      var headers = table.querySelectorAll('thead th[data-col-index]');
      headers.forEach(function (th) {
        th.classList.remove('is-sort-asc', 'is-sort-desc');
      });
      if (sortState.col === null) return;
      var current = table.querySelector("thead th[data-col-index='" + sortState.col + "']");
      if (!current) return;
      current.classList.add(sortState.dir === 1 ? 'is-sort-asc' : 'is-sort-desc');
    }

    function sortBy(col, kind) {
      var rows = allRows();
      var dir = 1;
      if (sortState.col === col) {
        dir = sortState.dir * -1;
      }
      sortState = { col: col, dir: dir };
      rows.sort(function (ra, rb) {
        return compareValues(getCellText(ra, col), getCellText(rb, col), kind) * dir;
      });
      tbody.innerHTML = '';
      rows.forEach(function (row) {
        tbody.appendChild(row);
      });
      updateIndicators();
      applyFilter();
    }

    function resetAll() {
      restoreRows();
      sortState = { col: null, dir: 1 };
      if (searchInput) searchInput.value = '';
      updateIndicators();
      applyFilter();
    }

    function clearSortOnly() {
      var query = searchInput ? searchInput.value : '';
      restoreRows();
      sortState = { col: null, dir: 1 };
      if (searchInput) searchInput.value = query;
      updateIndicators();
      applyFilter();
    }

    var headers = Array.prototype.slice.call(table.querySelectorAll('thead th[data-col-index]'));
    headers.forEach(function (th) {
      var kind = th.dataset.colKind || 'text';
      if (kind === 'json') return;
      var button = th.querySelector('.th-btn');
      if (!button) return;
      button.addEventListener('click', function () {
        var col = parseInt(th.dataset.colIndex || '0', 10);
        sortBy(col, kind);
      });
    });

    if (searchInput) {
      searchInput.addEventListener('input', applyFilter);
    }
    if (resetBtn) {
      resetBtn.addEventListener('click', resetAll);
    }
    if (clearSortBtn) {
      clearSortBtn.addEventListener('click', clearSortOnly);
    }

    applyFilter();
  }

  document.addEventListener('DOMContentLoaded', function () {
    var tables = document.querySelectorAll('table[data-total-rows]');
    tables.forEach(function (table) {
      bindTable(table);
    });
  });
})();
</script>
"""

        html = f"""
<!DOCTYPE html>
<html lang=\"zh-CN\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>{escape(page_title)}</title>
  <style>
    :root {{
      --bg: #f3f6fb;
      --panel: #ffffff;
      --line: #d9e0ea;
      --text: #1f2937;
      --muted: #6b7280;
      --brand: #2563eb;
      --brand-soft: #dbeafe;
      --good: #166534;
      --warn: #92400e;
      --bad: #991b1b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Noto Sans CJK SC", sans-serif;
      line-height: 1.5;
      color: var(--text);
      background:
        radial-gradient(circle at 10% 10%, #e0e7ff 0, rgba(224, 231, 255, 0) 35%),
        radial-gradient(circle at 90% 0%, #dbeafe 0, rgba(219, 234, 254, 0) 30%),
        var(--bg);
    }}
    .page {{ max-width: 1440px; margin: 0 auto; padding: 20px; }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 20px 22px;
      box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
    }}
    .hero h1 {{ margin: 0 0 6px 0; font-size: 28px; }}
    .hero p {{ margin: 4px 0; color: var(--muted); }}
    .quick-nav {{
      position: sticky;
      top: 8px;
      z-index: 10;
      margin-top: 14px;
      margin-bottom: 14px;
      padding: 10px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(6px);
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .quick-nav a {{
      text-decoration: none;
      color: #0f172a;
      background: #eef2ff;
      border: 1px solid #c7d2fe;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 12px;
      font-weight: 600;
    }}
    .quick-nav a:hover {{ background: #dbeafe; }}
    .section {{
      scroll-margin-top: 72px;
      margin-top: 14px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
    }}
    .section h2 {{ margin: 0 0 8px 0; }}
    .section .sub {{ margin: 0 0 12px 0; color: var(--muted); font-size: 14px; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 10px;
    }}
    .card {{
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 12px;
      background: #fbfdff;
    }}
    .card .k {{ color: var(--muted); font-size: 12px; }}
    .card .v {{ margin-top: 4px; font-size: 24px; font-weight: 700; }}
    .entry-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 10px;
    }}
    .entry {{
      border: 1px solid #bfdbfe;
      border-radius: 12px;
      background: #eff6ff;
      padding: 12px;
      color: inherit;
      text-decoration: none;
      display: block;
    }}
    .entry:hover {{ background: #dbeafe; }}
    .entry .title {{ font-weight: 700; }}
    .entry .desc {{ color: #334155; font-size: 13px; margin-top: 4px; }}
    .entry .count {{ margin-top: 6px; font-size: 12px; color: #1e3a8a; }}
    .pill {{
      display: inline-block;
      margin-right: 8px;
      margin-bottom: 8px;
      padding: 4px 10px;
      border-radius: 999px;
      background: var(--brand-soft);
      border: 1px solid #bfdbfe;
      color: #1e3a8a;
      font-size: 12px;
      font-weight: 600;
    }}
    .table-wrap {{
      margin-top: 10px;
      border: 1px solid var(--line);
      border-radius: 12px;
      overflow: auto;
      max-height: 540px;
      background: #fff;
    }}
    .table-controls {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
      margin-top: 10px;
      margin-bottom: 8px;
    }}
    .table-controls-left {{
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }}
    .table-search {{
      min-width: 260px;
      max-width: 460px;
      width: clamp(220px, 38vw, 420px);
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      padding: 7px 10px;
      font-size: 12px;
      background: #fff;
      color: #0f172a;
    }}
    .table-search:focus {{
      outline: none;
      border-color: #93c5fd;
      box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
    }}
    .table-btn {{
      border: 1px solid #cbd5e1;
      border-radius: 10px;
      background: #fff;
      color: #334155;
      font-size: 12px;
      font-weight: 600;
      padding: 7px 10px;
      cursor: pointer;
    }}
    .table-btn:hover {{ background: #f8fafc; }}
    .table-meta {{ color: var(--muted); font-size: 12px; font-weight: 600; }}
    table {{ border-collapse: collapse; width: 100%; min-width: 900px; }}
    th, td {{
      border-bottom: 1px solid #edf1f6;
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
      font-size: 12px;
    }}
    th {{
      position: sticky;
      top: 0;
      z-index: 1;
      background: #f8fafc;
      color: #334155;
      font-weight: 700;
    }}
    th.is-sort-asc, th.is-sort-desc {{ background: #e8f0ff; }}
    .th-btn {{
      appearance: none;
      border: none;
      background: none;
      width: 100%;
      text-align: left;
      color: inherit;
      font: inherit;
      font-weight: 700;
      padding: 0;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      cursor: pointer;
    }}
    .sort-indicator {{ color: #64748b; font-size: 10px; line-height: 1; }}
    th.is-sort-asc .sort-indicator::before {{ content: "▲"; }}
    th.is-sort-desc .sort-indicator::before {{ content: "▼"; }}
    tr:nth-child(even) td {{ background: #fbfdff; }}
    .muted {{ color: var(--muted); }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      padding: 2px 8px;
    }}
    .badge-true {{ background: #dcfce7; color: var(--good); border: 1px solid #86efac; }}
    .badge-false {{ background: #fee2e2; color: var(--bad); border: 1px solid #fecaca; }}
    .badge-unknown {{ background: #f1f5f9; color: #334155; border: 1px solid #cbd5e1; }}
    .cell-pre {{
      margin: 8px 0 0 0;
      padding: 8px;
      border-radius: 8px;
      border: 1px solid #dbe3ef;
      background: #f8fafc;
      white-space: pre-wrap;
      word-break: break-word;
      max-height: 260px;
      overflow: auto;
      font-size: 11px;
      line-height: 1.45;
    }}
    details > summary {{
      cursor: pointer;
      color: #1d4ed8;
      font-weight: 600;
      list-style: none;
    }}
    details > summary::-webkit-details-marker {{ display: none; }}
    .empty {{
      border: 1px dashed #cbd5e1;
      border-radius: 10px;
      padding: 12px;
      color: var(--muted);
      background: #f8fafc;
    }}
    code {{
      background: #eef2f7;
      border: 1px solid #dbe3ef;
      padding: 1px 6px;
      border-radius: 8px;
      font-size: 12px;
    }}
    a.link {{
      color: var(--brand);
      text-decoration: none;
      font-weight: 600;
    }}
    a.link:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class=\"page\">
  <header class=\"hero\" id=\"top\">
    <h1>{escape(page_title)}</h1>
    <p>输出目录：<code>{escape(str(self.output_dir))}</code></p>
    <p>生成时间：{escape(generated_at)}</p>
  </header>

  <nav class=\"quick-nav\">
    {''.join(f'<a href="#{section_id}">{escape(name)}</a>' for section_id, name in navigation_entries)}
  </nav>

  <section class=\"section\" id=\"overview\">
    <h2>概览</h2>
    <p class=\"sub\">核心指标与各维度入口。点击卡片可跳转到对应数据区。</p>
    <div class=\"cards\">
      <div class=\"card\"><div class=\"k\">总记录行（含恢复审计）</div><div class=\"v\">{len(steps)}</div></div>
      <div class=\"card\"><div class=\"k\">业务 Step 行</div><div class=\"v\">{len(runtime_steps)}</div></div>
      <div class=\"card\"><div class=\"k\">Action 行</div><div class=\"v\">{len(actions)}</div></div>
      <div class=\"card\"><div class=\"k\">Transition 行</div><div class=\"v\">{len(transitions)}</div></div>
      <div class=\"card\"><div class=\"k\">唯一状态数</div><div class=\"v\">{unique_states}</div></div>
      <div class=\"card\"><div class=\"k\">Issue 数</div><div class=\"v\">{len(issue_rows)}</div></div>
      <div class=\"card\"><div class=\"k\">out_of_app 次数</div><div class=\"v\">{out_of_app_count}</div></div>
      <div class=\"card\"><div class=\"k\">changed=True 次数</div><div class=\"v\">{changed_count}</div></div>
      <div class=\"card\"><div class=\"k\">恢复事件数</div><div class=\"v\">{recovery_event_count}</div></div>
      <div class=\"card\"><div class=\"k\">登录引导事件数</div><div class=\"v\">{len(bootstrap_rows)}</div></div>
      <div class=\"card\"><div class=\"k\">Checkpoint 数</div><div class=\"v\">{len(checkpoints_rows)}</div></div>
      <div class=\"card\"><div class=\"k\">APM</div><div class=\"v\">{benchmark_current.get("actions_per_minute", "-")}</div></div>
      <div class=\"card\"><div class=\"k\">Crash / 1k actions</div><div class=\"v\">{benchmark_current.get("crash_per_1k_actions", "-")}</div></div>
      <div class=\"card\"><div class=\"k\">Burst 占比</div><div class=\"v\">{benchmark_current.get("burst_step_ratio", "-")}</div></div>
      <div class=\"card\"><div class=\"k\">首次 Crash Step</div><div class=\"v\">{benchmark_current.get("time_to_first_crash_steps", "-")}</div></div>
      <div class=\"card\"><div class=\"k\">学习探索率</div><div class=\"v\">{benchmark_current.get("learning_exploration_rate", "-")}</div></div>
      <div class=\"card\"><div class=\"k\">学习平均奖励</div><div class=\"v\">{benchmark_current.get("learning_average_reward", "-")}</div></div>
      <div class=\"card\"><div class=\"k\">学习步占比</div><div class=\"v\">{benchmark_current.get("learning_step_ratio", "-")}</div></div>
    </div>
    <div style=\"margin-top:12px\">
      {issue_badges or "<span class='muted'>暂无 Issue 类型分布</span>"}
    </div>
    <div style=\"margin-top:4px\">
      {action_badges or "<span class='muted'>暂无动作类型分布</span>"}
    </div>
    <div style=\"margin-top:4px\">
      {bootstrap_badges or "<span class='muted'>暂无登录引导事件</span>"}
    </div>
    <div class=\"entry-grid\" style=\"margin-top:12px\">
      {self._render_entry('artifacts', '产物索引', len(artifact_rows), '查看所有产物文件并跳转')}
      {self._render_entry('issues', 'Issue 详情', len(issue_rows), '查看每条 issue 的标题、事件、日志、截图')}
      {self._render_entry('recovery', '恢复数据', len(recovery_rows), '查看恢复策略、原因、校验结果')}
      {self._render_entry('benchmark', '覆盖率KPI', 1 if coverage_benchmark else 0, '查看功能覆盖与对比评分')}
      {self._render_entry('bootstrap', '登录引导', len(bootstrap_rows), '查看登录引导触发记录与原因')}
      {self._render_entry('checkpoints', 'Checkpoint', len(checkpoints_rows), '查看检查点及其优先级')}
      {self._render_entry('steps', 'Steps', len(steps), '查看完整 step 轨迹（含 step=-1）')}
      {self._render_entry('actions', 'Actions', len(actions), '查看全部 action 参数、tags、score')}
      {self._render_entry('transitions', 'Transitions', len(transitions), '查看全部状态迁移明细')}
      {self._render_entry('utg', 'UTG', len(utg_edges_rows), '查看状态图节点和边')}
      {self._render_entry('raw', '原始 JSON', 3, '查看索引与指标 JSON 全文')}
    </div>
  </section>

  <section class=\"section\" id=\"artifacts\">
    <h2>产物索引</h2>
    <p class=\"sub\">所有核心产物文件均可直接跳转查看。</p>
    {self._render_table(
        artifact_rows,
        [
            ("artifact", "产物", "text"),
            ("description", "说明", "text"),
            ("exists", "存在", "bool"),
            ("path", "路径", "link"),
        ],
    )}
  </section>

  <section class=\"section\" id=\"issues\">
    <h2>Issue 详情（全量）</h2>
    <p class=\"sub\">Issue 来自 watchdog 事件（例如 out_of_app、permission_dialog、crash/anr 等）。</p>
    {self._render_table(
        issue_rows,
        [
            ("issue_dir", "目录", "text"),
            ("issue_type", "类型", "text"),
            ("title", "标题", "text"),
            ("event_type", "事件类型", "text"),
            ("severity", "严重级别", "text"),
            ("message", "消息", "text"),
            ("activity_name", "页面 Activity", "text"),
            ("summary_path", "Summary", "link"),
            ("logcat_path", "Logcat", "link"),
            ("screenshot_path", "Screenshot", "link"),
            ("log_excerpt", "日志摘录", "json"),
        ],
    )}
  </section>

  <section class=\"section\" id=\"recovery\">
    <h2>恢复数据（全量）</h2>
    <p class=\"sub\">包含 recovery 审计行（step=-1）和恢复校验数据。</p>
    {self._render_table(
        recovery_rows,
        [
            ("step", "Step", "text"),
            ("recovery_at_step", "触发于 Step", "text"),
            ("recovery_strategy", "策略", "text"),
            ("recovery_reason", "原因", "text"),
            ("checkpoint_id", "Checkpoint", "text"),
            ("recovery_plan_actions", "Plan 动作数", "text"),
            ("recovery_anchor_state", "Anchor State", "text"),
            ("recovery_candidate_state_ids", "Candidate States", "json"),
            ("recovery_validation_in_target_app", "在目标包内", "bool"),
            ("recovery_validation_exact_anchor_hit", "命中 Anchor", "bool"),
            ("recovery_validation_candidate_hit", "命中候选", "bool"),
        ],
    )}
    <div style=\"margin-top:12px\"></div>
    {self._render_table(
        recovery_validation_rows,
        [
            ("actual_state_id", "Actual State", "text"),
            ("expected_anchor_state", "Expected Anchor", "text"),
            ("candidate_state_ids", "Candidate States", "json"),
            ("reason", "Reason", "text"),
            ("in_target_app", "In Target App", "bool"),
            ("exact_anchor_hit", "Exact Anchor Hit", "bool"),
            ("candidate_hit", "Candidate Hit", "bool"),
        ],
    )}
  </section>

  <section class=\"section\" id=\"benchmark\">
    <h2>覆盖率 KPI（全量）</h2>
    <p class=\"sub\">A/B 评估指标：功能覆盖、登录停留、越界比例、issue 质量、恢复成功率与综合评分。</p>
    {self._render_json_block("coverage_benchmark.current_run", coverage_benchmark.get("current_run", {}))}
    {self._render_json_block("coverage_benchmark.baseline_run", coverage_benchmark.get("baseline_run", {}))}
    {self._render_json_block("coverage_benchmark.comparison", coverage_benchmark.get("comparison", {}))}
  </section>

  <section class=\"section\" id=\"bootstrap\">
    <h2>登录引导（全量）</h2>
    <p class=\"sub\">记录自动登录引导触发与尝试结果（step=-1 审计行）。</p>
    {self._render_table(
        bootstrap_rows,
        [
            ("step", "Step", "text"),
            ("bootstrap_at_step", "触发于 Step", "text"),
            ("bootstrap_status", "状态", "text"),
            ("bootstrap_reason", "原因", "text"),
        ],
    )}
  </section>

  <section class=\"section\" id=\"checkpoints\">
    <h2>Checkpoint（全量）</h2>
    <p class=\"sub\">用于恢复策略的锚点状态集合。</p>
    {self._render_table(
        checkpoints_rows,
        [
            ("checkpoint_id", "Checkpoint ID", "text"),
            ("name", "名称", "text"),
            ("priority", "优先级", "text"),
            ("state_id", "State ID", "text"),
            ("created_at_ms", "创建时间(ms)", "text"),
            ("metadata", "Metadata", "json"),
        ],
    )}
  </section>

  <section class=\"section\" id=\"steps\">
    <h2>Steps（全量）</h2>
    <p class=\"sub\">包含业务 step 行和恢复审计行（step=-1）。</p>
    {self._render_table(
        steps,
        [
            ("step", "Step", "text"),
            ("action_type", "动作类型", "text"),
            ("changed", "Changed", "bool"),
            ("out_of_app", "Out Of App", "bool"),
            ("current_state_id", "Current State", "text"),
            ("next_state_id", "Next State", "text"),
            ("action_id", "Action ID", "text"),
            ("score", "Score", "text"),
            ("stuck_score", "Stuck Score", "text"),
            ("recovery_strategy", "Recovery Strategy", "text"),
            ("recovery_reason", "Recovery Reason", "text"),
            ("bootstrap_status", "Bootstrap Status", "text"),
            ("bootstrap_reason", "Bootstrap Reason", "text"),
            ("score_detail", "Score Detail", "json"),
        ],
    )}
  </section>

  <section class=\"section\" id=\"actions\">
    <h2>Actions（全量）</h2>
    <p class=\"sub\">所有动作行，包括类型、参数、标签、评分。</p>
    {self._render_table(
        actions,
        [
            ("action_id", "Action ID", "text"),
            ("action_type", "类型", "text"),
            ("source_state_id", "Source State", "text"),
            ("target_element_id", "Target Element", "text"),
            ("score", "Score", "text"),
            ("tags", "Tags", "json"),
            ("params", "Params", "json"),
            ("score_detail", "Score Detail", "json"),
        ],
    )}
  </section>

  <section class=\"section\" id=\"transitions\">
    <h2>Transitions（全量）</h2>
    <p class=\"sub\">完整迁移明细，包括 crash/anr/out_of_app 标志。</p>
    {self._render_table(
        transitions,
        [
            ("transition_id", "Transition ID", "text"),
            ("action_id", "Action ID", "text"),
            ("from_state_id", "From State", "text"),
            ("to_state_id", "To State", "text"),
            ("success", "Success", "bool"),
            ("changed", "Changed", "bool"),
            ("out_of_app", "Out Of App", "bool"),
            ("crash", "Crash", "bool"),
            ("anr", "ANR", "bool"),
            ("duration_ms", "Duration(ms)", "text"),
            ("timestamp_ms", "Timestamp(ms)", "text"),
        ],
    )}
  </section>

  <section class=\"section\" id=\"utg\">
    <h2>UTG（全量）</h2>
    <p class=\"sub\">状态图节点与边明细。</p>
    {self._render_table(
        utg_nodes_rows,
        [
            ("state_id", "State ID", "text"),
            ("meta", "Meta", "json"),
        ],
    )}
    <div style=\"margin-top:12px\"></div>
    {self._render_table(
        utg_edges_rows,
        [
            ("edge_no", "No.", "text"),
            ("from_state_id", "From", "text"),
            ("to_state_id", "To", "text"),
            ("action_type", "Action Type", "text"),
            ("target_element_id", "Target Element", "text"),
            ("stats", "Stats", "json"),
        ],
    )}
  </section>

  <section class=\"section\" id=\"raw\">
    <h2>原始 JSON 汇总</h2>
    <p class=\"sub\">便于开发和排障时直接查看完整结构。</p>
    {self._render_json_block("lookup.summary", lookup.get("summary", {}))}
    {self._render_json_block("recovery_metrics", recovery_metrics)}
    {self._render_json_block("coverage_benchmark", coverage_benchmark)}
    {self._render_json_block("action_type_counter", dict(action_type_counter))}
    {self._render_json_block("issue_type_counter", dict(issue_counter))}
    {self._render_json_block("replay_rows (all)", replay_rows)}
  </section>

  <footer class=\"section\" style=\"padding-top:12px;padding-bottom:12px;\">
    <div class=\"muted\">End of report · generated by Smart Monkey</div>
  </footer>
  </div>
  {interaction_script}
</body>
</html>
"""
        target = self.report_dir / "index.html"
        target.write_text(html, encoding="utf-8")
        return target

    def _render_entry(self, section_id: str, title: str, count: int, desc: str) -> str:
        return (
            f"<a class='entry' href='#{escape(section_id)}'>"
            f"<div class='title'>{escape(title)}</div>"
            f"<div class='desc'>{escape(desc)}</div>"
            f"<div class='count'>数量：{count}</div>"
            "</a>"
        )

    def _render_json_block(self, title: str, payload: Any) -> str:
        content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        return (
            f"<details style='margin-bottom:10px'>"
            f"<summary>{escape(title)}</summary>"
            f"<pre class='cell-pre'>{escape(content)}</pre>"
            "</details>"
        )

    def _render_table(self, rows: list[dict[str, Any]], columns: list[tuple[str, str, str]]) -> str:
        if not rows:
            return "<div class='empty'>暂无数据</div>"
        self._table_seq += 1
        table_id = f"report-table-{self._table_seq}"
        headers = []
        for index, (_, title, kind) in enumerate(columns):
            label = escape(title)
            if kind == "json":
                headers.append(f"<th data-col-index='{index}' data-col-kind='{escape(kind)}'>{label}</th>")
                continue
            headers.append(
                "<th data-col-index='{idx}' data-col-kind='{kind}'>"
                "<button type='button' class='th-btn' aria-label='按 {title} 排序'>"
                "{title}<span class='sort-indicator'></span>"
                "</button>"
                "</th>".format(idx=index, kind=escape(kind), title=label)
            )
        header = "".join(headers)
        body_rows: list[str] = []
        for row in rows:
            cells = []
            for key, _, kind in columns:
                cells.append(f"<td>{self._render_cell(row.get(key), kind)}</td>")
            body_rows.append(f"<tr>{''.join(cells)}</tr>")
        controls_html = (
            "<div class='table-controls' data-table='{table_id}'>"
            "<div class='table-controls-left'>"
            "<input class='table-search' type='search' placeholder='在当前表内搜索（支持任意关键词）' />"
            "<button type='button' class='table-btn table-clear-sort'>清除排序</button>"
            "<button type='button' class='table-btn table-reset'>重置筛选</button>"
            "</div>"
            "<div class='table-meta'></div>"
            "</div>"
        ).format(table_id=table_id)
        table_html = (
            "<div class='table-wrap'>"
            "<table id='{table_id}' data-total-rows='{count}'>"
            "<thead><tr>{header}</tr></thead>"
            "<tbody>{body}</tbody>"
            "</table>"
            "</div>"
        ).format(table_id=table_id, count=len(rows), header=header, body="".join(body_rows))
        return controls_html + table_html

    def _render_cell(self, value: Any, kind: str) -> str:
        if kind == "bool":
            if value is True:
                return "<span class='badge badge-true'>TRUE</span>"
            if value is False:
                return "<span class='badge badge-false'>FALSE</span>"
            return "<span class='badge badge-unknown'>-</span>"
        if kind == "link":
            if not value:
                return "<span class='muted'>-</span>"
            target = escape(str(value), quote=True)
            return f"<a class='link' href='{target}' target='_blank' rel='noopener noreferrer'>打开</a>"
        if kind == "json":
            if value in (None, "", [], {}):
                return "<span class='muted'>-</span>"
            content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            return f"<details><summary>展开 JSON</summary><pre class='cell-pre'>{escape(content)}</pre></details>"

        if value is None or value == "":
            return "<span class='muted'>-</span>"
        if isinstance(value, (dict, list)):
            content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            return f"<details><summary>展开</summary><pre class='cell-pre'>{escape(content)}</pre></details>"
        text = str(value)
        if "\n" in text or len(text) > 160:
            preview = text[:160] + ("..." if len(text) > 160 else "")
            return (
                "<details>"
                f"<summary>{escape(preview)}</summary>"
                f"<pre class='cell-pre'>{escape(text)}</pre>"
                "</details>"
            )
        return escape(text)

    def _load_issues(self, issue_dirs: list[Path]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for issue_dir in issue_dirs:
            if not issue_dir.is_dir():
                continue
            summary = self._read_json(issue_dir / "summary.json")
            if not isinstance(summary, dict):
                continue
            payload = summary.get("payload", {})
            payload = payload if isinstance(payload, dict) else {}
            event = payload.get("event", {})
            event = event if isinstance(event, dict) else {}
            next_state = payload.get("next_state", {})
            next_state = next_state if isinstance(next_state, dict) else {}

            summary_path = f"../issues/{issue_dir.name}/summary.json"
            logcat = issue_dir / "logcat.txt"
            screenshot = issue_dir / "screenshot.png"
            rows.append(
                {
                    "issue_dir": issue_dir.name,
                    "issue_type": summary.get("issue_type"),
                    "title": summary.get("title"),
                    "event_type": event.get("event_type"),
                    "severity": event.get("severity"),
                    "message": event.get("message"),
                    "activity_name": next_state.get("activity_name"),
                    "summary_path": summary_path,
                    "logcat_path": f"../issues/{issue_dir.name}/logcat.txt" if logcat.exists() else "",
                    "screenshot_path": f"../issues/{issue_dir.name}/screenshot.png" if screenshot.exists() else "",
                    "log_excerpt": event.get("log_excerpt", ""),
                }
            )
        return rows

    def _count_unique_states(self, steps: list[dict[str, Any]]) -> int:
        states = set()
        for step in steps:
            if step.get("current_state_id"):
                states.add(step["current_state_id"])
            if step.get("next_state_id"):
                states.add(step["next_state_id"])
        return len(states)

    def _read_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return rows

    def _read_json(self, path: Path) -> Any:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
