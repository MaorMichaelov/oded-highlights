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
// KV list() is eventually consistent (a key written a second ago can be missing for a minute: the wizard jumped back a step, a new workspace/job/invite was "gone" after a reload),
// while get() by key is read-your-writes at the same location. So every key of a listable family (members, orgs of a user, invites, channels, jobs of an org) is ALSO recorded in one small index document
// and klist() returns the union of list() and the index. Always write these keys with kput() and remove them with kdel().
const IX_FAMILY = /^studio:(m|uo|io|c|oj):/, ixKey = (k) => "studio:ix:" + k.slice(0, k.lastIndexOf(":") + 1);
async function ixAdd(env, k) { if (!IX_FAMILY.test(k)) return; const ik = ixKey(k), cur = (await env.KV.get(ik, "json")) || []; if (cur.includes(k)) return; cur.push(k); await env.KV.put(ik, JSON.stringify(cur.slice(-2000))); }
async function ixDel(env, k) { if (!IX_FAMILY.test(k)) return; const ik = ixKey(k), cur = await env.KV.get(ik, "json"); if (!cur || !cur.includes(k)) return; await env.KV.put(ik, JSON.stringify(cur.filter((x) => x !== k))); }
const kput = async (env, k, v, opt) => { await env.KV.put(k, JSON.stringify(v), opt); await ixAdd(env, k); };
const kdel = async (env, k) => { await env.KV.delete(k); await ixDel(env, k); };
const noIx = new Map();   // prefix -> ms: "no index document and list() found nothing" (per isolate, 60 s): keeps polling of an empty org from burning the daily KV list() budget (free plan: ~1000 lists + writes per day for the whole account)
async function klist(env, prefix, limit = 200) {
  const ix = IX_FAMILY.test(prefix) ? await env.KV.get("studio:ix:" + prefix, "json") : null;
  if (ix) return [...ix].sort().slice(0, limit);   // the index is authoritative: no list() call at all
  if (IX_FAMILY.test(prefix) && Date.now() - (noIx.get(prefix) || 0) < 60000) return [];
  const r = await env.KV.list({ prefix, limit }); const keys = r.keys.map((x) => x.name);
  if (IX_FAMILY.test(prefix)) { if (keys.length) await env.KV.put("studio:ix:" + prefix, JSON.stringify(keys)); else noIx.set(prefix, Date.now()); }   // legacy data (created before the index existed) is indexed on first sight
  return keys;
}
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
const rlMem = new Map();   // best effort, per isolate, no KV: a KV counter costs a write per request and the free plan allows ~1000 writes/day for the whole account
async function limited(env, req, bucket, max, ttl = 3600) {
  const ip = req.headers.get("cf-connecting-ip") || "x", k = bucket + ":" + ip, t = Date.now(); let e = rlMem.get(k);
  if (!e || e.exp < t) { if (rlMem.size > 5000) for (const [kk, v] of rlMem) if (v.exp < t) rlMem.delete(kk); e = { n: 0, exp: t + Math.max(60, ttl) * 1000 }; rlMem.set(k, e); }
  if (e.n >= max) return true; e.n++; return false;
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
      if (!c || !c.id) {   // no Twitch app configured: read the same PUBLIC fields (bio + live title) from Twitch's web GraphQL endpoint. Unofficial: replace with the Helix branch below once a Twitch app exists (put {id,secret} into KV studio:cfg:twitch).
        const g = await fetchImpl("https://gql.twitch.tv/gql", { method: "POST", headers: { "client-id": "kimne78kx3ncx6brgo4mv6wki5h1ko", "content-type": "application/json" }, body: JSON.stringify({ query: "query($l:String!){user(login:$l){id displayName description stream{title}}}", variables: { l: slug } }) });
        if (!g.ok) return { ok: false, error: "fetch_failed_" + g.status, hint: "twitch web API refused the request and no Twitch app is configured (KV studio:cfg:twitch)" };
        const gj = await g.json(); const usr = gj && gj.data && gj.data.user; if (!usr) return { ok: false, error: "channel_not_found" };
        return { ok: true, user_id: String(usr.id || ""), display: usr.displayName, linked_youtube: null, texts: [["bio", usr.description], ["stream_title", usr.stream && usr.stream.title]] };
      }
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
async function refund(env, job) {   // the caller saves the job afterwards; we save it HERE first (credits_held = 0) so a crash between the two writes loses a credit instead of paying it twice
  if (!job.credits_held) return; const o = await kget(env, K.org(job.org)); if (!o) return;
  const n = job.credits_held; job.credits_held = 0; job.updated = now(); await kput(env, K.job(job.id), job);
  o.credits += n; await kput(env, K.org(o.id), o);   // TODO(D1): not atomic, use a ledger table + transaction
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
  draft_ready: { he: "{n} טיוטות מוכנות - תעברו עליהן!", en: "{n} drafts are ready - take a look!" },
  approved: { he: "אושר. מעולה!", en: "Approved. Nice!" },
  rejected: { he: "נדחה. אפשר לבקש גרסה אחרת בצ'אט.", en: "Rejected. Ask in the chat for another take." },
  failed: { he: "משהו השתבש. החזרנו לכם את הקרדיט.", en: "Something went wrong. Your credit is back." },
  cancelled: { he: "בוטל. החזרנו לכם את הקרדיט.", en: "Cancelled. Your credit is back." },
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
  const when = /yesterday|אתמול/.test(t) ? "yesterday" : /last week|this week|past week|שבוע שעבר|השבוע|מהשבוע|שבוע האחרון|בשבוע/.test(t) ? "week" : "last_stream";   // default: the latest stream
  const mood = /funny|lol|hilarious|מצחיק|הזוי|צחוק/.test(t) ? "funny" : /hype|epic|insane|clutch|מטורף|מטורפ|אפי/.test(t) ? "hype" : /fail|rage|כעס|פיל/.test(t) ? "fail" : null;
  const make = /make|create|cut|edit|give|need|want|תעשה|תכין|צור|תחתוך|תערוך|תן|רוצה|צריך|בא לי/.test(t);
  const noun = /moment|highlight|video|stream|vod|הייטלייט|היילייט|רגע|רגעים|סרטון|סטרים|וידאו/.test(t);   // a bare "I need 3 things" or "want help" must NOT spend a credit: a request needs a clip/video word
  const intent = status ? "status" : wantsLong || wantsShorts || (noun && (make || count)) ? "create" : "help";
  const shorts = wantsLong && !wantsShorts && !count ? 0 : Math.min(30, count || 5);
  return { intent, he, shorts, long: wantsLong, when, mood, text: raw };
}
const WHEN_TXT = { yesterday: { he: "מהסטרים של אתמול", en: "from yesterday's stream" }, last_stream: { he: "מהסטרים האחרון", en: "from your latest stream" }, week: { he: "מהשבוע האחרון", en: "from last week" } };
const MOOD_TXT = { funny: { he: "מצחיקים", en: "funny" }, hype: { he: "מטורפים", en: "hype" }, fail: { he: "של פיילים", en: "fail" } };
const HELP = { he: "אפשר לבקש בשפה חופשית, למשל: \"תכין 5 שורטס מצחיקים מאתמול\" או \"מה המצב?\"", en: "Ask in plain words, e.g. \"make 5 funny Shorts from yesterday\" or \"what's the status?\"" };
// ---- free-form understanding with a free LLM (Workers AI binding `AI`): replies vary, remember the conversation, answer product questions; the rule parser above stays as the fallback and as the safety net
const LLM_MODELS = ["@cf/mistralai/mistral-small-3.1-24b-instruct", "@cf/openai/gpt-oss-120b", "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/meta/llama-3.1-8b-instruct"];   // chosen by a Hebrew comparison on the live Worker: Mistral Small 3.1 gives the most natural Hebrew and is the fastest
const LLM_DIAG = { last: "", text: "", fail: "" };   // last model outcome, shown by /studio/api/health?ai=1
const LLM_USED = new Map(), CTX_CACHE = new Map(), HIST_MEM = new Map();
async function loadHist(env, orgId) { try { const h = (await kget(env, K.chat(orgId))) || []; HIST_MEM.set(orgId, h); if (HIST_MEM.size > 300) HIST_MEM.clear(); return h; } catch (e) { return HIST_MEM.get(orgId) || []; } }
async function saveHist(env, orgId, hist) { HIST_MEM.set(orgId, hist); try { await kput(env, K.chat(orgId), hist); } catch (e) { /* KV write limit: the in-memory copy keeps the conversation going */ } }
const LLM_DAILY = 300;   // per workspace; free tier friendly
function firstJson(text) { const t = String(text || ""); const a = t.indexOf("{"); if (a < 0) return null; let d = 0, q = false, e = false; for (let i = a; i < t.length; i++) { const c = t[i]; if (q) { if (e) e = false; else if (c === "\\") e = true; else if (c === '"') q = false; continue; } if (c === '"') q = true; else if (c === "{") d++; else if (c === "}" && --d === 0) { try { return JSON.parse(t.slice(a, i + 1)); } catch (x) { return null; } } } return null; }
async function llmUnderstand(env, org, role, text, hist, L, ctx) {
  LLM_DIAG.fail = "";
  if (!env.AI) return null;
  const day = new Date().toISOString().slice(0, 10), key = `${org.id}:${day}`; const used = LLM_USED.get(key) || 0; if (used >= LLM_DAILY) return null; LLM_USED.set(key, used + 1); if (LLM_USED.size > 500) LLM_USED.clear();   // in-memory (per isolate): no KV traffic per message
  const system = `You are the in-app assistant of "Studio" and a SENIOR video editor / content producer for live streamers (Kick, Twitch, YouTube). You talk like a sharp, friendly colleague who knows the craft, in the customer's language (${L === "he" ? "natural spoken Hebrew, no stiff translation" : "English"}). You can talk about anything the customer says, answer every kind of message (greetings, yes/no, why, how much, jokes, feedback, doubts) and always connect it back to helping their channel.
WHAT THE PRODUCT DOES (only facts you may state): the customer connects a channel by pasting its link and proving ownership with a code placed in the bio or stream title; one credit = one hour of source stream; Studio finds moments (laughs, hype, fails, stories, reactions, guest conversations), cuts at sentence boundaries, adds captions and a logo, runs a quality check, and delivers PRIVATE drafts in the Review tab (swipe or arrow keys to approve / reject, titles editable); long videos and Shorts are both supported; team members are invited in the Team tab (owner / editor / viewer); YouTube connection, payments and real-time clips from chat commands are coming soon. You can start jobs (up to 30 Shorts and/or one long video, from the last stream, yesterday or last week, optional mood funny/hype/fail) and report job status. Never invent features, numbers, screens, prices or results; if unsure say so and point to the right tab.
EDITING EXPERTISE you can share when asked or when useful: Shorts: hook in the first 1-2 seconds, one idea per clip, 20-45 s sweet spot, cut at the start of a sentence and end right after the punchline, captions on, loop-friendly endings, front-load the payoff; long videos: a clear premise in the title, chapters, cut dead air and repeated setup, keep reactions whole, 8-30 min for reactions and guest talks; titles: literal and true, specific names and moments, 40-70 characters, no clickbait lies, no hype words; thumbnails: one face with a clear emotion, 3-4 words max; publishing: consistency beats perfection, post Shorts several times a week and long videos weekly, reuse the best moment as a Short that points to the long video; comments and community: reply early; rights: only clip your own streams or with permission. Give concrete options (for example 3 title ideas, a better hook line, how to trim a clip) when the customer wants help, and keep advice short and practical.
LANGUAGE QUALITY: in Hebrew use simple everyday spoken words and short sentences, no literal translations of English idioms, no invented words, keep common terms like Shorts / Hook / Review as they are; double-check every sentence reads naturally. When the customer asks for general editing or growth advice (how to trim, why views are low, what makes a good title) answer with real craft advice first and mention Studio only if it truly helps; never put placeholders in brackets: if you need a name or detail, either ask for it or write the title without it; when giving titles, give 3 distinct options, each literal and true to what the customer described.
KNOWLEDGE BASE (general craft knowledge, state it as guidance, and when a number or policy matters tell the customer to confirm it in YouTube Studio): 
- YouTube Shorts: vertical 9:16, up to 3 minutes; the feed rewards viewed-vs-swiped-away and watch-through, so the first second must show the payoff or a question, no logo intros, loops and quick payoffs win; captions help because many watch muted; post 3-7 per week; a Short can link to the related long video.
- Long videos: click-through rate (title + thumbnail) and average view duration drive recommendations; promise and deliver, cut dead air and repeated setup, add chapters (timestamps starting at 0:00 in the description), end with a next-video suggestion; reactions, guest conversations and event recaps work well from streams; upload consistency matters more than length.
- Titles: specific and true, name the person / game / moment, one clear emotion or curiosity gap, front-load the important words, 40-70 characters; avoid ALL CAPS, avoid misleading claims (misleading metadata can be penalised).
- Thumbnails: one face with a readable emotion, 3-4 big words at most, high contrast, same style across the channel.
- Description and tags: first two lines matter, include names and the game, 3-5 relevant hashtags, link to the stream and credit sources.
- Stream clipping specifics: cut starts at the beginning of the sentence and ends right after the punchline; keep 2-3 seconds of context before the funny moment; reaction clips should keep the reaction whole; don't cut mid-word; normalise loudness (about -14 LUFS for Shorts); keep the game audio under the voice.
- Rights: clip only your own streams or with written permission; third-party music in a stream can trigger Content ID claims (consider muting or replacing it); fan channels should credit the streamer and use clear disclaimers, but permission is still needed to be safe.
- Growth: reuse one moment in 3 shapes (Short, long video, community post), reply to early comments, pin a comment, check analytics for retention drop-offs and cut those sections, review the top 10% and bottom 10% of videos each month; monetisation thresholds exist (subscribers plus watch hours or Shorts views) and change over time, so check the current numbers in YouTube Studio.
- Kick and Twitch: viewers' chat spikes and laughter mark good moments; Twitch clips are short viewer-made highlights, VODs can expire, so download or clip soon after the stream.
STYLE: warm, direct, specific, a little humour is fine; match the customer's energy; short messages get short answers, real questions get a complete useful answer (up to ~120 words); never repeat a sentence you said earlier in this conversation; ask ONE clarifying question when the request is vague; never lecture; if the customer corrects you, accept it and adjust. If the message is vague, emotional or a filler ("honestly I don't know", "whatever", "hmm"), do not assume it continues the last topic: respond to the person first, then offer two concrete next steps that fit their situation (no verified channel yet: connect one; has a channel: try a job such as "5 funny Shorts from the latest stream").
CUSTOMER CONTEXT: role=${role}; credits=${ctx.credits}; verified channels=${ctx.channels.join(", ") || "none yet"}; recent jobs=${ctx.jobs.join(" | ") || "none"}; recent drafts=${(ctx.drafts || []).join(" | ") || "none yet"}.
Output ONLY JSON: {"reply": "<what you say>", "intent": "create" | "status" | "chat", "shorts": <int 0-30>, "long": <true|false>, "when": "last_stream" | "yesterday" | "week", "mood": "funny" | "hype" | "fail" | null}. Use intent "create" only when the customer clearly asked you to make something now (then reply with a short confirmation); "status" when they ask about progress; otherwise "chat".`;
  const messages = [{ role: "system", content: system }, ...hist.slice(-14).map((h) => ({ role: h.r === "bot" ? "assistant" : "user", content: String(h.text || "").slice(0, 400) })), { role: "user", content: clean(text, 500) }];
  for (const m of LLM_MODELS) {
    try {
      const r = await env.AI.run(m, m.includes("gpt-oss") ? { input: messages, reasoning: { effort: "medium" }, max_output_tokens: 2500 } : { messages, max_tokens: 1200 });
      LLM_DIAG.last = m + ": got " + JSON.stringify(r).slice(0, 160);
      const msgItems = Array.isArray(r.output) ? r.output.filter((o) => o && o.type === "message") : [];   // gpt-oss returns a reasoning item first: read only the final message
      const t = r.response || (r.choices && r.choices[0] && r.choices[0].message && r.choices[0].message.content) || r.output_text || (msgItems.length ? msgItems.map((o) => (o.content || []).map((c) => c.text || "").join("")).join("") : (r.output && r.output.map((o) => (o.content || []).map((c) => c.text || "").join("")).join(""))) || "";
      LLM_DIAG.text = (typeof t === "string" ? t : JSON.stringify(t)).slice(0, 200);
      let j = (r.response && typeof r.response === "object") ? r.response : (r.choices && r.choices[0] && r.choices[0].message && r.choices[0].message.content && typeof r.choices[0].message.content === "object") ? r.choices[0].message.content : firstJson(t);   // some models return the JSON already parsed
      if (!j && typeof t === "string" && String(t).trim().length > 1 && !/[{}]/.test(String(t))) j = { reply: String(t).trim(), intent: "chat" };   // the model answered in plain text instead of JSON: that is a fine chat reply
      if (!j || typeof j.reply !== "string" || !j.reply.trim()) LLM_DIAG.fail = (LLM_DIAG.fail || "") + m.split("/").pop() + ": no-json " + String(t).slice(0, 80).replace(/\s+/g, " ") + " || ";
      else if (/[\u0900-\u097F\u0600-\u06FF\u4E00-\u9FFF\u0400-\u04FF]/.test(j.reply)) LLM_DIAG.fail = (LLM_DIAG.fail || "") + m.split("/").pop() + ": foreign-script || ";   // a model that slips into another script is skipped
      if (j && typeof j.reply === "string" && j.reply.trim() && !/[\u0900-\u097F\u0600-\u06FF\u4E00-\u9FFF\u0400-\u04FF]/.test(j.reply)) { return { reply: clean(j.reply, 1200), intent: ["create", "status", "chat"].includes(j.intent) ? j.intent : "chat", shorts: Math.max(0, Math.min(30, parseInt(j.shorts) || 0)), long: !!j.long, when: ["last_stream", "yesterday", "week"].includes(j.when) ? j.when : "last_stream", mood: ["funny", "hype", "fail"].includes(j.mood) ? j.mood : null }; }
    } catch (e) { LLM_DIAG.last = m + ": " + String(e && e.message || e).slice(0, 200); }
  }
  return null;
}
// ---- small talk without any model: greetings, thanks, yes/no, why/how much, goodbyes... several wordings per case, never the same reply twice in a row
const ST = {
  hi: { he: ["היי! מה נחתוך היום?", "שלום 👋 אפשר להתחיל מהשידור האחרון שלך. רוצה שורטס או סרטון ארוך?", "אהלן! אני כאן. תגיד מה אתה צריך ואני מתחיל.", "היי, טוב לראות אותך. יש שידור חדש שאפשר לעבוד עליו?"], en: ["Hey! What are we cutting today?", "Hi there. We can start from your latest stream. Shorts or a long video?", "Hello! I'm here. Tell me what you need and I'll get going.", "Hey, good to see you. Is there a new stream to work on?"] },
  bye: { he: ["להתראות! הטיוטות ימתינו לך כשתחזור.", "ביי! אם משהו יסתיים בינתיים, תראה אותו בלשונית הבדיקה.", "יאללה, נתראה. אני ממשיך לעבוד ברקע.", "לילה טוב, או יום טוב. אני כאן כשתצטרך."], en: ["See you! Your drafts will be waiting.", "Bye! If anything finishes meanwhile it will show up in the Review tab.", "Catch you later. I keep working in the background.", "Take care, I'm here when you need me."] },
  thanks: { he: ["בכיף!", "בשמחה, יש עוד משהו לחתוך?", "אין על מה. אני כאן.", "תמיד. רוצה שנמשיך?"], en: ["Anytime!", "My pleasure. Anything else to cut?", "No problem, I'm here.", "Always. Want to keep going?"] },
  yes: { he: ["מעולה! מה בדיוק לעשות? למשל \"5 שורטס מצחיקים מאתמול\".", "סבבה. תן לי משהו קונקרטי: כמה קליפים, ומאיזה שידור?", "יופי. שורטס או סרטון ארוך?", "בכיף. מאיפה מתחילים, מהשידור האחרון?"], en: ["Great! What exactly should I do? For example \"5 funny Shorts from yesterday\".", "Okay. Give me something concrete: how many clips, from which stream?", "Nice. Shorts or a long video?", "Happy to. Where do we start, the latest stream?"] },
  no: { he: ["אין בעיה, לא עושה כלום. אם תרצה משהו אחר, אני כאן.", "הבנתי, עוצר. מה כן?", "בסדר גמור. תגיד מה לשנות.", "סבבה, נשאיר את זה. משהו אחר?"], en: ["No problem, I won't do anything. I'm here if you want something else.", "Got it, stopping. What would you like instead?", "All good. Tell me what to change.", "Okay, we'll leave it. Anything else?"] },
  why: { he: ["תפרט לי קצת מה מעניין אותך, ואסביר: למה בחרתי רגע מסוים, למה עבודה בתור, או איך משהו עובד?", "שאלה טובה. על מה בדיוק? על בחירת קליפ, על קרדיטים, או על משהו שלא עבד?", "אשמח להסביר. תגיד על איזה קליפ או איזו פעולה מדובר."], en: ["Tell me a bit more and I'll explain: why a moment was picked, why a job is queued, or how something works?", "Good question. About what exactly: a clip choice, credits, or something that didn't work?", "Happy to explain. Which clip or action do you mean?"] },
  price: { he: ["קרדיט אחד מכסה שעה אחת של שידור מקור. בתקופת הניסיון יש לך כמה קרדיטים חינם, ואפשר לראות את היתרה בלשונית קרדיטים. תשלום יתווסף בהמשך.", "המחיר נקבע לפי שעות שידור: קרדיט לשעה. עכשיו זה ניסיון חינם. מחירים סופיים עוד לא פורסמו."], en: ["One credit covers one hour of source stream. During the trial you have a few free credits, and you can see the balance in the Credits tab. Payments come later.", "Pricing is by stream hours: one credit per hour. It's a free trial for now. Final prices are not published yet."] },
  what: { he: ["אני מוצא רגעים בשידורים שלך וחותך מהם שורטס וסרטונים ארוכים, עם כתוביות ובדיקת איכות. הכול מגיע כטיוטה פרטית שאתה מאשר. נסה: \"תכין 5 שורטס מצחיקים מאתמול\".", "אפשר לבקש ממני: שורטס מהשידור האחרון, סרטון ארוך מריאקשן או שיחה עם אורח, או \"מה המצב?\" על עבודה שרצה.", "אני העורך שלך. אתה מגדיר מה לחתוך, אני עושה, ואתה מאשר או דוחה. בוא נתחיל: מאיזה שידור?"], en: ["I find moments in your streams and cut Shorts and long videos from them, with captions and a quality check. Everything arrives as a private draft you approve. Try: \"make 5 funny Shorts from yesterday\".", "You can ask me for Shorts from the latest stream, a long video from a reaction or a guest conversation, or \"what's the status?\" on a running job.", "I'm your editor. You say what to cut, I do it, you approve or reject. Let's start: which stream?"] },
  who: { he: ["אני העוזר של Studio: מוצא רגעים בשידורים שלך ומכין מהם טיוטות.", "אני עוזר אוטומטי לעריכת קליפים. אני לא מפרסם כלום בלי אישור שלך."], en: ["I'm Studio's assistant: I find moments in your streams and turn them into drafts.", "I'm an automatic clip editor. I never publish anything without your approval."] },
  all: { he: ["הכול? בוא נתחיל קטן: מה הכי חשוב לך עכשיו, שורטס מהשידור האחרון או סרטון ארוך?", "אפשר להתחיל מההכול, אבל הכי טוב צעד אחר צעד. איזה שידור קודם?"], en: ["Everything? Let's start small: what matters most right now, Shorts from the latest stream or a long video?", "We can cover it all, but step by step works best. Which stream first?"] },
  ok: { he: ["👍 מה הלאה?", "רשמתי. עוד משהו?", "סגור."], en: ["👍 What's next?", "Noted. Anything else?", "Done."] },
  howmany: { he: ["כמה מה? קליפים, קרדיטים או שעות שידור? אפשר לשאול למשל \"כמה זה עולה?\" או לבקש \"5 שורטס\".", "תפרט קצת: כמה קליפים לחתוך, או כמה זה עולה?"], en: ["How many of what? Clips, credits or stream hours? You can ask \"how much does it cost?\" or request \"5 Shorts\".", "Tell me a bit more: how many clips to cut, or how much it costs?"] },
  me: { he: ["אתה? ספר לי: מה אתה רוצה שנחתוך?", "אני מקשיב. על מה מדובר?"], en: ["You? Tell me: what would you like cut?", "I'm listening. What's it about?"] },
  rec: { he: ["הייתי מתחיל מהשידור האחרון שלך: 5 שורטס מהרגעים הכי חזקים וסרטון ארוך אחד מהחלק הכי מעניין. אחר כך מסתכלים מה אישרת ומה דחית, והמערכת לומדת.", "המלצה: קודם שורטס, כי הם מהירים ונותנים תוצאות. כשיש לך 5 טיוטות שאהבת, נוסיף סרטון ארוך משיחה או ריאקשן.", "הדבר הכי משתלם: להדביק לי קישור לשידור, ואני אציע מה לחתוך ממנו."], en: ["I'd start with your latest stream: 5 Shorts from the strongest moments and one long video from the most interesting stretch. Then we look at what you approved and rejected, and the system learns.", "My tip: Shorts first, they're fast and give results. Once you have 5 drafts you like, add a long video from a conversation or reaction.", "The best value: paste me a stream link and I'll suggest what to cut from it."] },
  idk: { he: ["לא בטוח שהבנתי. אפשר לנסות: \"5 שורטס מצחיקים מאתמול\", \"סרטון ארוך מהשידור האחרון\" או \"מה המצב?\"", "ניסוח אחר? למשל מה לחתוך, כמה, ומאיזה שידור.", "לא תפסתי. תגיד לי במילים שלך מה אתה רוצה שייחתך."], en: ["Not sure I got that. Try: \"5 funny Shorts from yesterday\", \"a long video from the latest stream\" or \"what's the status?\"", "Another wording? For example what to cut, how many, and from which stream.", "I didn't catch that. Tell me in your own words what you want cut."] },
};
function stCategory(t) {
  const x = t.toLowerCase().replace(/[!?.,]+/g, " ").replace(/\s+/g, " ").trim(); const w = x.split(" ");
  const has = (re) => re.test(x);
  if (w.length <= 2 && /^(כמה|how much|how many)$/.test(x)) return "howmany";
  if (/^(שלום|היי|הי|אהלן|הלו|מה נשמע|מה קורה|בוקר טוב|ערב טוב|hi|hey|hello|yo|sup|good (morning|evening)|how are you)(?= |$)/.test(x) && w.length <= 5) return "hi";
  if (/^(ביי|להתראות|נתראה|לילה טוב|bye|goodbye|see you|cya|good night)(?= |$)/.test(x)) return "bye";
  if (/^(תודה|תודה רבה|thanks|thank you|thx)(?= |$)/.test(x)) return "thanks";
  if (w.length <= 3 && /^(כן|בטח|יאללה|אוקיי|אוקי|סבבה|yes|yeah|yep|sure|ok|okay)(?= |$)/.test(x)) return x.match(/^(אוקיי|אוקי|סבבה|ok|okay)/) ? "ok" : "yes";
  if (w.length <= 3 && /^(לא|no|nope|nah|עזוב|ביטול|cancel)(?= |$)/.test(x)) return "no";
  if (has(/כמה (זה )?(עולה|עלות|מחיר|קרדיט)|מחיר|עולה|תשלום|price|cost|how much|pricing|credits?(?= |$)/) ) return "price";
  if (has(/^(למה|מדוע|why|how come)(?= |$)|^איך (זה )?עובד|how (does|do) (it|this)/)) return "why";
  if (has(/מה (אתה|את|אפשר|ניתן) (יכול|יכולה|לעשות|לבקש)|במה אתה|עזרה|\bhelp\b|what can you|what do you do|מה אתה עושה/)) return "what";
  if (has(/^(מי אתה|מי את|who are you|what are you)/)) return "who";
  if (w.length <= 2 && /^(הכל|הכול|everything|all)$/.test(x)) return "all";
  if (/^(מה (אתה )?ממליץ|מה כדאי|מה דעתך|תמליץ|מה להתחיל|what do you (recommend|suggest)|what should i (do|start)|any (tips|ideas))/.test(x)) return "rec";
  if (w.length <= 2 && /^(כמה|how much|how many)$/.test(x)) return "howmany";
  if (w.length <= 2 && /^(אני|אני רוצה|i|me|i want)$/.test(x)) return "me";
  return null;
}
let stLast = "";
function smallTalk(text, L, turn, always) {
  let cat = stCategory(String(text || "")); if (!cat) { if (!always) return null; cat = "idk"; } const pool = ST[cat][L] || ST[cat].en; let i = ((turn || 0) + String(text).length) % pool.length; let r = pool[i]; if (r === stLast) r = pool[(i + 1) % pool.length]; stLast = r; return r;
}

const LINK_RE = /https?:\/\/[^\s<>"']+/i;
function safeLink(raw) { try { const x = new URL(String(raw).replace(/[).,!?]+$/, "")); if (!/^https?:$/.test(x.protocol)) return null; const h = x.hostname.toLowerCase(); if (!h.includes(".") || /^(localhost|127\.|10\.|192\.168\.|169\.254\.|0\.)/.test(h) || /^\d+\.\d+\.\d+\.\d+$/.test(h)) return null; return x.toString().slice(0, 300); } catch (e) { return null; } }
const linkSite = (l) => { const h = new URL(l).hostname.replace(/^www\./, ""); return /kick\.com/.test(h) ? "Kick" : /twitch\.tv/.test(h) ? "Twitch" : /youtu/.test(h) ? "YouTube" : /tiktok/.test(h) ? "TikTok" : h; };
function linkChoices(L, link) { return L === "he" ? [{ label: "5 שורטס", text: `תכין 5 שורטס מ ${link}` }, { label: "10 שורטס + סרטון ארוך", text: `תכין 10 שורטס וסרטון ארוך מ ${link}` }, { label: "סרטון ארוך בלבד", text: `תכין סרטון ארוך מ ${link}` }] : [{ label: "5 Shorts", text: `make 5 Shorts from ${link}` }, { label: "10 Shorts + a long video", text: `make 10 Shorts and a long video from ${link}` }, { label: "Long video only", text: `make a long video from ${link}` }]; }
async function assistant(env, org, me, role, b, store) {
  const rawMsg = String(b.message || ""); const lm = rawMsg.match(LINK_RE); const link = lm ? safeLink(lm[0]) : null;
  const u = understand(link ? rawMsg.replace(lm[0], " ") : rawMsg); if (link) u.text = clean(rawMsg, 500); u.link = link; const L = (link && !u.he && (b.lang === "he" || b.lang === "en")) ? b.lang : (u.he ? "he" : "en"); let reply, actions = [];
  if (!u.text) return { reply: HELP[L], actions };
  let llm = null;
  if (link && u.intent === "help") {   // a bare link: offer the options (what to make) as quick replies; the cost is shown up front
    const site = linkSite(link); reply = L === "he" ? `קיבלתי קישור מ-${site}. מה לעשות איתו? אפשר לבחור למטה או לכתוב בעצמך (למשל "8 שורטס מצחיקים"). העלות היא קרדיט אחד לכל שעת שידור, ואעדכן כשאדע את האורך המדויק.` : `Got a ${site} link. What should I do with it? Pick below or write your own (e.g. "8 funny Shorts"). Cost is one credit per hour of source, and I'll update you once I know the exact length.`;
    const hist1 = await loadHist(env, org.id); hist1.push({ r: "user", t: now(), text: u.text }, { r: "bot", t: now(), text: reply }); await saveHist(env, org.id, hist1.slice(-40));
    return { reply, actions, mode: "basic", choices: linkChoices(L, link), parsed: { intent: "link", link } };
  }
  if (!link) try {
    const hist0 = await loadHist(env, org.id);
    const cc = CTX_CACHE.get(org.id); let chs = [], js = [], drs = [];   // channel/job lists cost KV list() calls (free plan: 1000/day): cache them for 2 minutes per workspace
    if (cc && Date.now() - cc.t < 120000) { chs = cc.chs; js = cc.js; drs = cc.drs; } else try {
      chs = (await kgetMany(env, await klist(env, K.chansOfOrg(org.id)))).filter((c) => c.status === "verified").map((c) => `${c.platform}/${c.slug}`);
      const allJobs = (await kgetMany(env, (await klist(env, K.jobsOfOrg(org.id), 500)).map((k) => K.job(k.split(":")[3])))).sort((a, c) => (a.created < c.created ? 1 : -1)).slice(0, 4);
      js = allJobs.slice(0, 3).map((j) => `${j.status} ${j.progress}%`); drs = []; for (const j of allJobs) for (const d of ((j.result && j.result.drafts) || []).slice(0, 4)) drs.push(`"${String(d.title || "").slice(0, 60)}" (${d.decision || "pending"})`);
      CTX_CACHE.set(org.id, { t: Date.now(), chs, js, drs }); if (CTX_CACHE.size > 300) CTX_CACHE.clear();
    } catch (e) { /* KV list limit or hiccup: talk without the context */ }
    const fresh0 = await kget(env, K.org(org.id)).catch(() => null); llm = await llmUnderstand(env, org, role, u.text, hist0, L, { credits: fresh0 ? fresh0.credits : org.credits, channels: chs, jobs: js, drafts: drs.slice(0, 8) });
  } catch (e) { llm = null; }
  if (llm) { if (llm.intent === "create" && (llm.shorts > 0 || llm.long)) { u.intent = "create"; u.shorts = llm.shorts; u.long = llm.long; u.when = llm.when; u.mood = llm.mood; } else if (llm.intent === "status") u.intent = "status"; else u.intent = "chat"; }
  const turnN = (HIST_MEM.get(org.id) || []).length;
  if (u.intent === "chat") reply = llm ? llm.reply : (smallTalk(u.text, L, turnN, true) || HELP[L]);
  else if (u.intent === "help") reply = smallTalk(u.text, L, turnN, true) || HELP[L];
  else if (u.intent === "status") {
    const jobs = (await kgetMany(env, (await klist(env, K.jobsOfOrg(org.id), 500)).map((k) => K.job(k.split(":")[3])))).sort((a, c) => (a.created < c.created ? 1 : -1));
    const j = jobs[0]; reply = !j ? (L === "he" ? "עדיין אין עבודות. בקשו משהו בצ'אט!" : "No jobs yet. Ask me for something!") : `${(j.status_text || renderMsg(j.status) || { he: j.status, en: j.status })[L]} (${j.progress}%)`;
    if (j) actions.push({ type: "show_job", job_id: j.id });
  } else if (!can(role, "job.create")) reply = L === "he" ? "לצופים אין הרשאה ליצור עבודות. בקשו מהבעלים להפוך אתכם לעורכים." : "Viewers can't create jobs. Ask the owner to make you an editor.";
  else {
    let chans = (await kgetMany(env, await klist(env, K.chansOfOrg(org.id)))).filter((c) => c.status === "verified");
    if (!chans.length && u.link && me && me.guest) { const gch = { id: "c_" + rnd(6), org: org.id, platform: "link", slug: "guest", status: "verified", style_id: DEFAULT_STYLE, yt: { status: "not_connected" }, guest: true, created: now() }; await kput(env, K.chan(org.id, gch.id), gch); chans = [gch]; }   // preview phase: a guest works on any link without an ownership code (the render worker still applies its own source rules)
    const ch = chans.find((c) => c.id === b.channel_id) || chans[0];
    if (!ch) reply = L === "he" ? "קודם נחבר ערוץ: הוסיפו את הערוץ שלכם בעמוד ההתחלה ואמתו בעלות. זה לוקח דקה." : "First let's connect a channel: add your channel on the setup page and verify ownership. Takes a minute.";
    else {
      const source = u.link ? { type: "url", ref: u.link, duration_min: null } : { type: "auto", when: u.when, duration_min: null }, credits = estimateCredits(source); const fresh = await kget(env, K.org(org.id));
      if (fresh.credits < credits) reply = L === "he" ? `נגמרו הקרדיטים (צריך ${credits}, יש ${fresh.credits}). אפשר להוסיף בעמוד הקרדיטים.` : `Out of credits (need ${credits}, have ${fresh.credits}). You can top up on the Credits page.`;
      else {
        const job = await createJob(env, org, { channel_id: ch.id, kind: "edit", source, style_id: ch.style_id, outputs: { shorts: u.shorts, long: u.long }, credits, hints: { mood: u.mood, text: u.text } });
        const what = [u.shorts ? (L === "he" ? `${u.shorts} שורטס${u.mood ? " " + MOOD_TXT[u.mood].he : ""}` : `${u.shorts} ${u.mood ? MOOD_TXT[u.mood].en + " " : ""}Shorts`) : "", u.long ? (L === "he" ? "סרטון ארוך" : "a long video") : ""].filter(Boolean).join(L === "he" ? " ו" : " and ");
        const whenT = u.link ? { he: "מהקישור שלך", en: "from your link" } : WHEN_TXT[u.when];
        reply = L === "he" ? `סבבה! מכין ${what} ${whenT.he}. אעדכן כאן כשהטיוטות מוכנות. אפשר לבטל כל עוד זה בתור.` : `On it! Making ${what} ${whenT.en}. I'll update you here when drafts are ready. You can cancel while it's queued.`;
        actions.push({ type: "job_created", job_id: job.id });
      }
    }
  }
  const hist = await loadHist(env, org.id); hist.push({ r: "user", t: now(), text: u.text }, { r: "bot", t: now(), text: reply }); await saveHist(env, org.id, hist.slice(-40));   // TODO(D1): per-user threads
  return { reply, actions, mode: llm ? "ai" : "basic", why: llm ? undefined : String(LLM_DIAG.fail || LLM_DIAG.last || "no-ai").slice(0, 400), parsed: { intent: u.intent, shorts: u.shorts, long: u.long, when: u.when, mood: u.mood } };
}

// ---------- the router ----------
export async function handleStudio(req, env, fetchImpl = fetch) {   // never let an exception escape as Cloudflare's raw error page: the UI can only show a friendly message for JSON
  try { return await handleStudioInner(req, env, fetchImpl); } catch (e) { console.error("studio_error", String(e && e.stack || e).slice(0, 400)); return err(500, "server_error", { detail: String(e && e.message || e).slice(0, 180) }); }
}
async function handleStudioInner(req, env, fetchImpl) {
  const u = new URL(req.url); const p = u.pathname.replace(/\/+$/, "") || "/studio"; const m = req.method;
  if (p === "/studio") return new Response(STUDIO_HTML, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-cache", ...SEC } });
  if (p === "/studio/api/health") {
    if (u.searchParams.get("evalmodel")) {   // model comparison for Hebrew quality (allow-listed Workers AI models, short fixed-size prompt)
      const mm = u.searchParams.get("evalmodel"); const OK = ["@cf/openai/gpt-oss-120b", "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/google/gemma-3-12b-it", "@cf/mistralai/mistral-small-3.1-24b-instruct", "@cf/qwen/qwen3-30b-a3b-fp8", "@cf/meta/llama-4-scout-17b-16e-instruct", "@cf/meta/llama-3.1-8b-instruct"]; if (!OK.includes(mm) || !env.AI) return json({ ok: false, error: "model_not_allowed" });
      const q = clean(u.searchParams.get("q") || "תן לי 3 כותרות ליוטיוב לקליפ שבו סטרימר צועק על משחק", 200); const t0 = Date.now();
      try { const msgs = [{ role: "system", content: "אתה עורך וידאו מנוסה. ענה בעברית טבעית וקצרה, כמו חבר ישראלי, בלי תרגום מילולי מאנגלית." }, { role: "user", content: q }]; const r = await env.AI.run(mm, mm.includes("gpt-oss") ? { input: msgs, reasoning: { effort: "low" }, max_output_tokens: 600 } : { messages: msgs, max_tokens: 400 });
        const mi = Array.isArray(r.output) ? r.output.filter((o) => o && o.type === "message") : []; const text = r.response || (r.choices && r.choices[0] && r.choices[0].message && r.choices[0].message.content) || r.output_text || mi.map((o) => (o.content || []).map((c) => c.text || "").join("")).join("") || JSON.stringify(r).slice(0, 300);
        return json({ ok: true, model: mm, ms: Date.now() - t0, text: String(text).slice(0, 900) }); } catch (e) { return json({ ok: false, model: mm, error: String(e && e.message || e).slice(0, 200) }); }
    }
    if (u.searchParams.get("ai") === "1") { let out = null, err2 = null; if (!env.AI) err2 = "no AI binding"; else for (const m of LLM_MODELS) { try { const r = await env.AI.run(m, m.includes("gpt-oss") ? { input: [{ role: "user", content: "Reply with the word OK" }], reasoning: { effort: "low" }, max_output_tokens: 50 } : { messages: [{ role: "user", content: "Reply with the word OK" }], max_tokens: 20 }); out = m + ": " + JSON.stringify(r).slice(0, 200); break; } catch (e) { err2 = (err2 ? err2 + " | " : "") + m + ": " + String(e && e.message || e).slice(0, 200); } } return json({ ok: true, ai: out, ai_error: err2, last: LLM_DIAG.last, text: LLM_DIAG.text }); }
    return json({ ok: true, t: now() });
  }

  // --- render-worker API (machine to machine; secret lives in KV studio:cfg:worker_key or env.STUDIO_WORKER_KEY)
  if (p.startsWith("/studio/worker/")) return workerApi(req, env, p, m);
  if (!p.startsWith("/studio/api/")) return err(404, "not_found");
  const path = p.slice("/studio/api".length); let b = {};
  try { if (m === "POST" || m === "PATCH" || m === "PUT") b = await body(req); } catch (e) { return err(400, e.message); }

  // --- public: signup / login
  if (path === "/signup" && m === "POST") {
    if (await limited(env, req, "signup", 20)) return err(429, "rate_limited");
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
    if (await limited(env, req, "guest", 30)) return err(429, "rate_limited");
    const uid = "u_" + rnd(8), orgId = "o_" + rnd(8), email = "guest-" + rnd(6) + "@guest.invalid", name = "Guest";
    await Promise.all([kput(env, K.user(uid), { id: uid, email, name, guest: true, pw: await hashPassword(rnd(24)), created: now() }), env.KV.put(K.email(email), uid),
      kput(env, K.org(orgId), { id: orgId, name: "My studio", owner: uid, plan: "trial", credits: TRIAL_CREDITS, created: now() })]);
    await addMember(env, orgId, uid, email, "owner");
    return json({ token: await newSession(env, uid), user: { id: uid, email, name }, org_id: orgId });
  }
  if (path === "/login" && m === "POST") {
    if (await limited(env, req, "login", 60)) return err(429, "rate_limited");
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
    const have = await roleIn(env, inv.org, me.id); const RANK = { viewer: 1, editor: 2, owner: 3 }; if (!have || RANK[inv.role] > RANK[have]) await addMember(env, inv.org, me.id, me.email, inv.role); await Promise.all([env.KV.delete(K.inv(h)), kdel(env, K.invOfOrg(inv.org, h))]);
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
    if (m === "DELETE") { await Promise.all([kdel(env, K.mem(orgId, x[1])), kdel(env, K.orgOfUser(x[1], orgId))]); return json({ ok: true }); }
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
    if (act === "" && m === "DELETE") { let d = need("channel.manage"); if (d) return d; await kdel(env, K.chan(orgId, ch.id)); if (ch.status === "verified") await env.KV.delete(K.claim(ch.platform, ch.slug)); return json({ ok: true }); }
    if (act === "/verify" && m === "POST") {
      let d = need("channel.manage"); if (d) return d; if (ch.status === "verified") return json({ channel: ch });
      if (await limited(env, req, "verify:" + ch.id, 200)) return err(429, "rate_limited");   // the page re-checks every 8-30 s while open
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
  const chRec = f.channel_id ? await kget(env, K.chan(org.id, f.channel_id)) : null;
  const job = { id, ...(chRec && chRec.e2e ? { e2e: true } : {}), org: org.id, channel: f.channel_id, kind: f.kind || "edit", source: f.source, style_id: f.style_id || DEFAULT_STYLE, outputs: f.outputs || {}, hints: f.hints || {}, status: "queued", status_text: MSG.queued, credits_held: held, created: t, updated: t, queued_at: t, progress: 0, result: { drafts: [] }, events: [{ t, e: "queued" }] };
  await Promise.all([kput(env, K.job(id), job), kput(env, K.jobOfOrg(org.id, id), { t }), kput(env, K.queue(t, id), { id })]);
  return job;
}

// A GitHub Actions run token (GITHUB_TOKEN, "ghs_...") is valid only while that run lives and only for the repo that issued it. The Worker asks GitHub which repositories the token belongs to and accepts it only for this repo.
const GH_OK = new Map();
async function ghActionsTokenOk(env, tok) {
  const h = await sha256(tok); const hit = GH_OK.get(h); if (hit && hit > Date.now()) return true;
  try {
    const r = await fetch("https://api.github.com/installation/repositories?per_page=100", { headers: { authorization: "Bearer " + tok, accept: "application/vnd.github+json", "user-agent": "studio-app" } }); if (!r.ok) return false;
    const j = await r.json(); const repo = String(env.STUDIO_GH_REPO || "MaorMichaelov/oded-highlights").toLowerCase();
    const ok = Array.isArray(j.repositories) && j.repositories.length === 1 && String(j.repositories[0].full_name).toLowerCase() === repo;   // exactly this repo
    if (ok) { GH_OK.set(h, Date.now() + 10 * 60 * 1000); if (GH_OK.size > 50) GH_OK.clear(); } return ok;
  } catch (e) { return false; }
}
async function orgIsGuest(env, orgId) { try { const o = await kget(env, K.org(orgId)); const u = o && await kget(env, K.user(o.owner)); return !!(u && u.guest); } catch (e) { return false; } }
// ---------- render worker API ----------
async function workerApi(req, env, p, m) {
  const key = await cfg(env, "worker_key"); const got = req.headers.get("x-worker-key") || "";
  let authed = !!key && safeEq(await sha256(got), await sha256(key));
  if (!authed && /^gh[sp]_[A-Za-z0-9_.-]{20,400}$/.test(got)) authed = await ghActionsTokenOk(env, got);   // the repo's own GitHub Actions run proves itself with its run token: no shared secret to store anywhere
  if (!authed) { if (await limited(env, req, "workerkey_fail", 60)) return err(429, "rate_limited"); return err(401, "unauthorized"); }   // only FAILED attempts count (the real worker polls often)
  if (p === "/studio/worker/queue" && (m === "POST" || m === "GET")) {   // cheap peek for the GitHub Actions poller: how many jobs wait. Claims nothing, changes nothing.
    return json({ queued: (await klist(env, "studio:q:", 20)).length });
  }
  if (p === "/studio/worker/claim" && m === "POST") {
    // TODO(D1): KV is eventually consistent, two workers could claim the same job. With one worker it is fine; with several use a Durable Object/D1 UPDATE ... WHERE status='queued'.
    // Optional body {job_id}: claim exactly that job (used by the E2E tests; jobs of e2e-marked channels are never handed to a normal claim, so the real render worker ignores them).
    const cb = await body(req).catch(() => ({})); const want = clean(cb && cb.job_id, 40);
    if (want) {   // exactly this job (does not depend on the eventually consistent queue listing)
      const job = await kget(env, K.job(want)); if (!job || job.status !== "queued") return json({ job: null });
      await env.KV.delete(K.queue(job.queued_at, job.id)); job.status = "running"; setStatusText(job, "running"); job.updated = now(); job.events.push({ t: job.updated, e: "running" }); await kput(env, K.job(job.id), job);
      return json({ job: { id: job.id, org: job.org, channel: job.channel, kind: job.kind, source: job.source, style_id: job.style_id, outputs: job.outputs, hints: job.hints || {} } });
    }
    for (const k of await klist(env, "studio:q:", 100)) {
      const ref = await kget(env, k); const job = ref && await kget(env, K.job(ref.id));
      if (!job || job.status !== "queued") { await env.KV.delete(k); continue; }   // stale queue entry (cancelled/claimed elsewhere)
      if (want ? job.id !== want : job.e2e) continue;
      await env.KV.delete(k);
      job.status = "running"; setStatusText(job, "running"); job.updated = now(); job.events.push({ t: job.updated, e: "running" }); await kput(env, K.job(job.id), job);
      const ch = await kget(env, K.chan(job.org, job.channel));   // platform + slug let the worker resolve "my last stream" (type auto) of a trusted org from the platform's VODs
      return json({ job: { id: job.id, org: job.org, channel: job.channel, kind: job.kind, source: job.source, style_id: job.style_id, outputs: job.outputs, hints: job.hints || {}, channel_info: ch ? { platform: ch.platform, slug: ch.slug } : null, org_guest: await orgIsGuest(env, job.org) } });
      // TODO(youtube): hand the worker a short-lived access token (refreshed here) instead of the refresh token.
    }
    return json({ job: null });
  }
  if (p === "/studio/worker/e2e/verify" && m === "POST") {
    // Test hook for the Playwright journey (.github/workflows/studio-e2e.yml): marks a channel verified WITHOUT the ownership check so the rest of the product can be exercised on the deployed app.
    // Only with the worker key AND only for workspaces whose owner is a throw-away guest account; such channels are flagged e2e, their jobs are never claimed by the real render worker.
    const b = await body(req).catch(() => null); if (!b) return err(400, "bad_json"); const orgId = clean(b.org, 40), chId = clean(b.channel, 40);
    const org = await kget(env, K.org(orgId)), owner = org && await kget(env, K.user(org.owner)); if (!owner || !owner.guest) return err(403, "not_a_guest_workspace");
    const ch = await kget(env, K.chan(orgId, chId)); if (!ch) return err(404, "not_found");
    Object.assign(ch, { status: "verified", verified_at: now(), verified_via: "e2e", e2e: true }); await kput(env, K.chan(orgId, ch.id), ch); return json({ channel: ch });
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
