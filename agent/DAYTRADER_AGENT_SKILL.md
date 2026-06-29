# Day-Trader Agent — Skill-Wissen (HydraTrade)

> **Packaging:** `agent/plugin/install.py` → `.cursor/skills/hydratrade-daytrader/`
> **TEIL 1** = general day-trading knowledge (public, shared in this repo).
> **TEIL 2** = optional private notes in `agent/private/STRATEGY_KNOWLEDGE.md` (gitignored).

> **Zweck:** Eine AI soll **wie ein erfahrener Day-Trader denken** — Märkte lesen, Hypothesen
> bauen, ehrlich testen, Risiko verstehen — und das HydraTrade-Framework als Werkzeug nutzen,
> nicht umgekehrt.

---
---

# TEIL 1 — Allgemeines Trading-Wissen (teilbar, Framework-safe)

## 1. Mindset & Arbeitsregeln

### 1.1 Was ein Day-Trader eigentlich tut
Du handelst **Wiederholbarkeit unter Unsicherheit**, nicht „die Wahrheit über den Markt“.
Jede Idee ist eine Hypothese: *Unter welchen Bedingungen liefert dieses Verhalten einen
statistischen Vorteil?* Der Edge lebt in **Regime × Setup × Ausführung × Risiko** — nicht in
einem einzelnen Indikator.

### 1.2 Nicht verhandelbare Regeln
1. **Reports vor Meinungen** — jede Testidee endet in HTML/TXT/JSON unter `reports/runs/`.
   Konsole allein reicht nicht. Der User muss Ergebnisse öffnen und vergleichen können.
2. **Ein Hebel pro Iteration** — nicht gleichzeitig Entry, SL, Filter und Sizing ändern.
   Sonst weißt du nicht, was gewirkt hat.
3. **Regime zuerst** — vor dem Feintuning fragen: *In welchem Markttyp soll das funktionieren?*
   Trend-Setup im Chop optimieren ist Zeitverschwendung.
4. **Kein Lookahead** — Signale nur aus Daten, die zum Signalzeitpunkt **abgeschlossen** waren
   (geschlossene Kerzen, bestätigte Pivots). Visuell „schöne“ Linien mit Repainting sind Gift.
5. **Ein Indikator = eine Datei** in `strategie/tools/` (Stil `ATR.py`). Keine Sammeldateien,
   keine 200-Zeilen-Inline-Math in Strategien.
6. **Web-Recherche neutral** — Suchbegriffe nicht mit der eigenen Hypothese vorbelasten.
7. **Komplexität ist erlaubt** — aber jede Schicht muss isoliert testbar sein (eigene Grade,
   eigene Variante, eigener Report).

### 1.3 Typischer Research-Zyklus
```
Idee → minimale Implementierung → Sanity (Trades plausibel?)
     → ein Fenster → schlecht? verwerfen oder Regime prüfen
     → Multi-Period (3+ Fenster) → Floor & Konsistenz
     → FTMO/Prop-Check → Live nur mit explizitem User-OK
```
Nicht überspringen: **Sanity** fängt Sim-Bugs; **Multi-Period** fängt Overfitting.

### 1.4 Wann du stoppen sollst
- Floor negativ über mehrere Fenster trotz gutem Mittelwert → wahrscheinlich Overfit oder
  Regime-Mismatch.
- Edge funktioniert nur in einem Fenster → nicht generalisierbar ohne neue Hypothese.
- Win Rate hoch, aber Capture Ratio miserabel → du gibst Gewinne zu früh ab oder TP ist
  unrealistisch.
- Viele Trades mit winzigem SL → Spread/Slippage fressen den Edge live.

---

## 2. Marktmechanik (ohne Buzzwords)

### 2.1 Liquidität & Volatilität
- **Liquidität** = enge Spreads, schnelle Fills, weniger Stop-Hunts durch dünnes Buch.
  Höchste Aktivität: **London–New-York-Overlap** (ca. 13:00–17:00 UTC grob).
- **Volatilität** = Größe der Bewegungen. Trend-Strategien brauchen *genug* Vola zum Laufen;
  Fade-Strategien brauchen *begrenzte* Vola und klare Grenzen.
