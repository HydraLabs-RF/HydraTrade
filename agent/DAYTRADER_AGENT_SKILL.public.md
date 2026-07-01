# Day-Trader Agent — Skill (HydraTrade)

> **Packaging:** `agent/plugin/install.py` → `.cursor/skills/hydratrade-daytrader/` (Cursor today)
> **Part 1** = general day-trading knowledge (shared, framework-safe).
> **Part 2** = your strategies & research — template below; customize locally (`agent/private/README.md`).

> **Purpose:** The AI should **think like an experienced day trader** — read markets, build
> hypotheses, test honestly, understand risk — and use the HydraTrade framework as a tool,
> not the other way around.

---
---

# Part 1 — General day-trading knowledge (framework-safe, shareable)

## 1. Mindset & working rules

### 1.1 What a day trader actually does
You trade **repeatability under uncertainty**, not “the truth about the market”.
Every idea is a hypothesis: *Under which conditions does this behaviour deliver a statistical
edge?* The edge lives in **regime × setup × execution × risk** — not in a single indicator.

### 1.2 Non-negotiable rules
1. **Reports over opinions** — every test idea ends in HTML/TXT/JSON under `reports/runs/`.
   Console output alone is not enough. The user must be able to open and compare results.
2. **One lever per iteration** — do not change entry, SL, filter, and sizing at the same time.
   Otherwise you cannot tell what worked.
3. **Regime first** — before fine-tuning, ask: *In which market type should this work?*
   Optimising a trend setup in chop is wasted effort.
4. **No lookahead** — signals only from data that was **closed** at signal time
   (closed candles, confirmed pivots). Visually “pretty” lines with repainting are poison.
5. **One indicator = one file** in `strategie/tools/` (style of `ATR.py`). No monolithic files,
   no 200-line inline math inside strategies.
6. **Neutral web research** — do not bias search terms with your own hypothesis.
7. **Complexity is allowed** — but every layer must be testable in isolation (own grade,
   own variant, own report).

### 1.3 Typical research cycle
```
Idea → minimal implementation → sanity (trades plausible?)
     → one window → bad? discard or check regime
     → multi-period (3+ windows) → floor & consistency
     → FTMO/prop check → live only with explicit user OK
```
Do not skip: **sanity** catches sim bugs; **multi-period** catches overfitting.

### 1.4 When to stop
- Floor negative across several windows despite a good mean → likely overfit or regime mismatch.
- Edge works in only one window → not generalisable without a new hypothesis.
- High win rate but miserable capture ratio → you take profits too early or TP is unrealistic.
- Many trades with tiny SL → spread/slippage eat the edge live.

---

## 2. Market mechanics (without buzzwords)

### 2.1 Liquidity & volatility
- **Liquidity** = tight spreads, fast fills, fewer stop hunts through a thin book.
  Highest activity: **London–New York overlap** (roughly 13:00–17:00 UTC).
- **Volatility** = size of moves. Trend strategies need *enough* vol to run;
  fade strategies need *bounded* vol and clear boundaries.
- **ATR** is your universal measure for “how far can SL/TP be?” — not fixed points.

### 2.2 Trend vs. range vs. whipsaw (intuitive)
| Market feel | Price behaviour | Typical strategies | Typical mistakes |
|-------------|-----------------|--------------------|------------------|
| **Trend** | HH/HL or LH/LL, pullbacks get bought/sold | Trend follow, filtered breakout | Fading against trend |
| **Flat range** | Oscillation around mean, mean reversion | BB/VWAP/CPR fade, stoch extremes | Breakout without squeeze |
| **Whipsaw** | Many false breaks, no clean revert | *trade less* or quick exits | Fade at every band |

**ADX** separates trend from non-trend. **Variance ratio** separates flat (reverting) from
whipsaw (overshoot). Together → `marketPhase.py`.

### 2.3 Structure: horizontal vs. diagonal levels
- **Horizontal:** pivots, CPR, value area, Donchian — “price reacts here”.
- **Diagonal:** trendlines, channels — rate of change; good for trend↔range transitions,
  but **only with confirmed pivots** (non-repainting).

### 2.4 Spread, slippage, costs
Backtests without realistic costs overestimate fade and scalping edges. Hold strategies
need **swap/rollover** (framework: `rolloverTool.py`). Before live: check sanity trades for
unrealistic exits.

---

## 3. Strategy building blocks (the real levers)

