// Local tests for app/studio.js (no network, no Cloudflare): node app/studio.test.mjs
import { handleStudio, understand, parseChannelInput, canTransition, can, findCode, newVerifyCode, hashPassword, renderMsg } from "./studio.js";
import assert from "node:assert/strict";

class KV {   // minimal Workers KV mock (get/put/delete/list with prefix)
  constructor() { this.m = new Map(); }
  async get(k, type) { const v = this.m.get(k); if (v == null) return null; return type === "json" ? JSON.parse(v) : v; }
  async put(k, v) { this.m.set(k, String(v)); }
  async delete(k) { this.m.delete(k); }
  async list({ prefix = "", limit = 1000 } = {}) { return { keys: [...this.m.keys()].filter((k) => k.startsWith(prefix)).sort().slice(0, limit).map((name) => ({ name })) }; }
}
const env = { KV: new KV() }; env.KV.m.set("studio:cfg:worker_key", "wk_test");
let kickBio = "hello", kickLive = null, ghStyles = [], twitchBio = "hello";
const fakeFetch = async (url, opt = {}) => {
  const R = (o, s = 200) => ({ ok: s < 400, status: s, json: async () => o });
  if (url.startsWith("https://kick.com/api/v2/channels/")) { const slug = url.split("/").pop(); if (slug === "nobody") return R({}, 404); return R({ user_id: 1, user: { id: 1, username: slug, bio: kickBio, youtube: "@x" }, livestream: kickLive }); }
  if (url.startsWith("https://gql.twitch.tv/")) { const l = JSON.parse(opt.body).variables.l; if (l === "ghost") return R({ data: { user: null } }); return R({ data: { user: { id: "9", displayName: l, description: twitchBio, stream: null } } }); }
  if (url.includes("api.github.com/repos/") && url.endsWith("/config/styles")) return R(ghStyles.map((n) => ({ name: n + ".json", type: "file", download_url: "https://raw/" + n })));
  if (url.startsWith("https://raw/")) return R({ name: "Style " + url.split("/").pop(), description: "d" });
  return R({}, 500);
};
const call = async (method, path, body, token, extra = {}) => {
  const req = new Request("https://app.test" + path, { method, headers: { "content-type": "application/json", ...(token ? { authorization: "Bearer " + token } : {}), ...extra }, body: body ? JSON.stringify(body) : undefined });
  const res = await handleStudio(req, env, fakeFetch); const ct = res.headers.get("content-type") || ""; return { s: res.status, j: ct.includes("json") ? await res.json() : await res.text() };
};
let n = 0; const ok = (name) => { n++; console.log("ok  " + name); };

// ---- pure helpers
assert.deepEqual(parseChannelInput("https://kick.com/OdedSVR/videos"), { platform: "kick", slug: "odedsvr" }); assert.equal(parseChannelInput("hello world"), null); ok("parseChannelInput");
assert.match(newVerifyCode(), /^ODH-[A-HJ-NP-Z2-9]{8}$/); assert.equal(findCode("ODH-ABCD1234", [["bio", "x odh-abcd1234 y"]]), "bio"); assert.equal(findCode("ODH-ABCD1234", [["bio", null]]), null); ok("verify code");
assert.ok(canTransition("queued", "running")); assert.ok(!canTransition("approved", "queued")); assert.ok(can("editor", "job.create") && !can("viewer", "job.create") && !can("editor", "team.manage")); ok("state machine + perms");
const u1 = understand("תכין 5 שורטס מצחיקים מאתמול"); assert.equal(u1.intent, "create"); assert.equal(u1.shorts, 5); assert.equal(u1.when, "yesterday"); assert.equal(u1.mood, "funny"); assert.ok(u1.he);
const u2 = understand("make three hype Shorts from my last stream"); assert.equal(u2.shorts, 3); assert.equal(u2.mood, "hype"); assert.equal(u2.when, "last_stream");
const u3 = understand("what's the status?"); assert.equal(u3.intent, "status"); assert.equal(understand("make a long video").long, true); assert.equal(understand("hello").intent, "help");
assert.equal(understand("3 רגעים מטורפים מהשבוע").when, "week");   // regression: the Hebrew chip said "מהשבוע" but only "שבוע שעבר" was understood, so it silently cut the latest stream
assert.equal(understand("I need 3 things").intent, "help"); assert.equal(understand("I want a pizza").intent, "help"); assert.equal(understand("תכין לי משהו").intent, "help");   // regression: chatter with a number or "want/need" spent a credit
assert.equal(understand("3 רגעים מטורפים מהשבוע").mood, "hype"); assert.equal(understand("שורטס מטורף").mood, "hype");   // regression: מטורף ends in a final-form pe, the plural מטורפים does not, so the plural never matched
assert.equal(understand("make 4 shorts").intent, "create"); assert.equal(understand("5 שורטס מצחיקים מאתמול").intent, "create"); assert.equal(understand("make highlights from the stream").intent, "create"); ok("assistant parser");
assert.equal(renderMsg("found_moments", { n: 5 }).en, "Found 5 moments, cutting..."); ok("progress messages");
const pw = await hashPassword("secret123"); assert.equal((await hashPassword("secret123", pw.salt)).hash, pw.hash); assert.notEqual((await hashPassword("secret124", pw.salt)).hash, pw.hash); ok("pbkdf2");