- **ATR** ist dein universelles Maß für „wie weit darf SL/TP sein?“ — nicht fixe Punkte.

### 2.2 Trend vs. Range vs. Whipsaw (intuitiv)
| Marktgefühl | Preisverhalten | Typische Strategien | Typische Fehler |
|-------------|----------------|---------------------|-----------------|
| **Trend** | HH/HL oder LH/LL, Pullbacks werden gekauft/verkauft | Trendfolge, Breakout mit Filter | Fades gegen Trend |
| **Flat Range** | Oszillation um Mittelwert, Mean Reversion | BB/VWAP/CPR-Fade, Stoch-Extreme | Breakout ohne Squeeze |
| **Whipsaw** | Viele falsche Ausbrüche, kein sauberes Revert | *wenig handeln* oder schnelle Exits | Fade an jedem Band |

**ADX** trennt Trend von Nicht-Trend. **Variance Ratio** trennt Flat (revertierend) von
Whipsaw (overshoot). Beides zusammen → `marketPhase.py`.

### 2.3 Struktur: horizontale vs. diagonale Levels
- **Horizontal:** Pivots, CPR, Value Area, Donchian — „Preis reagiert hier“.
- **Diagonal:** Trendlinien, Kanäle — „Rate of change“; gut für Übergänge Trend↔Range,
  aber **nur mit bestätigten Pivots** (non-repainting).

### 2.4 Spread, Slippage, Kosten
Backtests ohne realistische Kosten überschätzen Fade- und Scalping-Edges. Halte-Strategien
brauchen **Swap/Rollover** (Framework: `rolloverTool.py`). Vor Live: Sanity-Trades auf
unrealistische Exits prüfen.

---

## 3. Strategie-Baukasten (die echten Hebel)

### 3.1 Entry-Typen — wann welcher?
| Typ | Mechanik | Gut für | Schlecht für |
|-----|----------|---------|--------------|
| **Market** | Sofort fill | Momentum, „jetzt oder nie“ | Fade am exakten Level |
| **Limit** | Besserer Preis, wartet | Pullback, Fade an Support | Breakout (verpasst Move) |
| **Stop** | Schlechterer Preis, wartet | Breakout über/unter Level | Mean Reversion |

**Regel:** Fade = fast immer **Limit** am Level. Breakout = **Stop** über/unter Grenze.
Market nur wenn Verzögerung den Edge zerstört.

### 3.2 Stop-Loss — Logik vor Punkten
1. **Struktur-SL** — hinter dem Level, das die Idee invalidiert (unter Swing-Low, über
   Range-High). Marktlogisch, aber variabel.
2. **ATR-SL** — N × ATR; passt sich Vola an. Start oft 1.5–2.5 × ATR für Intraday.
3. **Fixes RR** — nur wenn kein klares Strukturziel; sonst künstlich.

**Filter:** SL zu eng (< 0.5× ATR) → Rauschen; zu weit (> 4× ATR) → schlechtes RR und
kleine Size.

### 3.3 Take-Profit & Capture
- **Struktur-TP** an nächstem HVN, Pivot, gegenüberliegender Value-Kante.
- **RR-TP** (z.B. 1:2) als Fallback.
- **Capture Ratio** (Framework-Metrik): wie viel der maximal möglichen Bewegung (MFE) du
  realisierst. Niedrige Capture → TP zu früh oder Trailing zu eng.

### 3.4 Risiko & Sizing
- Risiko = **% der Equity pro Trade**, Lot aus SL-Distanz (`RiskManager.get_lot_size`).
- **Grade A/B/C** = getrennte Risikotöpfe und Logik — erlaubt parallele unkorrelierte Edges.
- **Prop:** worst **Tages**-DD ist oft die harte Grenze (~5%), nicht nur Gesamt-DD (~10%).
- **Mythe:** „Keine neuen Trades nach −X% Tagesverlust“ stoppt selten den echten Tages-DD,
  wenn offene Trades weiterlaufen → **per-Trade-Risiko** und Exposure senken.

