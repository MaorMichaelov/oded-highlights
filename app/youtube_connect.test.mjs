// Local tests for app/youtube_connect.js. No network: every Google endpoint is mocked, all secrets below are fake. Run: node app/youtube_connect.test.mjs
import { handleYouTube, buildAuthUrl, pkcePair, encryptSecret, decryptSecret, pacificDay, nextPacificReset, zonedToUtc, nextPublishAt, normalizeSettings, resolvePolicy, scopesFor, SCOPES } from "./youtube_connect.js";
import assert from "node:assert/strict";

class KV {
  constructor() { this.m = new Map(); }
  async get(k, type) { const v = this.m.get(k); if (v == null) return null; return type === "json" ? JSON.parse(v) : v; }
  async put(k, v) { this.m.set(k, String(v)); }
  async delete(k) { this.m.delete(k); }
  async list({ prefix = "", limit = 1000 } = {}) { return { keys: [...this.m.keys()].filter((k) => k.startsWith(prefix)).sort().slice(0, limit).map((name) => ({ name })) }; }
}
let n = 0; const ok = (name) => { n++; console.log("ok  " + name); };
const sha = async (t) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t)))].map((x) => x.toString(16).padStart(2, "0")).join("");
const FAKE_RT = "1//fake-refresh-token-NOT-REAL", FAKE_AT = "ya29.fake-access-token-NOT-REAL";
const KEY = Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString("base64");
const mkEnv = (extra = {}) => { const env = { KV: new KV(), YT_CLIENT_ID: "cid.apps.test", YT_CLIENT_SECRET: "csecret-fake", STUDIO_ENC_KEY: KEY, ...extra };
  env.KV.m.set("studio:cfg:worker_key", "wk_test"); return env; };
// studio.js layout: bearer token -> sha256 -> studio:s:<hash>; users studio:u:; memberships studio:m:<org>:<uid>
async function seedUser(env, uid, org, role, token) {
  env.KV.m.set(`studio:s:${await sha(token)}`, JSON.stringify({ uid, exp: Date.now() + 1e6 })); env.KV.m.set(`studio:u:${uid}`, JSON.stringify({ id: uid, email: uid + "@x.com" }));
  if (org) env.KV.m.set(`studio:m:${org}:${uid}`, JSON.stringify({ uid, role }));
}
// ---- Google mock ----
function mkGoogle(o = {}) {
  const g = { calls: [], revoked: [], channel: { id: "UCfake1", title: "Fake Channel" }, scope: SCOPES.upload + " " + SCOPES.readonly, refresh: FAKE_RT, refreshFails: null, ...o };
  g.fetch = async (url, opt = {}) => {
    const R = (j, s = 200) => ({ ok: s < 400, status: s, json: async () => j });
    const body = opt.body ? Object.fromEntries(new URLSearchParams(opt.body)) : {}; g.calls.push({ url, body, headers: opt.headers || {} });
    if (url === "https://oauth2.googleapis.com/token") {
      if (body.grant_type === "authorization_code") { if (body.code === "bad") return R({ error: "invalid_grant" }, 400); return R({ access_token: FAKE_AT, expires_in: 3599, scope: g.scope, ...(g.refresh ? { refresh_token: g.refresh } : {}) }); }
      if (body.grant_type === "refresh_token") { if (g.refreshFails) return R({ error: g.refreshFails }, g.refreshFails === "invalid_grant" ? 400 : 503); return R({ access_token: FAKE_AT + ".refreshed", expires_in: 3599 }); }
    }
    if (url === "https://oauth2.googleapis.com/revoke") { g.revoked.push(body.token); return R({}); }
    if (url.startsWith("https://www.googleapis.com/youtube/v3/channels")) { if (!g.channel) return R({ items: [] }); return R({ items: [{ id: g.channel.id, snippet: { title: g.channel.title, thumbnails: { default: { url: "https://t/x.jpg" } } } }] }); }
    return R({ error: "unexpected " + url }, 500);
  };
  return g;
}
const call = async (env, g, method, path, body, token, extra = {}) => {
  const req = new Request("https://app.test" + path, { method, headers: { "content-type": "application/json", ...(token ? { authorization: "Bearer " + token } : {}), ...extra }, body: body ? JSON.stringify(body) : undefined });
  const res = await handleYouTube(req, env, { fetchImpl: g.fetch }); if (!res) return null; const ct = res.headers.get("content-type") || ""; return { s: res.status, j: ct.includes("json") ? await res.json() : await res.text(), h: res.headers };
};

