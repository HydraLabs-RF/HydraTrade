"""
Multi-period benchmark: same variants across multiple separate time windows.

Goal: find strategies that are NOT overfit to a single market slice.
Each period starts with fresh capital. Per variant, a consistency view is
produced (return/DD/WR per period + average, worst period, prop suitability
in every period).

Additionally, TP research metrics are computed:
  * capture_ratio: how much of the maximum available move (MFE) the exit
    actually collects -> THE key metric for TP/trailing quality
  * max_consec_losses: longest losing streak (game-over risk with prop firms)
  * monthly_returns / payout_months: how often ~10%/month is achieved
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from analysis.report_styles import REPORT_TABLE_CSS, multi_period_colgroup
from analysis.strategyBenchmark import VariantResult, run_full_benchmark
from strategie.registry import VariantSpec, get_variant


@dataclass
class PeriodSpec:
    label: str
    start: datetime
    end: datetime


# Three separate ~3-month windows (M5 data goes back to ~2025-09).
DEFAULT_PERIODS: List[PeriodSpec] = [
    PeriodSpec("P1_Herbst25", datetime(2025, 9, 15, tzinfo=timezone.utc), datetime(2025, 12, 15, tzinfo=timezone.utc)),
    PeriodSpec("P2_Winter", datetime(2025, 12, 15, tzinfo=timezone.utc), datetime(2026, 3, 8, tzinfo=timezone.utc)),
    PeriodSpec("P3_Fruehjahr", datetime(2026, 3, 8, tzinfo=timezone.utc), datetime(2026, 6, 8, tzinfo=timezone.utc)),
]

START_BALANCE = 100_000.0


def extended_stats(result: VariantResult, start_balance: float = START_BALANCE) -> dict:
    """TP research and risk metrics from a single period run."""
    closed = sorted(
        [t.trade for t in result.report.trades if t.trade.close_time and t.trade.pnl is not None],
        key=lambda t: t.close_time,
    )
    analyses = result.report.trades

    # Capture ratio: realised R / maximum achievable R (trades with real movement only)
    capture_samples = [
        max(0.0, a.reward_r) / a.mfe_r
        for a in analyses
        if a.mfe_r >= 1.0
    ]
    capture_ratio = sum(capture_samples) / len(capture_samples) if capture_samples else 0.0

    # Losing streaks
    max_consec_losses = 0
    cur = 0
    for t in closed:
        if t.pnl <= 0:
            cur += 1
            max_consec_losses = max(max_consec_losses, cur)
        else:
            cur = 0

    # Monthly returns (relative to period-start capital, not compounded per month)
    monthly: Dict[str, float] = {}
    balance = start_balance
    month_start_balance: Dict[str, float] = {}
    for t in closed:
        key = t.close_time.strftime("%Y-%m")
        if key not in month_start_balance:
            month_start_balance[key] = balance
        balance += t.pnl
        monthly[key] = (balance - month_start_balance[key]) / month_start_balance[key] * 100

    payout_months = sum(1 for v in monthly.values() if v >= 10.0)

    avg_r = 0.0
    rs = [a.reward_r for a in analyses]
    if rs:
        avg_r = sum(rs) / len(rs)

    return {
        "capture_ratio": capture_ratio,
        "max_consec_losses": max_consec_losses,
        "monthly_returns": monthly,
        "payout_months": payout_months,
        "months": len(monthly),
        "avg_r": avg_r,
    }


@dataclass
class MultiPeriodResult:
    spec: VariantSpec
    # label -> (summary + extended stats) | None on error
    periods: Dict[str, Optional[dict]] = field(default_factory=dict)
    raw: Dict[str, VariantResult] = field(default_factory=dict)

    def valid_summaries(self) -> List[dict]:
        return [s for s in self.periods.values() if s and "error" not in s]

    def aggregate(self) -> dict:
        sums = self.valid_summaries()
        if not sums:
            return {"error": "no valid periods"}
        rets = [s.get("return_pct", 0.0) for s in sums]
        dds = [s.get("max_dd_pct", 0.0) for s in sums]
        day_dds = [s.get("max_daily_loss_pct", 0.0) for s in sums]
        n = len(rets)
        mean_ret = sum(rets) / n
        var = sum((r - mean_ret) ** 2 for r in rets) / n
        std_ret = var ** 0.5
        return {
            "periods_ok": n,
            "mean_return_pct": mean_ret,
            "min_return_pct": min(rets),
            "std_return_pct": std_ret,
            "consistency": mean_ret - std_ret,
            "worst_dd_pct": max(dds),
            "worst_day_dd_pct": max(day_dds),
            "all_profitable": all(r > 0 for r in rets),
            "all_prop_ok": all(s.get("prop_ftmo_ok") for s in sums),
            "all_bonus_ok": all(s.get("prop_bonus_ok") for s in sums),
            "total_trades": sum(s.get("trades", 0) for s in sums),
            "mean_capture": sum(s.get("capture_ratio", 0.0) for s in sums) / n,
            "worst_consec_losses": max(s.get("max_consec_losses", 0) for s in sums),
            "payout_months": sum(s.get("payout_months", 0) for s in sums),
            "months": sum(s.get("months", 0) for s in sums),
        }


def run_multi_period(
    variants: List[VariantSpec],
    periods: List[PeriodSpec] = None,
    on_period_done=None,
) -> List[MultiPeriodResult]:
    periods = periods or DEFAULT_PERIODS
    results: Dict[str, MultiPeriodResult] = {
        v.variant_id: MultiPeriodResult(spec=v) for v in variants
    }

    for period in periods:
        print(f"\n=== Period {period.label}: {period.start.date()} -> {period.end.date()} ===")
        period_results = run_full_benchmark(start=period.start, end=period.end, variants=variants)
        for r in period_results:
            mp = results[r.spec.variant_id]
            mp.raw[period.label] = r
            if "error" in r.summary:
                mp.periods[period.label] = r.summary
            else:
                s = dict(r.summary)
                s.update(extended_stats(r))
                mp.periods[period.label] = s
        if on_period_done:
            on_period_done(period, period_results)

    return list(results.values())


def format_multi_period_text(results: List[MultiPeriodResult], periods: List[PeriodSpec]) -> str:
    lines = [
        "=" * 110,
        "MULTI-PERIOD BENCHMARK (consistency check, fresh capital per period)",
        "=" * 110,
    ]
    aggs = [(r, r.aggregate()) for r in results]
    aggs.sort(key=lambda x: x[1].get("consistency", -1e9), reverse=True)

    for r, agg in aggs:
        lines.append("")
        lines.append(f"--- {r.spec.name}  [{r.spec.variant_id}] ---")
        if "error" in agg:
            lines.append(f"  ERROR: {agg['error']}")
            continue
        for p in periods:
            s = r.periods.get(p.label)
            if not s or "error" in s:
                lines.append(f"  {p.label:<14} -> {s.get('error') if s else 'no result'}")
                continue
            lines.append(
                f"  {p.label:<14} Ret {s.get('return_pct', 0):+6.1f}% | WR {s.get('win_rate', 0):4.1f}% | "
                f"PF {min(s.get('profit_factor', 0), 99):5.2f} | Trades {s.get('trades', 0):3d} | "
                f"maxDD {s.get('max_dd_pct', 0):4.1f}% | TagDD {s.get('max_daily_loss_pct', 0):4.1f}% | "
                f"Capture {s.get('capture_ratio', 0):4.2f} | LossStreak {s.get('max_consec_losses', 0)}"
            )
        lines.append(
            f"  AGGREGATE      Mean {agg['mean_return_pct']:+6.1f}% | Min {agg['min_return_pct']:+6.1f}% | "
            f"Consistency {agg['consistency']:+6.1f} | worstDD {agg['worst_dd_pct']:4.1f}% | "
            f"all profitable: {'YES' if agg['all_profitable'] else 'NO'} | "
            f"prop ok everywhere: {'YES' if agg['all_prop_ok'] else 'NO'} | "
            f"payout months {agg['payout_months']}/{agg['months']}"
        )
    return "\n".join(lines)


def generate_multi_period_html(
    results: List[MultiPeriodResult],
    periods: List[PeriodSpec],
    output_path: str,
    title: str = "Multi-Period Benchmark",
) -> str:
    aggs = [(r, r.aggregate()) for r in results]
    aggs.sort(key=lambda x: x[1].get("consistency", -1e9), reverse=True)
    n_periods = len(periods)
    agg_cols = 8
    total_data_cols = 1 + n_periods * 4 + agg_cols

    period_headers = "".join(
        f"<th colspan='4'>{p.label}<br/><span class='small'>{p.start.date()} – {p.end.date()}</span></th>"
        for p in periods
    )
    sub_headers = "".join("<th class='num'>Ret</th><th class='num'>DD</th><th class='num'>WR</th><th class='num'>Tr</th>" for _ in periods)

    rows = []
    for r, agg in aggs:
        if "error" in agg:
            rows.append(
                f"<tr><td class='variant-col'><strong>{r.spec.name}</strong></td>"
                f"<td colspan='{total_data_cols - 1}' class='neg'>{agg['error']}</td></tr>"
            )
            continue
        cells = ""
        for p in periods:
            s = r.periods.get(p.label) or {}
            if "error" in s or not s:
                cells += f"<td colspan='4' class='neg num'>{s.get('error', '–')}</td>"
                continue
            ret = s.get("return_pct", 0)
            cells += (
                f"<td class='num {'pos' if ret >= 0 else 'neg'}'>{ret:+.1f}%</td>"
                f"<td class='num {'neg' if s.get('max_dd_pct', 0) >= 10 else ''}'>{s.get('max_dd_pct', 0):.1f}%</td>"
                f"<td class='num'>{s.get('win_rate', 0):.0f}%</td>"
                f"<td class='num'>{s.get('trades', 0)}</td>"
            )
        konsistenz = agg["consistency"]
        rows.append(
            f"<tr><td class='variant-col'><strong>{r.spec.name}</strong>"
            f"<br/><span class='small'>{r.spec.variant_id} ({r.spec.group})</span></td>"
            f"{cells}"
            f"<td class='num {'pos' if agg['mean_return_pct'] >= 0 else 'neg'}'>{agg['mean_return_pct']:+.1f}%</td>"
            f"<td class='num {'pos' if agg['min_return_pct'] >= 0 else 'neg'}'>{agg['min_return_pct']:+.1f}%</td>"
            f"<td class='num'>{konsistenz:+.1f}</td>"
            f"<td class='num'>{agg['worst_dd_pct']:.1f}%</td>"
            f"<td class='num'>{agg['mean_capture']:.2f}</td>"
            f"<td class='num'>{agg['worst_consec_losses']}</td>"
            f"<td class='num'>{agg['payout_months']}/{agg['months']}</td>"
            f"<td class='num'>{'<span class=pos>YES</span>' if agg['all_prop_ok'] else '<span class=neg>NO</span>'}</td></tr>"
        )

    colgroup = multi_period_colgroup(n_periods)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
  body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; margin: 0; }}
  h1 {{ color: #f0f3f6; border-bottom: 2px solid #2dd4bf; padding-bottom: 8px; }}
  {REPORT_TABLE_CSS}
  .pos {{ color: #3fb950; }}
  .neg {{ color: #f85149; }}
  .small {{ color: #8b949e; font-size: 10px; }}
  .card {{ background: #161b22; border-radius: 8px; padding: 16px; margin: 16px 0; border: 1px solid #30363d; }}
  .legend {{ font-size: 12px; color: #8b949e; line-height: 1.5; }}
</style>
</head>
<body>
<h1>{title}</h1>
<p class="legend">Each period starts with fresh capital ({START_BALANCE:,.0f}).
Consistency = mean return minus standard deviation across periods (penalises single-window luck).
Capture = share of maximum favourable excursion (MFE) collected at exit.
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
<div class="card table-wrap">
<table class="report-table">
{colgroup}
<thead>
<tr><th rowspan="2" class="variant-col">Strategy</th>{period_headers}
<th colspan="{agg_cols}">Aggregate</th></tr>
<tr>{sub_headers}<th class="num">Mean Ret</th><th class="num">Min Ret</th><th class="num">Consist.</th><th class="num">Worst DD</th><th class="num">Capture</th><th class="num">Loss Streak</th><th class="num">Payout Mo.</th><th class="num">Prop OK</th></tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>
<h2>Period reports</h2>
<div class="card">
  <p class="legend">This page is the cross-period summary table only. Each period report has the
  full per-window benchmark (metrics and per-strategy breakdown).</p>
  <ul>
{"".join(f'    <li><a href="period_{p.label}.html">{p.label}</a> — {p.start.date()} – {p.end.date()}</li>\n' for p in periods)}
  </ul>
</div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