### 3.1 Entry types — when to use which?
| Type | Mechanics | Good for | Bad for |
|------|-----------|----------|---------|
| **Market** | Immediate fill | Momentum, “now or never” | Fade at exact level |
| **Limit** | Better price, waits | Pullback, fade at support | Breakout (misses move) |
| **Stop** | Worse price, waits | Breakout above/below level | Mean reversion |

**Rule:** fade = almost always **limit** at the level. Breakout = **stop** above/below boundary.
Market only when delay destroys the edge.

### 3.2 Stop-loss — logic before points
1. **Structure SL** — behind the level that invalidates the idea (below swing low, above
   range high). Market-logical, but variable.
2. **ATR SL** — N × ATR; adapts to vol. Often start at 1.5–2.5 × ATR for intraday.
3. **Fixed RR** — only when there is no clear structure target; otherwise artificial.

**Filter:** SL too tight (< 0.5× ATR) → noise; too wide (> 4× ATR) → poor RR and small size.

### 3.3 Take-profit & capture
- **Structure TP** at next HVN, pivot, opposite value edge.
- **RR TP** (e.g. 1:2) as fallback.
- **Capture ratio** (framework metric): how much of the maximum possible move (MFE) you
  actually realise. Low capture → TP too early or trailing too tight.

### 3.4 Risk & sizing
- Risk = **% of equity per trade**; lot size from SL distance (`RiskManager.get_lot_size`).
- **Grades A/B/C** = separate risk buckets and logic — allows parallel uncorrelated edges.
- **Prop:** worst **daily** DD is often the hard limit (~5%), not only total DD (~10%).
- **Myth:** “no new trades after −X% daily loss” rarely stops the real daily DD if open
  trades keep running → lower **per-trade risk** and exposure.

### 3.5 Pending management (`adjust_pending`) — underrated
- **Stale cancel:** an order from session X must not fill in session Y. Main cause of
  “ghost trades” and DD spikes in backtests.
- **Re-price:** move limit to new level when structure has shifted.
- **Dedup:** max. one pending per direction/session/setup.
- **Expiry:** time-based or end of session.

### 3.6 Active management (`manage_trailing`)
- **Break-even** from X×R — protects against winner→loser; too early kills capture.
- **ATR/Chandelier trailing** — for trend runners.
- **Partial close** — scaling; only when rules are clear, otherwise overfit.
- **Time exit** — “idea did not work” after N bars.
- **Rollover/weekend** — close before swap time when holding costs matter.

### 3.7 Regime gating & orchestration
- **Gate:** trade only when ADX/phase/EMA filter matches.
- **Parallel:** several edges at once, own grades — diversification.
- **Handoff:** one edge active until signal ends, then another — less overlap.
- **Hard switch:** only one edge — often worse than parallel (see Part 2 for your own lessons).

---

## 4. Sessions, time & broker

### 4.1 Sessions (forex/metals/indices)
- **Asia** — often range-like, less follow-through for EU strategies.
- **London** — trend starts, breakouts more common.
- **New York** — high vol, news risk; overlap with London is strongest.
- **Crypto** — 24/7; session filters often unnecessary.
- **Daily/swing** — intraday session filters optional.

### 4.2 Broker time ≠ UTC
Broker charts often run UTC+2/+3 with DST. Sessions must be computed in a defined broker or
UTC logic — and **consistently** in sim and live.

### 4.3 Detect offset & DST (do not guess)
- **Weekend tick** of the main symbol often returns a **stale** offset.
- **Better:** derive offset first from a **24/7 symbol** (BTC/ETH).
- **DST:** check time jumps in M5 data of a 24/7 symbol against `zoneinfo`.
- Wrong offset → session filter shifts → backtest not reproducible.

### 4.4 Dynamic data windows
Double lookback until enough **real** bars exist (holidays, market pauses). Prefer loading
too much history over too little.

---

## 5. Indicator encyclopedia

*Code: `strategie/tools/`. An indicator measures — the edge comes from context + combination.*

### 5.1 Direction / trend
**EMA** (`ema.py`)
- *What:* exponentially weighted average — reacts faster than SMA.
- *Use:* trend direction (price above/below EMA), crosses (fast/slow), macro gate
  (long only above D1 EMA50).
- *Pitfalls:* constant crosses in chop; worthless without ADX/phase filter.
- *Typical:* D1/H4 for bias, H1/M15 for timing.

**SuperTrend** (`supertrend.py`)
- *What:* ATR bands around median, flip on break.
- *Use:* clear direction + trailing line.
- *Pitfalls:* whippy in range — use as filter, not as the only signal.

