"""
HTML benchmark report with embedded charts (matplotlib -> base64 PNG).
"""

from __future__ import annotations

import base64
import io
from datetime import datetime
from typing import List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

from analysis.strategyBenchmark import VariantResult, BENCHMARK_START, BENCHMARK_END
from analysis.report_styles import REPORT_TABLE_CSS, benchmark_colgroup


def _fig_to_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight", facecolor="#1a1d23")
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _style_ax(ax):
    ax.set_facecolor("#1a1d23")
    ax.tick_params(colors="#c9d1d9")
    ax.xaxis.label.set_color("#c9d1d9")
    ax.yaxis.label.set_color("#c9d1d9")
    ax.title.set_color("#f0f3f6")
    for spine in ax.spines.values():
        spine.set_color("#444")


def chart_pnl_comparison(results: List[VariantResult]) -> str:
    valid = [r for r in results if "error" not in r.summary]
    valid.sort(key=lambda r: r.summary.get("total_pnl", 0), reverse=True)
    names = [r.spec.name[:28] for r in valid]
    pnls = [r.summary.get("total_pnl", 0) for r in valid]
    colors = ["#3fb950" if p >= 0 else "#f85149" for p in pnls]

    fig, ax = plt.subplots(figsize=(12, max(5, len(names) * 0.35)))
    ax.barh(names[::-1], pnls[::-1], color=colors[::-1])
    ax.set_xlabel("Total P/L")
    ax.set_title("P/L by Strategy")
    ax.axvline(0, color="#666", linewidth=0.8)
    _style_ax(ax)
    ax.xaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    return _fig_to_b64(fig)


def chart_winrate_pf(results: List[VariantResult]) -> str:
    valid = [r for r in results if "error" not in r.summary]
    names = [r.spec.name[:20] for r in valid]
    wr = [r.summary.get("win_rate", 0) for r in valid]
    pf = [min(r.summary.get("profit_factor", 0), 5) for r in valid]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    ax1.bar(range(len(names)), wr, color="#58a6ff")
    ax1.set_xticks(range(len(names)))
    ax1.set_xticklabels(names, rotation=65, ha="right", fontsize=7, color="#c9d1d9")
    ax1.set_ylabel("Win Rate %")
    ax1.set_title("Win Rate")
    ax1.axhline(50, color="#666", linestyle="--", linewidth=0.8)
    _style_ax(ax1)

    ax2.bar(range(len(names)), pf, color="#d2a8ff")
    ax2.set_xticks(range(len(names)))
    ax2.set_xticklabels(names, rotation=65, ha="right", fontsize=7, color="#c9d1d9")
    ax2.set_ylabel("Profit Factor (cap 5)")
    ax2.set_title("Profit Factor")
    ax2.axhline(1, color="#666", linestyle="--", linewidth=0.8)
    _style_ax(ax2)
    fig.tight_layout()
    return _fig_to_b64(fig)


def chart_equity_curves(results: List[VariantResult], top_n: int = 6) -> str:
    valid = [r for r in results if r.equity_curve and "error" not in r.summary]
    valid.sort(key=lambda r: r.summary.get("total_pnl", 0), reverse=True)
    top = valid[:top_n]

    fig, ax = plt.subplots(figsize=(12, 6))
    palette = ["#58a6ff", "#3fb950", "#f0883e", "#d2a8ff", "#f85149", "#79c0ff"]
    for i, r in enumerate(top):
        if not r.equity_curve:
            continue
        xs = [p[0] for p in r.equity_curve]
        ys = [p[1] for p in r.equity_curve]
        ax.plot(xs, ys, label=r.spec.name[:24], color=palette[i % len(palette)], linewidth=1.8)

    ax.set_title(f"Equity Curves — Top {top_n}")
    ax.set_ylabel("Balance")
    ax.legend(fontsize=8, facecolor="#1a1d23", edgecolor="#444", labelcolor="#c9d1d9")
    _style_ax(ax)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    fig.autofmt_xdate()
    return _fig_to_b64(fig)


def chart_outcome_stacked(results: List[VariantResult]) -> str:
    """Outcome categories for Original vs No-Trailing vs best."""
    picks = []
    for vid in ("g1_ref_original", "g1_ref_no_trailing", "g1_ref_struct_pullback"):
        for r in results:
            if r.spec.variant_id == vid:
                picks.append(r)
    valid = [r for r in results if "error" not in r.summary]
    if valid:
        best = max(valid, key=lambda r: r.summary.get("total_pnl", 0))
        if best not in picks:
            picks.append(best)

    cats = ["DIRECT_TP", "DIRECT_SL", "SL_TP_REACHED_AFTER", "TP_EXCEEDED", "TP_NEAR_MISS", "SL_DESPITE_TP_DURING"]
    cat_colors = ["#3fb950", "#f85149", "#f0883e", "#58a6ff", "#d2a8ff", "#ff7b72"]

    fig, ax = plt.subplots(figsize=(10, 4))
    x = range(len(picks))
    bottoms = [0] * len(picks)
    for cat, color in zip(cats, cat_colors):
        vals = [r.summary.get("categories", {}).get(cat, 0) for r in picks]
        if sum(vals) == 0:
            continue
        ax.bar(x, vals, bottom=bottoms, label=cat, color=color)
        bottoms = [b + v for b, v in zip(bottoms, vals)]

    ax.set_xticks(list(x))
    ax.set_xticklabels([r.spec.name[:22] for r in picks], rotation=15, ha="right", color="#c9d1d9")
    ax.set_ylabel("Trade Count")
    ax.set_title("Outcome Categories")
    ax.legend(fontsize=7, facecolor="#1a1d23", edgecolor="#444", labelcolor="#c9d1d9")
    _style_ax(ax)
    return _fig_to_b64(fig)


