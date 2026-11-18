// YOUTUBE CONNECT: lets each studio customer connect THEIR YouTube channel (Google OAuth 2.0 web-server flow + PKCE) so the render worker can upload
// finished drafts to that channel automatically, with no manual token handling. Full design, risks, owner checklist: docs/YOUTUBE_CONNECT.md
//
// Standalone ES module: no imports, only Web Crypto + fetch (works in Cloudflare Workers and in Node >= 20 for the tests in app/youtube_connect.test.mjs).
// Own KV prefix "studio:yt:". It never touches the owner app keys and never edits worker.js / studio.js.
//
// ROUTES (all handled by handleYouTube(req, env, opts); it returns null for any other path so the caller can fall through):
//   POST /studio/yt/start        Bearer session, owner role. body {org_id, channel_id?, scope_level?: "basic"|"manage"} -> {url}  (the app navigates the browser to url)
//   GET  /studio/yt/callback     Google redirects the browser here (state + PKCE + state cookie are verified), then the page returns to /studio#youtube=...
//   GET  /studio/yt/status       Bearer session, any member. ?org_id=&channel_id=  -> connection summary (never a token)
//   POST /studio/yt/settings     Bearer session, owner. {org_id, channel_id?, mode: "private"|"schedule"|"public", max_per_day, schedule:{tz,times,per_day,lead_min}, confirm_public}
//   POST /studio/yt/disconnect   Bearer session, owner. {org_id, channel_id?} -> revokes at Google, deletes everything we stored
//   POST /internal/yt/token      x-worker-key. {org_id, channel_id?, job_id, thumbnail?, renew?} -> short-lived access token + upload policy + quota reservation
//   POST /internal/yt/report     x-worker-key. {org_id, channel_id?, job_id, event: "uploaded"|"failed"|"quota_exceeded", video_id?, publish_at?, privacy?, units?}
//
// INTEGRATION HOOK (needs ONE tiny edit in worker.js, intentionally not done here because other agents are editing it). Add at the very top of fetch(), before the /studio route:
//     import { handleYouTube } from "./youtube_connect.js";
//     ...
//     if (p.startsWith("/studio/yt/") || p.startsWith("/internal/yt/")) { const r = await handleYouTube(req, env); if (r) return r; }
// and app/deploy.py must upload this file as a second module next to studio.js (copy the studio.js line: f"youtube_connect.js=@.../youtube_connect.js;type=application/javascript+module;filename=youtube_connect.js").
//
// CONFIGURATION (Worker secrets / vars; secrets must be added with "keep_bindings":["secret_text"] in deploy.py's metadata or they are wiped on every deploy):
//   YT_CLIENT_ID, YT_CLIENT_SECRET   Google OAuth client (Web application). Secret only in Worker secrets, never in KV or the repo.
//   STUDIO_ENC_KEY                   base64 of 32 random bytes (AES-256-GCM key for refresh tokens at rest). Optional STUDIO_ENC_KEY_OLD for rotation.
//   YT_REDIRECT_URI                  optional override; default <origin>/studio/yt/callback. MUST be registered exactly in Google Cloud Console.
//   STUDIO_WORKER_KEY / KV studio:cfg:worker_key   same shared key studio.js already uses for /studio/worker/*.
//   KV studio:cfg:yt_quota           optional JSON {daily_units, upload_cost, thumb_cost, headroom_units, max_per_day_cap} (quota model differs by date, see the doc).
//   YT_AUDIT_PASSED=1 / KV studio:cfg:yt_audit_passed = "1"   set ONLY after Google's YouTube API audit: until then videos from this project are locked to private,
//                                                             so "schedule"/"public" modes are downgraded to private (reported as policy.downgraded).

const GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth";
const GOOGLE_TOKEN = "https://oauth2.googleapis.com/token";
const GOOGLE_REVOKE = "https://oauth2.googleapis.com/revoke";
const YT_CHANNELS = "https://www.googleapis.com/youtube/v3/channels?part=id,snippet&mine=true";
export const SCOPES = {
  upload: "https://www.googleapis.com/auth/youtube.upload",
  readonly: "https://www.googleapis.com/auth/youtube.readonly",
  manage: "https://www.googleapis.com/auth/youtube.force-ssl",   // only for scope_level "manage" (videos.update: flip a draft to public after the customer approves it)
};
const READ_SCOPES = [SCOPES.readonly, SCOPES.manage, "https://www.googleapis.com/auth/youtube"];   // any of these lets channels.list mine=true work
const STATE_TTL_S = 600;
const COOKIE = "ytstate";

