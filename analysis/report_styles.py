"""Shared CSS for HydraTrade HTML reports — fixed table layout for aligned columns."""

REPORT_TABLE_CSS = """
  .table-wrap { overflow-x: auto; -webkit-overflow-scrolling: touch; }
  table.report-table {
    width: 100%;
    min-width: 960px;
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 12px;
  }
  table.report-table th,
  table.report-table td {
    padding: 6px 8px;
    border-bottom: 1px solid #30363d;
    text-align: left;
    overflow: hidden;
    text-overflow: ellipsis;
    vertical-align: middle;
    white-space: nowrap;
  }
  table.report-table td.variant-col,
  table.report-table th.variant-col {
    white-space: normal;
    word-break: break-word;
  }
  table.report-table th { background: #21262d; color: #f0f3f6; }
  table.report-table tr:hover { background: #1c2128; }
  table.report-table .num { text-align: right; font-variant-numeric: tabular-nums; }
"""


def _metric_width_pct(metric_count: int, variant_pct: float = 15.0) -> str:
    """Equal width for each metric column; variant column keeps fixed share."""
    if metric_count <= 0:
        return "85%"
    return f"{(100.0 - variant_pct) / metric_count:.3f}%"


def multi_period_colgroup(period_count: int) -> str:
    """colgroup: 1 variant + 4 cols per period + 8 aggregate columns."""
    metric_count = period_count * 4 + 8
    mw = _metric_width_pct(metric_count)
    cols = ['<col style="width:15%"/>']
    cols.extend([f'<col style="width:{mw}"/>' for _ in range(metric_count)])
    return f"<colgroup>{''.join(cols)}</colgroup>"


def benchmark_colgroup() -> str:
    """colgroup for the 13-column variant benchmark table."""
    mw = _metric_width_pct(10, variant_pct=22.0)
    return (
        "<colgroup>"
        f'<col style="width:{mw}"/>'
        f'<col style="width:{mw}"/>'
        '<col style="width:22%"/>'
        + "".join([f'<col style="width:{mw}"/>' for _ in range(10)])
        + "</colgroup>"
    )
