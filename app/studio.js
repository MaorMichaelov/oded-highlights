// STUDIO: customer-facing area of the Worker (route prefix /studio). Separate from the owner app: own auth, own KV key prefix "studio:".
// MVP SKELETON. KV is not transactional/queryable: every place marked TODO(D1) must move to D1 or a Durable Object before real customers (see docs/PRODUCT_ARCHITECTURE.md).
// This file is an ES module imported by worker.js; the page HTML (app/studio.html) is substituted for __STUDIO_HTML__ by app/deploy.py.
export const STUDIO_HTML = "__STUDIO_HTML__";
const REPO = "MaorMichaelov/oded-highlights";

// ---------- small helpers ----------
const enc = new TextEncoder();
const hex = (b) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
export const sha256 = async (t) => hex(await crypto.subtle.digest("SHA-256", enc.encode(t)));
const rnd = (n = 16) => hex(crypto.getRandomValues(new Uint8Array(n)));
const json = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
const SEC = { "x-content-type-options": "nosniff", "x-frame-options": "DENY", "referrer-policy": "no-referrer", "content-security-policy": "frame-ancestors 'none'; base-uri 'none'; object-src 'none'" };
const err = (s, code, extra = {}) => json({ error: code, ...extra }, s);
const now = () => new Date().toISOString();
const ALPHA = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";   // no 0/O/1/I: a code typed from a screenshot must not be ambiguous
export const newVerifyCode = () => "ODH-" + [...crypto.getRandomValues(new Uint8Array(8))].map((x) => ALPHA[x % ALPHA.length]).join("");
const ROLES = ["owner", "editor", "viewer"];
const PLATFORMS = ["kick", "twitch"];
const TRIAL_CREDITS = 2;                       // TODO(payment): free trial size is a product decision; 1 credit = 1 hour of source stream
const VERIFY_TTL_H = 48;
const INVITE_TTL_D = 7;

// ---------- permissions: role -> allowed actions ----------
const PERMS = {
  owner: ["view", "job.create", "job.review", "style.set", "channel.manage", "team.manage", "billing.manage", "youtube.connect"],
  editor: ["view", "job.create", "job.review", "style.set"],
  viewer: ["view"],
};
export const can = (role, action) => !!(PERMS[role] && PERMS[role].includes(action));

// ---------- KV key layout (all under "studio:" so the owner app's keys are never touched) ----------
const K = {
  user: (id) => `studio:u:${id}`, email: (e) => `studio:e:${e}`, sess: (h) => `studio:s:${h}`,
  org: (id) => `studio:o:${id}`, mem: (o, u) => `studio:m:${o}:${u}`, memOfOrg: (o) => `studio:m:${o}:`, orgOfUser: (u, o) => `studio:uo:${u}:${o}`, orgsOfUser: (u) => `studio:uo:${u}:`,
  inv: (h) => `studio:i:${h}`, invOfOrg: (o, h) => `studio:io:${o}:${h}`, invsOfOrg: (o) => `studio:io:${o}:`,
  chan: (o, c) => `studio:c:${o}:${c}`, chansOfOrg: (o) => `studio:c:${o}:`, claim: (p, s) => `studio:claim:${p}:${s}`,
  job: (j) => `studio:j:${j}`, jobOfOrg: (o, j) => `studio:oj:${o}:${j}`, jobsOfOrg: (o) => `studio:oj:${o}:`, queue: (ts, j) => `studio:q:${ts}:${j}`,
  ingest: (h) => `studio:ingest:${h}`, ingestIdem: (h) => `studio:ingest:idem:${h}`, chat: (o) => `studio:chat:${o}`, rl: (k) => `studio:rl:${k}`, cfg: (k) => `studio:cfg:${k}`, cache: (k) => `studio:cache:${k}`,
};
const kget = (env, k) => env.KV.get(k, "json");
const kput = (env, k, v, opt) => env.KV.put(k, JSON.stringify(v), opt);
async function klist(env, prefix, limit = 200) { const r = await env.KV.list({ prefix, limit }); return r.keys.map((x) => x.name); }
async function kgetMany(env, keys) { return (await Promise.all(keys.map((k) => kget(env, k)))).filter(Boolean); }
async function cfg(env, name) { return (await env.KV.get(K.cfg(name))) || env["STUDIO_" + name.toUpperCase()] || ""; }

// ---------- passwords (PBKDF2-SHA256; 100000 is the Workers WebCrypto maximum) ----------
export async function hashPassword(pw, saltHex = rnd(16), iter = 100000) {
  const key = await crypto.subtle.importKey("raw", enc.encode(pw), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt: new Uint8Array(saltHex.match(/../g).map((h) => parseInt(h, 16))), iterations: iter }, key, 256);
  return { salt: saltHex, iter, hash: hex(bits) };
}
const safeEq = (a, b) => { if (a.length !== b.length) return false; let d = 0; for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i); return d === 0; };

// ---------- rate limit (best effort: KV counter) ----------
async function limited(env, req, bucket, max, ttl = 3600) {
  const ip = req.headers.get("cf-connecting-ip") || "x"; const k = K.rl(`${bucket}:${ip}`); const n = parseInt((await env.KV.get(k)) || "0");
  if (n >= max) return true;
  await env.KV.put(k, String(n + 1), { expirationTtl: Math.max(60, ttl) }); return false;
}

// ---------- request helpers ----------
async function body(req) { const t = await req.text(); if (t.length > 20000) throw new Error("too_large"); try { return t ? JSON.parse(t) : {}; } catch { throw new Error("bad_json"); } }
const clean = (s, n = 200) => String(s == null ? "" : s).trim().slice(0, n);
const validEmail = (e) => /^[^\s@]{1,64}@[^\s@]{1,190}\.[^\s@]{2,}$/.test(e);
// Accepts "https://kick.com/odedsvr", "twitch.tv/name", "@name" (+ explicit platform) -> {platform, slug} or null. One paste field instead of a platform dropdown + name field.
export function parseChannelInput(input, platformHint) {
  const t = clean(input, 200); if (!t) return null; const mm = t.match(/(?:^|\/\/)(?:www\.|m\.)?(kick\.com|twitch\.tv)\/([A-Za-z0-9_-]{2,25})/i);
  const platform = mm ? (mm[1].toLowerCase() === "kick.com" ? "kick" : "twitch") : clean(platformHint, 10).toLowerCase(); if (!PLATFORMS.includes(platform)) return null;
  const slug = normSlug(platform, mm ? mm[2] : t); return slug ? { platform, slug } : null;
}
export const normSlug = (platform, s) => { s = clean(s, 40).toLowerCase().replace(/^@/, ""); if (platform === "kick") s = s.replace(/_/g, "-"); return /^[a-z0-9][a-z0-9_-]{1,24}$/.test(s) ? s : ""; };