// ================= pure helpers =================
assert.equal(await handleYouTube(new Request("https://app.test/studio/api/me"), mkEnv(), {}), null); ok("returns null for foreign paths (caller falls through)");
const pk = await pkcePair(); assert.ok(pk.verifier.length >= 43 && pk.verifier.length <= 128);
assert.equal(pk.challenge, Buffer.from(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(pk.verifier))).toString("base64url")); ok("PKCE S256 challenge = base64url(sha256(verifier))");
{ const u = new URL(buildAuthUrl({ clientId: "cid", redirectUri: "https://app.test/studio/yt/callback", state: "st", challenge: "ch", scopes: scopesFor("basic"), loginHint: "a@x.com" }));
  assert.equal(u.origin + u.pathname, "https://accounts.google.com/o/oauth2/v2/auth"); const q = u.searchParams;
  assert.equal(q.get("access_type"), "offline"); assert.equal(q.get("response_type"), "code"); assert.equal(q.get("code_challenge_method"), "S256"); assert.equal(q.get("state"), "st");
  assert.match(q.get("prompt"), /consent/); assert.match(q.get("prompt"), /select_account/); assert.equal(q.get("scope"), SCOPES.upload + " " + SCOPES.readonly); assert.equal(q.get("login_hint"), "a@x.com");
  assert.ok(!scopesFor("basic").includes(SCOPES.manage) && scopesFor("manage").includes(SCOPES.manage)); ok("consent URL params"); }
{ const env = mkEnv(); const rec = await encryptSecret(env, FAKE_RT, "o_1:c_1"); assert.ok(!JSON.stringify(rec).includes(FAKE_RT));
  assert.equal((await decryptSecret(env, rec, "o_1:c_1")).plaintext, FAKE_RT);
  await assert.rejects(decryptSecret(env, rec, "o_2:c_1"), "ciphertext must not decrypt under another customer's aad");
  const rec2 = await encryptSecret(env, FAKE_RT, "o_1:c_1"); assert.notEqual(rec.iv, rec2.iv); assert.notEqual(rec.ct, rec2.ct);
  const tampered = { ...rec, ct: rec.ct.slice(0, -4) + (rec.ct.endsWith("AAAA") ? "BBBB" : "AAAA") }; await assert.rejects(decryptSecret(env, tampered, "o_1:c_1"));
  const rotated = { ...env, STUDIO_ENC_KEY: Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString("base64"), STUDIO_ENC_KEY_OLD: KEY };
  const d = await decryptSecret(rotated, rec, "o_1:c_1"); assert.equal(d.plaintext, FAKE_RT); assert.equal(d.rotated, true);
  await assert.rejects(decryptSecret({ ...env, STUDIO_ENC_KEY: Buffer.from(new Uint8Array(32)).toString("base64") }, rec, "o_1:c_1")); ok("AES-GCM: round trip, aad binding, tamper, key rotation"); }
{ // Pacific day / reset (PST in Nov = UTC-8, PDT in Jul = UTC-7)
  assert.equal(pacificDay(Date.parse("2026-11-18T07:59:00Z")), "2026-11-17"); assert.equal(pacificDay(Date.parse("2026-11-18T08:00:00Z")), "2026-11-18");
  assert.equal(new Date(nextPacificReset(Date.parse("2026-11-17T21:00:00Z"))).toISOString(), "2026-11-18T08:00:00.000Z"); assert.equal(new Date(nextPacificReset(Date.parse("2026-07-10T12:00:00Z"))).toISOString(), "2026-07-11T07:00:00.000Z");
  assert.equal(new Date(zonedToUtc(2026, 11, 18, 18, 0, "Asia/Jerusalem")).toISOString(), "2026-11-18T16:00:00.000Z"); assert.equal(new Date(zonedToUtc(2026, 7, 18, 18, 0, "Asia/Jerusalem")).toISOString(), "2026-07-18T15:00:00.000Z"); ok("Pacific quota day + DST-correct zoned times"); }
{ const sc = { tz: "Asia/Jerusalem", times: ["12:00", "18:00"], per_day: 1, lead_min: 60 };
  const now = Date.parse("2026-11-18T09:00:00Z");                                  // 11:00 local
  assert.equal(nextPublishAt(sc, now, []), "2026-11-18T10:00:00.000Z");            // 12:00 local is >60 min ahead
  assert.equal(nextPublishAt(sc, Date.parse("2026-11-18T09:30:00Z"), []), "2026-11-18T16:00:00.000Z");   // 11:30 local: 12:00 is only 30 min away -> 18:00
  assert.equal(nextPublishAt(sc, now, ["2026-11-18T10:00:00.000Z"]), "2026-11-19T10:00:00.000Z");        // per_day=1 and today already has one -> tomorrow
  assert.equal(nextPublishAt({ ...sc, per_day: 2 }, now, ["2026-11-18T10:00:00.000Z"]), "2026-11-18T16:00:00.000Z");
  assert.equal(nextPublishAt({ ...sc, per_day: 2 }, now, []) < nextPublishAt({ ...sc, per_day: 2 }, now, ["2026-11-18T10:00:00.000Z"]), true); ok("nextPublishAt: lead time, per-day cap, taken slots"); }
{ assert.equal(normalizeSettings({ mode: "nope" }).error, "bad_mode"); assert.equal(normalizeSettings({ max_per_day: 0 }).error, "bad_max_per_day"); assert.equal(normalizeSettings({ max_per_day: 99 }, null, 20).error, "bad_max_per_day");
  assert.equal(normalizeSettings({ schedule: { tz: "Mars/Base" } }).error, "bad_tz"); assert.equal(normalizeSettings({ schedule: { times: ["25:00"] } }).error, "bad_times"); assert.equal(normalizeSettings({ schedule: { lead_min: 1 } }).error, "bad_lead_min");
  assert.equal(normalizeSettings({ mode: "public" }).error, "confirm_public_required"); const r = normalizeSettings({ mode: "public", confirm_public: true }); assert.ok(r.settings.public_ack_at);
  assert.equal(normalizeSettings({ mode: "schedule", schedule: { times: ["21:00", "09:00", "09:00"] } }).settings.schedule.times.join(), "09:00,21:00"); ok("settings validation"); }
{ const e0 = mkEnv(); const conn = { settings: { mode: "schedule", max_per_day: 3, schedule: { tz: "UTC", times: ["10:00"], per_day: 1, lead_min: 15 } } };
  let p = await resolvePolicy(e0, conn, Date.parse("2026-11-18T00:00:00Z")); assert.equal(p.privacy, "private"); assert.equal(p.publish_at, null); assert.equal(p.downgraded, "project_not_audited");
  const e1 = mkEnv({ YT_AUDIT_PASSED: "1" }); p = await resolvePolicy(e1, conn, Date.parse("2026-11-18T00:00:00Z")); assert.equal(p.publish_at, "2026-11-18T10:00:00.000Z"); assert.equal(p.privacy, "private"); assert.equal(p.downgraded, null);
  p = await resolvePolicy(e1, { settings: { mode: "public", public_ack_at: null } }); assert.equal(p.privacy, "private"); assert.equal(p.downgraded, "public_not_confirmed");
  p = await resolvePolicy(e1, { settings: { mode: "public", public_ack_at: "x" } }); assert.equal(p.privacy, "public");
  p = await resolvePolicy(e0, { settings: { mode: "private" } }); assert.equal(p.privacy, "private"); assert.equal(p.downgraded, null); ok("policy: private by default, schedule/public only after the audit flag"); }