### 3.5 Pending-Management (`adjust_pending`) — unterschätzt
- **Stale-Cancel:** Order aus Session X darf nicht in Session Y fillen. Hauptursache für
  „Geister-Trades“ und DD-Spitzen in Backtests.
- **Re-Price:** Limit an neues Level wenn Struktur sich verschoben hat.
- **Dedup:** max. 1 Pending je Richtung/Session/Setup.
- **Expiry:** Zeitbasiert oder Session-Ende.

### 3.6 Aktives Management (`manage_trailing`)
- **Break-Even** ab X×R — schützt vor Winner→Loser; zu früh = Capture killt.
- **ATR/Chandelier Trailing** — für Trend-Runner.
- **Teil-Schließung** — Skalierung; nur wenn Regeln klar, sonst overfit.
- **Zeit-Exit** — „Idee hat nicht funktioniert“ nach N Bars.
- **Rollover/Weekend** — vor Swap-Zeit schließen wenn Haltekosten relevant.

### 3.7 Regime-Gating & Orchestration
- **Gate:** Trade nur wenn ADX/Phase/EMA-Filter passt.
- **Parallel:** mehrere Edges gleichzeitig, eigene Grades — Diversifikation.
- **Handoff:** eine Edge aktiv bis Signal endet, dann andere — weniger Overlap.
- **Hard Switch:** nur eine Edge — oft schlechter als parallel (siehe TEIL 2 für eigene Lessons).

---

## 4. Sessions, Zeit & Broker

### 4.1 Sessions (Forex/Metalle/Indizes)
- **Asia** — oft rangeartig, weniger Follow-Through für EU-Strategien.
- **London** — Trend-Starts, Breakouts häufiger.
- **New York** — hohe Vola, News-Risiko; Overlap mit London am stärksten.
- **Krypto** — 24/7; Session-Filter oft unnötig.
- **Daily/Swing** — Intraday-Session-Filter optional.

### 4.2 Broker-Zeit ≠ UTC
Broker-Charts laufen oft UTC+2/+3 mit DST. Sessions **immer in definierter Broker- oder
UTC-Logik** rechnen — und **konsistent** in Sim und Live.

### 4.3 Offset & DST erkennen (nicht raten)
- **Wochenend-Tick** des Hauptsymbols liefert oft **veralteten** Offset.
- **Besser:** Offset zuerst von **24/7-Symbol** (BTC/ETH) ableiten.
- **DST:** Zeitsprünge in M5-Daten eines 24/7-Symbols gegen `zoneinfo` prüfen.
- Falcher Offset → Session-Filter verschiebt sich → Backtest nicht reproduzierbar.

### 4.4 Datenfenster dynamisch
Lookback verdoppeln bis genug **echte** Bars da sind (Feiertage, Marktpausen). Lieber zu viel
Historie laden als zu wenig.

---

## 5. Indikatoren-Enzyklopädie

*Code: `strategie/tools/`. Ein Indikator misst — der Edge kommt aus Kontext + Kombination.*

### 5.1 Richtung / Trend
**EMA** (`ema.py`)
- *Was:* exponentiell gewichteter Mittelwert — reagiert schneller als SMA.
- *Nutzen:* Trendrichtung (Preis über/unter EMA), Crosses (schnell/langsam), Makro-Gate
  (nur Long über D1-EMA50).
- *Fallen:* im Chop ständige Crosses; ohne ADX/Phase-Filter wertlos.
- *Typisch:* D1/H4 für Bias, H1/M15 für Timing.

**SuperTrend** (`supertrend.py`)
- *Was:* ATR-Bänder um Median, Flip bei Durchbruch.
- *Nutzen:* klare Richtung + Trailing-Linie.
- *Fallen:* whippy in Range — als Filter, nicht als einziges Signal.

### 5.2 Trendstärke (richtungsneutral)
**ADX** (`adx.py`)
- *Was:* Stärke des Trends (nicht Richtung); +DI/−DI für Richtung.
- *Nutzen:* ADX hoch → Trendfolge erlauben; niedrig → Range/Fade erwägen.
- *Fallen:* kann in starkem Trend spät sein; Schwellenwert symbolabhängig testen.