async function session(req, env) {
  const a = req.headers.get("authorization") || ""; if (!a.startsWith("Bearer ")) return null;
  const s = await kget(env, K.sess(await sha256(a.slice(7)))); if (!s || s.exp < Date.now()) return null;
  const u = await kget(env, K.user(s.uid)); return u ? { user: u, hash: await sha256(a.slice(7)) } : null;
}
async function roleIn(env, orgId, uid) { const m = await kget(env, K.mem(orgId, uid)); return m ? m.role : null; }
async function orgsOf(env, uid) {
  const keys = await klist(env, K.orgsOfUser(uid)); const out = [];
  for (const k of keys) { const orgId = k.split(":")[3]; const [o, r] = await Promise.all([kget(env, K.org(orgId)), roleIn(env, orgId, uid)]); if (o && r) out.push({ id: o.id, name: o.name, role: r, plan: o.plan, credits: o.credits }); }
  return out;
}
async function addMember(env, orgId, uid, email, role) {
  await Promise.all([kput(env, K.mem(orgId, uid), { uid, email, role, added: now() }), kput(env, K.orgOfUser(uid, orgId), { orgId })]);
}

// ---------- channel ownership verification ----------
// A code is placed by the streamer in the public bio/description or the live stream title; we read the public page and compare.
export function findCode(code, texts) { const c = code.toLowerCase(); for (const [where, t] of texts) if (t && String(t).toLowerCase().includes(c)) return where; return null; }

// Reads the PUBLIC channel info. fetchImpl is injectable for tests. Returns {ok, texts:[[where,text]], user_id, display, linked_youtube, error}.
// NOTE: kick.com/api/v2 is an undocumented endpoint and Kick's ToS section 1.4 forbids automated access: this is a stopgap.
// TODO(oauth): replace with Kick OAuth 2.1 (scope user:read, never channel:read: it returns the stream key) / Twitch OIDC login; then the code check becomes a fallback.
export async function fetchChannelPublic(platform, slug, env, fetchImpl = fetch) {
  try {
    if (platform === "kick") {
      const r = await fetchImpl(`https://kick.com/api/v2/channels/${encodeURIComponent(slug)}`, { headers: { accept: "application/json", "user-agent": "Mozilla/5.0 (compatible; OdedStudio/0.1)" } });
      if (r.status === 404) return { ok: false, error: "channel_not_found" };
      if (!r.ok) return { ok: false, error: "fetch_failed_" + r.status, hint: "Kick blocked the request; use the GitHub Actions/runner fallback (docs/PRODUCT_ARCHITECTURE.md)" };
      const d = await r.json();
      return { ok: true, user_id: String((d.user && d.user.id) || d.user_id || ""), display: d.user && d.user.username, linked_youtube: (d.user && d.user.youtube) || null,
        texts: [["bio", d.user && d.user.bio], ["stream_title", d.livestream && (d.livestream.session_title || d.livestream.title)]] };
    }
    if (platform === "twitch") {
      const c = await kget(env, K.cfg("twitch")) || (env.STUDIO_TWITCH_ID ? { id: env.STUDIO_TWITCH_ID, secret: env.STUDIO_TWITCH_SECRET } : null);
      if (!c || !c.id) return { ok: false, error: "twitch_not_configured", hint: "put {id,secret} of a Twitch app (client credentials) into KV key studio:cfg:twitch" };
      let tok = await env.KV.get(K.cache("twitch_tok"));
      if (!tok) {
        const t = await fetchImpl(`https://id.twitch.tv/oauth2/token?client_id=${encodeURIComponent(c.id)}&client_secret=${encodeURIComponent(c.secret)}&grant_type=client_credentials`, { method: "POST" });
        if (!t.ok) return { ok: false, error: "twitch_auth_failed_" + t.status };
        const tj = await t.json(); tok = tj.access_token; await env.KV.put(K.cache("twitch_tok"), tok, { expirationTtl: Math.max(60, (tj.expires_in || 3600) - 300) });
      }
      const h = { authorization: "Bearer " + tok, "client-id": c.id };
      const [u, s] = await Promise.all([fetchImpl(`https://api.twitch.tv/helix/users?login=${encodeURIComponent(slug)}`, { headers: h }), fetchImpl(`https://api.twitch.tv/helix/streams?user_login=${encodeURIComponent(slug)}`, { headers: h })]);
      if (!u.ok) return { ok: false, error: "fetch_failed_" + u.status };
      const uj = await u.json(); const usr = uj.data && uj.data[0]; if (!usr) return { ok: false, error: "channel_not_found" };
      const sj = s.ok ? await s.json() : { data: [] }; const st = sj.data && sj.data[0];
      return { ok: true, user_id: usr.id, display: usr.display_name, linked_youtube: null, texts: [["bio", usr.description], ["stream_title", st && st.title]] };
    }
  } catch (e) { return { ok: false, error: "fetch_exception", hint: String(e && e.message || e).slice(0, 120) }; }
  return { ok: false, error: "bad_platform" };
}

// ---------- styles (config/styles/*.json, created by another workstream) ----------
// ONE signature style for now (owner decision). The data model keeps style_id per channel so more styles can be added later without a migration; the UI shows no picker.
export const DEFAULT_STYLE = "signature";
const BUILTIN_STYLES = [{ id: DEFAULT_STYLE, name: "הסגנון שלנו / Our style", description: "Fast cuts, burned captions, strong hook, clean ending.", source: "builtin" }];
export async function listStyles(env, fetchImpl = fetch) {
  const cached = await kget(env, K.cache("styles")); if (cached) return cached;
  let list = [];
  try {
    const tok = await env.KV.get("gh");          // optional owner token (needed once the repo is private); only used to read style metadata
    const h = { accept: "application/vnd.github+json", "user-agent": "odedstudio", ...(tok ? { authorization: "Bearer " + tok } : {}) };
    const r = await fetchImpl(`https://api.github.com/repos/${REPO}/contents/config/styles`, { headers: h });
    if (r.ok) {
      const files = (await r.json()).filter((f) => f.name.endsWith(".json") && f.type === "file");
      list = (await Promise.all(files.slice(0, 50).map(async (f) => {
        try { const j = await (await fetchImpl(f.download_url, { headers: h })).json(); const id = f.name.replace(/\.json$/, "");
          return { id, name: clean(j.name || j.title || j.label || id, 80), description: clean(j.description || j.summary || j.notes || "", 300), lang: j.lang || j.language || null, source: "repo" }; } catch { return null; }
      }))).filter(Boolean);
    }
  } catch { /* keep builtin */ }
  const out = [...BUILTIN_STYLES, ...list.filter((s) => s.id !== DEFAULT_STYLE)];
  await kput(env, K.cache("styles"), out, { expirationTtl: 600 }); return out;
}

// ---------- jobs ----------
const JOB_FLOW = { queued: ["running", "cancelled"], running: ["qa", "failed", "cancelled"], qa: ["draft_ready", "failed"], draft_ready: ["approved", "rejected"], approved: [], rejected: [], failed: [], cancelled: [] };
export const canTransition = (from, to) => (JOB_FLOW[from] || []).includes(to);
export const estimateCredits = (src) => Math.max(1, Math.ceil((Number(src && src.duration_min) || 60) / 60));   // 1 credit = 1 started hour of source; TODO(pricing): see PRODUCT_PLAN.md
async function refund(env, job) {
  if (!job.credits_held) return; const o = await kget(env, K.org(job.org)); if (!o) return;
  o.credits += job.credits_held; job.credits_held = 0; await kput(env, K.org(o.id), o);   // TODO(D1): not atomic, use a ledger table + transaction
}
// preview_url = where the browser can play a small preview rendition of a draft (preview phase: a public GitHub release asset made by .github/workflows/studio-worker.yml, see docs/STUDIO_PREVIEW_SETUP.md).
// Only that exact shape is accepted (https, github.com release download of an .mp4), so a leaked worker key cannot point the player at an arbitrary site.
export const previewUrl = (u) => (typeof u === "string" && u.length <= 300 && /^https:\/\/github\.com\/[A-Za-z0-9_.-]{1,60}\/[A-Za-z0-9_.-]{1,100}\/releases\/download\/[A-Za-z0-9._-]{1,120}\/[A-Za-z0-9._-]{1,120}\.mp4$/.test(u) ? u : "");
const pubJob = (j) => j;   // jobs hold no secrets; keep a hook in case that changes