// ================= the flow =================
const ORG = "o_aaaa1111", ORG2 = "o_bbbb2222", CH = "c_cccc3333";
const env = mkEnv(); const g = mkGoogle();
await seedUser(env, "u_owner", ORG, "owner", "tok_owner"); await seedUser(env, "u_edit", ORG, "editor", "tok_edit"); await seedUser(env, "u_other", ORG2, "owner", "tok_other"); await seedUser(env, "u_nomem", null, null, "tok_nomem");
env.KV.m.set(`studio:c:${ORG}:${CH}`, JSON.stringify({ id: CH, org: ORG, platform: "kick", slug: "x", status: "verified", yt: { status: "not_connected" } }));
env.KV.m.set("studio:j:j_job1", JSON.stringify({ id: "j_job1", org: ORG, channel: CH, status: "running" })); env.KV.m.set("studio:j:j_other", JSON.stringify({ id: "j_other", org: ORG2, channel: "c_zzzz", status: "running" }));
const cookieFrom = (h) => (h.get("set-cookie") || "").split(";")[0];

let r = await call(env, g, "POST", "/studio/yt/start", { org_id: ORG, channel_id: CH }); assert.equal(r.s, 401);
r = await call(env, g, "POST", "/studio/yt/start", { org_id: ORG, channel_id: CH }, "tok_edit"); assert.equal(r.s, 403);
r = await call(env, g, "POST", "/studio/yt/start", { org_id: ORG, channel_id: CH }, "tok_other"); assert.equal(r.s, 404, "other org's owner must not even learn the org exists");
r = await call(env, g, "POST", "/studio/yt/start", { org_id: ORG, channel_id: CH }, "tok_nomem"); assert.equal(r.s, 404);
r = await call(mkEnvNoSecret(), g, "POST", "/studio/yt/start", { org_id: ORG }, "tok_owner").catch(() => null);
function mkEnvNoSecret() { const e = mkEnv(); delete e.STUDIO_ENC_KEY; return e; }
ok("start: auth, role, org isolation");
{ const e2 = mkEnvNoSecret(); await seedUser(e2, "u_owner", ORG, "owner", "tok_owner"); const rr = await call(e2, g, "POST", "/studio/yt/start", { org_id: ORG }, "tok_owner"); assert.equal(rr.s, 503); assert.equal(rr.j.error, "enc_key_missing");
  const e3 = mkEnv(); delete e3.YT_CLIENT_ID; await seedUser(e3, "u_owner", ORG, "owner", "tok_owner"); assert.equal((await call(e3, g, "POST", "/studio/yt/start", { org_id: ORG }, "tok_owner")).j.error, "yt_not_configured"); ok("start refuses without client / encryption key"); }