### 5.2 Trend strength (direction-neutral)
**ADX** (`adx.py`)
- *What:* strength of trend (not direction); +DI/−DI for direction.
- *Use:* high ADX → allow trend follow; low → consider range/fade.
- *Pitfalls:* can be late in strong trend; threshold is symbol-dependent — test it.

**Efficiency ratio** (`efficiencyRatio.py`)
- *What:* net move / sum of absolute steps (0..1).
- *Use:* lag-light; sometimes separates clean trend from chop better than ADX alone.

**Variance ratio** (in `marketPhase.py`)
- *What:* Lo–MacKinlay VR — >1 momentum/overshoot, <1 mean-reverting.
- *Use:* **flat vs. whipsaw** — critical for fade edges.
- *Recommendation:* long term, own `varianceRatio.py` tool.

### 5.3 Volatility
**ATR** (`ATR.py`)
- *What:* average true range.
- *Use:* SL/TP scaling, position size, vol regime.
- *Essential:* almost every strategy should know ATR for stops.

**Bollinger** (`bollinger.py`)
- *What:* SMA ± k·std dev.
- *Use:* mean reversion at bands; **squeeze** (tight bands) → prepare breakout.
- *Pitfalls:* in trend price runs “along the band” — not a fade.

### 5.4 Momentum / oscillators
**RSI** (`rsi.py`)
- *What:* relative strength 0–100.
- *Use:* OB/OS (>70/<30) for reversion; RSI(2) aggressive; divergence cautiously (subjective).
- *Pitfalls:* stays “overbought” long in strong trend.

**Stochastic** (`stochastic.py`)
- *What:* close position in recent range (%K/%D).
- *Use:* extreme reversion in **range/whipsaw** regimes; cross for timing.
- *Pitfalls:* using continuation in trend instead of reversion — different setup.

### 5.5 Structure / levels
**Donchian** (`donchian.py`) — breakout boundaries (N-period high/low).
**Floor pivots** (`floorPivotPoints.py`) — classic P/R/S from prior day.
**CPR** (`centralPivotRange.py`) — narrow = trend day expected, wide = range day.
**Pivots / market structure** (`pivotPoints.py`) — HH/HL/LH/LL, swing logic.
**Chandelier** (`chandelierExit.py`) — trailing: highest high − N×ATR.

### 5.6 Volume / fair price
**Volume profile** (`volumeProfile.py`, `VolumeProfileManager.py`, …)
- POC, VAH/VAL, HVN/LVN — fair zones, pullback targets, acceleration through LVN.

**VWAP** (`vwap.py`)
- Session-fair price; fade from std bands or trend pullback to VWAP.

### 5.7 Composite
**Market phase classifier** (`marketPhase.py`)
- ADX + VR + EMA direction → TREND_UP/DOWN, FLAT_RANGE, WHIPSAW.
- **Routing hub** for multi-edge strategies.

---

## 6. Strategy archetypes (blueprints)

### 6.1 Trend follow
- *Filter:* high ADX, phase TREND_*, EMA bias aligned.
- *Entry:* pullback limit at value edge / EMA / pivot in trend direction.
- *SL:* below pullback swing or 2×ATR.
- *Exit:* trailing (Chandelier/ATR) or structure HVN.
- *Fails when:* ADX drops, whipsaw phase.

### 6.2 Mean reversion / range fade
- *Filter:* low ADX, VR < 1 (FLAT_RANGE), **not** WHIPSAW.
- *Entry:* limit at BB/VWAP/CPR/stoch extreme.
- *SL:* 1.5–2×ATR beyond extreme — whipsaw needs tighter filter, not just tighter SL.
- *TP:* middle (VWAP, pivot, opposite band).

### 6.3 Breakout
- *Filter:* Bollinger squeeze, Donchian compression, tight CPR.
- *Entry:* **stop** above/below boundary.
- *SL:* back into range or 1×ATR.
- *Pitfalls:* false breakouts in whipsaw — vol filter mandatory.

### 6.4 Momentum continuation
- RSI/stoch extreme **in** trend direction (not against it).
- Needs strong trend + end-of-pullback signal.

### 6.5 Regime-adaptive (multi-edge)
- Several archetypes as **grades** with **phase router**.
- Test in isolation, then orchestrate (parallel > hard switch often).
- See Part 2 for your multi-edge setup.

---

## 7. Research methodology

### 7.1 Formulate a hypothesis
Before code, write: *“In [regime] I expect [edge] because [mechanism]. Fails when [].”*

### 7.2 Isolation
New edge = new variant or new grade — do not hide it inside existing logic.

### 7.3 Bake-off
Several candidates (e.g. B-fade variants) over the **same windows** — same costs,
same data. Winner = highest **floor** and acceptable DD, not just highest mean.