def chart_group_comparison(results: List[VariantResult]) -> str:
    groups = {}
    for r in results:
        if "error" in r.summary:
            continue
        g = r.spec.group
        groups.setdefault(g, []).append(r.summary.get("total_pnl", 0))

    labels = list(groups.keys())
    avgs = [sum(v) / len(v) if v else 0 for v in groups.values()]

    fig, ax = plt.subplots(figsize=(8, 4))
    colors = ["#58a6ff", "#3fb950", "#f0883e", "#d2a8ff"]
    ax.bar(labels, avgs, color=colors[: len(labels)])
    ax.set_title("Average P/L by Group")
    ax.set_ylabel("P/L (average)")
    ax.axhline(0, color="#666", linewidth=0.8)
    _style_ax(ax)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, _: f"{x:,.0f}"))
    return _fig_to_b64(fig)


def _table_rows(results: List[VariantResult]) -> str:
    rows = []
    sorted_r = sorted(
        results,
        key=lambda r: r.summary.get("total_pnl", 0) if "error" not in r.summary else -1e18,
        reverse=True,
    )
    for i, r in enumerate(sorted_r, 1):
        s = r.summary
        if "error" in s:
            rows.append(f"<tr><td>{i}</td><td>{r.spec.group}</td><td>{r.spec.name}</td>"
                        f"<td colspan='11'>{s['error']}</td></tr>")
            continue
        dd = s.get("max_dd_pct", 0)
        day_dd = s.get("max_daily_loss_pct", 0)
        if s.get("prop_bonus_ok"):
            prop = "<span style='color:#3fb950'>BONUS</span>"
        elif s.get("prop_ftmo_ok"):
            prop = "<span style='color:#58a6ff'>FTMO ok</span>"
        else:
            prop = "<span style='color:#f85149'>no</span>"
        rows.append(
            f"<tr>"
            f"<td>{i}</td><td>{r.spec.group}</td><td>{r.spec.name}</td>"
            f"<td class='num'>{s.get('trades', 0)}</td>"
            f"<td class='num {'pos' if s.get('win_rate', 0) >= 50 else 'neg'}'>{s.get('win_rate', 0):.1f}%</td>"
            f"<td class='num'>{s.get('profit_factor', 0):.2f}</td>"
            f"<td class='num {'pos' if s.get('total_pnl', 0) >= 0 else 'neg'}'>{s.get('total_pnl', 0):,.0f}</td>"
            f"<td class='num {'pos' if s.get('return_pct', 0) >= 0 else 'neg'}'>{s.get('return_pct', 0):.1f}%</td>"
            f"<td class='num {'neg' if dd >= 10 else ''}'>{dd:.1f}%</td>"
            f"<td class='num {'neg' if day_dd >= 2 else ''}'>{day_dd:.1f}%</td>"
            f"<td class='num'>{prop}</td>"
            f"<td class='num'>{s.get('same_day_close_pct', 0):.0f}%</td>"
            f"<td class='num'>{s.get('avg_win_r', 0):.2f} / {s.get('avg_loss_r', 0):.2f}</td>"
            f"</tr>"
        )
    return "\n".join(rows)