r = await call(env, g, "GET", `/studio/yt/status?org_id=${ORG}&channel_id=${CH}`, null, "tok_owner"); assert.equal(r.j.connected, false); assert.equal(r.j.configured, true); assert.equal(r.j.can_connect, true);

async function startFlow(e, token = "tok_owner", body = { org_id: ORG, channel_id: CH }) {
  const s = await call(e, g, "POST", "/studio/yt/start", body, token); assert.equal(s.s, 200); const url = new URL(s.j.url); const state = url.searchParams.get("state");
  assert.equal(url.searchParams.get("redirect_uri"), "https://app.test/studio/yt/callback"); assert.ok(url.searchParams.get("code_challenge")); return { state, cookie: cookieFrom(s.h), setCookie: s.h.get("set-cookie") };
}
let f = await startFlow(env); assert.match(f.setCookie, /HttpOnly/); assert.match(f.setCookie, /Secure/); assert.match(f.setCookie, /SameSite=Lax/); ok("start returns consent url + hardened state cookie");

// browser mismatch (attacker's link opened in the victim's browser: no cookie / wrong cookie)
r = await call(env, g, "GET", `/studio/yt/callback?state=${f.state}&code=abc`, null, null, {}); assert.match(r.j, /error=browser_mismatch/); assert.equal(g.calls.filter((c) => c.body.grant_type === "authorization_code").length, 0, "no token exchange without the cookie");
r = await call(env, g, "GET", `/studio/yt/callback?state=${f.state}&code=abc`, null, null, { cookie: f.cookie }); assert.match(r.j, /error=state_invalid/, "state is single-use (burned by the failed attempt)");
f = await startFlow(env); r = await call(env, g, "GET", `/studio/yt/callback?state=forged&code=abc`, null, null, { cookie: "ytstate=forged" }); assert.match(r.j, /error=state_invalid/); ok("callback: CSRF protections (cookie binding, single-use state, forged state)");
f = await startFlow(env); r = await call(env, g, "GET", `/studio/yt/callback?state=${f.state}&error=access_denied`, null, null, { cookie: f.cookie }); assert.match(r.j, /error=access_denied/);
{ const g2 = mkGoogle({ scope: SCOPES.readonly }); f = await startFlow(env); const rr = await call(env, g2, "GET", `/studio/yt/callback?state=${f.state}&code=ok`, null, null, { cookie: f.cookie }); assert.match(rr.j, /error=missing_scope/); assert.equal(g2.revoked.length, 1, "token revoked when we refuse the grant"); }
{ const g2 = mkGoogle({ refresh: null }); f = await startFlow(env); const rr = await call(env, g2, "GET", `/studio/yt/callback?state=${f.state}&code=ok`, null, null, { cookie: f.cookie }); assert.match(rr.j, /error=no_refresh_token/); }
{ const g2 = mkGoogle({ channel: null }); f = await startFlow(env); const rr = await call(env, g2, "GET", `/studio/yt/callback?state=${f.state}&code=ok`, null, null, { cookie: f.cookie }); assert.match(rr.j, /error=no_youtube_channel/); assert.equal(g2.revoked.length, 1); }
{ f = await startFlow(env); const rr = await call(env, g, "GET", `/studio/yt/callback?state=${f.state}&code=bad`, null, null, { cookie: f.cookie }); assert.match(rr.j, /error=token_exchange_failed/); }
ok("callback: denied / missing scope / no refresh token / no channel / bad code all fail closed");
assert.equal(await env.KV.get(`studio:yt:c:${ORG}:${CH}`), null, "nothing stored by failed attempts");

