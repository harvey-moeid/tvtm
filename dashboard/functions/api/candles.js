export async function onRequest(context) {
  const { request } = context;
  const headers = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
    "Content-Type": "application/json",
  };

  if (request.method === "OPTIONS") {
    return new Response(null, { status: 204, headers });
  }

  const url = new URL(request.url);
  const symbol = (url.searchParams.get("symbol") || "").toUpperCase();
  const timeframe = url.searchParams.get("timeframe") || "15m";
  const limit = Math.min(Math.max(parseInt(url.searchParams.get("limit") || "300", 10) || 300, 10), 300);

  // Pemetaan symbol internal -> instId OKX. HARUS selalu identik dengan
  // src/config/symbols.json (exchange_symbol) - dashboard menampilkan
  // candle yang dipakai ENGINE untuk generate sinyal. Kalau beda instrumen,
  // level zona/SL/TP yang dikirim ke Discord tidak akan match secara
  // visual dengan chart di sini (pernah terjadi utk GOLDUSDT: engine sudah
  // pindah ke XAU-USDT-SWAP tapi chart masih PAXG-USDT spot - lihat commit
  // fix ini).
  const INSTRUMENTS = {
    BTCUSDT: "BTC-USDT-SWAP",
    GOLDUSDT: "XAU-USDT-SWAP",
  };
  const instId = INSTRUMENTS[symbol];
  if (!instId) {
    return new Response(
      JSON.stringify({ error: "Symbol tidak dikenal: " + symbol, known: Object.keys(INSTRUMENTS) }),
      { status: 400, headers }
    );
  }

  const BAR_MAP = { "5m": "5m", "15m": "15m" };
  const bar = BAR_MAP[timeframe] || "15m";

  try {
    const okxUrl =
      "https://www.okx.com/api/v5/market/candles?instId=" +
      encodeURIComponent(instId) +
      "&bar=" + bar +
      "&limit=" + limit;

    const res = await fetch(okxUrl, { headers: { Accept: "application/json" } });
    if (!res.ok) {
      return new Response(JSON.stringify({ error: "OKX HTTP " + res.status }), { status: 502, headers });
    }
    const body = await res.json();
    if (body.code !== "0") {
      return new Response(
        JSON.stringify({ error: "OKX error: " + (body.msg || body.code) }),
        { status: 502, headers }
      );
    }

    // OKX mengembalikan data terbaru dulu: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm].
    // Satuan `vol` beda per jenis instrumen (sama seperti src/market/exchange_adapter.py):
    // SPOT -> vol sudah dalam koin dasar; SWAP -> vol dalam jumlah KONTRAK,
    // sedangkan volCcy dalam koin dasar. Pakai volCcy utk instrumen -SWAP supaya
    // angka volume di chart konsisten dengan koin dasar, bukan jumlah kontrak.
    const volIdx = instId.endsWith("-SWAP") ? 6 : 5;
    const candles = (body.data || [])
      .map((row) => ({
        time: Math.floor(Number(row[0]) / 1000),
        open: Number(row[1]),
        high: Number(row[2]),
        low: Number(row[3]),
        close: Number(row[4]),
        volume: Number(row[volIdx]),
      }))
      .reverse();

    return new Response(
      JSON.stringify({ symbol, timeframe, instId, candles }),
      { headers }
    );
  } catch (error) {
    return new Response(JSON.stringify({ error: String(error) }), { status: 500, headers });
  }
}