**Efficiency Ratio** (`efficiencyRatio.py`)
- *Was:* Nettobewegung / Summe absoluter Schritte (0..1).
- *Nutzen:* lag-arm; unterscheidet sauberen Trend von Chop besser als ADX allein manchmal.

**Variance Ratio** (in `marketPhase.py`)
- *Was:* Lo-MacKinlay VR — >1 momentum/overshoot, <1 mean-reverting.
- *Nutzen:* **Flat vs. Whipsaw** — kritisch für Fade-Edges.
- *Empfehlung:* langfristig eigenes `varianceRatio.py` Tool.

### 5.3 Volatilität
**ATR** (`ATR.py`)
- *Was:* durchschnittliche True Range.
- *Nutzen:* SL/TP-Skalierung, Positionsgröße, Vola-Regime.
- *Pflicht:* fast jede Strategie sollte ATR für Stops kennen.

**Bollinger** (`bollinger.py`)
- *Was:* SMA ± k·StdAbw.
- *Nutzen:* Mean Reversion an Bändern; **Squeeze** (enge Bänder) → Breakout vorbereiten.
- *Fallen:* in Trend läuft Preis „entlang des Bandes“ — kein Fade.

### 5.4 Momentum / Oszillatoren
**RSI** (`rsi.py`)
- *Was:* relative Stärke 0–100.
- *Nutzen:* OB/OS (>70/<30) für Reversion; RSI(2) aggressiv; Divergenz vorsichtig (subjektiv).
- *Fallen:* in starkem Trend lange „überkauft“.

**Stochastic** (`stochastic.py`)
- *Was:* Close-Position in jüngster Range (%K/%D).
- *Nutzen:* Extrem-Reversion in **Range/Whipsaw**-Regimen; Cross für Timing.
- *Fallen:* in Trend continuation statt Reversion nutzen — anderes Setup.

### 5.5 Struktur / Levels
**Donchian** (`donchian.py`) — Breakout-Grenzen (N-Period High/Low).
**Floor Pivots** (`floorPivotPoints.py`) — klassische P/R/S aus Vortag.
**CPR** (`centralPivotRange.py`) — schmal = Trend-Tag erwartet, breit = Range-Tag.
**Pivots / Market Structure** (`pivotPoints.py`) — HH/HL/LH/LL, Swing-Logik.
**Chandelier** (`chandelierExit.py`) — Trailing: Highest High − N×ATR.

### 5.6 Volumen / faire Preise
**Volume Profile** (`volumeProfile.py`, `VolumeProfileManager.py`, …)
- POC, VAH/VAL, HVN/LVN — faire Zonen, Pullback-Ziele, Beschleunigung durch LVN.

**VWAP** (`vwap.py`)
- Session-fairer Preis; Fade von Std-Bändern oder Trend-Pullback zum VWAP.

### 5.7 Komposit
**Market Phase Classifier** (`marketPhase.py`)
- ADX + VR + EMA-Richtung → TREND_UP/DOWN, FLAT_RANGE, WHIPSAW.
- **Routing-Hub** für Multi-Edge-Strategien.

---

## 6. Strategie-Archetypen (Baupläne)

### 6.1 Trendfolge
- *Filter:* ADX hoch, Phase TREND_*, EMA-Bias aligned.
- *Entry:* Pullback Limit an Value-Kante / EMA / Pivot in Trendrichtung.
- *SL:* unter Pullback-Swing oder 2×ATR.
- *Exit:* Trailing (Chandelier/ATR) oder Struktur-HVN.
- *Scheitern wenn:* ADX fällt, Whipsaw-Phase.

### 6.2 Mean Reversion / Range Fade
- *Filter:* ADX niedrig, VR < 1 (FLAT_RANGE), **nicht** WHIPSAW.
- *Entry:* Limit an BB/VWAP/CPR/Stoch-Extrem.
- *SL:* 1.5–2×ATR hinter Extrem — Whipsaw braucht engeren Filter, nicht nur engeren SL.
- *TP:* Mitte (VWAP, Pivot, gegenüberliegendes Band).

