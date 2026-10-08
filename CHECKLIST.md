# TVTM Trading Integrity Checklist

## GitHub workflow + state
- [x] Cron GitHub Actions, five-minute schedule (best effort only).
- [x] GitHub branch tvtm-state state.json storage with SHA precondition.
- [x] R2 only used for one-time safe migration (no silent reset).
- [x] Pages dashboard reads state from GitHub (no R2/D1 binding).
- [ ] Verify production cutover after PR merge, then remove legacy R2 secrets.
- [ ] Confirm GitHub Actions GITHUB_TOKEN contents-write permission.
- [ ] Monitor file size and archive before GitHub Contents API limit.

## Trading strategy and journal
- [x] Prevent repeated BOS/CHoCH on same broken level.
- [x] Live candle freshness, history-count and recent gap validation.
- [x] Entry proximity, single virtual position limit.
- [x] Shared partial TP1 exit accounting for live and backtest.
- [x] Legacy journal retains old PnL behavior.
- [x] Single TP target closes correctly and risk target validation.
- [x] Retry close notifications, expire stale pending entry alerts.
- [ ] Backtest with actual OKX history and out-of-sample validation.
- [ ] Include fees, funding, slippage, realistic fill/latency and portfolio sizing.
- [ ] Calibrate scoring weights and score threshold statistically.

CAUTION: GitHub schedule can miss/delay runs; repository state is public.