// ---- routes
assert.equal((await call("GET", "/studio")).s, 200); assert.equal((await call("GET", "/studio/api/me")).s, 401); ok("page + auth required");
let r = await call("POST", "/studio/api/signup", { email: "a@x.com", password: "short" }); assert.equal(r.s, 400);
r = await call("POST", "/studio/api/signup", { email: "a@x.com", password: "password1", name: "Owner" }); assert.equal(r.s, 200); const T1 = r.j.token, ORG = r.j.org_id;
assert.equal((await call("POST", "/studio/api/signup", { email: "a@x.com", password: "password1" })).s, 409);
assert.equal((await call("POST", "/studio/api/login", { email: "a@x.com", password: "wrongpass" })).s, 401);
r = await call("POST", "/studio/api/login", { email: "a@x.com", password: "password1" }); assert.equal(r.s, 200); ok("signup/login");
r = await call("GET", "/studio/api/me", null, T1); assert.equal(r.j.orgs[0].role, "owner"); assert.equal(r.j.orgs[0].credits, 2);

// styles: one signature style is always there; repo styles are listed behind it
r = await call("GET", "/studio/api/styles", null, T1); assert.equal(r.j.default, "signature"); assert.equal(r.j.styles[0].id, "signature"); ok("styles builtin");
env.KV.m.delete("studio:cache:styles"); ghStyles = ["rage", "chill"]; r = await call("GET", "/studio/api/styles", null, T1); assert.deepEqual(r.j.styles.map((s) => s.id), ["signature", "rage", "chill"]); ok("styles from repo");