// role removed between start and callback
{ f = await startFlow(env); env.KV.m.set(`studio:m:${ORG}:u_owner`, JSON.stringify({ role: "viewer" })); const rr = await call(env, g, "GET", `/studio/yt/callback?state=${f.state}&code=ok`, null, null, { cookie: f.cookie }); assert.match(rr.j, /error=forbidden/); env.KV.m.set(`studio:m:${ORG}:u_owner`, JSON.stringify({ role: "owner" })); ok("callback re-checks the owner role"); }

// happy path
f = await startFlow(env); r = await call(env, g, "GET", `/studio/yt/callback?state=${f.state}&code=good`, null, null, { cookie: f.cookie }); assert.equal(r.s, 200); assert.match(r.j, /youtube=connected&org=o_aaaa1111/);
const ex = g.calls.find((c) => c.body.grant_type === "authorization_code" && c.body.code === "good"); assert.ok(ex.body.code_verifier && ex.body.redirect_uri === "https://app.test/studio/yt/callback" && ex.body.client_secret === "csecret-fake");
const rec = JSON.parse(await env.KV.get(`studio:yt:c:${ORG}:${CH}`)); assert.equal(rec.yt_channel_id, "UCfake1"); assert.equal(rec.yt_channel_title, "Fake Channel"); assert.equal(rec.status, "connected"); assert.equal(rec.settings.mode, "private");
let allKv = [...env.KV.m.entries()].map(([k, v]) => k + "=" + v).join("\n"); assert.ok(!allKv.includes(FAKE_RT), "refresh token never in KV in plaintext"); assert.ok(!allKv.includes(FAKE_AT), "access token never stored"); assert.ok(!allKv.includes("csecret-fake"));
assert.equal(JSON.parse(env.KV.m.get(`studio:c:${ORG}:${CH}`)).yt.status, "connected"); assert.equal(JSON.parse(env.KV.m.get(`studio:c:${ORG}:${CH}`)).yt.channel_id, "UCfake1");
ok("callback happy path: channel stored, refresh token encrypted, studio channel record synced");