// ---------- helpers ----------
const enc = new TextEncoder();
const hex = (b) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
const sha256 = async (t) => hex(await crypto.subtle.digest("SHA-256", enc.encode(t)));
export const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
export const b64uToBytes = (s) => Uint8Array.from(atob(String(s).replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
const rndB64u = (n) => b64u(crypto.getRandomValues(new Uint8Array(n)));
const safeEq = async (a, b) => { const [x, y] = await Promise.all([sha256(String(a)), sha256(String(b))]); let d = 0; for (let i = 0; i < x.length; i++) d |= x.charCodeAt(i) ^ y.charCodeAt(i); return d === 0; };
const json = (o, s = 200, h = {}) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...h } });
const err = (s, code, extra = {}) => json({ error: code, ...extra }, s);
const clean = (s, n = 200) => String(s == null ? "" : s).trim().slice(0, n);
const ID = /^[A-Za-z0-9_-]{1,40}$/;
const kget = (env, k) => env.KV.get(k, "json");
const kput = (env, k, v, opt) => env.KV.put(k, JSON.stringify(v), opt);
async function readBody(req) { const t = await req.text(); if (t.length > 20000) throw new Error("too_large"); try { return t ? JSON.parse(t) : {}; } catch { throw new Error("bad_json"); } }
// Google error bodies carry {error, error_description} only; we keep just those two short fields so no token can ever end up in a log or a response.
const googleErr = (j) => ({ code: clean(j && (j.error && j.error.status || (typeof j.error === "string" ? j.error : j.error && j.error.message)), 60) || "unknown", description: clean(j && (j.error_description || (j.error && j.error.message)), 160) });

const K = {
  conn: (o, c) => `studio:yt:c:${o}:${c}`, connsOfOrg: (o) => `studio:yt:c:${o}:`, claim: (ytId) => `studio:yt:ch:${ytId}`, state: (h) => `studio:yt:st:${h}`,
  used: (day, o, c) => `studio:yt:u:${day}:${o}:${c}`, global: (day) => `studio:yt:g:${day}`, studioChan: (o, c) => `studio:c:${o}:${c}`,
};

// ---------- config ----------
export function oauthClient(env) { const id = env.YT_CLIENT_ID || env.STUDIO_YT_CLIENT_ID, secret = env.YT_CLIENT_SECRET || env.STUDIO_YT_CLIENT_SECRET; return id && secret ? { id, secret } : null; }
// Quota model. Google changed it over time (see the doc): old = 10,000 units/day shared, 1,600 per upload; since mid-2026 videos.insert may have its own bucket (~100 calls/day).
// The conservative old model is the default; set KV studio:cfg:yt_quota to match what Cloud Console > Quotas shows for the project.
export async function quotaModel(env) {
  let o = {}; try { o = (await kget(env, "studio:cfg:yt_quota")) || {}; } catch { /* default */ }
  return { daily_units: Number(o.daily_units) || 10000, upload_cost: Number(o.upload_cost) || 1600, thumb_cost: Number(o.thumb_cost) || 50, headroom_units: Number.isFinite(Number(o.headroom_units)) && o.headroom_units != null ? Number(o.headroom_units) : 500, max_per_day_cap: Number(o.max_per_day_cap) || 20 };
}
async function auditPassed(env) { return String(env.YT_AUDIT_PASSED || (await env.KV.get("studio:cfg:yt_audit_passed")) || "") === "1"; }
async function workerKeyOk(req, env) { const key = (await env.KV.get("studio:cfg:worker_key")) || env.STUDIO_WORKER_KEY || ""; return !!key && (await safeEq(req.headers.get("x-worker-key") || "", key)); }