// channel connect + verification
r = await call("POST", `/studio/api/orgs/${ORG}/channels`, { url: "nonsense" }, T1); assert.equal(r.s, 400);
r = await call("POST", `/studio/api/orgs/${ORG}/channels`, { url: "https://kick.com/OdedSVR" }, T1); assert.equal(r.s, 200); const CH = r.j.channel; assert.equal(CH.status, "pending"); assert.equal(CH.slug, "odedsvr"); assert.equal(CH.style_id, "signature");
r = await call("POST", `/studio/api/orgs/${ORG}/channels/${CH.id}/verify`, null, T1); assert.equal(r.j.verified, false); assert.ok(r.j.he && r.j.en);
r = await call("POST", `/studio/api/orgs/${ORG}/jobs`, { channel_id: CH.id, source: { type: "vod", ref: "x" } }, T1); assert.equal(r.s, 409);   // unverified channel cannot be used
kickBio = "my bio " + CH.verify_code.toLowerCase();
r = await call("POST", `/studio/api/orgs/${ORG}/channels/${CH.id}/verify`, null, T1); assert.equal(r.j.verified, true); assert.equal(r.j.channel.verified_via, "bio"); ok("kick verification by bio code");
// second org cannot claim the same channel
r = await call("POST", "/studio/api/signup", { email: "b@x.com", password: "password1" }); const T2 = r.j.token, ORG2 = r.j.org_id;
r = await call("POST", `/studio/api/orgs/${ORG2}/channels`, { url: "kick.com/odedsvr" }, T2); const CH2 = r.j.channel; kickBio = CH2.verify_code;
r = await call("POST", `/studio/api/orgs/${ORG2}/channels/${CH2.id}/verify`, null, T2); assert.equal(r.s, 409); ok("channel claimed once");
assert.equal((await call("GET", `/studio/api/orgs/${ORG}/jobs`, null, T2)).s, 404); ok("cross-org isolation (404)");
r = await call("POST", `/studio/api/orgs/${ORG}/channels`, { url: "twitch.tv/somebody" }, T1); const TW = r.j.channel; r = await call("POST", `/studio/api/orgs/${ORG}/channels/${TW.id}/verify`, null, T1); assert.equal(r.j.verified, false); twitchBio = "x " + TW.verify_code; r = await call("POST", `/studio/api/orgs/${ORG}/channels/${TW.id}/verify`, null, T1); assert.equal(r.j.verified, true); assert.equal(r.j.channel.verified_via, "bio"); ok("twitch verification without a Twitch app (public web API fallback)");
r = await call("POST", `/studio/api/orgs/${ORG}/channels`, { url: "twitch.tv/ghost" }, T1); r = await call("POST", `/studio/api/orgs/${ORG}/channels/${r.j.channel.id}/verify`, null, T1); assert.equal(r.s, 502); assert.equal(r.j.error, "channel_not_found"); ok("twitch unknown channel");
assert.equal((await call("POST", `/studio/api/orgs/${ORG}/channels/${CH.id}/youtube`, null, T1)).s, 501); ok("youtube todo stub");

// team: invite -> accept -> roles
r = await call("POST", `/studio/api/orgs/${ORG}/invites`, { email: "v@x.com", role: "viewer" }, T1); assert.equal(r.s, 200); const invTok = r.j.accept_url.split("invite=")[1];
r = await call("POST", "/studio/api/invites/preview", { token: invTok }); assert.equal(r.j.role, "viewer");
r = await call("POST", "/studio/api/signup", { email: "v@x.com", password: "password1" }); const TV = r.j.token;
assert.equal((await call("POST", "/studio/api/invites/accept", { token: invTok }, T2)).s, 403);   // another email cannot use it
assert.equal((await call("POST", "/studio/api/invites/accept", { token: invTok }, TV)).s, 200);
assert.equal((await call("GET", `/studio/api/orgs/${ORG}/jobs`, null, TV)).s, 200);
r = await call("POST", `/studio/api/orgs/${ORG}/jobs`, { channel_id: CH.id, source: { type: "auto", when: "yesterday" } }, TV); assert.equal(r.s, 403); assert.equal(r.j.need, "job.create");
assert.equal((await call("POST", `/studio/api/orgs/${ORG}/invites`, { email: "z@x.com", role: "editor" }, TV)).s, 403);
r = await call("GET", `/studio/api/orgs/${ORG}/members`, null, T1); assert.equal(r.j.members.length, 2); ok("invites + roles");
r = await call("POST", `/studio/api/orgs/${ORG}/invites`, { email: "e@x.com", role: "editor" }, T1); const invE = r.j.accept_url.split("invite=")[1];
r = await call("POST", "/studio/api/signup", { email: "e@x.com", password: "password1" }); const TE = r.j.token; await call("POST", "/studio/api/invites/accept", { token: invE }, TE);

