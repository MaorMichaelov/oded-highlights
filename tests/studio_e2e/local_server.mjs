// Local stand-in for the deployed Worker: runs the REAL app/studio.js (+ studio.html) on node with an in-memory KV and a fake Kick/Twitch.
// usage: node tests/studio_e2e/local_server.mjs [port]     control: GET /__ctl?kick_bio=TEXT&kick_status=403&twitch=1
import http from "node:http";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
const root = join(dirname(fileURLToPath(import.meta.url)), "..", "..", "app");
const { handleStudio } = await import(join(root, "studio.js")); const { handleYouTube } = await import(join(root, "youtube_connect.js"));
const html = readFileSync(join(root, "studio.html"), "utf8");
class KV { constructor() { this.m = new Map(); } async get(k, t) { const v = this.m.get(k); if (v == null) return null; return t === "json" ? JSON.parse(v) : v; } async put(k, v) { this.m.set(k, String(v)); } async delete(k) { this.m.delete(k); }
  async list({ prefix = "", limit = 1000 } = {}) { return { keys: [...this.m.keys()].filter((k) => k.startsWith(prefix)).sort().slice(0, limit).map((name) => ({ name })) }; } }
const env = { KV: new KV() }; env.KV.m.set("studio:cfg:worker_key", "wk_local_e2e");
const ctl = { kick_bio: "", kick_status: 200, twitch: false, twitch_bio: "" };
const fakeFetch = async (url) => {
  const R = (o, s = 200) => ({ ok: s < 400, status: s, json: async () => o, text: async () => JSON.stringify(o) });
  if (url.startsWith("https://kick.com/api/v2/channels/")) { const slug = decodeURIComponent(url.split("/").pop()); if (ctl.kick_status !== 200) return R({}, ctl.kick_status); if (slug === "nobody-here") return R({}, 404); return R({ user_id: 7, user: { id: 7, username: slug, bio: ctl.kick_bio }, livestream: null }); }
  if (url.startsWith("https://gql.twitch.tv/")) { if (!ctl.twitch) return R({}, 500); return R({ data: { user: { id: "1", displayName: "kaicenat", description: ctl.twitch_bio, stream: null } } }); }
  if (url.includes("api.github.com")) return R([], 404);
  return R({}, 500);
};
const port = +(process.argv[2] || process.env.PORT || 8787);
http.createServer(async (rq, rs) => {
  const u = new URL(rq.url, "http://localhost:" + port);
  if (u.pathname === "/__ctl") { for (const [k, v] of u.searchParams) ctl[k] = k === "kick_status" ? +v : k === "twitch" ? v === "1" : v; rs.end(JSON.stringify(ctl)); return; }
  const chunks = []; for await (const c of rq) chunks.push(c); const body = Buffer.concat(chunks);
  const req = new Request("http://localhost:" + port + rq.url, { method: rq.method, headers: Object.fromEntries(Object.entries(rq.headers).filter(([k]) => !["host", "connection", "content-length"].includes(k))), body: ["GET", "HEAD"].includes(rq.method) ? undefined : body });
  const res = (u.pathname.startsWith("/studio/yt/") || u.pathname.startsWith("/internal/yt/")) && (await handleYouTube(req, env)) || await handleStudio(req, env, fakeFetch);
  const text = await res.text(); const h = Object.fromEntries(res.headers); let out = text;
  if (text === "__STUDIO_HTML__") out = html;   // studio.js ships a placeholder: deploy.py substitutes the page
  rs.writeHead(res.status, h); rs.end(out);
}).listen(port, () => console.log("studio local server on :" + port));