// ---------- AES-GCM at rest (refresh tokens) ----------
async function importKey(b64) { const raw = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0)); if (raw.length !== 32) throw new Error("STUDIO_ENC_KEY must be base64 of exactly 32 bytes"); return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]); }
const kidOf = async (b64) => (await sha256("yt-kid:" + b64)).slice(0, 8);
async function keyring(env) { const out = []; for (const name of ["STUDIO_ENC_KEY", "STUDIO_ENC_KEY_OLD"]) if (env[name]) out.push({ kid: await kidOf(env[name]), key: await importKey(env[name]), current: name === "STUDIO_ENC_KEY" }); return out; }
// aad binds the ciphertext to one (org, channel): a record copied to another customer's key will not decrypt.
export async function encryptSecret(env, plaintext, aad) {
  const ring = await keyring(env); const cur = ring.find((k) => k.current); if (!cur) throw new Error("STUDIO_ENC_KEY missing");
  const iv = crypto.getRandomValues(new Uint8Array(12)); const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: enc.encode(aad) }, cur.key, enc.encode(plaintext));
  return { v: 1, kid: cur.kid, iv: b64u(iv), ct: b64u(ct) };
}
export async function decryptSecret(env, rec, aad) {
  const ring = await keyring(env); const k = ring.find((x) => x.kid === rec.kid); if (!k) throw new Error("no key for kid " + rec.kid);
  const pt = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64uToBytes(rec.iv), additionalData: enc.encode(aad) }, k.key, b64uToBytes(rec.ct)); return { plaintext: new TextDecoder().decode(pt), rotated: !k.current };
}

// ---------- PKCE + consent URL ----------
export async function pkcePair() { const verifier = rndB64u(48); return { verifier, challenge: b64u(await crypto.subtle.digest("SHA-256", enc.encode(verifier))) }; }
export function scopesFor(level) { return level === "manage" ? [SCOPES.upload, SCOPES.readonly, SCOPES.manage] : [SCOPES.upload, SCOPES.readonly]; }
export function buildAuthUrl({ clientId, redirectUri, state, challenge, scopes, loginHint }) {
  const q = new URLSearchParams({ client_id: clientId, redirect_uri: redirectUri, response_type: "code", scope: scopes.join(" "), state, code_challenge: challenge, code_challenge_method: "S256",
    access_type: "offline",              // needed to get a refresh token
    prompt: "consent select_account",    // consent: Google returns a refresh token every time; select_account: the customer picks the right Google account / brand-account channel
    include_granted_scopes: "true" });   // incremental authorization (basic -> manage later keeps what was granted)
  if (loginHint) q.set("login_hint", loginHint);
  return GOOGLE_AUTH + "?" + q.toString();
}

// ---------- time (Pacific day for Google quota, customer time zone for schedules) ----------
const dtfCache = new Map();
function dtf(tz) { let f = dtfCache.get(tz); if (!f) { f = new Intl.DateTimeFormat("en-US", { timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }); dtfCache.set(tz, f); } return f; }
export function zonedParts(ts, tz) { const o = {}; for (const p of dtf(tz).formatToParts(new Date(ts))) o[p.type] = p.value; return { y: +o.year, mo: +o.month, d: +o.day, h: +o.hour % 24, mi: +o.minute, s: +o.second }; }
const tzOffsetMs = (ts, tz) => { const p = zonedParts(ts, tz); return Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi, p.s) - Math.floor(ts / 1000) * 1000; };
export function zonedToUtc(y, mo, d, h, mi, tz) { const guess = Date.UTC(y, mo - 1, d, h, mi); let t = guess - tzOffsetMs(guess, tz); t = guess - tzOffsetMs(t, tz); return t; }
const dayKey = (p) => `${p.y}-${String(p.mo).padStart(2, "0")}-${String(p.d).padStart(2, "0")}`;
export const pacificDay = (ts = Date.now()) => dayKey(zonedParts(ts, "America/Los_Angeles"));
export function nextPacificReset(ts = Date.now()) { const p = zonedParts(ts, "America/Los_Angeles"); const n = new Date(Date.UTC(p.y, p.mo - 1, p.d + 1)); return zonedToUtc(n.getUTCFullYear(), n.getUTCMonth() + 1, n.getUTCDate(), 0, 0, "America/Los_Angeles"); }
const validTz = (tz) => { try { dtf(tz); return true; } catch { return false; } };

