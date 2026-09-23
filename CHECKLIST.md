# Checklist Upgrade: ICT Full Suite + Dashboard Card UI

Status: [ ] belum, [x] selesai, [~] sedang dikerjakan.

## 1. Engine — deteksi konsep ICT tambahan
- [x] FVG detector + mitigation
- [x] Order Block detector + mitigation
- [x] Liquidity Sweep / equal highs-lows
- [x] Volume Profile / POC / imbalance
- [x] ICT dataclasses + Signal scoring fields
- [x] Strategy configuration parameters

## 2. Engine — scoring & confidence
- [x] Five-component scorer, total 10 points
- [x] Wired to M5 trigger with minScoreToNotify
- [x] "Market Structure" component now checks a *fresh* M15 BOS/CHoCH event, not just trend direction — previously it was structurally guaranteed true (direction is only set after m15_bias already matches trend), so it granted a free 2.5/10 that never discriminated
- [ ] Validate component weights via historical backtest (tooling ready — see §6, not yet run against real data)

## 3. Storage (D1)
- [x] signals: confidence_pct, score, checklist_json
- [x] trades table for TP1/TP2/SL lifecycle and PnL/PnL-R
- [x] scripts/migrate_d1.py idempotent migration

## 4. Tracker (posisi berjalan)
- [x] src/strategy/tracker.py detects TP1/TP2/SL from closed OHLC candles
- [x] Persists trade status, exit reason, PnL and R multiple
- [x] Discord "Trade Closed" notification
- [x] PnL/R-multiple math moved to src/strategy/pnl.py, shared by tracker.py (live) and src/backtest/simulator.py (backtest) — one formula, guaranteed consistent
- [ ] Partial-close position sizing/accounting; TP1 is currently a milestone only

## 5. Dashboard
- [x] /api/stats
- [x] /api/trades
- [x] /api/performance
- [x] /api/signals exposes SL/TP + confidence/score/checklist
- [x] /api/candles instrument mapping kept in sync with src/config/symbols.json (was serving PAXG-USDT spot for GOLDUSDT while the engine already traded XAU-USDT-SWAP)
- [ ] Card UI, ICT chart overlays, volume profile, performance chart, notification feed, sidebar

## 6. Backtest & validation
- [x] Unit tests for FVG/OB/Liquidity/Volume Profile/Scorer
- [x] Synthetic tracker tests
- [x] Walk-forward backtest engine (`src/backtest/`) — replays the *exact* production functions (`compute_m15_bias` → `evaluate_m5_trigger`) candle by candle over historical OHLC, with cooldown/rate-limit simulated against a **simulated clock** (not wall-clock — see `src/backtest/store.py` docstring for why that distinction matters)
- [x] `src/market/history_fetch.py` — paginated OKX `history-candles` fetcher (bypasses the 300-candle-per-request limit of the live endpoint) for pulling months of history
- [x] `scripts/backtest.py` CLI + `.github/workflows/backtest.yml` (`workflow_dispatch`) to run it against real OKX data from a runner that actually has network access to OKX
- [x] `src/backtest/metrics.py` — win rate, expectancy (R), profit factor, max drawdown (R), breakdowns by direction/pattern/exit_reason
- [ ] **Historical backtest actually run against real OKX data and results reviewed** — the tooling above was built and validated with synthetic candle fixtures (`tests/test_backtest_*.py`) in a sandboxed environment without OKX network access; running it for real is the next step, via `.github/workflows/backtest.yml`
- [ ] Tune/lock scorer weights and strategy parameters from backtest results

## Notes
- Scorer weights are still design defaults, not empirically validated — the backtest tooling to validate them now exists (§6) but has not yet been run against real market data.
- Tracker resolves a candle that touches both SL and target as SL first because OHLC does not reveal intrabar order. The backtest simulator makes the exact same conservative assumption for consistency.
- PnL is based on the full position exit; TP1 is a milestone until partial-close sizing is modeled.
- Backtest results are historical estimates only — they do not account for slippage, perpetual funding rate, or OKX/D1/Discord downtime, and past performance does not guarantee future results.