r = await call(env, g, "GET", `/studio/yt/status?org_id=${ORG}&channel_id=${CH}`, null, "tok_edit"); assert.equal(r.j.connected, true); assert.equal(r.j.channel.title, "Fake Channel"); assert.equal(r.j.can_manage, false);
assert.ok(!JSON.stringify(r.j).includes(FAKE_RT) && !JSON.stringify(r.j).includes("ct\"") && !r.j.rt, "status exposes no secret material"); ok("status: visible to members, no secrets");

// the same YouTube channel cannot be attached to a second customer
{ f = await startFlow(env, "tok_other", { org_id: ORG2, channel_id: "c_zzzz" }); const rr = await call(env, g, "GET", `/studio/yt/callback?state=${f.state}&code=good2`, null, null, { cookie: f.cookie }); assert.match(rr.j, /error=channel_already_connected/); assert.equal(await env.KV.get(`studio:yt:c:${ORG2}:c_zzzz`), null); ok("one YouTube channel can belong to one customer only"); }

// settings
r = await call(env, g, "POST", "/studio/yt/settings", { org_id: ORG, channel_id: CH, mode: "schedule" }, "tok_edit"); assert.equal(r.s, 403);
r = await call(env, g, "POST", "/studio/yt/settings", { org_id: ORG, channel_id: CH, mode: "public" }, "tok_owner"); assert.equal(r.j.error, "confirm_public_required");
r = await call(env, g, "POST", "/studio/yt/settings", { org_id: ORG, channel_id: CH, mode: "schedule", max_per_day: 2, schedule: { tz: "Asia/Jerusalem", times: ["18:00"], per_day: 1 } }, "tok_owner"); assert.equal(r.s, 200); assert.equal(r.j.policy.privacy, "private"); assert.equal(r.j.policy.downgraded, "project_not_audited");
r = await call(env, g, "POST", "/studio/yt/settings", { org_id: ORG, channel_id: CH, mode: "private", max_per_day: 2 }, "tok_owner"); assert.equal(r.j.settings.mode, "private"); ok("settings: owner only, validated, downgrade explained");

// ---- internal token endpoint ----
const tokCall = (body, key = "wk_test") => call(env, g, "POST", "/internal/yt/token", body, null, { "x-worker-key": key });
r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_job1" }, "wrong"); assert.equal(r.s, 401);
r = await call(env, g, "POST", "/internal/yt/token", { org_id: ORG, job_id: "j_job1" }, "tok_owner"); assert.equal(r.s, 401, "a customer session token is not a worker key");
r = await tokCall({ org_id: ORG, channel_id: CH }); assert.equal(r.s, 403, "job_id required");
r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_other" }); assert.equal(r.s, 403, "job of another customer");
r = await tokCall({ org_id: ORG2, channel_id: "c_zzzz", job_id: "j_other" }); assert.equal(r.s, 404, "customer without a connection");
r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_job1" }); assert.equal(r.s, 200); assert.equal(r.j.access_token, FAKE_AT + ".refreshed"); assert.equal(r.j.channel_id, "UCfake1"); assert.equal(r.j.policy.privacy, "private"); assert.equal(r.j.policy.publish_at, null);
assert.equal(r.j.reserved_units, 1600); assert.ok(!JSON.stringify(r.j).includes(FAKE_RT)); const rf = g.calls.filter((c) => c.body.grant_type === "refresh_token").at(-1); assert.equal(rf.body.refresh_token, FAKE_RT, "server decrypted and used the stored refresh token");
r = await tokCall({ org_id: ORG, job_id: "j_job1" }); assert.equal(r.s, 200, "channel defaults to the job's channel"); assert.equal(r.j.quota.customer_used_today, 2);
r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_job1" }); assert.equal(r.s, 429); assert.equal(r.j.error, "customer_daily_limit"); assert.ok(r.j.retry_after_s >= 60); ok("token endpoint: worker auth, job binding, per-customer daily limit");

