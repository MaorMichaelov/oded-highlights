// Local stand-in for the deployed studio Worker: the REAL app/studio.js (handleStudio, createJob) on an in-memory KV, over plain HTTP on 127.0.0.1.
// For tests only: node tests/helpers/studio_mock_server.mjs  -> prints "PORT <n>"; extra test-only routes (never part of the Worker): POST /__seed {source, outputs, credits} -> {job_id, org_id}, GET /__job/<id> -> the stored job.
import http from "node:http";
import { handleStudio, createJob } from "../../app/studio.js";

const m = new Map();
const KV = {
  async get(k, type) { const v = m.get(k); if (v == null) return null; return type === "json" ? JSON.parse(v) : v; },
  async put(k, v) { m.set(k, String(v)); },
  async delete(k) { m.delete(k); },
  async list({ prefix = "", limit = 1000 } = {}) { return { keys: [...m.keys()].filter((k) => k.startsWith(prefix)).sort().slice(0, limit).map((name) => ({ name })) }; },
};
const env = { KV }; m.set("studio:cfg:worker_key", process.env.MOCK_WORKER_KEY || "wk_local_test_key");
const fakeFetch = async () => ({ ok: false, status: 500, json: async () => ({}) });

const srv = http.createServer(async (req, res) => {
  const chunks = []; for await (const c of req) chunks.push(c); const body = Buffer.concat(chunks);
  const url = new URL(req.url, "http://127.0.0.1");
  const send = (status, obj) => { res.writeHead(status, { "content-type": "application/json" }); res.end(JSON.stringify(obj)); };
  if (url.pathname === "/__seed" && req.method === "POST") {
    const b = JSON.parse(body.toString() || "{}");
    const g = await handleStudio(new Request("http://x/studio/api/guest", { method: "POST", headers: { "content-type": "application/json" }, body: "{}" }), env, fakeFetch); const gj = await g.json();
    const org = JSON.parse(m.get("studio:o:" + gj.org_id)); org.credits = b.credits ?? 5; m.set("studio:o:" + org.id, JSON.stringify(org));
    const ch = { id: "c_test", org: org.id, platform: b.platform || "twitch", slug: b.slug || "noa", status: "verified", style_id: "signature" }; m.set(`studio:c:${org.id}:${ch.id}`, JSON.stringify(ch));
    const job = await createJob(env, org, { channel_id: ch.id, kind: "edit", source: b.source, style_id: "signature", outputs: b.outputs || { shorts: 1, long: false }, credits: b.hold ?? 1 });
    return send(200, { job_id: job.id, org_id: org.id });
  }
  if (url.pathname.startsWith("/__job/")) { const j = m.get("studio:j:" + url.pathname.slice(7)); return j ? send(200, JSON.parse(j)) : send(404, {}); }
  const headers = {}; for (const [k, v] of Object.entries(req.headers)) headers[k] = v;
  const r = new Request("http://127.0.0.1" + req.url, { method: req.method, headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : body });
  const out = await handleStudio(r, env, fakeFetch); const buf = Buffer.from(await out.arrayBuffer()); const h = {}; out.headers.forEach((v, k) => { h[k] = v; });
  res.writeHead(out.status, h); res.end(buf);
});
srv.listen(0, "127.0.0.1", () => console.log("PORT " + srv.address().port));