// ---------- per-customer settings and the resulting upload policy ----------
export const DEFAULT_SETTINGS = { mode: "private", max_per_day: 3, schedule: { tz: "Asia/Jerusalem", times: ["18:00"], per_day: 1, lead_min: 60 }, public_ack_at: null };
export function normalizeSettings(input, prev, cap = 20) {
  const s = JSON.parse(JSON.stringify(prev || DEFAULT_SETTINGS)); const i = input || {};
  if (i.mode !== undefined) { if (!["private", "schedule", "public"].includes(i.mode)) return { error: "bad_mode" }; s.mode = i.mode; }
  if (i.max_per_day !== undefined) { const n = Math.floor(Number(i.max_per_day)); if (!(n >= 1 && n <= cap)) return { error: "bad_max_per_day", max: cap }; s.max_per_day = n; }
  if (i.schedule !== undefined) {
    const sc = i.schedule || {}; const t = { ...s.schedule };
    if (sc.tz !== undefined) { if (!validTz(String(sc.tz))) return { error: "bad_tz" }; t.tz = String(sc.tz); }
    if (sc.times !== undefined) { if (!Array.isArray(sc.times) || !sc.times.length || sc.times.length > 6 || !sc.times.every((x) => /^([01]\d|2[0-3]):[0-5]\d$/.test(x))) return { error: "bad_times" }; t.times = [...new Set(sc.times)].sort(); }
    if (sc.per_day !== undefined) { const n = Math.floor(Number(sc.per_day)); if (!(n >= 1 && n <= 10)) return { error: "bad_per_day" }; t.per_day = n; }
    if (sc.lead_min !== undefined) { const n = Math.floor(Number(sc.lead_min)); if (!(n >= 15 && n <= 1440)) return { error: "bad_lead_min" }; t.lead_min = n; }
    s.schedule = t;
  }
  if (s.mode === "public") { if (i.confirm_public !== true && !s.public_ack_at) return { error: "confirm_public_required" }; if (i.confirm_public === true) s.public_ack_at = new Date().toISOString(); }
  return { settings: s };
}
// Next free publish slot (UTC ISO) at or after now + lead, skipping slots already taken and days that are full. Slots are wall-clock times in the customer's time zone.
export function nextPublishAt(schedule, nowMs, taken = []) {
  const tz = schedule.tz, takenMs = taken.map((x) => Date.parse(x)).filter(Number.isFinite); const base = zonedParts(nowMs, tz);
  for (let add = 0; add < 60; add++) {
    const day = new Date(Date.UTC(base.y, base.mo - 1, base.d + add)); const y = day.getUTCFullYear(), mo = day.getUTCMonth() + 1, d = day.getUTCDate();
    let sameDay = takenMs.filter((t) => { const p = zonedParts(t, tz); return p.y === y && p.mo === mo && p.d === d; }).length;
    for (const hm of schedule.times) {
      if (sameDay >= schedule.per_day) break; const [h, mi] = hm.split(":").map(Number); const t = zonedToUtc(y, mo, d, h, mi, tz);
      if (t < nowMs + schedule.lead_min * 60000 || takenMs.includes(t)) continue;
      return new Date(t).toISOString();
    }
  }
  return null;
}
// What the worker is allowed to do for this customer right now. Never publishes unless the owner chose it AND the Google project has passed the audit.
export async function resolvePolicy(env, conn, nowMs = Date.now()) {
  const st = conn.settings || DEFAULT_SETTINGS; const out = { mode: st.mode, privacy: "private", publish_at: null, downgraded: null };
  if (st.mode === "private") return out;
  if (!(await auditPassed(env))) { out.downgraded = "project_not_audited"; return out; }          // unverified API projects: every upload is locked private by YouTube
  if (st.mode === "public") { if (!st.public_ack_at) { out.downgraded = "public_not_confirmed"; return out; } out.privacy = "public"; return out; }
  const slot = nextPublishAt(st.schedule, nowMs, (conn.scheduled || []).filter((x) => Date.parse(x) > nowMs));
  if (!slot) { out.downgraded = "no_free_slot"; return out; }
  out.publish_at = slot; return out;     // privacyStatus stays "private"; YouTube flips it to public at publish_at (videos.insert status.publishAt)
}