r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_job1", renew: true }); assert.equal(r.s, 200, "renew works even at the daily limit"); assert.equal(r.j.reserved_units, 0); assert.equal(r.j.quota.customer_used_today, 2); ok("renew: no second reservation");
// report refunds a reservation when nothing was uploaded; frees a slot
r = await call(env, g, "POST", "/internal/yt/report", { org_id: ORG, channel_id: CH, job_id: "j_job1", event: "failed", units: 1600 }, null, { "x-worker-key": "wk_test" }); assert.equal(r.s, 200);
r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_job1" }); assert.equal(r.s, 200); ok("report(failed) refunds the reservation");
r = await call(env, g, "POST", "/internal/yt/report", { org_id: ORG, channel_id: CH, job_id: "j_job1", event: "uploaded", video_id: "vid123", privacy: "private" }, null, { "x-worker-key": "wk_test" }); assert.equal(r.s, 200);
r = await call(env, g, "GET", `/studio/yt/status?org_id=${ORG}&channel_id=${CH}`, null, "tok_owner"); assert.equal(r.j.last_upload.video_id, "vid123"); assert.equal(r.j.usage.today, 2);

// project quota: global budget (default model: 10,000 units, 1,600 per upload, 500 headroom) -> 5 uploads, the 6th is refused for the whole project
{ const e = mkEnv(); await seedUser(e, "u_owner", ORG, "owner", "tok_owner"); e.KV.m.set("studio:j:j1", JSON.stringify({ org: ORG, channel: CH })); const gg = mkGoogle(); const c = (b) => call(e, gg, "POST", "/internal/yt/token", b, null, { "x-worker-key": "wk_test" });
  let ff = await startFlow(e); await call(e, gg, "GET", `/studio/yt/callback?state=${ff.state}&code=good`, null, null, { cookie: ff.cookie });
  e.KV.m.set("studio:cfg:yt_quota", JSON.stringify({ max_per_day_cap: 50 })); await call(e, gg, "POST", "/studio/yt/settings", { org_id: ORG, channel_id: CH, max_per_day: 50 }, "tok_owner");
  const codes = []; for (let i = 0; i < 7; i++) codes.push((await c({ org_id: ORG, channel_id: CH, job_id: "j1" })).s); assert.deepEqual(codes, [200, 200, 200, 200, 200, 429, 429]);
  const lim = await c({ org_id: ORG, channel_id: CH, job_id: "j1" }); assert.equal(lim.j.error, "quota_exhausted"); assert.equal(lim.j.scope, "project");
  e.KV.m.set("studio:cfg:yt_quota", JSON.stringify({ daily_units: 100, upload_cost: 1, thumb_cost: 0, headroom_units: 0, max_per_day_cap: 50 })); assert.equal((await c({ org_id: ORG, channel_id: CH, job_id: "j1" })).s, 429, "exhausted flag/used units persist");
  // quota_exceeded from Google closes the project for the rest of the Pacific day
  const e2 = mkEnv(); await seedUser(e2, "u_owner", ORG, "owner", "tok_owner"); e2.KV.m.set("studio:j:j1", JSON.stringify({ org: ORG, channel: CH })); const g2 = mkGoogle(); ff = await startFlow(e2); await call(e2, g2, "GET", `/studio/yt/callback?state=${ff.state}&code=good`, null, null, { cookie: ff.cookie });
  const c2 = (path, b) => call(e2, g2, "POST", path, b, null, { "x-worker-key": "wk_test" }); assert.equal((await c2("/internal/yt/token", { org_id: ORG, channel_id: CH, job_id: "j1" })).s, 200);
  await c2("/internal/yt/report", { org_id: ORG, channel_id: CH, job_id: "j1", event: "quota_exceeded", units: 1600 }); const after = await c2("/internal/yt/token", { org_id: ORG, channel_id: CH, job_id: "j1" }); assert.equal(after.s, 429); assert.equal(after.j.error, "quota_exhausted"); ok("project quota guard + quota_exceeded closes the day"); }