// ---------- progress messages (short, friendly, he+en). The render worker sends a key + vars; the app shows the language of the browser. ----------
export const MSG = {
  queued: { he: "בתור - מתחילים עוד רגע", en: "Queued - starting in a moment" },
  running: { he: "מתחילים לעבוד על זה...", en: "Getting started..." },
  downloading: { he: "מביאים את הסטרים...", en: "Fetching your stream..." },
  transcribing: { he: "מקשיבים לסטרים... {pct}%", en: "Listening to the stream... {pct}%" },
  found_moments: { he: "מצאנו {n} רגעים, חותכים...", en: "Found {n} moments, cutting..." },
  rendering: { he: "מכינים קליפ {i} מתוך {n}...", en: "Making clip {i} of {n}..." },
  qa: { he: "בודקים איכות...", en: "Quality check..." },
  draft_ready: { he: "{n} טיוטות מוכנות - תעבור עליהן!", en: "{n} drafts are ready - take a look!" },
  approved: { he: "אושר. מעולה!", en: "Approved. Nice!" },
  rejected: { he: "נדחה. אפשר לבקש גרסה אחרת בצ'אט.", en: "Rejected. Ask in the chat for another take." },
  failed: { he: "משהו השתבש. החזרנו לך את הקרדיט.", en: "Something went wrong. Your credit is back." },
  cancelled: { he: "בוטל. החזרנו לך את הקרדיט.", en: "Cancelled. Your credit is back." },
};
export const renderMsg = (key, vars = {}) => { const t = MSG[key]; if (!t) return null; const f = (s) => s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] != null ? String(vars[k]).slice(0, 20) : "")); return { he: f(t.he), en: f(t.en) }; };
const setStatusText = (job, key, vars) => { const m = renderMsg(key, vars); if (m) job.status_text = m; };