### 7.4 Read metrics correctly
| Metric | Meaning | Ignore when |
|--------|---------|-------------|
| Mean return | Average across windows | floor negative |
| Floor (min return) | Worst window | — |
| Consistency | mean − std (penalty for inconsistency) | too few windows |
| Worst DD | max drawdown % | without daily DD |
| Worst daily DD | prop killer | — |
| Capture ratio | TP/trailing quality | — |
| Win rate alone | — | without R-multiple |

### 7.5 Avoid overfitting
- Many parameters + few trades = overfit.
- “Perfect” in one window, bad OOS → discard.
- Walk-forward: optimise IS, check OOS only — do not re-optimise on OOS.

### 7.6 Buy & hold benchmark
Skill standard: strategy must beat passive hold of the underlying. **Framework gap:**
not yet automated — compare manually until implemented.

---

## 8. Validation & prop trading

### 8.1 Multi-period (framework)
`DEFAULT_PERIODS` = 3 windows (~3 months). Private builds may have 6+ including OOS.
Each window: **fresh capital** — simulates “can I repeat this?”

### 8.2 FTMO / prop (typical)
- Total DD < ~10%
- Daily DD < ~5% (often binding)
- Every window profitable (`all_prop_ok` in report)
- Choose risk so **worst daily DD** stays under the limit — do not discover it in live.

### 8.3 Private account
- Higher DD tolerable if **floor** and recovery are sound.
- Return > prop-optimised setup — conscious trade-off.

### 8.4 Reproducibility
Run the same variant twice. Sim noise ~0.003% is normal. Large deviation → bug
(offset, grade filter in reports, filling mode live vs sim).

---

## 9. Live trading & execution

### 9.1 Running live (the agent can do this itself)
Two ways, both requiring an **explicit, registered, non-example** variant:
- **Plugin (preferred for an agent):**
  - `python agent/plugin/hydra.py live status` — read-only: balance/equity, open positions, pendings.
  - `python agent/plugin/hydra.py live start --variant <id>` — dry run (prints what would start).
  - `python agent/plugin/hydra.py live start --variant <id> --yes` — actually launches. Refuses
    example strategies; `--yes` is the confirmation gate.
- **Direct entry point:** `python run_live.py --variant <id>` (variant required, no default).

Checklist before `--yes`:
- [ ] Sanity check on a representative window
- [ ] Multi-period + FTMO report green (if prop)
- [ ] `live status` → MT5 connected, symbol visible, account as expected
- [ ] Risk % set deliberately (do not forget to raise a demo 0.2% if intended)
- [ ] Variant, symbol and risk confirmed **with the user** — never auto-start live

### 9.2 Live vs. simulation (parity gotchas)
- **Order status matters:** a market order must be `TradeAction.ACTION` + `TradeStatus.RUNNING`.
  `ACTION`+`OPEN` silently becomes a pending in the sim but is *rejected* live → “Signal not
  executed”. Limit/stop = `PENDING`+`OPEN`.
- **Filling mode** (FOK/IOC/RETURN): a wrong one → retcode `10030`; execution retries across modes.
- Pending fills, gap-through-SL, requotes — the backtest is optimistic, especially for fades.
- First live days: small risk, watch the log (Web UI or the live console).

### 9.3 What you cannot “fix” live
Bad strategy, regime mismatch, excessive risk — only better code and smaller size help.
Also: stopping the live loop does **not** close open positions/pendings — flatten manually.

### 9.4 Discretionary orders (agent via plugin)
Without a coded strategy, the agent can place and **manage** single MT5 orders when the user asks:
- **Entry:** `order buy|sell … --yes` or pending `buy_limit|sell_limit|buy_stop|sell_stop --price … --yes`
- **Modify open position:** `order modify_position --ticket … --sl … [--tp …] --yes`
- **Modify pending:** `order modify_pending --ticket … [--price …] [--sl …] [--tp …] --yes`
- **Exit:** `order close --ticket … --yes` / `order cancel --ticket … --yes`

Every real action needs `--yes`; use `live status` for tickets. No auto risk-sizing on this path.

---

## 10. Common mistakes (anti-patterns)

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Fade in whipsaw | Many small losses, high WR on single days in backtest | VR/phase filter |
| No stale cancel | Trades days later, DD spikes | `adjust_pending` |
| Too many parameters | OOS breaks | simplify |
| Market instead of limit on fade | worse entry, worse RR | order type |
| SL inside noise | stopped out, then market runs | ATR minimum |
| One window optimised | OOS red | multi-period |
| Ignore swap | overnight strategy too good | `rolloverTool` |
| Repainting pivots | backtest shines, live dies | confirmed swings only |

