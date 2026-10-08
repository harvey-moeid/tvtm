export const headers = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET,OPTIONS",
  "Content-Type": "application/json",
  "Cache-Control": "no-store",
};

export function reply(body, status = 200) {
  return new Response(JSON.stringify(body), { status, headers });
}

// Read state from the GitHub state branch, not from Cloudflare R2/D1.
// Public repository: raw CDN access by default (30-second cache-busting).
// If GH_STATE_TOKEN is set, use the authenticated GitHub Contents API instead.
export async function readState(env) {
  const repository = env.GH_REPO || "harvey-moeid/tvtm";
  const branch = env.GH_STATE_BRANCH || "tvtm-state";
  if (!/^[\w.-]+\/[\w.-]+$/.test(repository) || !/^[\w.-]+$/.test(branch)) {
    throw new Error("GitHub state location tidak valid");
  }
  let state;
  if (env.GH_STATE_TOKEN) {
    const endpoint = \`https://api.github.com/repos/\${repository}/contents/state.json?ref=\${encodeURIComponent(branch)}\`;
    const response = await fetch(endpoint, {
      headers: {
        Authorization: \`Bearer \${env.GH_STATE_TOKEN}\`,
        Accept: "application/vnd.github+json",
        "User-Agent": "tvtm-dashboard",
        "Cache-Control": "no-cache",
      },
    });
    if (!response.ok) throw new Error(\`GitHub state HTTP \${response.status}\`);
    const payload = await response.json();
    const raw = atob(payload.content.replace(/\s/g, ""));
    const bytes = Uint8Array.from(raw, (c) => c.charCodeAt(0));
    state = JSON.parse(new TextDecoder().decode(bytes));
  } else {
    const refresh = Math.floor(Date.now() / 30000);
    const endpoint = \`https://raw.githubusercontent.com/\${repository}/\${branch}/state.json?v=\${refresh}\`;
    const response = await fetch(endpoint, { headers: { Accept: "application/json" } });
    if (!response.ok) throw new Error(\`GitHub state HTTP \${response.status}; cek apakah migrasi awal sudah berhasil\`);
    state = await response.json();
  }
  if (state.version !== 1 || !Array.isArray(state.signals) || !Array.isArray(state.trades)) {
    throw new Error("Format GitHub state.json tidak dikenal");
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