// ---------- assistant chat: plain language -> a job (rule based; TODO(LLM): env.AI/Haiku-class model for free-form requests, same output shape) ----------
const NUMW = { one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10, "אחד": 1, "אחת": 1, "שני": 2, "שתי": 2, "שניים": 2, "שלוש": 3, "שלושה": 3, "ארבע": 4, "ארבעה": 4, "חמש": 5, "חמישה": 5, "שש": 6, "שישה": 6, "שבע": 7, "שבעה": 7, "שמונה": 8, "תשע": 9, "תשעה": 9, "עשר": 10, "עשרה": 10 };
export function understand(text) {
  const raw = clean(text, 500), t = raw.toLowerCase(), he = /[֐-׿]/.test(raw);
  let count = (t.match(/\d+/) || [])[0]; if (count) count = parseInt(count); else for (const w of t.split(/[\s,.!?]+/)) if (NUMW[w]) { count = NUMW[w]; break; }
  const status = /status|progress|ready yet|how.*(going|long)|what.?s up|מה המצב|התקדמות|מוכן כבר|עוד כמה|איפה זה/.test(t);
  const wantsLong = /\blong\b|full video|compilation|סרטון ארוך|וידאו ארוך|סרטון מלא|סיכום|קומפילציה|יוטיוב ארוך/.test(t);
  const wantsShorts = /short|clip|reel|tiktok|שורט|קליפ|קצר/.test(t);
  const when = /yesterday|אתמול/.test(t) ? "yesterday" : /last week|שבוע שעבר/.test(t) ? "week" : "last_stream";   // default: the latest stream
  const mood = /funny|lol|hilarious|מצחיק|הזוי|צחוק/.test(t) ? "funny" : /hype|epic|insane|clutch|מטורף|אפי/.test(t) ? "hype" : /fail|rage|כעס|פיל/.test(t) ? "fail" : null;
  const make = /make|create|cut|edit|give|need|want|תעשה|תכין|צור|תחתוך|תערוך|תן|רוצה|צריך|בא לי/.test(t);
  const intent = status ? "status" : make || wantsLong || wantsShorts || count ? "create" : "help";
  const shorts = wantsLong && !wantsShorts && !count ? 0 : Math.min(30, count || 5);
  return { intent, he, shorts, long: wantsLong, when, mood, text: raw };
}
const WHEN_TXT = { yesterday: { he: "מהסטרים של אתמול", en: "from yesterday's stream" }, last_stream: { he: "מהסטרים האחרון", en: "from your latest stream" }, week: { he: "מהשבוע האחרון", en: "from last week" } };
const MOOD_TXT = { funny: { he: "מצחיקים", en: "funny" }, hype: { he: "מטורפים", en: "hype" }, fail: { he: "של פיילים", en: "fail" } };
const HELP = { he: "אפשר לבקש בשפה חופשית, למשל: \"תכין 5 שורטס מצחיקים מאתמול\" או \"מה המצב?\"", en: "Ask in plain words, e.g. \"make 5 funny Shorts from yesterday\" or \"what's the status?\"" };
// ---- free-form understanding with a free LLM (Workers AI binding `AI`): replies vary, remember the conversation, answer product questions; the rule parser above stays as the fallback and as the safety net
const LLM_MODELS = ["@cf/openai/gpt-oss-120b", "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/meta/llama-3.1-8b-instruct"];
const LLM_DAILY = 60;   // per workspace; free tier friendly
function firstJson(text) { const t = String(text || ""); const a = t.indexOf("{"); if (a < 0) return null; let d = 0, q = false, e = false; for (let i = a; i < t.length; i++) { const c = t[i]; if (q) { if (e) e = false; else if (c === "\\") e = true; else if (c === '"') q = false; continue; } if (c === '"') q = true; else if (c === "{") d++; else if (c === "}" && --d === 0) { try { return JSON.parse(t.slice(a, i + 1)); } catch (x) { return null; } } } return null; }
async function llmUnderstand(env, org, role, text, hist, L, ctx) {
  if (!env.AI) return null;
  const day = new Date().toISOString().slice(0, 10), key = `studio:llm:${org.id}:${day}`; const used = parseInt((await env.KV.get(key)) || "0"); if (used >= LLM_DAILY) return null;
  try { await env.KV.put(key, String(used + 1), { expirationTtl: 172800 }); } catch (e) {}
  const system = `You are the assistant inside "Studio", a product that turns a streamer's live streams (Kick / Twitch) into Shorts and long YouTube videos, edited automatically, delivered as PRIVATE drafts that the customer approves.
Facts you can rely on: the customer connects a channel by pasting its link and proving ownership with a code placed in the channel bio or stream title; one credit = one hour of source stream; drafts are always private until the customer publishes; approve / reject happens in the Review tab (swipe or arrow keys); team members are invited in the Team tab (owner / editor / viewer); the system picks moments (laughs, hype, fails, stories), cuts at sentence boundaries, adds captions and a logo, and runs a quality check; YouTube connection and payments are coming soon; the assistant itself can start jobs and report status. Never claim anything else, never invent numbers, never promise publishing.
You can start a job for the customer: up to 30 Shorts and/or one long video, from the last stream, yesterday, or last week, optionally with a mood (funny / hype / fail).
Style: warm, short, specific, like a sharp producer; reply in the customer's language (${L === "he" ? "Hebrew" : "English"}); never repeat a sentence you already said in this conversation; if the request is vague, ask ONE clear question; if they ask what you can do, give a concrete example tailored to their situation.
Customer context: role=${role}; credits=${ctx.credits}; verified channels=${ctx.channels.join(", ") || "none yet"}; recent jobs=${ctx.jobs.join(" | ") || "none"}.
Output ONLY JSON: {"reply": "<what you say>", "intent": "create" | "status" | "chat", "shorts": <int 0-30>, "long": <true|false>, "when": "last_stream" | "yesterday" | "week", "mood": "funny" | "hype" | "fail" | null}. Use intent "create" only when the customer clearly asked you to make something now; "status" when they ask about progress; otherwise "chat".`;
  const messages = [{ role: "system", content: system }, ...hist.slice(-10).map((h) => ({ role: h.r === "bot" ? "assistant" : "user", content: String(h.text || "").slice(0, 400) })), { role: "user", content: clean(text, 500) }];
  for (const m of LLM_MODELS) {
    try {
      const r = await env.AI.run(m, m.includes("gpt-oss") ? { input: messages, reasoning: { effort: "low" }, max_output_tokens: 700 } : { messages, max_tokens: 700 });
      const t = r.response || (r.choices && r.choices[0] && r.choices[0].message && r.choices[0].message.content) || r.output_text || (r.output && r.output.map((o) => (o.content || []).map((c) => c.text || "").join("")).join("")) || "";
      const j = firstJson(t); if (j && typeof j.reply === "string" && j.reply.trim()) { return { reply: clean(j.reply, 700), intent: ["create", "status", "chat"].includes(j.intent) ? j.intent : "chat", shorts: Math.max(0, Math.min(30, parseInt(j.shorts) || 0)), long: !!j.long, when: ["last_stream", "yesterday", "week"].includes(j.when) ? j.when : "last_stream", mood: ["funny", "hype", "fail"].includes(j.mood) ? j.mood : null }; }
    } catch (e) { /* next model */ }
  }
  return null;
}
async function assistant(env, org, me, role, b, store) {
  const u = understand(b.message); const L = u.he ? "he" : "en"; let reply, actions = [];
  if (!u.text) return { reply: HELP[L], actions };
  let llm = null;
  try {
    const hist0 = (await kget(env, K.chat(org.id))) || [];
    const chs = (await kgetMany(env, await klist(env, K.chansOfOrg(org.id)))).filter((c) => c.status === "verified").map((c) => `${c.platform}/${c.slug}`);
    const js = (await kgetMany(env, (await klist(env, K.jobsOfOrg(org.id), 500)).map((k) => K.job(k.split(":")[3])))).sort((a, c) => (a.created < c.created ? 1 : -1)).slice(0, 3).map((j) => `${j.status} ${j.progress}%`);
    const fresh0 = await kget(env, K.org(org.id)); llm = await llmUnderstand(env, org, role, u.text, hist0, L, { credits: fresh0 ? fresh0.credits : org.credits, channels: chs, jobs: js });
  } catch (e) { llm = null; }
  if (llm) { if (llm.intent === "create" && (llm.shorts > 0 || llm.long)) { u.intent = "create"; u.shorts = llm.shorts; u.long = llm.long; u.when = llm.when; u.mood = llm.mood; } else if (llm.intent === "status") u.intent = "status"; else u.intent = "chat"; }
  if (u.intent === "chat") reply = llm ? llm.reply : HELP[L];
  else if (u.intent === "help") reply = HELP[L];
  else if (u.intent === "status") {
    const jobs = (await kgetMany(env, (await klist(env, K.jobsOfOrg(org.id), 500)).map((k) => K.job(k.split(":")[3])))).sort((a, c) => (a.created < c.created ? 1 : -1));
    const j = jobs[0]; reply = !j ? (L === "he" ? "עדיין אין עבודות. בקש משהו בצ'אט!" : "No jobs yet. Ask me for something!") : `${(j.status_text || renderMsg(j.status) || { he: j.status, en: j.status })[L]} (${j.progress}%)`;
    if (j) actions.push({ type: "show_job", job_id: j.id });
  } else if (!can(role, "job.create")) reply = L === "he" ? "לצפיינים אין הרשאה ליצור עבודות. בקש מהבעלים להפוך אותך לעורך." : "Viewers can't create jobs. Ask the owner to make you an editor.";
  else {
    const chans = (await kgetMany(env, await klist(env, K.chansOfOrg(org.id)))).filter((c) => c.status === "verified"); const ch = chans.find((c) => c.id === b.channel_id) || chans[0];
    if (!ch) reply = L === "he" ? "קודם נחבר ערוץ: הדבק קישור לערוץ שלך למעלה ואמת בעלות. זה לוקח דקה." : "First let's connect a channel: paste your channel link above and verify ownership. Takes a minute.";
    else {
      const source = { type: "auto", when: u.when, duration_min: null }, credits = estimateCredits(source); const fresh = await kget(env, K.org(org.id));
      if (fresh.credits < credits) reply = L === "he" ? `נגמרו הקרדיטים (צריך ${credits}, יש ${fresh.credits}). אפשר להוסיף בלשונית תשלום.` : `Out of credits (need ${credits}, have ${fresh.credits}). You can top up in Billing.`;
      else {
        const job = await createJob(env, org, { channel_id: ch.id, kind: "edit", source, style_id: ch.style_id, outputs: { shorts: u.shorts, long: u.long }, credits, hints: { mood: u.mood, text: u.text } });
        const what = [u.shorts ? (L === "he" ? `${u.shorts} שורטס${u.mood ? " " + MOOD_TXT[u.mood].he : ""}` : `${u.shorts} ${u.mood ? MOOD_TXT[u.mood].en + " " : ""}Shorts`) : "", u.long ? (L === "he" ? "סרטון ארוך" : "a long video") : ""].filter(Boolean).join(L === "he" ? " ו" : " and ");
        reply = L === "he" ? `סבבה! מכין ${what} ${WHEN_TXT[u.when].he}. אעדכן כאן כשהטיוטות מוכנות. אפשר לבטל כל עוד זה בתור.` : `On it! Making ${what} ${WHEN_TXT[u.when].en}. I'll update you here when drafts are ready. You can cancel while it's queued.`;
        actions.push({ type: "job_created", job_id: job.id });
      }
    }
  }
  const hist = (await kget(env, K.chat(org.id))) || []; hist.push({ r: "user", t: now(), text: u.text }, { r: "bot", t: now(), text: reply }); await kput(env, K.chat(org.id), hist.slice(-40));   // TODO(D1): per-user threads
  return { reply, actions, parsed: { intent: u.intent, shorts: u.shorts, long: u.long, when: u.when, mood: u.mood } };
}

