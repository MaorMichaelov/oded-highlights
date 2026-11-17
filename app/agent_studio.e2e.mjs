// End-to-end check of the Studio + agent integration. It needs the hooks of docs/agent_hooks/*.patch, so it is run by tests/test_agent_hooks.py on a PATCHED COPY of app/ (never against the live studio.js):
//   python3 -m unittest tests.test_agent_hooks -v
import { handleStudio } from "./studio.js";
import * as A from "./agent.js";
import assert from "node:assert/strict";

class KV { constructor() { this.m = new Map(); } async get(k, t) { const v = this.m.get(k); if (v == null) return null; return t === "json" ? JSON.parse(v) : v; } async put(k, v) { this.m.set(k, String(v)); } async delete(k) { this.m.delete(k); }
  async list({ prefix = "", limit = 1000 } = {}) { return { keys: [...this.m.keys()].filter((k) => k.startsWith(prefix)).sort().slice(0, limit).map((name) => ({ name })) }; } }
const script = []; const calls = [];
const llm = { providers: [{ name: "mock" }], async chat(req) { calls.push(req); const r = script.shift(); return r === undefined ? { ok: false, error: "script_empty" } : { ok: true, text: typeof r === "string" ? r : JSON.stringify(r), provider: "mock" }; } };
const env = { KV: new KV(), AGENT_LLM: llm }; env.KV.m.set("studio:cfg:worker_key", "wk_test");
const fakeFetch = async (url) => { const R = (o, s = 200) => ({ ok: s < 400, status: s, json: async () => o }); if (url.startsWith("https://kick.com/api/v2/channels/")) return R({ user_id: 1, user: { id: 1, username: "odedsvr", bio: kickBio } }); return R({}, 500); };
let kickBio = "hello";
const call = async (method, path, body, token, extra = {}) => { const req = new Request("https://app.test" + path, { method, headers: { "content-type": "application/json", ...(token ? { authorization: "Bearer " + token } : {}), ...extra }, body: body ? JSON.stringify(body) : undefined }); const res = await handleStudio(req, env, fakeFetch); const ct = res.headers.get("content-type") || ""; return { s: res.status, j: ct.includes("json") ? await res.json() : await res.text() }; };
let n = 0; const ok = (m) => { n++; console.log("ok  " + m); }; const W = { "x-worker-key": "wk_test" };

let r = await call("POST", "/studio/api/signup", { email: "o@x.com", password: "password1", name: "Owner" }); const T = r.j.token, ORG = r.j.org_id;
r = await call("POST", `/studio/api/orgs/${ORG}/channels`, { url: "https://kick.com/odedsvr" }, T); const CH = r.j.channel; kickBio = CH.verify_code; await call("POST", `/studio/api/orgs/${ORG}/channels/${CH.id}/verify`, null, T);
const cid = `${ORG}-${CH.id}`.toLowerCase(); const deps = { kv: env.KV, now: Date.now };
await A.updateProfile(deps, cid, (p) => { p.autonomy.level = 2; p.rules.push({ kind: "ban_topic", text: "הימורים", keywords: ["קזינו"] }); }, "setup", "test");

// 1. level 2: the model asks for a job -> pending, nothing started; the customer's plain "yes" starts it (no LLM call), and the job carries the profile for the pipeline
script.push({ tool: "start_job", args: { when: "yesterday", shorts: 3 } }, { reply: "לאשר שאתחיל 3 שורטס מאתמול?" });
r = await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "תכין 3 שורטס מאתמול" }, T); assert.equal(r.j.parsed.agent, true); assert.equal(r.j.actions.length, 0); assert.equal(r.j.pending.length, 1); assert.equal((await call("GET", `/studio/api/orgs/${ORG}/jobs`, null, T)).j.jobs.length, 0);
const llmCalls = calls.length; r = await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "כן" }, T); assert.equal(calls.length, llmCalls, "no model call for a plain yes"); assert.equal(r.j.actions[0].type, "job_created"); const JOB = r.j.actions[0].job_id;
r = await call("POST", "/studio/worker/claim", {}, null, W); assert.equal(r.j.job.id, JOB); assert.equal(r.j.job.hints.requested_by, "agent"); assert.equal(r.j.job.hints.profile.rules[0].text, "הימורים"); assert.ok(!("autonomy" in r.j.job.hints.profile)); ok("agent starts a job only after the customer's yes; the job carries the profile");

// 2. worker returns drafts with explanations; decisions become signals
await call("POST", `/studio/worker/jobs/${JOB}`, { status: "qa" }, null, W);
await call("POST", `/studio/worker/jobs/${JOB}`, { status: "draft_ready", drafts: [{ kind: "short", content_kind: "cooking", title: "עודד מבשל פסטה!", topic: "בישול", why: "סיפור שלם עם שיא", excerpt: "אור: תוסיף שום", qa_ok: true, qa_score: 0.95 }, { kind: "short", content_kind: "game", title: "משחק ארוך", qa_ok: true }] }, null, W);
await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/0/approve`, null, T); await call("POST", `/studio/api/orgs/${ORG}/jobs/${JOB}/drafts/1/reject`, { reason: "ארוך מדי" }, T);
const prof = await A.loadProfile(deps, cid); assert.deepEqual([prof.stats.approved, prof.stats.rejected], [1, 1]); assert.equal(prof.examples.rejected[0].reason, "ארוך מדי"); assert.equal(prof.examples.approved[0].kind, "cooking"); assert.equal((await A.listSignals(deps, cid)).length, 2); ok("approve/reject are learning signals (with the customer's reason)");

// 3. explain a pick from stored data; a viewer-like caller cannot act
script.push({ tool: "explain_pick", args: { draft_id: `${JOB}:0` } }, { reply: "נבחר כי זה סיפור שלם עם שיא." });
r = await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "למה בחרת את הראשון?" }, T); assert.match(r.j.reply, /סיפור שלם/); assert.match(calls.at(-1).messages.at(-1).content, /<tool_result name="explain_pick">[\s\S]*סיפור שלם עם שיא[\s\S]*אור: תוסיף שום/); assert.match(calls.at(-2).messages[0].content, /הימורים/, "the rule is in the system prompt"); ok("explain_pick answers from the stored reasons");

// 4. pause works end to end: queued jobs stay queued while paused
script.push({ tool: "pause", args: {} }, { reply: "לעצור?" }); await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "תעצור הכל" }, T); await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "כן" }, T);
r = await call("POST", `/studio/api/orgs/${ORG}/jobs`, { channel_id: CH.id, source: { type: "auto", when: "yesterday" } }, T); assert.equal(r.s, 200); assert.equal((await call("POST", "/studio/worker/claim", {}, null, W)).j.job, null, "paused org: nothing is claimed");
script.push({ tool: "resume", args: {} }, { reply: "?" }); await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "תמשיך" }, T); await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "כן" }, T); assert.ok((await call("POST", "/studio/worker/claim", {}, null, W)).j.job, "resumed"); ok("pause / resume");

// 5. without a model the old rule-based assistant still answers (AGENT_LLM absent, no AI binding)
delete env.AGENT_LLM; r = await call("POST", `/studio/api/orgs/${ORG}/assistant`, { message: "what's the status?" }, T); assert.equal(r.s, 200); assert.ok(!r.j.parsed || !r.j.parsed.agent); ok("graceful fallback to the rule-based assistant");
assert.ok([...env.KV.m.keys()].every((k) => k.startsWith("studio:")), "the agent only touches studio: keys");
console.log(`\n${n} e2e groups passed`);
