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
- [ ] Validate component weights via historical backtest

## 3. Storage (D1)
- [x] signals: confidence_pct, score, checklist_json
- [x] trades table for TP1/TP2/SL lifecycle and PnL/PnL-R
- [x] scripts/migrate_d1.py idempotent migration

## 4. Tracker (posisi berjalan)
- [x] src/strategy/tracker.py detects TP1/TP2/SL from closed OHLC candles
- [x] Persists trade status, exit reason, PnL and R multiple
- [x] Discord "Trade Closed" notification
- [ ] Partial-close position sizing/accounting; TP1 is currently a milestone only

## 5. Dashboard
- [x] /api/stats
- [x] /api/trades
- [x] /api/performance
- [x] /api/signals exposes SL/TP + confidence/score/checklist
- [ ] Card UI, ICT chart overlays, volume profile, performance chart, notification feed, sidebar

## 6. Backtest & validation
- [x] Unit tests for FVG/OB/Liquidity/Volume Profile/Scorer
- [x] Synthetic tracker tests
- [ ] Historical backtest on real candles
- [ ] Tune/lock scorer weights and strategy parameters from backtest

## Notes
- Scorer weights are still design defaults, not empirically validated.
- Tracker resolves a candle that touches both SL and target as SL first because OHLC does not reveal intrabar order.
- PnL is based on the full position exit; TP1 is a milestone until partial-close sizing is modeled.