// ---------- the router ----------
export async function handleStudio(req, env, fetchImpl = fetch) {
  const u = new URL(req.url); const p = u.pathname.replace(/\/+$/, "") || "/studio"; const m = req.method;
  if (p === "/studio") return new Response(STUDIO_HTML, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-cache", ...SEC } });
  if (p === "/studio/api/health") return json({ ok: true, t: now() });

  // --- render-worker API (machine to machine; secret lives in KV studio:cfg:worker_key or env.STUDIO_WORKER_KEY)
  if (p.startsWith("/studio/worker/")) return workerApi(req, env, p, m);
  if (!p.startsWith("/studio/api/")) return err(404, "not_found");
  const path = p.slice("/studio/api".length); let b = {};
  try { if (m === "POST" || m === "PATCH" || m === "PUT") b = await body(req); } catch (e) { return err(400, e.message); }

  // --- public: signup / login
  if (path === "/signup" && m === "POST") {
    if (await limited(env, req, "signup", 10)) return err(429, "rate_limited");
    const email = clean(b.email, 254).toLowerCase(); const pw = String(b.password || ""); const name = clean(b.name, 80) || email.split("@")[0];
    if (!validEmail(email)) return err(400, "bad_email"); if (pw.length < 8) return err(400, "password_too_short");
    if (await env.KV.get(K.email(email))) return err(409, "email_exists");
    const uid = "u_" + rnd(8), orgId = "o_" + rnd(8);
    await Promise.all([kput(env, K.user(uid), { id: uid, email, name, pw: await hashPassword(pw), created: now() }), env.KV.put(K.email(email), uid),
      kput(env, K.org(orgId), { id: orgId, name: name + " team", owner: uid, plan: "trial", credits: TRIAL_CREDITS, created: now() })]);   // TODO(email): verify the email address before granting trial credits (abuse)
    await addMember(env, orgId, uid, email, "owner");
    return json({ token: await newSession(env, uid), user: { id: uid, email, name }, org_id: orgId });
  }
  if (path === "/guest" && m === "POST") {   // no email, no password: one click creates a throw-away workspace (owner request for the preview phase); disable with env STUDIO_GUEST=0
    if (env.STUDIO_GUEST === "0") return err(403, "guest_disabled");
    if (await limited(env, req, "guest", 8)) return err(429, "rate_limited");
    const uid = "u_" + rnd(8), orgId = "o_" + rnd(8), email = "guest-" + rnd(6) + "@guest.invalid", name = "Guest";
    await Promise.all([kput(env, K.user(uid), { id: uid, email, name, guest: true, pw: await hashPassword(rnd(24)), created: now() }), env.KV.put(K.email(email), uid),
      kput(env, K.org(orgId), { id: orgId, name: "My studio", owner: uid, plan: "trial", credits: TRIAL_CREDITS, created: now() })]);
    await addMember(env, orgId, uid, email, "owner");
    return json({ token: await newSession(env, uid), user: { id: uid, email, name }, org_id: orgId });
  }
  if (path === "/login" && m === "POST") {
    if (await limited(env, req, "login", 20)) return err(429, "rate_limited");
    const email = clean(b.email, 254).toLowerCase(); const uid = await env.KV.get(K.email(email)); const usr = uid && await kget(env, K.user(uid));
    const bad = () => err(401, "bad_credentials");
    if (email) { const ak = K.rl("acct:" + email.slice(0, 120)); const fails = parseInt((await env.KV.get(ak)) || "0"); if (fails >= 10) return err(429, "rate_limited"); b._ak = ak; b._fails = fails; }   // per-account: 10 wrong passwords per hour, whatever the IP
    if (!usr) { await hashPassword(String(b.password || ""), rnd(16)); if (b._ak) await env.KV.put(b._ak, String(b._fails + 1), { expirationTtl: 3600 }); return bad(); }   // equalise timing
    const h = await hashPassword(String(b.password || ""), usr.pw.salt, usr.pw.iter); if (!safeEq(h.hash, usr.pw.hash)) { if (b._ak) await env.KV.put(b._ak, String(b._fails + 1), { expirationTtl: 3600 }); return bad(); }
    return json({ token: await newSession(env, uid), user: { id: uid, email: usr.email, name: usr.name } });
  }
  if (path === "/invites/preview" && m === "POST") {   // public: lets an invitee see what they are joining before signup
    const inv = await kget(env, K.inv(await sha256(String(b.token || "")))); if (!inv || inv.exp < Date.now()) return err(404, "invite_invalid");
    const o = await kget(env, K.org(inv.org)); return json({ org: o && o.name, role: inv.role, email: inv.email });
  }

  // --- everything below needs a session
  const ses = await session(req, env); if (!ses) return err(401, "unauthorized");
  const me = ses.user; let mt;
  if (path === "/logout" && m === "POST") { await env.KV.delete(K.sess(ses.hash)); return json({ ok: true }); }
  if (path === "/me" && m === "GET") return json({ user: { id: me.id, email: me.email, name: me.name }, orgs: await orgsOf(env, me.id) });
  if (path === "/styles" && m === "GET") return json({ default: DEFAULT_STYLE, styles: await listStyles(env, fetchImpl) });   // the app shows only "our style"; the list exists for later
  if (path === "/invites/accept" && m === "POST") {
    const h = await sha256(String(b.token || "")); const inv = await kget(env, K.inv(h)); if (!inv || inv.exp < Date.now()) return err(404, "invite_invalid");
    if (inv.email && inv.email !== me.email) return err(403, "invite_for_other_email");
    const have = await roleIn(env, inv.org, me.id); const RANK = { viewer: 1, editor: 2, owner: 3 }; if (!have || RANK[inv.role] > RANK[have]) await addMember(env, inv.org, me.id, me.email, inv.role); await Promise.all([env.KV.delete(K.inv(h)), env.KV.delete(K.invOfOrg(inv.org, h))]);
    return json({ ok: true, org_id: inv.org, role: have && RANK[have] >= RANK[inv.role] ? have : inv.role });
  }

  // --- org-scoped routes: /orgs/:id/...
  if (path === "/orgs" && m === "POST") {   // create another org (agency/editor with several clients)
    const name = clean(b.name, 80); if (!name) return err(400, "name_required"); const orgId = "o_" + rnd(8);
    await kput(env, K.org(orgId), { id: orgId, name, owner: me.id, plan: "none", credits: 0, created: now() }); await addMember(env, orgId, me.id, me.email, "owner"); return json({ org_id: orgId });
  }
  if (!(mt = path.match(/^\/orgs\/(o_[a-f0-9]+)(\/.*)?$/))) return err(404, "not_found");
  const orgId = mt[1], sub = mt[2] || ""; const role = await roleIn(env, orgId, me.id); if (!role) return err(404, "not_found");   // 404, not 403: do not reveal other orgs exist
  const org = await kget(env, K.org(orgId)); if (!org) return err(404, "not_found");
  const need = (a) => (can(role, a) ? null : err(403, "forbidden", { need: a, role }));
  let x;

  if (sub === "" && m === "GET") return json({ org: { id: org.id, name: org.name, plan: org.plan, credits: org.credits }, role });

  // team ---
  if (sub === "/members" && m === "GET") return json({ members: (await kgetMany(env, await klist(env, K.memOfOrg(orgId)))).map((x) => ({ uid: x.uid, email: x.email, role: x.role })), invites: (await kgetMany(env, await klist(env, K.invsOfOrg(orgId)))).map((i) => ({ id: i.id, email: i.email, role: i.role, expires: new Date(i.exp).toISOString() })) });
  if (sub === "/invites" && m === "POST") {
    let d = need("team.manage"); if (d) return d; const email = clean(b.email, 254).toLowerCase(); if (!validEmail(email)) return err(400, "bad_email"); if (!ROLES.includes(b.role) || b.role === "owner") return err(400, "bad_role");
    const token = "inv_" + rnd(24), h = await sha256(token), exp = Date.now() + INVITE_TTL_D * 864e5; const rec = { id: h.slice(0, 12), org: orgId, email, role: b.role, exp, by: me.id };
    await Promise.all([kput(env, K.inv(h), rec, { expirationTtl: INVITE_TTL_D * 86400 }), kput(env, K.invOfOrg(orgId, h), rec, { expirationTtl: INVITE_TTL_D * 86400 })]);
    return json({ ok: true, invite_id: rec.id, accept_url: `${u.origin}/studio#invite=${token}`, note: "TODO(email): send this link by email; for now the owner copies it." });
  }
  if ((x = sub.match(/^\/invites\/([a-f0-9]{12})$/)) && m === "DELETE") {
    let d = need("team.manage"); if (d) return d; for (const k of await klist(env, K.invsOfOrg(orgId))) { const i = await kget(env, k); if (i && i.id === x[1]) { const h = k.split(":")[3]; await Promise.all([env.KV.delete(k), env.KV.delete(K.inv(h))]); return json({ ok: true }); } } return err(404, "not_found");
  }
  if ((x = sub.match(/^\/members\/(u_[a-f0-9]+)$/))) {
    let d = need("team.manage"); if (d) return d; const mem = await kget(env, K.mem(orgId, x[1])); if (!mem) return err(404, "not_found");
    if (mem.role === "owner") return err(400, "cannot_change_owner");   // TODO: ownership transfer flow
    if (m === "PATCH") { if (!ROLES.includes(b.role) || b.role === "owner") return err(400, "bad_role"); mem.role = b.role; await kput(env, K.mem(orgId, x[1]), mem); return json({ ok: true }); }
    if (m === "DELETE") { await Promise.all([env.KV.delete(K.mem(orgId, x[1])), env.KV.delete(K.orgOfUser(x[1], orgId))]); return json({ ok: true }); }
  }

  // channels ---
  if (sub === "/channels" && m === "GET") return json({ channels: await kgetMany(env, await klist(env, K.chansOfOrg(orgId))) });
  if (sub === "/channels" && m === "POST") {
    let d = need("channel.manage"); if (d) return d; const pc = parseChannelInput(b.url || b.slug, b.platform); if (!pc) return err(400, "bad_channel", { he: "לא הצלחתי לזהות את הערוץ. הדבק קישור כמו kick.com/name או twitch.tv/name", en: "Could not recognise the channel. Paste a link like kick.com/name or twitch.tv/name" }); const { platform, slug } = pc;
    const existing = (await kgetMany(env, await klist(env, K.chansOfOrg(orgId)))).find((c) => c.platform === platform && c.slug === slug); if (existing) return json({ channel: existing, existing: true });
    const ch = { id: "c_" + rnd(6), org: orgId, platform, slug, status: "pending", verify_code: newVerifyCode(), verify_expires: new Date(Date.now() + VERIFY_TTL_H * 36e5).toISOString(), style_id: DEFAULT_STYLE, yt: { status: "not_connected" }, created: now() };
    await kput(env, K.chan(orgId, ch.id), ch);
    return json({ channel: ch, instructions: `Put the code ${ch.verify_code} in your ${platform === "kick" ? "Kick profile bio" : "Twitch channel description (About panel)"} OR in your live stream title, then press Verify. You may remove it afterwards.` });
  }
  if ((x = sub.match(/^\/channels\/(c_[a-f0-9]+)(\/[a-z-]+)?$/))) {
    const ch = await kget(env, K.chan(orgId, x[1])); if (!ch) return err(404, "not_found"); const act = x[2] || "";
    if (act === "" && m === "DELETE") { let d = need("channel.manage"); if (d) return d; await env.KV.delete(K.chan(orgId, ch.id)); if (ch.status === "verified") await env.KV.delete(K.claim(ch.platform, ch.slug)); return json({ ok: true }); }
    if (act === "/verify" && m === "POST") {
      let d = need("channel.manage"); if (d) return d; if (ch.status === "verified") return json({ channel: ch });
      if (await limited(env, req, "verify:" + ch.id, 30)) return err(429, "rate_limited");
      if (Date.parse(ch.verify_expires) < Date.now()) { ch.verify_code = newVerifyCode(); ch.verify_expires = new Date(Date.now() + VERIFY_TTL_H * 36e5).toISOString(); await kput(env, K.chan(orgId, ch.id), ch); return err(410, "code_expired", { new_code: ch.verify_code }); }
      const pub = await fetchChannelPublic(ch.platform, ch.slug, env, fetchImpl); if (!pub.ok) return err(502, pub.error, { hint: pub.hint });
      const where = findCode(ch.verify_code, pub.texts); if (!where) return json({ verified: false, reason: "code_not_found", checked: pub.texts.map(([w]) => w), he: "עוד לא רואים את הקוד. ודא שהוא בביו/בתיאור או בכותרת הסטרים ושמרת.", en: "Code not visible yet. Make sure it is in your bio/description or stream title and saved." });
      const owner = await env.KV.get(K.claim(ch.platform, ch.slug)); if (owner && owner !== orgId) return err(409, "channel_already_claimed");   // TODO: dispute flow (the real owner proves with the code, ours is revoked)
      Object.assign(ch, { status: "verified", verified_at: now(), verified_via: where, platform_user_id: pub.user_id, display: pub.display, linked_youtube: pub.linked_youtube });
      await Promise.all([kput(env, K.chan(orgId, ch.id), ch), env.KV.put(K.claim(ch.platform, ch.slug), orgId)]);
      return json({ verified: true, channel: ch });
    }
    if (act === "/style" && m === "POST") {   // not used by the UI today (single signature style); kept so a later multi-style product needs no migration
      let d = need("style.set"); if (d) return d; const sid = clean(b.style_id, 60);
      if (!(await listStyles(env, fetchImpl)).some((s) => s.id === sid)) return err(400, "unknown_style"); ch.style_id = sid; await kput(env, K.chan(orgId, ch.id), ch); return json({ channel: ch });
    }
    if (act === "/ingest" && m === "POST") {   // restream key for docs/INGEST.md: the customer streams to rtmp://<ingest host>/live/<key>; only the SHA-256 is stored, the key is shown once (calling again rotates it)
      let d = need("channel.manage"); if (d) return d; if (ch.status !== "verified") return err(409, "channel_not_verified");
      const key = "ik_" + rnd(16), h = await sha256(key); if (ch.ingest_hash) await env.KV.delete(K.ingest(ch.ingest_hash));
      ch.ingest_hash = h; ch.ingest_at = now(); await Promise.all([kput(env, K.chan(orgId, ch.id), ch), kput(env, K.ingest(h), { org: orgId, channel: ch.id })]);
      return json({ ingest_key: key, path: "live/" + key, note: "Shown once. Stream to rtmp://<ingest host>/live/" + key + " (or srt://<ingest host>:8890?streamid=publish:live/" + key + "). Calling this again replaces the key." });
    }
    if (act === "/youtube" && m === "POST") {
      let d = need("youtube.connect"); if (d) return d;
      // TODO(youtube-oauth): build https://accounts.google.com/o/oauth2/v2/auth?client_id=..&redirect_uri=<origin>/studio/api/youtube/callback&response_type=code&access_type=offline&prompt=consent
      //   &scope=youtube.upload youtube.readonly&state=<signed {org,channel,uid}>. In the callback exchange the code, store the REFRESH token encrypted (AES-GCM, key in secret STUDIO_ENC_KEY), never in plaintext KV.
      //   Needs Google OAuth app verification (sensitive scopes) + public privacy policy/ToS pages; until verified only 100 test users. See docs/PRODUCT_PLAN.md section 2.
      return err(501, "youtube_oauth_not_implemented", { todo: "see TODO(youtube-oauth) in app/studio.js" });
    }
  }

  // jobs ---
  if (sub === "/jobs" && m === "GET") return json({ jobs: (await kgetMany(env, await klist(env, K.jobsOfOrg(orgId), 500).then((ks) => ks.map((k) => K.job(k.split(":")[3]))))).sort((a, b) => (a.created < b.created ? 1 : -1)).slice(0, 100).map(pubJob) });
  if (sub === "/jobs" && m === "POST") {
    let d = need("job.create"); if (d) return d; const ch = await kget(env, K.chan(orgId, clean(b.channel_id, 20))); if (!ch) return err(400, "channel_not_found"); if (ch.status !== "verified") return err(409, "channel_not_verified");
    const type = clean(b.source && b.source.type, 10); if (!["vod", "live", "url", "auto"].includes(type)) return err(400, "bad_source_type");
    const source = { type, ref: clean(b.source && b.source.ref, 300), when: ["yesterday", "last_stream", "week"].includes(b.source && b.source.when) ? b.source.when : undefined, duration_min: Number(b.source && b.source.duration_min) || null };   // "auto" = worker finds the stream by date (the assistant and one-click flows use it)   // TODO(ingest): for "live" the poller creates jobs itself; for "vod" validate that ref belongs to ch.slug
    const credits = estimateCredits(source); if (org.credits < credits) return err(402, "insufficient_credits", { need: credits, have: org.credits });   // TODO(payment): offer top-up/checkout here
    const job = await createJob(env, org, { channel_id: ch.id, kind: "edit", source, style_id: ch.style_id, outputs: { shorts: Math.min(30, Number(b.shorts) || 5), long: b.long !== false }, credits });
    return json({ job: pubJob(job) });
  }
  let x1 = null;
  if ((x = sub.match(/^\/jobs\/(j_[a-f0-9]+)(\/[a-z]+|\/drafts\/\d+\/(?:approve|reject|title))?$/))) {
    const job = await kget(env, K.job(x[1])); if (!job || job.org !== orgId) return err(404, "not_found"); const act = x[2] && x[2].startsWith("/drafts") ? "/draft" : x[2] || "";
    if (act === "" && m === "GET") return json({ job: pubJob(job) });
    // Approve / reject: per draft (the swipe action in the UI) or all undecided drafts at once (bulk buttons). When every draft has a decision the job is closed.
    // Approve never publishes by itself in the MVP; TODO(youtube): flip the private draft to the visibility chosen in settings via videos.update, only after this explicit click.
    if (act === "/approve" || act === "/reject" || (x1 = sub.match(/^\/jobs\/j_[a-f0-9]+\/drafts\/(\d+)\/(approve|reject)$/))) {
      let d = need("job.review"); if (d) return d; if (m !== "POST") return err(405, "method"); if (job.status !== "draft_ready") return err(409, "bad_state", { status: job.status });
      const verdict = (x1 ? x1[2] : act.slice(1)) === "approve" ? "approved" : "rejected";
      const targets = x1 ? [job.result.drafts[parseInt(x1[1])]] : job.result.drafts.filter((dr) => !dr.decision); if (targets.some((t) => !t)) return err(404, "draft_not_found");
      for (const t of targets) { t.decision = verdict; t.decided_by = me.id; }
      job.events.push({ t: now(), e: "draft_" + verdict, by: me.id, n: targets.length });
      if (job.result.drafts.every((dr) => dr.decision)) { job.status = job.result.drafts.some((dr) => dr.decision === "approved") ? "approved" : "rejected"; setStatusText(job, job.status); }
      job.updated = now(); await kput(env, K.job(job.id), job); return json({ job: pubJob(job) });
    }
    // Inline title edit from the review screen: the customer may rename a draft before approving (the render worker / YouTube step reads the final title from job.result.drafts[i].title).
    if ((x1 = sub.match(/^\/jobs\/j_[a-f0-9]+\/drafts\/(\d+)\/title$/))) {
      let d = need("job.review"); if (d) return d; if (m !== "POST") return err(405, "method"); const dr = job.result.drafts[parseInt(x1[1])]; if (!dr) return err(404, "draft_not_found");
      if (!["draft_ready", "approved"].includes(job.status)) return err(409, "bad_state", { status: job.status }); const title = clean(b.title, 100); if (!title) return err(400, "title_required");
      dr.title = title; dr.title_edited = true; job.events.push({ t: now(), e: "draft_title", by: me.id }); job.updated = now(); await kput(env, K.job(job.id), job); return json({ job: pubJob(job) });
    }
    if (act === "/cancel" && m === "POST") {
      let d = need("job.create"); if (d) return d; if (!canTransition(job.status, "cancelled")) return err(409, "bad_state", { status: job.status });
      job.status = "cancelled"; setStatusText(job, "cancelled"); job.updated = now(); await refund(env, job); await Promise.all([kput(env, K.job(job.id), job), env.KV.delete(K.queue(job.queued_at, job.id))]); return json({ job: pubJob(job) });
    }
  }

  // assistant chat ---
  if (sub === "/assistant" && m === "GET") return json({ history: ((await kget(env, K.chat(orgId))) || []).slice(-40), hint: HELP });
  if (sub === "/assistant" && m === "POST") { if (await limited(env, req, "assist:" + orgId, 60)) return err(429, "rate_limited"); return json(await assistant(env, org, me, role, b)); }

  // billing ---
  if (sub === "/billing" && m === "GET") return json({ plan: org.plan, credits: org.credits, plans: [], todo: "TODO(payment): Paddle/Lemon Squeezy (merchant of record) checkout + webhook that tops up org.credits; see docs/PRODUCT_PLAN.md section 4" });
  if (sub === "/billing/checkout" && m === "POST") { let d = need("billing.manage"); if (d) return d; return err(501, "payment_not_implemented", { todo: "TODO(payment): create a hosted checkout session for b.plan/b.pack and return its URL" }); }
  return err(404, "not_found");
}

async function newSession(env, uid) { const t = "s_" + rnd(32); await kput(env, K.sess(await sha256(t)), { uid, exp: Date.now() + 30 * 864e5 }, { expirationTtl: 30 * 86400 }); return t; }

// Creates the job record + puts it in the queue. Credits are held at creation and refunded on cancel/fail.
export async function createJob(env, org, f) {
  const id = "j_" + rnd(8), t = now(); const o = await kget(env, K.org(org.id)); const held = Math.min(f.credits || 0, o.credits);
  if (held) { o.credits -= held; await kput(env, K.org(o.id), o); }   // TODO(D1): atomic reservation
  const job = { id, org: org.id, channel: f.channel_id, kind: f.kind || "edit", source: f.source, style_id: f.style_id || DEFAULT_STYLE, outputs: f.outputs || {}, hints: f.hints || {}, status: "queued", status_text: MSG.queued, credits_held: held, created: t, updated: t, queued_at: t, progress: 0, result: { drafts: [] }, events: [{ t, e: "queued" }] };
  await Promise.all([kput(env, K.job(id), job), kput(env, K.jobOfOrg(org.id, id), { t }), kput(env, K.queue(t, id), { id })]);
  return job;
}

// ---------- render worker API ----------
async function workerApi(req, env, p, m) {
  const key = await cfg(env, "worker_key"); const got = req.headers.get("x-worker-key") || "";
  if (!key || !safeEq(await sha256(got), await sha256(key))) { if (await limited(env, req, "workerkey_fail", 60)) return err(429, "rate_limited"); return err(401, "unauthorized"); }   // only FAILED attempts count (the real worker polls often)
  if (p === "/studio/worker/queue" && (m === "POST" || m === "GET")) {   // cheap peek for the GitHub Actions poller: how many jobs wait. Claims nothing, changes nothing.
    return json({ queued: (await klist(env, "studio:q:", 20)).length });
  }
  if (p === "/studio/worker/claim" && m === "POST") {
    // TODO(D1): KV is eventually consistent, two workers could claim the same job. With one worker it is fine; with several use a Durable Object/D1 UPDATE ... WHERE status='queued'.
    for (const k of await klist(env, "studio:q:", 20)) {
      const ref = await kget(env, k); await env.KV.delete(k); const job = ref && await kget(env, K.job(ref.id)); if (!job || job.status !== "queued") continue;
      job.status = "running"; setStatusText(job, "running"); job.updated = now(); job.events.push({ t: job.updated, e: "running" }); await kput(env, K.job(job.id), job);
      const ch = await kget(env, K.chan(job.org, job.channel));   // platform + slug let the worker resolve "my last stream" (type auto) of a trusted org from the platform's VODs
      return json({ job: { id: job.id, org: job.org, channel: job.channel, kind: job.kind, source: job.source, style_id: job.style_id, outputs: job.outputs, hints: job.hints || {}, channel_info: ch ? { platform: ch.platform, slug: ch.slug } : null } });
      // TODO(youtube): hand the worker a short-lived access token (refreshed here) instead of the refresh token.
    }
    return json({ job: null });
  }
  if (p === "/studio/worker/ingest" && m === "POST") {
    // Called by scripts/ingest_watcher.py (x-worker-key). op "check": is this restream key known (MediaMTX auth hook). op "job": a recording of that stream is ready -> create the job (credits held like any job). idem makes a re-sent call return the same job.
    const b = await body(req).catch(() => null); if (!b) return err(400, "bad_json"); const key = clean(b.key, 80); if (!/^ik_[a-f0-9]{32}$/.test(key)) return err(404, "unknown_key");
    const h = await sha256(key), ent = await kget(env, K.ingest(h)); if (!ent) return err(404, "unknown_key");
    if (b.op === "check") return json({ ok: true, org: ent.org, channel: ent.channel });
    if (b.op !== "job") return err(400, "bad_op");
    const ref = clean(b.ref, 120); if (!/^ingest:[A-Za-z0-9][A-Za-z0-9._-]{0,100}$/.test(ref)) return err(400, "bad_ref");
    const idem = clean(b.idem, 120) || ref, ik = K.ingestIdem(await sha256(ent.org + ":" + idem)); const dup = await kget(env, ik); if (dup) return json({ ok: true, job_id: dup.id, existing: true });
    const org = await kget(env, K.org(ent.org)), ch = await kget(env, K.chan(ent.org, ent.channel)); if (!org || !ch || ch.status !== "verified") return err(404, "channel_gone");
    const source = { type: b.live ? "live" : "url", ref, duration_min: Number(b.duration_min) || null }, credits = estimateCredits(source); if (org.credits < credits) return err(402, "insufficient_credits", { need: credits, have: org.credits });
    const job = await createJob(env, org, { channel_id: ch.id, kind: "edit", source, style_id: ch.style_id, outputs: { shorts: Math.min(30, Number(b.shorts) || 5), long: !!b.long }, credits });
    await kput(env, ik, { id: job.id }, { expirationTtl: 30 * 86400 }); return json({ ok: true, job_id: job.id });
  }
  let x; if ((x = p.match(/^\/studio\/worker\/jobs\/(j_[a-f0-9]+)$/)) && m === "POST") {
    const b = await body(req).catch(() => null); if (!b) return err(400, "bad_json"); const job = await kget(env, K.job(x[1])); if (!job) return err(404, "not_found");
    if (b.status && b.status !== job.status) { if (!canTransition(job.status, b.status) || !["qa", "draft_ready", "failed"].includes(b.status)) return err(409, "bad_state", { status: job.status }); job.status = b.status; job.events.push({ t: now(), e: b.status, note: clean(b.error || "", 200) }); if (!b.msg) setStatusText(job, b.status === "draft_ready" ? "draft_ready" : b.status, { n: (b.drafts || job.result.drafts).length }); }
    if (b.msg && MSG[b.msg]) setStatusText(job, b.msg, b.vars || {}); else if (typeof b.message === "string") job.status_text = { he: clean(b.message, 120), en: clean(b.message, 120) };   // worker progress: {msg:"found_moments", vars:{n:5}} (see MSG) or free text
    if (typeof b.progress === "number") job.progress = Math.max(0, Math.min(100, b.progress));
    if (Array.isArray(b.drafts)) job.result.drafts = b.drafts.slice(0, 50).map((d) => ({ kind: clean(d.kind, 10), title: clean(d.title, 100), yt_video_id: clean(d.yt_video_id, 20), qa_ok: !!d.qa_ok, qa_notes: clean(d.qa_notes, 300), qa_score: Number.isFinite(d.qa_score) ? Math.max(0, Math.min(100, d.qa_score)) : null, duration_s: Number.isFinite(d.duration_s) ? d.duration_s : null, local_id: clean(d.local_id, 80), hook: clean(d.hook, 60), preview_url: previewUrl(d.preview_url), private: true, decision: null }));   // local_id = where the render server keeps the file (scripts/render_worker.py out/<job>/<file>); the uploader reads it, the browser never needs it
    if (job.status === "failed") await refund(env, job);
    job.updated = now(); await kput(env, K.job(job.id), job); return json({ ok: true });
  }
  return err(404, "not_found");
}
