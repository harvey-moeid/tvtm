import { headers, reply, readState, number } from "../_lib/state.js";

export async function onRequest({ env, request }) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers });
  const u = new URL(request.url);
  const symbol = u.searchParams.get("symbol") || "";
  const status = u.searchParams.get("status") || "";
  const limit = Math.min(Math.max(Number(u.searchParams.get("limit") || 50), 1), 100);
  try {
    const { trades } = await readState(env);
    const filtered = trades.filter((t) => (!symbol || t.symbol === symbol) && (!status || t.status === status));
    const closed = filtered.filter((t) => t.status === "CLOSED");
    const stats = {
      total: filtered.length, closed: closed.length,
      open: filtered.filter((t) => ["OPEN", "TP1_HIT"].includes(t.status)).length,
      pnl_pct: closed.reduce((n, t) => n + number(t.pnl_pct), 0),
      pnl_r: closed.reduce((n, t) => n + number(t.pnl_r), 0),
    };
    filtered.sort((a, b) => (b.exit_time || b.entry_time).localeCompare(a.exit_time || a.entry_time));
    return reply({ trades: filtered.slice(0, limit), stats });
  } catch (e) { return reply({ error: String(e) }, 500); }
}
