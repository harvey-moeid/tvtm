import { headers, reply, readState, number } from "../_lib/state.js";

export async function onRequest({ env, request }) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers });
  const days = Math.min(Math.max(Number(new URL(request.url).searchParams.get("days") || 7), 1), 30);
  try {
    const { trades } = await readState(env);
    const cutoff = Date.now() - days * 86400000;
    const closed = trades.filter((t) => t.status === "CLOSED" && Date.parse(t.exit_time) >= cutoff);
    const byDay = new Map(), bySymbol = new Map();
    for (const t of closed) {
      const day = t.exit_time.slice(0, 10);
      for (const [map, key, name] of [[byDay, day, "day"], [bySymbol, t.symbol, "symbol"]]) {
        if (!map.has(key)) map.set(key, { [name]: key, trades: 0, wins: 0, pnl_pct: 0, pnl_r: 0 });
        const row = map.get(key);
        row.trades++;
        row.wins += number(t.pnl_r) > 0 ? 1 : 0;
        row.pnl_pct += number(t.pnl_pct);
        row.pnl_r += number(t.pnl_r);
      }
    }
    return reply({
      days,
      by_day: [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day)),
      by_symbol: [...bySymbol.values()].sort((a, b) => b.pnl_r - a.pnl_r),
    });
  } catch (e) { return reply({ error: String(e) }, 500); }
}