// ---------- Google calls (fetchImpl is injectable; nothing here logs a body) ----------
async function formPost(fetchImpl, url, params) {
  const r = await fetchImpl(url, { method: "POST", headers: { "content-type": "application/x-www-form-urlencoded" }, body: new URLSearchParams(params).toString() });
  let j = {}; try { j = await r.json(); } catch { /* empty body */ } return { ok: r.ok, status: r.status, j };
}
export async function exchangeCode(env, fetchImpl, { code, verifier, redirectUri }) { const c = oauthClient(env); return formPost(fetchImpl, GOOGLE_TOKEN, { code, client_id: c.id, client_secret: c.secret, redirect_uri: redirectUri, grant_type: "authorization_code", code_verifier: verifier }); }
export async function refreshAccess(env, fetchImpl, refreshToken) { const c = oauthClient(env); return formPost(fetchImpl, GOOGLE_TOKEN, { client_id: c.id, client_secret: c.secret, refresh_token: refreshToken, grant_type: "refresh_token" }); }
export async function revoke(fetchImpl, token) { try { const r = await formPost(fetchImpl, GOOGLE_REVOKE, { token }); return r.ok; } catch { return false; } }
async function myChannel(fetchImpl, accessToken) {
  const r = await fetchImpl(YT_CHANNELS, { headers: { authorization: "Bearer " + accessToken } }); let j = {}; try { j = await r.json(); } catch { /* */ }
  if (!r.ok) return { ok: false, status: r.status, ...googleErr(j) }; const it = (j.items || [])[0]; if (!it) return { ok: false, status: 200, code: "no_youtube_channel", description: "This Google account has no YouTube channel" };
  return { ok: true, id: it.id, title: clean(it.snippet && it.snippet.title, 100), thumb: clean(it.snippet && it.snippet.thumbnails && it.snippet.thumbnails.default && it.snippet.thumbnails.default.url, 300) };
}

// ---------- default auth adapter: the session / membership layout of app/studio.js (bearer token -> sha256 -> studio:s:<hash>; membership studio:m:<org>:<uid>) ----------
export async function studioSession(req, env) {
  const a = req.headers.get("authorization") || ""; if (!a.startsWith("Bearer ")) return null;
  const s = await kget(env, `studio:s:${await sha256(a.slice(7))}`); if (!s || s.exp < Date.now()) return null; const u = await kget(env, `studio:u:${s.uid}`); return u ? { uid: u.id || s.uid, email: u.email } : null;
}
export async function studioRole(env, org, uid) { const m = await kget(env, `studio:m:${org}:${uid}`); return m ? m.role : null; }
const canConnect = (role) => role === "owner";   // same rule as studio.js PERMS: only "owner" has "youtube.connect"