def generate_html_report(results: List[VariantResult], output_path: str) -> str:
    valid = [r for r in results if "error" not in r.summary]
    best = max(valid, key=lambda r: r.summary.get("total_pnl", 0)) if valid else None
    orig = next((r for r in results if r.spec.variant_id == "g1_ref_original"), None)
    notrail = next((r for r in results if r.spec.variant_id == "g1_ref_no_trailing"), None)

    img_pnl = chart_pnl_comparison(results)
    img_wr = chart_winrate_pf(results)
    img_eq = chart_equity_curves(results)
    img_out = chart_outcome_stacked(results)
    img_grp = chart_group_comparison(results)

    baseline_note = ""
    if orig and notrail and "error" not in orig.summary and "error" not in notrail.summary:
        diff = notrail.summary["total_pnl"] - orig.summary["total_pnl"]
        better = "without trailing" if diff > 0 else "with trailing"
        baseline_note = (
            f"<p class='highlight'>Baseline comparison: fixed SL/TP P/L "
            f"{notrail.summary['total_pnl']:,.0f} vs original {orig.summary['total_pnl']:,.0f} "
            f"({diff:+,.0f}) &mdash; <strong>{better}</strong> performs better.</p>"
        )

    winner_note = ""
    if best:
        winner_note = f"<p class='winner'>Best strategy (P/L): <strong>{best.spec.name}</strong> "
        winner_note += f"(P/L {best.summary['total_pnl']:,.0f}, Return {best.summary.get('return_pct', 0):.1f}%, "
        winner_note += f"PF {best.summary['profit_factor']:.2f}, WR {best.summary['win_rate']:.1f}%, "
        winner_note += f"max DD {best.summary.get('max_dd_pct', 0):.1f}%, day DD {best.summary.get('max_daily_loss_pct', 0):.1f}%)</p>"

    prop_note = ""
    prop_cands = [
        r for r in valid
        if r.summary.get("prop_bonus_ok") or r.summary.get("prop_ftmo_ok")
    ]
    if prop_cands:
        prop_cands.sort(key=lambda r: r.summary.get("return_pct", 0), reverse=True)
        items = []
        for r in prop_cands:
            tag = "BONUS (<2% Tag, <10% DD)" if r.summary.get("prop_bonus_ok") else "FTMO ok (<5% Tag, <10%)"
            items.append(
                f"<li><strong>{r.spec.name}</strong>: Return {r.summary.get('return_pct', 0):.1f}%, "
                f"max DD {r.summary.get('max_dd_pct', 0):.1f}%, Tag-DD {r.summary.get('max_daily_loss_pct', 0):.1f}% &mdash; {tag}</li>"
            )
        prop_note = (
            "<p class='highlight'>Prop-suitable candidates (realised DD; intraday floating may be slightly higher):</p>"
            f"<ul class='legend'>{''.join(items)}</ul>"
        )
    else:
        prop_note = "<p class='highlight'>No candidate currently meets prop drawdown limits (realised).</p>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>HydraTrade Strategy Benchmark</title>
<style>
  :root {{ --bg:#0d1117; --card:#161b22; --text:#c9d1d9; --accent:#2dd4bf; --green:#3fb950; --red:#f85149; }}
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text);
          margin: 0; padding: 24px; line-height: 1.5; }}
  h1 {{ color: #f0f3f6; border-bottom: 2px solid var(--accent); padding-bottom: 8px; }}
  h2 {{ color: var(--accent); margin-top: 32px; }}
  .meta {{ color: #8b949e; margin-bottom: 24px; }}
  .card {{ background: var(--card); border-radius: 8px; padding: 16px; margin: 16px 0;
           border: 1px solid #30363d; }}
  img {{ max-width: 100%; border-radius: 6px; }}
  {REPORT_TABLE_CSS}
  .pos {{ color: var(--green); }}
  .neg {{ color: var(--red); }}
  .highlight {{ background: #1c2128; padding: 12px; border-left: 4px solid var(--accent); }}
  .winner {{ background: #122117; padding: 12px; border-left: 4px solid var(--green); }}
  .legend {{ font-size: 12px; color: #8b949e; }}
</style>
</head>
<body>
<h1>HydraTrade &mdash; Strategy Benchmark</h1>
<p class="meta">Period: {BENCHMARK_START.date()} to {BENCHMARK_END.date()} (~3 months) |
Symbol: XAUUSD | {len(results)} strategies | Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

{winner_note}
{baseline_note}
{prop_note}

<h2>P/L Overview</h2>
<div class="card"><img src="data:image/png;base64,{img_pnl}" alt="P/L comparison"/></div>

<h2>Win Rate &amp; Profit Factor</h2>
<div class="card"><img src="data:image/png;base64,{img_wr}" alt="WR and PF"/></div>

<h2>Equity Curves (Top 6)</h2>
<div class="card"><img src="data:image/png;base64,{img_eq}" alt="Equity"/></div>

<h2>Outcome Categories</h2>
<div class="card"><img src="data:image/png;base64,{img_out}" alt="Outcomes"/></div>
<p class="legend">SL_TP_REACHED_AFTER = stopped out, then TP was reached (trailing issue)</p>

<h2>Group Comparison</h2>
<div class="card"><img src="data:image/png;base64,{img_grp}" alt="Groups"/></div>

<h2>All Strategies (sorted by P/L)</h2>
<div class="card table-wrap">
<table class="report-table">
{benchmark_colgroup()}
<thead><tr>
  <th class="num">#</th><th>Group</th><th class="variant-col">Strategy</th><th class="num">Trades</th>
  <th class="num">WR</th><th class="num">PF</th><th class="num">P/L</th><th class="num">Return</th><th class="num">Max DD</th><th class="num">Day DD</th><th class="num">Prop</th><th class="num">Intraday</th><th class="num">Avg Win/Loss R</th>
</tr></thead>
<tbody>
{_table_rows(results)}
</tbody>
</table>
</div>

<h2>Methodology</h2>
<div class="card legend">
<p>Example strategies shipped with HydraTrade for educational purposes — not production recommendations.</p>
<p>All rules are time- and price-based (EMA, ATR, SuperTrend, Volume Profile).</p>
</div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