// refresh token revoked by the user -> needs_reconnect, surfaced in status
g.refreshFails = "invalid_grant"; env.KV.m.delete(`studio:yt:u:${pacificDay()}:${ORG}:${CH}`); env.KV.m.delete(`studio:yt:g:${pacificDay()}`);
r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j1x" }); // wrong job id first
env.KV.m.set("studio:j:j_job1", JSON.stringify({ id: "j_job1", org: ORG, channel: CH })); r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_job1" }); assert.equal(r.s, 409); assert.equal(r.j.error, "needs_reconnect");
r = await call(env, g, "GET", `/studio/yt/status?org_id=${ORG}&channel_id=${CH}`, null, "tok_owner"); assert.equal(r.j.status, "needs_reconnect"); assert.equal(JSON.parse(env.KV.m.get(`studio:c:${ORG}:${CH}`)).yt.status, "needs_reconnect");
g.refreshFails = "backendError"; r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_job1" }); assert.equal(r.s, 409, "stays needs_reconnect until the customer reconnects");
f = await startFlow(env); await call(env, g, "GET", `/studio/yt/callback?state=${f.state}&code=good3`, null, null, { cookie: f.cookie }); g.refreshFails = null;
r = await call(env, g, "GET", `/studio/yt/status?org_id=${ORG}&channel_id=${CH}`, null, "tok_owner"); assert.equal(r.j.status, "connected"); assert.equal(r.j.settings.max_per_day, 2, "settings survive a reconnect"); ok("invalid_grant -> needs_reconnect -> reconnect restores");
{ g.refreshFails = "backendError"; const rr = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_job1" }); assert.equal(rr.s, 502); assert.equal(rr.j.transient, true); g.refreshFails = null; assert.equal((await call(env, g, "GET", `/studio/yt/status?org_id=${ORG}&channel_id=${CH}`, null, "tok_owner")).j.status, "connected"); ok("transient Google errors do not disconnect"); }

// a connection record moved to another customer's key cannot be decrypted (aad binding)
{ const raw = env.KV.m.get(`studio:yt:c:${ORG}:${CH}`); env.KV.m.set(`studio:yt:c:${ORG2}:c_zzzz`, raw); const rr = await tokCall({ org_id: ORG2, channel_id: "c_zzzz", job_id: "j_other" }); assert.equal(rr.s, 500); assert.equal(rr.j.error, "decrypt_failed"); env.KV.m.delete(`studio:yt:c:${ORG2}:c_zzzz`); ok("copied record is useless under another customer key"); }

// disconnect
r = await call(env, g, "POST", "/studio/yt/disconnect", { org_id: ORG, channel_id: CH }, "tok_edit"); assert.equal(r.s, 403);
const before = g.revoked.length; r = await call(env, g, "POST", "/studio/yt/disconnect", { org_id: ORG, channel_id: CH }, "tok_owner"); assert.equal(r.s, 200); assert.equal(r.j.revoked_at_google, true); assert.equal(g.revoked.length, before + 1); assert.equal(g.revoked.at(-1), FAKE_RT);
assert.equal(await env.KV.get(`studio:yt:c:${ORG}:${CH}`), null); assert.equal(await env.KV.get("studio:yt:ch:UCfake1"), null); assert.equal(JSON.parse(env.KV.m.get(`studio:c:${ORG}:${CH}`)).yt.status, "not_connected");
r = await tokCall({ org_id: ORG, channel_id: CH, job_id: "j_job1" }); assert.equal(r.s, 404); r = await call(env, g, "POST", "/studio/yt/disconnect", { org_id: ORG, channel_id: CH }, "tok_owner"); assert.equal(r.j.was_connected, false); ok("disconnect: revokes at Google, deletes record + claim, token endpoint stops");
// the channel is free again for another customer
{ f = await startFlow(env, "tok_other", { org_id: ORG2, channel_id: "c_zzzz" }); const rr = await call(env, g, "GET", `/studio/yt/callback?state=${f.state}&code=good4`, null, null, { cookie: f.cookie }); assert.match(rr.j, /youtube=connected/); ok("channel can be re-claimed after disconnect"); }

// nothing in any response or in KV ever contained the fake secrets in plaintext; the code does not console.log
allKv = [...env.KV.m.entries()].map(([k, v]) => k + "=" + v).join("\n"); assert.ok(!allKv.includes(FAKE_RT) && !allKv.includes(FAKE_AT));
import { readFileSync } from "node:fs"; assert.ok(!/console\.(log|error|warn|info|debug)/.test(readFileSync(new URL("./youtube_connect.js", import.meta.url), "utf8")), "module must never log"); ok("no plaintext secrets in KV, no logging in the module");
console.log(`\n${n} checks passed`);
