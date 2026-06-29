# HydraTrade Plugin — fachliche Spec (für den bauenden Agenten)

> **An den Framework-/Programmier-Agenten:** Du baust das Plugin, du brauchst **kein**
> Trading-Wissen dafür. Diese Spec sagt dir, **welche Fähigkeiten** das Plugin bündeln soll
> und **warum** — die fachliche Logik steckt schon im Framework-Code und in
> `DAYTRADER_AGENT_SKILL.md`. Deine Aufgabe: Skill + Slash-Commands sauber als Claude-Code-
> Plugin verpacken, Pfade/Defaults aus der Framework-Config ziehen, nichts hartkodieren.

## Zweck
Ein Plugin, das eine AI zum produktiven **Strategie-Entwickler & Trader** im HydraTrade-
Framework macht: bündelt die Day-Trader-Skill + wiederkehrende Workflow-Commands, sodass der
User nicht jedes Mal den Ablauf neu erklären muss.

## Bestandteile
1. **Skill** = `DAYTRADER_AGENT_SKILL.md` (TEIL 1 public; TEIL 2 optional via
   `agent/private/STRATEGY_KNOWLEDGE.md` + `install.py --private`).
2. **Slash-Commands** (dünne Wrapper um vorhandene Framework-Einstiegspunkte — NICHT neu
   implementieren, nur orchestrieren + Report-Pfad zurückgeben):

| Command | Was es tut (fachlich) | Stützt sich auf |
|---|---|---|
| `/bt` (backtest) | Strategie über die Standard-Fenster (inkl. OOS) backtesten, **HTML-Report** + Multi-Period-Summary erzeugen, Pfad ausgeben | `analysis/multiPeriod`, `htmlReport`, `runManager` |
| `/report` | Letzten/gewählten Run als ansehbaren Report rendern (Grade-Split) | `analysis/htmlReport` |
| `/newstrategy <name>` | Gerüst einer **standalone** Strategie anlegen (Strategy-Subklasse, planTradeGrade_A/B, on_tick, adjust_pending) aus Vorlage | Strategy-Basis |
| `/newindicator <name>` | Gerüst eines **Indikator-Tools** anlegen (Indicator-Klasse + Result-Dataclass, Stil `tools/ATR.py`) | `strategie/tools/` |
| `/validate` | OOS-Validierung: Floor/Konsistenz/worstDD/Tages-DD + Vergleich vs Buy&Hold | `multiPeriod`-Aggregat |
| `/ftmo` | Prop-Check: worstDD<10% UND worst Tages-DD<5% UND jedes Fenster profitabel → PASS/FAIL | `_grade_full_stats`/Aggregat |
| `/phasemap` | Markt-Phasen-Klassifikation + Edge×Phase-Routing-Tabelle als Report | Phase-Classifier-Tool |
| `/sanity` | Einzelner Trade-by-Trade-Check vor Live / nach neuer Strategie | `run_sanity_check.py` |
| `/catalog` | Timeframes, Indikatoren (`tools/`), registrierte Varianten auflisten | `registry` + `tools/` |

CLI-Einstieg (vom Agent aufgerufen): `python agent/plugin/hydra.py <command> …`

## Harte Anforderungen (aus der Skill abgeleitet — bitte einhalten)
- **Jeder Command, der etwas testet, erzeugt einen ansehbaren Report** (kein reiner
  Konsolen-Output). Report-Pfad immer zurückgeben.
- **Standard-Fenster** (In-Sample + OOS) zentral/konfigurierbar halten, nicht je Command
  hartkodieren.
- **Symbol/Datenquelle/Broker-Settings** aus der Framework-Config (`configConnection`) lesen.
- Commands sind **dünn**: sie rufen vorhandene Framework-Funktionen auf; Trading-Logik bleibt
  im Framework/in den Strategien, nicht im Plugin.
- **Two install modes:** default = TEIL 1 only; `--private` merges `agent/private/STRATEGY_KNOWLEDGE.md`.

## Offen / vom User zu entscheiden
- Genaue Command-Namen/Aliase, Default-Fenster, ob `/live` (Echtbetrieb) mit ins Plugin soll
  (Risiko!). Im Zweifel fragen, nicht annehmen.