// ---------- connection record helpers ----------
const aadOf = (org, chan) => `${org}:${chan}`;
const getConn = (env, org, chan) => kget(env, K.conn(org, chan));
function publicConn(c, extra = {}) {
  return { connected: true, status: c.status, channel: { id: c.yt_channel_id, title: c.yt_channel_title, thumb: c.yt_channel_thumb || null }, scopes: c.scopes, connected_at: c.connected_at, settings: c.settings,
    last_upload: c.last_upload || null, last_error: c.last_error || null, ...extra };
}
async function syncStudioChannel(env, org, chan, yt) { try { const ch = await kget(env, K.studioChan(org, chan)); if (ch) { ch.yt = yt; await kput(env, K.studioChan(org, chan), ch); } } catch { /* studio channel record is optional */ } }
const cookieOf = (req, name) => { const m = (req.headers.get("cookie") || "").split(/;\s*/).find((c) => c.startsWith(name + "=")); return m ? m.slice(name.length + 1) : ""; };
const pageBack = (qs, cookieHeader) => new Response(`<!doctype html><meta charset=utf-8><meta name=referrer content=no-referrer><title>YouTube</title><script>location.replace("/studio#youtube=${qs.replace(/[^A-Za-z0-9_=&.-]/g, "")}")</script><noscript><a href="/studio">/studio</a></noscript>`,
  { status: 200, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store", "referrer-policy": "no-referrer", "set-cookie": cookieHeader } });
const clearCookie = `${COOKIE}=; Path=/studio/yt; Max-Age=0; HttpOnly; Secure; SameSite=Lax`;

// ---------- the router ----------
import { withStore } from "./studio.js";
export async function handleYouTube(req, env0, opts = {}) {
  const env = withStore(env0);
  const u = new URL(req.url); const p = u.pathname.replace(/\/+$/, ""); const m = req.method;
  if (!(p.startsWith("/studio/yt/") || p.startsWith("/internal/yt/"))) return null;
  const fetchImpl = opts.fetchImpl || fetch, getSession = opts.getSession || studioSession, getRole = opts.getRole || studioRole, now = opts.now ? opts.now() : Date.now();

  // ----- internal (render worker) -----
  if (p.startsWith("/internal/yt/")) {
    if (!(await workerKeyOk(req, env))) return err(401, "unauthorized");
    let b; try { b = await readBody(req); } catch (e) { return err(400, e.message); }
    const org = clean(b.org_id, 40); if (!ID.test(org)) return err(400, "bad_ids");
    let job = null;
    if (b.job_id !== undefined || env.YT_REQUIRE_JOB !== "0") {   // least privilege: a token is only handed out for a real job of that customer (YT_REQUIRE_JOB=0 relaxes it for manual tests)
      job = b.job_id && ID.test(String(b.job_id)) ? await kget(env, `studio:j:${b.job_id}`) : null;
      if (!job || job.org !== org) return err(403, "job_mismatch");
    }
    const chan = clean(b.channel_id || (job && job.channel) || "main", 40); if (!ID.test(chan)) return err(400, "bad_ids");
    if (job && job.channel && job.channel !== chan) return err(403, "job_mismatch");
    const conn = await getConn(env, org, chan); if (!conn) return err(404, "not_connected");
    const q = await quotaModel(env), day = pacificDay(now);

    if (p === "/internal/yt/token" && m === "POST") {
      if (conn.status === "needs_reconnect") return err(409, "needs_reconnect", { channel_title: conn.yt_channel_title });
      const g = (await kget(env, K.global(day))) || { units: 0, uploads: 0, exhausted: false }; const used = parseInt((await env.KV.get(K.used(day, org, chan))) || "0");
      const renew = b.renew === true;   // renew: a fresh access token for an upload that already holds its reservation (token expired mid-upload, or a resumed upload): no new reservation
      const cost = renew ? 0 : q.upload_cost + (b.thumbnail ? q.thumb_cost : 0); const st = conn.settings || DEFAULT_SETTINGS; const cap = Math.min(st.max_per_day, q.max_per_day_cap);
      const retry = Math.max(60, Math.ceil((nextPacificReset(now) - now) / 1000));
      if (!renew && used >= cap) return err(429, "customer_daily_limit", { limit: cap, used, retry_after_s: retry });
      if (!renew && (g.exhausted || g.units + cost > q.daily_units - q.headroom_units)) return err(429, "quota_exhausted", { scope: "project", retry_after_s: retry, reset_at: new Date(nextPacificReset(now)).toISOString() });
      let rt; try { const d = await decryptSecret(env, conn.rt, aadOf(org, chan)); rt = d.plaintext; if (d.rotated) { conn.rt = await encryptSecret(env, rt, aadOf(org, chan)); await kput(env, K.conn(org, chan), conn); } } catch { return err(500, "decrypt_failed"); }   // key lost / rotated away
      const t = await refreshAccess(env, fetchImpl, rt);
      if (!t.ok || !t.j.access_token) {
        const ge = googleErr(t.j);
        if (ge.code === "invalid_grant") { conn.status = "needs_reconnect"; conn.last_error = { at: new Date(now).toISOString(), code: "invalid_grant" }; await kput(env, K.conn(org, chan), conn); await syncStudioChannel(env, org, chan, { status: "needs_reconnect", channel_id: conn.yt_channel_id, title: conn.yt_channel_title }); return err(409, "needs_reconnect", { channel_title: conn.yt_channel_title }); }
        return err(502, "google_token_error", { google: ge, transient: t.status >= 500 || t.status === 429 });
      }
      if (conn.status !== "connected" || conn.last_error) { conn.status = "connected"; conn.last_error = null; await kput(env, K.conn(org, chan), conn); }
      const policy = await resolvePolicy(env, conn, now);
      if (!renew) { g.units += cost; g.uploads += 1; await Promise.all([kput(env, K.global(day), g, { expirationTtl: 3 * 86400 }), env.KV.put(K.used(day, org, chan), String(used + 1), { expirationTtl: 3 * 86400 })]); }   // KV is not atomic: fine for one worker, move to a Durable Object/D1 before scaling
      return json({ access_token: t.j.access_token, expires_in: t.j.expires_in || 3600, token_type: "Bearer", channel_id: conn.yt_channel_id, channel_title: conn.yt_channel_title, scopes: conn.scopes,
        policy: { ...policy, allowed: ["private"].concat(policy.privacy === "public" ? ["public"] : []) }, reserved_units: cost, quota: { customer_used_today: used + (renew ? 0 : 1), customer_limit: cap, project_day: day } });
    }
    if (p === "/internal/yt/report" && m === "POST") {
      const ev = clean(b.event, 20); if (!["uploaded", "failed", "quota_exceeded"].includes(ev)) return err(400, "bad_event");
      const refund = Math.max(0, Math.min(Number(b.units) || 0, q.upload_cost + q.thumb_cost));
      if (ev === "uploaded") {
        conn.last_upload = { video_id: clean(b.video_id, 20), at: new Date(now).toISOString(), privacy: clean(b.privacy, 10) || "private", publish_at: clean(b.publish_at, 30) || null, job_id: clean(b.job_id, 40) };
        conn.scheduled = [...(conn.scheduled || []).filter((x) => Date.parse(x) > now), ...(b.publish_at ? [clean(b.publish_at, 30)] : [])].slice(-60); await kput(env, K.conn(org, chan), conn);
      } else {   // nothing was created on YouTube: give the reservation back (quota_exceeded additionally closes the project for the rest of the Pacific day)
        const g = (await kget(env, K.global(day))) || { units: 0, uploads: 0, exhausted: false }; g.units = Math.max(0, g.units - refund); g.uploads = Math.max(0, g.uploads - 1); if (ev === "quota_exceeded") g.exhausted = true;
        const used = parseInt((await env.KV.get(K.used(day, org, chan))) || "0"); await Promise.all([kput(env, K.global(day), g, { expirationTtl: 3 * 86400 }), env.KV.put(K.used(day, org, chan), String(Math.max(0, used - 1)), { expirationTtl: 3 * 86400 })]);
      }
      return json({ ok: true });
    }
    return err(404, "not_found");
  }

  // ----- the Google redirect (no bearer: identity comes from the one-time state we stored + the cookie set at /start) -----
  if (p === "/studio/yt/callback" && m === "GET") {
    const state = u.searchParams.get("state") || ""; const sh = state ? await sha256(state) : ""; const st = sh ? await kget(env, K.state(sh)) : null;
    if (st) await env.KV.delete(K.state(sh));    // single use
    const fail = (code) => pageBack("error=" + code, clearCookie);
    if (!st || st.exp < now) return fail("state_invalid");
    if (!(await safeEq(cookieOf(req, COOKIE), state))) return fail("browser_mismatch");    // blocks "victim finishes the attacker's flow" (login CSRF)
    if (u.searchParams.get("error")) return fail(clean(u.searchParams.get("error"), 40).replace(/[^a-z_]/g, "") || "denied");
    const code = u.searchParams.get("code"); if (!code) return fail("no_code");
    if (!oauthClient(env)) return fail("yt_not_configured");
    if (!canConnect(await getRole(env, st.org, st.uid))) return fail("forbidden");
    const t = await exchangeCode(env, fetchImpl, { code, verifier: st.verifier, redirectUri: st.redirect_uri });
    if (!t.ok || !t.j.access_token) return fail("token_exchange_failed");
    const granted = String(t.j.scope || u.searchParams.get("scope") || "").split(/\s+/);
    const reject = async (c) => { await revoke(fetchImpl, t.j.refresh_token || t.j.access_token); return fail(c); };
    if (!granted.includes(SCOPES.upload) || !granted.some((s) => READ_SCOPES.includes(s))) return reject("missing_scope");   // Google lets users untick individual permissions
    if (!t.j.refresh_token) return reject("no_refresh_token");
    const ch = await myChannel(fetchImpl, t.j.access_token); if (!ch.ok) return reject(ch.code === "no_youtube_channel" ? "no_youtube_channel" : "channel_lookup_failed");
    const claim = await kget(env, K.claim(ch.id)); if (claim && (claim.org !== st.org || claim.chan !== st.chan)) return reject("channel_already_connected");
    const prev = await getConn(env, st.org, st.chan);
    if (prev && prev.yt_channel_id !== ch.id) { await env.KV.delete(K.claim(prev.yt_channel_id)); try { const old = await decryptSecret(env, prev.rt, aadOf(st.org, st.chan)); await revoke(fetchImpl, old.plaintext); } catch { /* best effort */ } }
    const rec = { v: 1, org: st.org, chan: st.chan, yt_channel_id: ch.id, yt_channel_title: ch.title, yt_channel_thumb: ch.thumb, scopes: granted.filter(Boolean), rt: await encryptSecret(env, t.j.refresh_token, aadOf(st.org, st.chan)),
      status: "connected", last_error: null, connected_at: new Date(now).toISOString(), connected_by: st.uid, settings: (prev && prev.settings) || DEFAULT_SETTINGS, scheduled: (prev && prev.scheduled) || [], last_upload: (prev && prev.last_upload) || null };
    await Promise.all([kput(env, K.conn(st.org, st.chan), rec), kput(env, K.claim(ch.id), { org: st.org, chan: st.chan }), syncStudioChannel(env, st.org, st.chan, { status: "connected", channel_id: ch.id, title: ch.title })]);
    return pageBack("connected&org=" + st.org, clearCookie);
  }

  // ----- customer-facing, bearer session -----
  const ses = await getSession(req, env); if (!ses) return err(401, "unauthorized");
  let b = {}; if (m === "POST") { try { b = await readBody(req); } catch (e) { return err(400, e.message); } }
  const org = clean(b.org_id || u.searchParams.get("org_id"), 40), chan = clean(b.channel_id || u.searchParams.get("channel_id") || "main", 40);
  if (!ID.test(org) || !ID.test(chan)) return err(400, "bad_ids");
  const role = await getRole(env, org, ses.uid); if (!role) return err(404, "not_found");    // 404 not 403: do not reveal other orgs
  const owner = canConnect(role);

  if (p === "/studio/yt/start" && m === "POST") {
    if (!owner) return err(403, "forbidden", { need: "youtube.connect", role });
    const client = oauthClient(env); if (!client) return err(503, "yt_not_configured");
    if (!(env.STUDIO_ENC_KEY)) return err(503, "enc_key_missing");        // never start a flow we cannot store safely
    const state = rndB64u(32), { verifier, challenge } = await pkcePair(), redirectUri = env.YT_REDIRECT_URI || u.origin + "/studio/yt/callback";
    const level = b.scope_level === "manage" ? "manage" : "basic";
    await kput(env, K.state(await sha256(state)), { org, chan, uid: ses.uid, verifier, redirect_uri: redirectUri, level, exp: now + STATE_TTL_S * 1000 }, { expirationTtl: STATE_TTL_S + 60 });
    return json({ url: buildAuthUrl({ clientId: client.id, redirectUri, state, challenge, scopes: scopesFor(level), loginHint: ses.email }), expires_in: STATE_TTL_S },
      200, { "set-cookie": `${COOKIE}=${state}; Path=/studio/yt; Max-Age=${STATE_TTL_S}; HttpOnly; Secure; SameSite=Lax` });
  }
  if (p === "/studio/yt/status" && m === "GET") {
    const conn = await getConn(env, org, chan); const q = await quotaModel(env);
    if (!conn) return json({ connected: false, configured: !!oauthClient(env) && !!env.STUDIO_ENC_KEY, can_connect: owner });
    const used = parseInt((await env.KV.get(K.used(pacificDay(now), org, chan))) || "0");
    return json(publicConn(conn, { can_manage: owner, policy: await resolvePolicy(env, conn, now), usage: { today: used, limit: Math.min((conn.settings || DEFAULT_SETTINGS).max_per_day, q.max_per_day_cap) }, project_audited: await auditPassed(env) }));
  }
  if (p === "/studio/yt/settings" && m === "POST") {
    if (!owner) return err(403, "forbidden", { need: "youtube.connect", role });
    const conn = await getConn(env, org, chan); if (!conn) return err(404, "not_connected");
    const r = normalizeSettings(b, conn.settings, (await quotaModel(env)).max_per_day_cap); if (r.error) return err(400, r.error, r.max ? { max: r.max } : {});
    conn.settings = r.settings; await kput(env, K.conn(org, chan), conn); return json({ ok: true, settings: conn.settings, policy: await resolvePolicy(env, conn, now) });
  }
  if (p === "/studio/yt/disconnect" && m === "POST") {
    if (!owner) return err(403, "forbidden", { need: "youtube.connect", role });
    const conn = await getConn(env, org, chan); if (!conn) return json({ ok: true, was_connected: false });
    let revoked = false; try { const d = await decryptSecret(env, conn.rt, aadOf(org, chan)); revoked = await revoke(fetchImpl, d.plaintext); } catch { /* key lost: still delete our copy */ }
    await Promise.all([env.KV.delete(K.conn(org, chan)), env.KV.delete(K.claim(conn.yt_channel_id)), syncStudioChannel(env, org, chan, { status: "not_connected" })]);
    return json({ ok: true, was_connected: true, revoked_at_google: revoked, note: revoked ? undefined : "Our copy is deleted. The customer can also remove access at https://myaccount.google.com/permissions" });
  }
  return err(404, "not_found");
}