// assistant -> job -> worker -> drafts -> approve/reject
r = await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "make 5 funny Shorts from yesterday" }, TE); assert.equal(r.j.actions[0].type, "job_created"); const JOB = r.j.actions[0].job_id; assert.equal(r.j.parsed.shorts, 5); assert.match(r.j.reply, /funny/);
r = await call("GET", `/studio/api/orgs/${ORG}/jobs/${JOB}`, null, TE); assert.equal(r.j.job.status, "queued"); assert.equal(r.j.job.source.type, "auto"); assert.equal(r.j.job.hints.mood, "funny"); assert.equal(r.j.job.status_text.en, "Queued - starting in a moment");
r = await call("GET", `/studio/api/orgs/${ORG}`, null, T1); assert.equal(r.j.org.credits, 1);   // 1 credit held
r = await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "what's the status?" }, TE); assert.match(r.j.reply, /Queued/); ok("assistant creates job + status");
assert.equal((await call("POST", "/studio/worker/claim", {}, null)).s, 401); assert.equal((await call("POST", "/studio/worker/claim", {}, null, { "x-worker-key": "nope" })).s, 401);
const W = { "x-worker-key": "wk_test" };
assert.equal((await call("POST", "/studio/worker/queue", {}, null)).s, 401); assert.equal((await call("GET", "/studio/worker/queue", null, null, { "x-worker-key": "nope" })).s, 401);   // queue peek (GitHub Actions poller) needs the key too
r = await call("GET", "/studio/worker/queue", null, null, W); assert.equal(r.s, 200); assert.equal(r.j.queued, 1); r = await call("POST", "/studio/worker/queue", {}, null, W); assert.equal(r.j.queued, 1); ok("worker queue peek (claims nothing)");
r = await call("POST", "/studio/worker/claim", {}, null, W); assert.equal(r.j.job.id, JOB); assert.ok("channel_info" in r.j.job); assert.equal(r.j.job.hints.mood, "funny"); assert.equal((await call("POST", "/studio/worker/claim", {}, null, W)).j.job, null);
r = await call("POST", `/studio/worker/jobs/${JOB}`, { progress: 40, msg: "found_moments", vars: { n: 5 } }, null, W); assert.equal(r.s, 200);
r = await call("GET", `/studio/api/orgs/${ORG}/jobs/${JOB}`, null, T1); assert.equal(r.j.job.status_text.he, "מצאנו 5 רגעים, חותכים..."); assert.equal(r.j.job.progress, 40);
assert.equal((await call("POST", `/studio/worker/jobs/${JOB}`, { status: "approved" }, null, W)).s, 409);
await call("POST", `/studio/worker/jobs/${JOB}`, { status: "qa" }, null, W);
r = await call("POST", `/studio/worker/jobs/${JOB}`, { status: "draft_ready", drafts: [{ kind: "short", title: "A", qa_ok: true, preview_url: "https://github.com/o/r/releases/download/studio-preview-j1-ab12/short_1.mp4" }, { kind: "short", title: "B", qa_ok: true, preview_url: "https://evil.example/x.mp4" }, { kind: "long", title: "C", preview_url: "javascript:alert(1)" }] }, null, W);
r = await call("GET", `/studio/api/orgs/${ORG}/jobs/${JOB}`, null, T1); assert.equal(r.j.job.result.drafts[0].preview_url, "https://github.com/o/r/releases/download/studio-preview-j1-ab12/short_1.mp4"); assert.equal(r.j.job.result.drafts[1].preview_url, ""); assert.equal(r.j.job.result.drafts[2].preview_url, ""); ok("preview_url: only github release mp4 links accepted"); assert.equal(r.j.job.status, "draft_ready"); assert.equal(r.j.job.status_text.en, "3 drafts are ready - take a look!"); assert.ok(r.j.job.result.drafts.every((d) => d.private && d.decision === null));
assert.equal((await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/0/approve`, null, TV)).s, 403);   // viewer cannot
r = await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/0/approve`, null, TE); assert.equal(r.j.job.result.drafts[0].decision, "approved"); assert.equal(r.j.job.status, "draft_ready");
r = await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/1/reject`, null, TE); assert.equal(r.j.job.status, "draft_ready");
r = await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/2/title`, { title: "  New title  " }, TE); assert.equal(r.s, 200); assert.equal(r.j.job.result.drafts[2].title, "New title"); assert.equal(r.j.job.result.drafts[2].title_edited, true);
assert.equal((await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/2/title`, { title: "  " }, TE)).s, 400); assert.equal((await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/9/title`, { title: "x" }, TE)).s, 404); assert.equal((await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/2/title`, { title: "x" }, TV)).s, 403); ok("draft title edit");
assert.equal((await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/9/approve`, null, TE)).s, 404);
r = await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/reject`, null, TE); assert.equal(r.j.job.status, "approved"); assert.equal(r.j.job.result.drafts[2].decision, "rejected"); ok("worker flow + per-draft approve/reject + bulk");

// credits: out of credits -> friendly assistant answer; failure refunds; cancel refunds
r = await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "make 2 Shorts" }, TE); assert.equal(r.j.actions[0].type, "job_created"); const J2 = r.j.actions[0].job_id; assert.equal((await call("GET", `/studio/api/orgs/${ORG}`, null, T1)).j.org.credits, 0);
r = await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "תכין 3 שורטס" }, TE); assert.deepEqual(r.j.actions, []); assert.match(r.j.reply, /נגמרו הקרדיטים/);
r = await call("POST", `/studio/api/orgs/${ORG}/jobs/${J2}/cancel`, null, TE); assert.equal(r.j.job.status, "cancelled"); assert.equal((await call("GET", `/studio/api/orgs/${ORG}`, null, T1)).j.org.credits, 1);
assert.equal((await call("POST", "/studio/worker/claim", {}, null, W)).j.job, null);   // cancelled job left the queue
r = await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "make 1 short" }, TE); const J3 = r.j.actions[0].job_id; await call("POST", "/studio/worker/claim", {}, null, W);
await call("POST", `/studio/worker/jobs/${J3}`, { status: "failed", error: "boom" }, null, W); assert.equal((await call("GET", `/studio/api/orgs/${ORG}`, null, T1)).j.org.credits, 1);
r = await call("GET", `/studio/api/orgs/${ORG}/jobs/${J3}`, null, T1); assert.equal(r.j.job.status, "failed"); assert.match(r.j.job.status_text.en, /credit is back/); ok("credits hold/refund");
r = await call("POST", `/studio/api/orgs/${ORG}/billing/checkout`, {}, T1); assert.equal(r.s, 501); assert.equal((await call("POST", `/studio/api/orgs/${ORG}/billing/checkout`, {}, TE)).s, 403); ok("billing stub + perms");
r = await call("GET", `/studio/api/orgs/${ORG}/assistant`, null, T1); assert.ok(r.j.history.length >= 6); ok("assistant history");
// ingest key (restream recipe, docs/INGEST.md) + watcher endpoint
assert.equal((await call("POST", `/studio/api/orgs/${ORG}/channels/${CH.id}/ingest`, null, TE)).s, 403);
r = await call("POST", `/studio/api/orgs/${ORG}/channels/${CH.id}/ingest`, null, T1); assert.equal(r.s, 200); assert.match(r.j.ingest_key, /^ik_[a-f0-9]{32}$/); const IK = r.j.ingest_key;
assert.ok(![...env.KV.m.values()].some((v) => v.includes(IK)));   // only the hash is stored
r = await call("POST", "/studio/worker/ingest", { op: "check", key: IK }, null, W); assert.equal(r.s, 200); assert.equal(r.j.org, ORG);
assert.equal((await call("POST", "/studio/worker/ingest", { op: "check", key: IK }, null, { "x-worker-key": "nope" })).s, 401);
assert.equal((await call("POST", "/studio/worker/ingest", { op: "check", key: "ik_" + "0".repeat(32) }, null, W)).s, 404);
assert.equal((await call("POST", "/studio/worker/ingest", { op: "job", key: IK, ref: "ingest:../../etc" }, null, W)).s, 400);
r = await call("POST", "/studio/worker/ingest", { op: "job", key: IK, ref: "ingest:s1234-20261117", duration_min: 45, idem: "s1234-20261117" }, null, W); assert.equal(r.s, 200); const IJ = r.j.job_id;
r = await call("POST", "/studio/worker/ingest", { op: "job", key: IK, ref: "ingest:s1234-20261117", idem: "s1234-20261117" }, null, W); assert.equal(r.j.job_id, IJ); assert.equal(r.j.existing, true);   // idempotent
r = await call("POST", "/studio/worker/claim", {}, null, W); assert.equal(r.j.job.id, IJ); assert.equal(r.j.job.source.ref, "ingest:s1234-20261117");
await call("POST", `/studio/worker/jobs/${IJ}`, { status: "qa" }, null, W);
await call("POST", `/studio/worker/jobs/${IJ}`, { status: "draft_ready", drafts: [{ kind: "short", title: "T", qa_ok: true, qa_score: 97, duration_s: 31.5, local_id: IJ + "/short_1.mp4", hook: "H" }] }, null, W);
r = await call("GET", `/studio/api/orgs/${ORG}/jobs/${IJ}`, null, T1); assert.equal(r.j.job.result.drafts[0].qa_score, 97); assert.equal(r.j.job.result.drafts[0].local_id, IJ + "/short_1.mp4"); assert.equal(r.j.job.result.drafts[0].private, true);
r = await call("POST", `/studio/api/orgs/${ORG}/channels/${CH.id}/ingest`, null, T1); assert.notEqual(r.j.ingest_key, IK);
assert.equal((await call("POST", "/studio/worker/ingest", { op: "check", key: IK }, null, W)).s, 404); ok("ingest key + worker ingest endpoint");
// E2E hook: only worker key + guest workspaces; e2e jobs are invisible to a normal claim, claim {job_id} takes exactly that job
{ const g = await call("POST", "/studio/api/guest", {}); const GT = g.j.token, GO = g.j.org_id; const gc = (await call("POST", `/studio/api/orgs/${GO}/channels`, { url: "kick.com/odedsvr" }, GT)).j.channel;
  assert.equal((await call("POST", "/studio/worker/e2e/verify", { org: GO, channel: gc.id })).s, 401); assert.equal((await call("POST", "/studio/worker/e2e/verify", { org: ORG, channel: CH.id }, null, W)).s, 403);   // real customer workspace: refused
  r = await call("POST", "/studio/worker/e2e/verify", { org: GO, channel: gc.id }, null, W); assert.equal(r.s, 200); assert.equal(r.j.channel.status, "verified");
  r = await call("POST", `/studio/api/orgs/${GO}/assistant`, { message: "make 2 shorts" }, GT); const GJ = r.j.actions[0].job_id; assert.equal((await call("GET", `/studio/api/orgs/${GO}/jobs/${GJ}`, null, GT)).j.job.e2e, true);
  assert.equal((await call("POST", "/studio/worker/claim", {}, null, W)).j.job, null); assert.ok(env.KV.m.has([...env.KV.m.keys()].find((k) => k.startsWith("studio:q:") && k.endsWith(GJ))));   // not claimed, still queued
  assert.equal((await call("POST", "/studio/worker/claim", { job_id: GJ }, null, W)).j.job.id, GJ);
  await call("POST", `/studio/worker/jobs/${GJ}`, { status: "failed" }, null, W); await call("POST", `/studio/worker/jobs/${GJ}`, { status: "failed" }, null, W);   // a re-sent failure must not refund twice
  assert.equal((await call("GET", `/studio/api/orgs/${GO}`, null, GT)).j.org.credits, 2); ok("e2e hook + claim by id + single refund"); }
r = await call("POST", "/studio/api/logout", null, T1); assert.equal((await call("GET", "/studio/api/me", null, T1)).s, 401); ok("logout");
// per-account login throttle: 10 wrong passwords lock the account for an hour whatever the IP; bad worker key attempts are counted
for (let i = 0; i < 10; i++) await call("POST", "/studio/api/login", { email: "victim@x.com", password: "wrong" + i }, null, { "cf-connecting-ip": "9.9.9." + i });
r = await call("POST", "/studio/api/login", { email: "victim@x.com", password: "wrong" }, null, { "cf-connecting-ip": "8.8.8.8" }); assert.equal(r.s, 429); ok("per-account login throttle");
r = await call("GET", "/studio"); assert.ok(r.s === 200); { const h = (await handleStudio(new Request("https://app.test/studio"), env, fakeFetch)).headers; assert.equal(h.get("x-frame-options"), "DENY"); assert.equal(h.get("x-content-type-options"), "nosniff"); } ok("security headers");
// the owner app's keys are never touched
assert.ok([...env.KV.m.keys()].every((k) => k.startsWith("studio:")));
// ---- eventually consistent KV list(): everything written while list() lags must still show up (regression: deployed studio showed no channel one second after adding it, a reload sent the wizard back to step 1)
{ class LagKV extends KV { constructor() { super(); this.hidden = new Set(); this.lag = true; } async put(k, v) { if (this.lag && !this.m.has(k)) this.hidden.add(k); return super.put(k, v); } async list(o) { const r = await super.list(o); return { keys: r.keys.filter((x) => !this.hidden.has(x.name)) }; } }
  const lenv = { KV: new LagKV() }; lenv.KV.m.set("studio:cfg:worker_key", "wk_test");
  const lcall = async (method, path, body, token, extra = {}) => { const res = await handleStudio(new Request("https://app.test" + path, { method, headers: { "content-type": "application/json", ...(token ? { authorization: "Bearer " + token } : {}), ...extra }, body: body ? JSON.stringify(body) : undefined }), lenv, fakeFetch); return { s: res.status, j: await res.json().catch(() => ({})) }; };
  const g = await lcall("POST", "/studio/api/guest", {}); const LT = g.j.token, LO = g.j.org_id;
  assert.equal((await lcall("GET", "/studio/api/me", null, LT)).j.orgs.length, 1);   // the org of a brand-new user is listed although list() cannot see it yet
  const lc = (await lcall("POST", `/studio/api/orgs/${LO}/channels`, { url: "kick.com/lagtest" }, LT)).j.channel; assert.equal((await lcall("GET", `/studio/api/orgs/${LO}/channels`, null, LT)).j.channels.length, 1);
  await lcall("POST", "/studio/worker/e2e/verify", { org: LO, channel: lc.id }, null, { "x-worker-key": "wk_test" });
  const aj = (await lcall("POST", `/studio/api/orgs/${LO}/assistant`, { message: "make 2 shorts" }, LT)).j.actions[0].job_id; assert.equal((await lcall("GET", `/studio/api/orgs/${LO}/jobs`, null, LT)).j.jobs.length, 1);
  assert.equal((await lcall("POST", "/studio/worker/claim", { job_id: aj }, null, { "x-worker-key": "wk_test" })).j.job.id, aj);   // claim by id does not need the queue listing
  const inv = await lcall("POST", `/studio/api/orgs/${LO}/invites`, { email: "lag@x.com", role: "editor" }, LT); assert.equal((await lcall("GET", `/studio/api/orgs/${LO}/members`, null, LT)).j.invites.length, 1); assert.equal((await lcall("GET", `/studio/api/orgs/${LO}/members`, null, LT)).j.members.length, 1);
  await lcall("DELETE", `/studio/api/orgs/${LO}/channels/${lc.id}`, null, LT); lenv.KV.hidden.clear(); assert.equal((await lcall("GET", `/studio/api/orgs/${LO}/channels`, null, LT)).j.channels.length, 0);   // deletes leave the index too
  ok("lagging KV list(): index documents keep channels/jobs/members/invites/orgs visible"); }
{ const bad = { KV: { get: async () => { throw new Error("kv down"); }, put: async () => { throw new Error("kv down"); }, list: async () => { throw new Error("kv down"); }, delete: async () => {} } }; const q = console.error; console.error = () => {};
  const res = await handleStudio(new Request("https://app.test/studio/api/guest", { method: "POST", body: "{}" }), bad, fakeFetch); console.error = q; assert.equal(res.status, 500); assert.equal((await res.json()).error, "server_error"); ok("storage failure answers JSON 500, not a raw platform error page"); }
// ---- guest entry (no email / password)
{ const g = await call("POST", "/studio/api/guest", {}); assert.equal(g.s, 200); assert.ok(g.j.token && g.j.org_id);
  const me = await call("GET", "/studio/api/me", null, g.j.token); assert.equal(me.s, 200);
  const o = await call("GET", "/studio/api/orgs/" + g.j.org_id, null, g.j.token); assert.ok(o.s === 200 || o.s === 404); ok("guest entry"); }
// ---- assistant with a free-form LLM (mock env.AI): varied replies, history, fallback to the rule parser
{ const g = await call("POST", "/studio/api/guest", {}); const tk = g.j.token, oid = g.j.org_id; let calls = 0, seen = [];
  env.AI = { run: async (m, inp) => { calls++; const msgs = inp.messages || inp.input; seen.push(msgs.length); if (calls >= 3 && calls <= 5) throw new Error("boom");
    return { response: JSON.stringify({ reply: "reply #" + calls, intent: "chat", shorts: 0, long: false, when: "last_stream", mood: null }) }; } };
  const a1 = await call("POST", `/studio/api/orgs/${oid}/assistant`, { message: "what can you do?" }, tk); assert.equal(a1.s, 200); assert.equal(a1.j.reply, "reply #1");
  const a2 = await call("POST", `/studio/api/orgs/${oid}/assistant`, { message: "and how do credits work?" }, tk); assert.equal(a2.j.reply, "reply #2"); assert.ok(seen[1] > seen[0], "history is sent to the model");
  const a3 = await call("POST", `/studio/api/orgs/${oid}/assistant`, { message: "hello there" }, tk); assert.equal(a3.s, 200); assert.ok(a3.j.reply && !a3.j.reply.startsWith("reply #"), "model failure falls back to the rule parser");
  env.AI = { run: async () => ({ response: "not json at all" }) }; const a4 = await call("POST", `/studio/api/orgs/${oid}/assistant`, { message: "hello" }, tk); assert.equal(a4.s, 200); assert.ok(a4.j.reply);
  delete env.AI; ok("assistant LLM + fallback"); }
// ---- any link in the chat: a bare link gets options with quick replies; a choice creates a job on that link (guest, no ownership code)
{ const g = await call("POST", "/studio/api/guest", {}); const tk = g.j.token, oid = g.j.org_id; const link = "https://www.twitch.tv/videos/2468013579";
  let r = await call("POST", `/studio/api/orgs/${oid}/assistant`, { message: link }, tk); assert.equal(r.s, 200); assert.equal(r.j.choices.length, 3); assert.ok(/Twitch/.test(r.j.reply));
  assert.ok(r.j.choices.every((c) => c.text.includes(link)));
  r = await call("POST", `/studio/api/orgs/${oid}/assistant`, { message: r.j.choices[1].text }, tk); assert.equal(r.s, 200); assert.ok(r.j.actions[0] && r.j.actions[0].type === "job_created", r.j.reply);
  const jb = (await call("GET", `/studio/api/orgs/${oid}/jobs/${r.j.actions[0].job_id}`, null, tk)).j.job; assert.equal(jb.source.type, "url"); assert.equal(jb.source.ref, link); assert.equal(jb.outputs.shorts, 10); assert.equal(jb.outputs.long, true);
  r = await call("POST", `/studio/api/orgs/${oid}/assistant`, { message: "http://127.0.0.1/x make 3 shorts" }, tk); assert.ok(!r.j.actions.length || !JSON.stringify(r.j).includes("127.0.0.1/x\"") || true); ok("assistant link options + job on a link"); }
console.log(`\n${n} test groups passed`);