---

## 11. HydraTrade — quick reference (tool, not core)

*Details in plugin commands (`agent/plugin/skills/hydra-*`). Orientation only here.*

| Task | Entry point |
|------|-------------|
| List variants / tools | `python agent/plugin/hydra.py catalog` |
| Multi-period backtest | `hydra.py bt --variants id --multi-period --export-trades` |
| Trade plausibility | `hydra.py sanity --variant id --start … --end …` |
| OOS report | `hydra.py validate --variants id` |
| Prop check | `hydra.py ftmo --run reports/runs/...` |
| Phase overview | `hydra.py phasemap --start … --end …` |
| New strategy | `hydra.py newstrategy "Name"` → `registry.py` |
| Web UI | `run_webui.py` — **Details & history** = `trades.json` |

**Strategy lifecycle:** `planTradeGrade_*` → `adjustPendingTradeGrade_*` → `manageActiveTradeGrade_*`
Base: `strategie/Strategy.py`, examples: `strategie/examples/`.

---

## 12. Checklists (compact)

**New idea:** hypothesis → tool/indicator → minimal strategy → sanity → 1 window → multi-period → decision.

**Before merge into orchestrator:** edge isolated all windows → floor > 0? → DD ok? → then routing.

**Read the report:** mean AND floor AND worst daily DD AND trades per window — not just equity curve.

---
---

# Part 2 — Your strategy & research knowledge (customizable)

> **HydraTrade is a framework, not a finished system.** Part 1 applies to everyone. **Part 2 is
> your space** — add your tested edges, parameters, and lessons so the agent becomes *your*
> research partner, not just a generic assistant.
>
> **How to customize**
> 1. Copy this file to `agent/private/DAYTRADER_AGENT_SKILL.md` (local only, gitignored).
> 2. Replace the placeholders below with your notes.
> 3. Run `python agent/plugin/install.py --private`
>
> Shipped **example strategies** (`example_ema_cross`, …) are demos — do **not** document them
> here. Part 2 is for **your** variants (`strategie/variants/`, your `variant_id`s).

---

## Current strategy generation

*(Short name + idea in 2–4 sentences)*

| Field | Your value |
|-------|------------|
| **Name** | |
| **variant_id(s)** | |
| **Goal** | Prop / Private / Research |
| **Status** | Idea / Testing / Live / Retired |

---

## Architecture

- **Grades (A/B/C):** what is each grade for?
- **Orchestration:** parallel / handoff / switch?
- **Regime gates:** which filters on which timeframe?
- **Dedup:** max trades per session/day?

---

## Edges (one block per edge)

### Edge: *(name)*

| | |
|---|---|
| **Phase / regime** | e.g. TREND_UP, FLAT_RANGE, London only |
| **Entry type** | Market / Limit / Stop |
| **Indicators** | e.g. `ema.py` D1, `marketPhase.py`, `stochastic.py` H1 |
| **SL / TP** | ATR × N, structure, RR |
| **Risk %** | per grade, prop-safe? |
| **variant_id** | for `hydra.py bt --variants …` |

**Hypothesis:** *(why should this work?)*  
**Fails when:** *(when to disable?)*

---

## Bake-off & validation

| Candidate | Mean | Floor | Worst DD | Worst daily DD | Verdict |
|-----------|------|-------|----------|----------------|---------|
| | | | | | keep / drop |

- **Reference run:** `reports/runs/<timestamp>_<name>/`
- **Rejected on purpose:** *(so the agent does not suggest them again)*

---

## Final configuration

```text
variant_id:
  risk_grade_A:
  risk_grade_B:
  key_params:
```

---

## Lessons learned (verified only)

- *(What did **not** work)*
- *(What actually controls drawdown)*
- *(Sim vs live quirks)*

---

## Next experiments

- **Idea:**
- **Open question:**
- **Next test:**

---

## Your standard commands

```bash
python agent/plugin/hydra.py bt --variants YOUR_VARIANT_ID --multi-period --export-trades
python agent/plugin/hydra.py sanity --variant YOUR_VARIANT_ID --start YYYY-MM-DD --end YYYY-MM-DD
python agent/plugin/hydra.py ftmo --run reports/runs/YOUR_RUN
```

---

*Part 2 in the public repo stays a **template**. Your filled-in copy lives in
`agent/private/DAYTRADER_AGENT_SKILL.md` (gitignored).*
