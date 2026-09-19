/**
 * GET /api/signals
 * Dashboard API for TVTM.
 */
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Content-Type": "application/json",
};

export async function onRequest(context) {
  const { env, request } = context;
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: CORS });
  if (!env.DB) return Response.json({ error: "D1 binding 'DB' tidak ditemukan." }, { status: 500, headers: CORS });

  const url = new URL(request.url);
  const symbol = url.searchParams.get("symbol") || "";
  const direction = url.searchParams.get("direction") || "";
  const notified = url.searchParams.get("notified");
  const limit = Math.min(Math.max(parseInt(url.searchParams.get("limit") || "50", 10) || 50, 1), 100);
  const offset = Math.max(parseInt(url.searchParams.get("offset") || "0", 10) || 0, 0);

  const conditions = [], params = [];
  if (symbol) { conditions.push("symbol = ?"); params.push(symbol); }
  if (direction) { conditions.push("direction = ?"); params.push(direction); }
  if (notified !== null && notified !== "") { conditions.push("notified = ?"); params.push(parseInt(notified, 10)); }
  const where = conditions.length ? "WHERE " + conditions.join(" AND ") : "";

  try {
    const [dataResult, countResult, symbolsResult, statsResult] = await Promise.all([
      env.DB.prepare(
        \`SELECT id, symbol, market, timeframe, direction, m15_bias, price,
                zone_type, zone_level, structure_event, pattern,
                candle_time, notified, created_at
         FROM signals \${where}
         ORDER BY created_at DESC
         LIMIT ? OFFSET ?\`
      ).bind(...params, limit, offset).all(),
      env.DB.prepare(\`SELECT COUNT(*) AS total FROM signals \${where}\`).bind(...params).first(),
      env.DB.prepare("SELECT DISTINCT symbol FROM signals ORDER BY symbol").all(),
      env.DB.prepare(
        \`SELECT COUNT(*) AS total,
          COALESCE(SUM(CASE WHEN direction='BUY' THEN 1 ELSE 0 END),0) AS buys,
          COALESCE(SUM(CASE WHEN direction='SELL' THEN 1 ELSE 0 END),0) AS sells,
          COALESCE(SUM(CASE WHEN notified=1 THEN 1 ELSE 0 END),0) AS notified,
          COALESCE(SUM(CASE WHEN notified=0 THEN 1 ELSE 0 END),0) AS pending,
          MAX(created_at) AS latest
         FROM signals \${where}\`
      ).bind(...params).first(),
    ]);

    return Response.json({
      signals: dataResult.results || [],
      total: Number(countResult?.total || 0),
      limit, offset,
      symbols: (symbolsResult.results || []).map(r => r.symbol),
      stats: {
        total: Number(statsResult?.total || 0),
        buys: Number(statsResult?.buys || 0),
        sells: Number(statsResult?.sells || 0),
        notified: Number(statsResult?.notified || 0),
        pending: Number(statsResult?.pending || 0),
        latest: statsResult?.latest || null,
      }
    }, { headers: CORS });
  } catch (err) {
    return Response.json({ error: String(err) }, { status: 500, headers: CORS });
  }
}