### 6.3 Breakout
- *Filter:* Bollinger-Squeeze, Donchian-Kompression, enge CPR.
- *Entry:* **Stop** über/unter Grenze.
- *SL:* zurück in Range oder 1×ATR.
- *Fallen:* falsche Breakouts in Whipsaw — Vola-Filter Pflicht.

### 6.4 Momentum-Continuation
- RSI/Stoch-Extrem **in** Trendrichtung (nicht dagegen).
- Braucht starken Trend + Pullback-Ende-Signal.

### 6.5 Regime-adaptiv (Multi-Edge)
- Mehrere Archetypen als **Grades** mit **Phase-Router**.
- Isoliert testen, dann orchestrieren (parallel > hard switch oft).
- Siehe TEIL 2 für deine konkrete Multi-Edge-Umsetzung.

---

## 7. Research-Methodik

### 7.1 Hypothese formulieren
Schreibe vor dem Code: *„In [Regime] erwarte ich [Edge], weil [Mechanismus]. Scheitert wenn [].“*

### 7.2 Isolation
Neue Edge = neue Variante oder neuer Grade — nicht in bestehende Logik verstecken.

### 7.3 Bake-off
Mehrere Kandidaten (z.B. B-Fade-Varianten) über **dieselben Fenster** — gleiche Kosten,
gleiche Daten. Gewinner = höchster **Floor** und akzeptable DD, nicht nur höchster Mean.

### 7.4 Metriken richtig lesen
| Metrik | Bedeutung | Ignorieren wenn |
|--------|-----------|-----------------|
| Mean Return | Durchschnitt über Fenster | Floor negativ |
| Floor (Min Return) | Schlechtestes Fenster | — |
| Consistency | Mean − Std (Penalty für Inkonsistenz) | zu wenig Fenster |
| Worst DD | Max Drawdown % | ohne Tages-DD |
| Worst Tages-DD | Prop-Killer | — |
| Capture Ratio | TP/Trailing-Qualität | — |
| Win Rate allein | — | ohne R-Multiple |

### 7.5 Overfitting vermeiden
- Viele Parameter + wenig Trades = Overfit.
- „Perfekt“ in einem Fenster, schlecht in OOS → verwerfen.
- Walk-forward: IS optimieren, OOS nur prüfen — OOS nicht nachoptimieren.

### 7.6 Buy & Hold Benchmark
Skill-Standard: Strategie muss passives Halten des Underlyings schlagen. **Framework-Lücke:**
noch nicht automatisiert — manuell vergleichen bis implementiert.

---

## 8. Validierung & Prop Trading

### 8.1 Multi-Period (Framework)
`DEFAULT_PERIODS` = 3 Fenster (~3 Monate). Private Builds können 6+ inkl. OOS haben.
Jedes Fenster: **frisches Kapital** — simuliert „kann ich das wiederholen?“

### 8.2 FTMO / Prop (typisch)
- Gesamt-DD < ~10%
- Tages-DD < ~5% (oft bindend)
- Jedes Fenster profitabel (`all_prop_ok` im Report)
- Risiko so wählen, dass **worst Tages-DD** unter Grenze bleibt — nicht erst im Live merken.

### 8.3 Private Konto
- Höherer DD tolerierbar wenn **Floor** und Recovery stimmen.
- Return > Prop-optimiertes Setup — bewusste Trade-off.

### 8.4 Reproduzierbarkeit
Gleiche Variante 2× backtesten. Sim-Rauschen ~0.003% normal. Große Abweichung → Bug
(Offset, Grade-Filter in Reports, Filling-Mode Live vs Sim).

---

## 9. Live-Trading & Execution

### 9.1 Vor Live (Checkliste)
- [ ] Sanity-Check auf repräsentativem Fenster
- [ ] Multi-Period + FTMO-Report grün (wenn Prop)
- [ ] `run_live.py --variant <id>` — Variante **explizit** (kein Default)
- [ ] MT5 verbunden, Symbol & Filling-Mode passen
- [ ] Risiko % bewusst gesetzt (nicht Demo-0.2% vergessen zu erhöhen wenn gewollt)

