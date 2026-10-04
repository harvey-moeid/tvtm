export const headers = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,OPTIONS",
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
};

export function reply(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers });
}

export async function readState(env) {
  if (!env.DATA) throw new Error("R2 binding 'DATA' tidak ditemukan.");
  const object = await env.DATA.get("state.json");
  if (!object) throw new Error("state.json tidak ditemukan di R2.");
  const state = await object.json();
  if (state.version !== 1 || !Array.isArray(state.signals) || !Array.isArray(state.trades)) {
    throw new Error("Format state.json R2 tidak dikenal.");
  }
  return state;
}

export function signalStats(signals) {
  return {
    total: signals.length,
    buys: signals.filter((s) => s.direction === "BUY").length,
    sells: signals.filter((s) => s.direction === "SELL").length,
    notified: signals.filter((s) => s.notified === 1).length,
    pending: signals.filter((s) => s.notified === 0).length,
    latest: signals.reduce((v, s) => s.created_at > v ? s.created_at : v, "") || null,
  };
}

export const number = (value) => Number(value || 0);
