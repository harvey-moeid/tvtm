import { headers, reply, readState, signalStats, number } from "../_lib/state.js";

export async function onRequest({ env, request }) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers });
  try {
    const { trades, signals } = await readState(env);
    const closed = trades.filter((t) => t.status === "CLOSED");
    const s = signalStats(signals);
    return reply({ summary: {
      total_pnl_pct: closed.reduce((n, t) => n + number(t.pnl_pct), 0),
      total_pnl_r: closed.reduce((n, t) => n + number(t.pnl_r), 0),
      win_rate_pct: closed.length ? Math.round(closed.filter((t) => number(t.pnl_r) > 0).length / closed.length * 10000) / 100 : 0,
      total_trades: trades.length, closed_trades: closed.length,
      open_trades: trades.filter((t) => ["OPEN", "TP1_HIT"].includes(t.status)).length,
      signals: s.total, buys: s.buys, sells: s.sells, latest_signal: s.latest,
    } });
  } catch (e) { return reply({ error: String(e) }, 500); }
}
