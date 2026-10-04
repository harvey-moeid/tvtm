import { headers, reply, readState, signalStats } from "../_lib/state.js";

export async function onRequest({ env, request }) {
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers });
  const u = new URL(request.url);
  const symbol = u.searchParams.get("symbol") || "";
  const direction = u.searchParams.get("direction") || "";
  const limit = Math.min(Math.max(Number(u.searchParams.get("limit") || 50), 1), 100);
  const offset = Math.max(Number(u.searchParams.get("offset") || 0), 0);
  try {
    const { signals } = await readState(env);
    const filtered = signals.filter((s) => (!symbol || s.symbol === symbol) && (!direction || s.direction === direction));
    filtered.sort((a, b) => b.created_at.localeCompare(a.created_at));
    return reply({
      signals: filtered.slice(offset, offset + limit), total: filtered.length, limit, offset,
      stats: signalStats(signals), symbols: [...new Set(signals.map((s) => s.symbol))].sort(),
    });
  } catch (e) { return reply({ error: String(e) }, 500); }
}
