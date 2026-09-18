/**
 * GET /api/signals
 * Cloudflare Pages Function — query D1 `signals` table dengan filter & pagination.
 *
 * Query params:
 *   symbol      (string)  — filter by symbol, mis. BTCUSDT
 *   direction   (string)  — BUY | SELL
 *   notified    (0 | 1)   — filter status pengiriman Discord
 *   limit       (number)  — default 50, max 100
 *   offset      (number)  — default 0
 *
 * D1 binding: `DB` (dikonfigurasi di Pages project settings / wrangler.toml)
 */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Content-Type": "application/json",
};

export async function onRequest(context) {
  const { env, request } = context;

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers: CORS });
  }

  if (!env.DB) {
    return Response.json(
      { error: "D1 binding 'DB' tidak ditemukan. Cek konfigurasi Pages project." },
      { status: 500, headers: CORS }
    );
  }

  const url = new URL(request.url);
  const symbol    = url.searchParams.get("symbol")    || "";
  const direction = url.searchParams.get("direction") || "";
  const notified  = url.searchParams.get("notified");   // "0" | "1" | null
  const limit     = Math.min(parseInt(url.searchParams.get("limit")  || "50", 10), 100);
  const offset    = Math.max(parseInt(url.searchParams.get("offset") || "0",  10), 0);

  const conditions = [];
  const params     = [];

  if (symbol)    { conditions.push("symbol = ?");    params.push(symbol); }
  if (direction) { conditions.push("direction = ?"); params.push(direction); }
  if (notified !== null && notified !== "") {
    conditions.push("notified = ?");
    params.push(parseInt(notified, 10));
  }

  const where = conditions.length ? "WHERE " + conditions.join(" AND ") : "";

  try {
    const [dataResult, countResult, symbolsResult] = await Promise.all([
      env.DB.prepare(
        `SELECT id, symbol, market, timeframe, direction, m15_bias, price,
                zone_type, zone_level, structure_event, pattern,
                candle_time, notified, created_at
         FROM signals ${where}
         ORDER BY created_at DESC
         LIMIT ? OFFSET ?`
      ).bind(...params, limit, offset).all(),

      env.DB.prepare(
        `SELECT COUNT(*) AS total FROM signals ${where}`
      ).bind(...params).first(),

      env.DB.prepare(
        `SELECT DISTINCT symbol FROM signals ORDER BY symbol`
      ).all(),
    ]);

    return Response.json(
      {
        signals:  dataResult.results  || [],
        total:    countResult?.total  || 0,
        limit,
        offset,
        symbols:  (symbolsResult.results || []).map((r) => r.symbol),
      },
      { headers: CORS }
    );
  } catch (err) {
    return Response.json(
      { error: String(err) },
      { status: 500, headers: CORS }
    );
  }
}