### 9.2 Live vs. Simulation
- Filling Mode (FOK/IOC/RETURN) — Live-Retry bei 10030 beachten.
- Pending-Fills, Gap über SL, Requotes — Backtest ist optimistisch für Fades.
- Erste Live-Tage: kleines Risiko, Logs in Web UI beobachten.

### 9.3 Was du live nicht „fixen“ kannst
Schlechte Strategie, Regime-Mismatch, zu hohes Risiko — nur Code und Size ändern helfen.

---

## 10. Häufige Fehler (Anti-Patterns)

| Fehler | Symptom | Fix |
|--------|---------|-----|
| Fade in Whipsaw | Viele kleine Verluste, hohe WR in Backtest einzelner Tage | VR/Phase-Filter |
| Kein Stale-Cancel | Trades Tage später, DD-Spitzen | `adjust_pending` |
| Zu viele Parameter | OOS bricht ein | vereinfachen |
| Market statt Limit beim Fade | schlechter Entry, schlechter RR | Order-Typ |
| SL innerhalb Rauschen | gestoppt, dann läuft Markt | ATR-Minimum |
| Ein Fenster optimiert | OOS rot | Multi-Period |
| Ignore Swap | Overnight-Strategie zu gut | `rolloverTool` |
| Repainting Pivots | Backtest glänzt, Live stirbt | nur bestätigte Swings |

---

## 11. HydraTrade — Kurzreferenz (Werkzeug, nicht Kern)

*Details in Plugin-Commands (`agent/plugin/skills/hydra-*`). Hier nur Orientierung.*

| Aufgabe | Einstieg |
|---------|----------|
| Varianten / Tools listen | `python agent/plugin/hydra.py catalog` |
| Multi-Period Backtest | `hydra.py bt --variants id --multi-period --export-trades` |
| Trade-Plausibilität | `hydra.py sanity --variant id --start … --end …` |
| OOS-Report | `hydra.py validate --variants id` |
| Prop-Check | `hydra.py ftmo --run reports/runs/...` |
| Phasen-Übersicht | `hydra.py phasemap --start … --end …` |
| Neue Strategie | `hydra.py newstrategy "Name"` → `registry.py` |
| Web UI | `run_webui.py` — **Details & history** = `trades.json` |

**Strategy-Lifecycle:** `planTradeGrade_*` → `adjustPendingTradeGrade_*` → `manageActiveTradeGrade_*`
Basis: `strategie/Strategy.py`, Beispiele: `strategie/examples/`.

---

## 12. Checklisten (kompakt)

**Neue Idee:** Hypothese → Tool/Indikator → minimale Strategie → Sanity → 1 Fenster → Multi-Period → Entscheidung.

**Vor Merge in Orchestrator:** Edge isoliert alle Fenster → Floor > 0? → DD ok? → dann Routing.

**Report lesen:** Mean UND Floor UND worst Tages-DD UND Trades pro Fenster — nicht nur Equity-Kurve.

---
---

# TEIL 2 — Your private strategy knowledge (optional)

> **For everyone using HydraTrade:** This section is intentionally empty in the public repo.
> Add **your** tested edges, parameters, bake-offs, and lessons — not example-strategy secrets.
>
> **Recommended workflow**
> 1. Copy `agent/private/STRATEGY_KNOWLEDGE.md.example` → `agent/private/STRATEGY_KNOWLEDGE.md`
> 2. Fill it in (kept local via `.gitignore` by default)
> 3. Run `python agent/plugin/install.py --private` to merge it into the Cursor skill
>
> **Public install** (`install.py` without `--private`) uses **TEIL 1 only** — no private file.

The template below is a reminder of what to document. Replace it in your local
`STRATEGY_KNOWLEDGE.md`, not necessarily in this file.

## Current strategy generation
*(Your name + short idea)*

## Edges & routing
*(Per-edge: regime, entry type, indicators, SL/TP, variant_id)*

## Bake-off results
*(What you kept vs. rejected, with report folder names)*

## Final configuration
*(Risk %, variant IDs, key metrics from your last serious run)*

## Lessons learned
*(Only verified — sim quirks, prop limits, what failed)*

## Next experiments
*(Parked ideas)*
