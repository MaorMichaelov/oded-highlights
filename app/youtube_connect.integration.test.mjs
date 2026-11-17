// Integration check: youtube_connect.js running on top of the REAL app/studio.js session/org/job storage (not seeded by hand). Google is mocked. node app/youtube_connect.integration.test.mjs
import { handleStudio, createJob } from "./studio.js";
import { handleYouTube, SCOPES } from "./youtube_connect.js";
import assert from "node:assert/strict";

class KV {
  constructor() { this.m = new Map(); }
  async get(k, type) { const v = this.m.get(k); if (v == null) return null; return type === "json" ? JSON.parse(v) : v; }
  async put(k, v) { this.m.set(k, String(v)); }
  async delete(k) { this.m.delete(k); }
  async list({ prefix = "", limit = 1000 } = {}) { return { keys: [...this.m.keys()].filter((k) => k.startsWith(prefix)).sort().slice(0, limit).map((name) => ({ name })) }; }
}
const env = { KV: new KV(), YT_CLIENT_ID: "cid", YT_CLIENT_SECRET: "sec", STUDIO_ENC_KEY: Buffer.from(crypto.getRandomValues(new Uint8Array(32))).toString("base64") };
env.KV.m.set("studio:cfg:worker_key", "wk_test");
const google = async (url, opt = {}) => {
  const R = (j, s = 200) => ({ ok: s < 400, status: s, json: async () => j }); const b = opt.body ? Object.fromEntries(new URLSearchParams(opt.body)) : {};
  if (url.endsWith("/token")) return b.grant_type === "authorization_code" ? R({ access_token: "at1", refresh_token: "rt1", expires_in: 3599, scope: SCOPES.upload + " " + SCOPES.readonly }) : R({ access_token: "at2", expires_in: 3599 });
  if (url.includes("/channels")) return R({ items: [{ id: "UCreal1", snippet: { title: "My Channel" } }] });
  return R({}, 200);
};
const req = (method, path, body, token, extra = {}) => new Request("https://app.test" + path, { method, headers: { "content-type": "application/json", ...(token ? { authorization: "Bearer " + token } : {}), ...extra }, body: body ? JSON.stringify(body) : undefined });

// real signup -> real session + org + owner membership
let res = await handleStudio(req("POST", "/studio/api/signup", { email: "o@x.com", password: "password1", name: "Owner" }), env); const su = await res.json(); assert.equal(res.status, 200);
const TOKEN = su.token, ORG = su.org_id;
res = await handleStudio(req("POST", "/studio/api/signup", { email: "ed@x.com", password: "password1", name: "Ed" }), env); const ed = await res.json();   // a different customer
// a (verified) studio channel record in the shape studio.js writes
const CH = "c_abc123"; env.KV.m.set(`studio:c:${ORG}:${CH}`, JSON.stringify({ id: CH, org: ORG, platform: "kick", slug: "x", status: "verified", yt: { status: "not_connected" } }));

assert.equal((await handleYouTube(req("GET", "/studio/api/me"), env, { fetchImpl: google })), null, "foreign path falls through");
const yt = (r) => handleYouTube(r, env, { fetchImpl: google });
res = await yt(req("POST", "/studio/yt/start", { org_id: ORG, channel_id: CH }, TOKEN)); assert.equal(res.status, 200); const start = await res.json(); const state = new URL(start.url).searchParams.get("state"); const cookie = res.headers.get("set-cookie").split(";")[0];
res = await yt(req("POST", "/studio/yt/start", { org_id: ORG, channel_id: CH }, ed.token)); assert.equal(res.status, 404, "other customer cannot touch this org");
res = await yt(req("GET", `/studio/yt/callback?state=${state}&code=c`, null, null, { cookie })); assert.match(await res.text(), /youtube=connected/);
res = await yt(req("GET", `/studio/yt/status?org_id=${ORG}&channel_id=${CH}`, null, TOKEN)); const st = await res.json(); assert.equal(st.channel.title, "My Channel");
const chRec = JSON.parse(env.KV.m.get(`studio:c:${ORG}:${CH}`)); assert.equal(chRec.yt.status, "connected"); assert.equal(chRec.platform, "kick", "studio channel record otherwise untouched");

// a real job from studio.js's own createJob
const org = JSON.parse(env.KV.m.get(`studio:o:${ORG}`)); const job = await createJob(env, org, { channel_id: CH, source: { type: "auto" }, credits: 1 });
res = await yt(req("POST", "/internal/yt/token", { org_id: ORG, job_id: job.id }, null, { "x-worker-key": "wk_test" })); const tk = await res.json(); assert.equal(res.status, 200, JSON.stringify(tk)); assert.equal(tk.access_token, "at2"); assert.equal(tk.channel_id, "UCreal1"); assert.equal(tk.policy.privacy, "private");
res = await yt(req("POST", "/internal/yt/token", { org_id: "o_" + "0".repeat(8), job_id: job.id }, null, { "x-worker-key": "wk_test" })); assert.equal(res.status, 403, "job of another org");
res = await yt(req("POST", "/studio/yt/disconnect", { org_id: ORG, channel_id: CH }, TOKEN)); assert.equal((await res.json()).was_connected, true);
console.log("integration with real studio.js: ok");
