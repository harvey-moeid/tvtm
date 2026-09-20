// Endpoint tombol "Run now" di dashboard.
//
//   POST /api/run  -> memicu workflow_dispatch untuk check-signal.yml (wajib header x-run-key)
//   GET  /api/run  -> daftar run manual terbaru + status konfigurasi (read-only)
//
// Secret yang dibutuhkan (Cloudflare Pages project "tvtm"):
//   GH_DISPATCH_TOKEN  fine-grained PAT khusus repo ini, permission "Actions: Read and write"
//   RUN_KEY            kunci bebas; UI mengirimnya lewat header x-run-key supaya
//                      orang lain yang membuka dashboard tidak bisa memicu run
// Opsional: GH_REPO (default harvey-moeid/tvtm), GH_WORKFLOW (default check-signal.yml),
//           GH_REF (default main)
//
// Fail-closed: kalau salah satu secret belum ada, POST ditolak dengan 501.

const ACTIVE = new Set(["queued", "in_progress", "waiting", "requested", "pending"]);
const ACTIVE_WINDOW_MS = 10 * 60 * 1000;

const json = (body, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
  });

// Bandingkan lewat hash SHA-256 supaya waktu eksekusi tidak bocor panjang/isi key.
async function safeEqual(a, b) {
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([
    crypto.subtle.digest("SHA-256", enc.encode(a)),
    crypto.subtle.digest("SHA-256", enc.encode(b)),
  ]);
  const x = new Uint8Array(ha);
  const y = new Uint8Array(hb);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

function gh(env, path, init = {}) {
  const repo = env.GH_REPO || "harvey-moeid/tvtm";
  return fetch("https://api.github.com/repos/" + repo + path, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "tvtm-dashboard",
      ...(env.GH_DISPATCH_TOKEN ? { Authorization: "Bearer " + env.GH_DISPATCH_TOKEN } : {}),
      ...(init.headers || {}),
    },
  });
}

async function latestRuns(env, n = 5) {
  const wf = env.GH_WORKFLOW || "check-signal.yml";
  const res = await gh(env, "/actions/workflows/" + wf + "/runs?event=workflow_dispatch&per_page=" + n);
  if (!res.ok) {
    const detail = (await res.text()).slice(0, 200);
    throw new Error("GitHub " + res.status + ": " + detail);
  }
  const data = await res.json();
  return (data.workflow_runs || []).map((r) => ({
    id: r.id,
    status: r.status,
    conclusion: r.conclusion,
    created_at: r.created_at,
    html_url: r.html_url,
  }));
}

export async function onRequest({ request, env }) {
  const configured = Boolean(env.GH_DISPATCH_TOKEN && env.RUN_KEY);

  if (request.method === "GET") {
    try {
      return json({ ok: true, configured, runs: await latestRuns(env) });
    } catch (e) {
      return json({ ok: false, configured, error: "github_error", message: String(e.message || e) }, 502);
    }
  }

  if (request.method !== "POST") {
    return json({ ok: false, error: "method_not_allowed" }, 405);
  }

  if (!configured) {
    return json({
      ok: false,
      error: "not_configured",
      message: "Tombol Run belum dikonfigurasi: secret GH_DISPATCH_TOKEN dan RUN_KEY belum diset di Cloudflare Pages.",
    }, 501);
  }

  const key = request.headers.get("x-run-key") || "";
  if (!(await safeEqual(key, env.RUN_KEY))) {
    return json({ ok: false, error: "unauthorized", message: "Run key salah." }, 401);
  }

  let runs;
  try {
    runs = await latestRuns(env, 5);
  } catch (e) {
    return json({ ok: false, error: "github_error", message: String(e.message || e) }, 502);
  }

  // Cegah spam: kalau masih ada run manual yang antre/berjalan, jangan tambah lagi.
  const active = runs.find(
    (r) => ACTIVE.has(r.status) && Date.now() - Date.parse(r.created_at) < ACTIVE_WINDOW_MS
  );
  if (active) {
    return json({ ok: false, error: "already_running", message: "Run manual sebelumnya masih berjalan.", run: active }, 409);
  }

  const wf = env.GH_WORKFLOW || "check-signal.yml";
  const res = await gh(env, "/actions/workflows/" + wf + "/dispatches", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ref: env.GH_REF || "main" }),
  });

  if (res.status !== 204) {
    const detail = (await res.text()).slice(0, 200);
    return json({ ok: false, error: "github_error", message: "GitHub " + res.status + ": " + detail }, 502);
  }

  // before_id = ID run manual terakhir sebelum dispatch; UI menunggu run dengan ID lebih besar.
  return json({ ok: true, before_id: runs[0] ? runs[0].id : 0 }, 202);
}
