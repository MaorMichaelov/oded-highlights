// ODED HIGHLIGHTS chat app backend (Cloudflare Worker). Serves the PWA, authenticates the owner, runs an LLM agent (Workers AI) with tools that read/write the GitHub system.
const REPO = "MaorMichaelov/oded-highlights";
const HTML = __HTML__;
const ICON = "__ICON__";
const MODELS = ["@cf/openai/gpt-oss-120b", "@cf/meta/llama-3.3-70b-instruct-fp8-fast", "@cf/openai/gpt-oss-20b", "@cf/meta/llama-3.1-8b-instruct"];
const ERRS = [];
const J = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
const hex = (b) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
const sha = async (t) => hex(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t)));
const b64 = (s) => btoa(unescape(encodeURIComponent(s)));

async function ghRead(path, tok) {
  const url = tok ? `https://api.github.com/repos/${REPO}/contents/${path}` : `https://raw.githubusercontent.com/${REPO}/main/${path}?t=${Date.now() >> 14}`;
  const r = await fetch(url, { headers: { "user-agent": "oded-app", ...(tok ? { authorization: "Bearer " + tok, accept: "application/vnd.github.raw+json" } : {}) } });
  return r.ok ? await r.text() : null;
}
const ghJson = async (p, t) => { const x = await ghRead(p, t); try { return x ? JSON.parse(x) : null; } catch { return null; } };
async function ghWrite(path, content, msg, tok) {   // create or update a file (needs the owner's GitHub token)
  const u = `https://api.github.com/repos/${REPO}/contents/${path}`, h = { authorization: "Bearer " + tok, "user-agent": "oded-app", accept: "application/vnd.github+json" };
  const cur = await fetch(u, { headers: h }); const sha_ = cur.ok ? (await cur.json()).sha : undefined;
  const r = await fetch(u, { method: "PUT", headers: h, body: JSON.stringify({ message: msg, content: b64(content), sha: sha_, branch: "main" }) });
  return r.ok;
}
async function ghDelete(path, msg, tok) {
  const u = `https://api.github.com/repos/${REPO}/contents/${path}`, h = { authorization: "Bearer " + tok, "user-agent": "oded-app", accept: "application/vnd.github+json" };
  const cur = await fetch(u, { headers: h }); if (!cur.ok) return false;
  const r = await fetch(u, { method: "DELETE", headers: h, body: JSON.stringify({ message: msg, sha: (await cur.json()).sha, branch: "main" }) }); return r.ok;
}
const clip = (t, n = 3500) => (t.length > n ? t.slice(0, n) + "…" : t);
const mmss = (s) => `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const TOOLS = {
  async status(a, tok) {
    const [live, health, pick, pend, ing] = await Promise.all(["live_status.json", "health.json", "pick_state.json", "pending_candidates.json", "ingest_state.json"].map((f) => ghJson("state/" + f, tok)));
    const cat = (await ghRead("state/category.jsonl", tok) || "").trim().split("\n").slice(-1)[0];
    return { live, last_category_change: cat ? JSON.parse(cat) : null, health, pick_state: pick, pending_candidates: (pend || []).length, current_vod: ing && ing._current_vod };
  },
  async skipped(a, tok) { return { pick_state: await ghJson("state/pick_state.json", tok), pending_candidates: await ghJson("state/pending_candidates.json", tok), lessons: ((await ghJson("state/lessons.json", tok)) || []).slice(-8) }; },
  async views(a, tok) {   // channel views gained in the last N hours, from our own hourly snapshots (state/yt_history.jsonl)
    const h = Number(a.hours || 48); const raw = await ghRead("state/yt_history.jsonl", tok); if (!raw) return { note: "אין עדיין היסטוריה. הנתונים מצטברים מעכשיו, כל חצי שעה." };
    const rows = raw.trim().split("\n").map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean); const last = rows[rows.length - 1];
    const tgt = Date.parse(last.t) - h * 3600e3; const base = rows.filter((r) => Date.parse(r.t) <= tgt).pop(); const first = rows[0];
    const ref = base || first; const have = (Date.parse(last.t) - Date.parse(ref.t)) / 3600e3;
    return { requested_hours: h, covered_hours: Math.round(have * 10) / 10, views_gained: last.views - ref.views, exact: !!base, channel_views_total: last.views, as_of: last.t, history_since: first.t, note: base ? "מדויק" : "ההיסטוריה שלנו קצרה מהחלון שביקשת: זה הגידול מאז " + first.t + " בלבד. לנתון מדויק ל-48 שעות צריך להפעיל את YouTube Analytics API." };
  },
  async drafts(a, tok) { const i = (await ghJson("state/index.json", tok)) || []; return i.slice(-15).reverse().map((c) => ({ title: c.title, uploaded: !!c.draft, url: c.draft || null, uploaded_at: c.draft_at || null, note: c.draft ? "טיוטה פרטית ביוטיוב" : (c.quality_errors && c.quality_errors.length ? "נחסם בבדיקת איכות" : "לא הועלה (בדיקה או בתהליך)") })); },
  async stats(a, tok) { const s = await ghJson("state/yt_stats.json", tok); if (!s) return "אין עדיין נתוני יוטיוב"; const v = [...s.videos].sort((x, y) => y.views - x.views); return { channel: s.channel, fetched_at: s.fetched_at, top: v.slice(0, 8).map((x) => ({ title: x.title, views: x.views, likes: x.likes, privacy: x.privacy })), latest: [...s.videos].slice(0, 6).map((x) => ({ title: x.title, views: x.views, privacy: x.privacy })) }; },
  async transcript(a, tok) {   // search the current stream transcript by words and/or time window (seconds of the stream)
    const ing = await ghJson("state/ingest_state.json", tok); if (!ing || !ing._current_vod) return "אין שידור מתומלל";
    const raw = await ghRead(`state/transcripts/${ing._current_vod}.jsonl`, tok); if (!raw) return "אין תמלול";
    let rows = raw.trim().split("\n").map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean);
    const end = rows.length ? rows[rows.length - 1].end : 0;
    if (a.last_minutes) rows = rows.filter((r) => r.start >= end - a.last_minutes * 60);
    if (a.from != null) rows = rows.filter((r) => r.start >= a.from);
    if (a.to != null) rows = rows.filter((r) => r.end <= a.to);
    if (a.query) { const q = String(a.query).split(/\s+/).filter(Boolean); rows = rows.filter((r) => q.some((w) => r.text.includes(w))); }
    return { vod: ing._current_vod, transcript_end: mmss(end), matches: rows.slice(-40).map((r) => `[${mmss(r.start)}|${Math.round(r.start)}] ${r.text}`) };
  },
  async cut(a, tok) {
    if (!tok) return "חסר מפתח GitHub בהגדרות האפליקציה";
    const ing = await ghJson("state/ingest_state.json", tok); const vod = a.vod || ing._current_vod; const s = Math.max(0, Math.floor(a.start - 3)), e = Math.floor(a.end);
    if (!(e - s >= 120)) return "הקטע קצר מדי (מינימום 2 דקות)";
    const id = `app_${vod}_${s}`, d = `state/clips/${id}`;
    const desc = (a.description || "") + "\n\nהרגעים הכי טובים מהלייב של עודד בקיק | ODED HIGHLIGHTS\n\nהקטע מתוך הלייב של עודד בקיק: https://kick.com/odedsvr\n\n#עודד #OdedSVR #עודדהיילייטס #קיק";
    const ok1 = await ghWrite(d + "/cuts.json", JSON.stringify({ vod, base: ing._vod_base, pieces: [{ keep: [[s, e]], ch: (a.brief && a.brief.about || "הנושא").slice(0, 40) }] }, null, 1), "app: cut " + id, tok);
    const ok2 = await ghWrite(d + "/spec.json", JSON.stringify({ title: a.title || "בדיקה: קליפ מהאפליקציה (לשנות כותרת)!", description: desc, tags: ["עודד", "OdedSVR", "ODED HIGHLIGHTS"], preset: "reaction_video", head: "", accent: "", refs: "shock,excited,smirk", brief: a.brief || {}, auto: false, picked_by: "app" }, null, 1), "app: spec " + id, tok);
    if (!ok1 || !ok2) return "כתיבה ל-GitHub נכשלה (בדוק את המפתח)";
    const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/render-clip.yml/dispatches`, { method: "POST", headers: { authorization: "Bearer " + tok, "user-agent": "oded-app", accept: "application/vnd.github+json" }, body: JSON.stringify({ ref: "main", inputs: { clip_id: id, upload: "true" } }) });
    return r.status === 204 ? `התחיל: ${id} (${Math.round((e - s) / 60)} דקות). טיוטה בעוד כ-5-8 דקות.` : "הפעלת הרינדור נכשלה " + r.status;
  },
  async pause(a, tok) { if (!tok) return "חסר מפתח GitHub"; return (await ghWrite("state/PAUSE", "paused from app\n", "app: pause", tok)) ? "המערכת עצורה (הלולאה תיעצר בסיבוב הבא)" : "נכשל"; },
  async resume(a, tok) { if (!tok) return "חסר מפתח GitHub"; const ok = await ghDelete("state/PAUSE", "app: resume", tok); const r = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/live-loop.yml/dispatches`, { method: "POST", headers: { authorization: "Bearer " + tok, "user-agent": "oded-app", accept: "application/vnd.github+json" }, body: JSON.stringify({ ref: "main" }) }); return `PAUSE ${ok ? "הוסר" : "לא היה"}; הלולאה ${r.status === 204 ? "הופעלה מחדש" : "לא הופעלה " + r.status}`; },
  async lesson(a, tok) { if (!tok) return "חסר מפתח GitHub"; const L = (await ghJson("state/lessons.json", tok)) || []; L.push({ t: new Date().toISOString().slice(0, 10), source: "owner_chat", text: a.text }); return (await ghWrite("state/lessons.json", JSON.stringify(L.slice(-200), null, 1), "app: lesson", tok)) ? "נרשם לקח. תחנת הבחירה תקרא אותו" : "נכשל"; },
  async instruction(a, tok) { if (!tok) return "חסר מפתח GitHub"; const cur = (await ghRead("state/chat_instructions.md", tok)) || ""; return (await ghWrite("state/chat_instructions.md", (cur + "\n- " + a.text).slice(-4000), "app: instruction", tok)) ? "נוספה הנחיה קבועה" : "נכשל"; },
};
const TOOL_DOC = `status: מצב הלייב והמערכת. args: {}
skipped: מה המערכת פסלה ולמה (הערות תחנת הבחירה, מועמדים, לקחים). args: {}
views: כמה צפיות הערוץ קיבל ב-N שעות אחרונות. args: {hours}
drafts: רשימת הקליפים והטיוטות האחרונות עם קישורים. args: {}
stats: נתוני יוטיוב (צפיות, לייקים, הכי חזקים). args: {}
transcript: חיפוש בתמלול של השידור הנוכחי. args: {query?: "מילים", last_minutes?: n, from?: שניות, to?: שניות}
cut: חיתוך קליפ והעלאה כטיוטה פרטית. args: {start: שניות, end: שניות, title: "40-55 תווים בעברית שמסתיים ב-! או ?!", description: "...", brief: {about, who, peak}}  (לפני חיתוך מצא את הזמנים עם transcript; אם הבקשה לא ברורה שאל)
pause / resume: עצירה והמשך של המערכת. args: {}
lesson: לקח קבוע לבחירת נושאים. args: {text}
instruction: הנחיה קבועה לצ'אט. args: {text}`;

async function groq(key, messages) {   // primary LLM when the owner added a Groq key in the app settings (separate free quota from Cloudflare Workers AI)
  const r = await fetch("https://api.groq.com/openai/v1/chat/completions", { method: "POST", headers: { authorization: "Bearer " + key, "content-type": "application/json" }, body: JSON.stringify({ model: "openai/gpt-oss-120b", messages, temperature: 0.3, max_tokens: 1500, reasoning_effort: "low" }) });
  const j = await r.json(); if (!r.ok) throw new Error("groq " + r.status + ": " + JSON.stringify(j).slice(0, 140));
  return j.choices && j.choices[0] && j.choices[0].message && j.choices[0].message.content;
}
async function llm(env, messages, gkey) {
  ERRS.length = 0;
  if (gkey) { try { const t = await groq(gkey, messages); if (t && !/(.)\1{12,}/.test(t)) return t; } catch (e) { ERRS.push(String(e.message).slice(0, 200)); } }
  for (const m of MODELS) {
    try {
      const r = await env.AI.run(m, m.includes("gpt-oss") ? { input: messages.map((x) => ({ role: x.role, content: x.content })), reasoning: { effort: "low" }, max_output_tokens: 1500 } : { messages, max_tokens: 1200 });
      const t = r.response || (r.choices && r.choices[0] && r.choices[0].message && r.choices[0].message.content) || r.output_text ||
        (r.output && r.output.map((o) => (o.content || []).map((c) => c.text || "").join("")).join("")) || null;
      if (t && !/(.)\1{12,}/.test(t)) return t;   // a degenerate repeated-character output counts as a failure: try the next model
    } catch (e) { ERRS.push(m + ": " + String(e && e.message || e).slice(0, 160)); }
  }
  return null;
}
async function agent(env, msgs, tok, gkey) {
  const instr = (await ghRead("state/chat_instructions.md", tok)) || "";
  const system = `אתה העוזר של בעל הערוץ ODED HIGHLIGHTS (קליפים בעברית מהלייבים של הסטרימר עודד, kick.com/odedsvr). עונה בעברית, קצר וברור, כמו וואטסאפ. תאריך: ${new Date().toISOString()}.
המערכת: GitHub מזהה לייב, מתמלל, בוחר נושאים, חותך, עורך ומעלה טיוטות פרטיות. אתה לא מפרסם ולא מוחק שום דבר.
כלים (קרא להם בפורמט JSON בלבד):
${TOOL_DOC}
פורמט תשובה: או {"tool":"שם","args":{...}} כדי להפעיל כלי, או {"reply":"הטקסט למשתמש"} כדי לענות. החזר JSON בלבד, שורה אחת, בלי טקסט נוסף.
אל תמציא נתונים: אם צריך מידע, הפעל כלי. קליפ נחשב שהועלה רק אם uploaded=true. כללי נתונים: אסור לנחש, להעריך או לעגל מספרים. צטט רק מספרים מתוצאת כלי וציין עד מתי הנתון (as_of/fetched_at). אם הכלי אומר שהנתון חלקי או חסר, אמור את זה בגלוי. שאלה על צפיות בטווח זמן: הפעל views. אחרי תוצאת כלי, סכם בקצרה.${instr ? "\nהנחיות קבועות מהבעלים:\n" + instr : ""}`;
  const m = [{ role: "system", content: system }, ...msgs.slice(-12)];
  for (let i = 0; i < 5; i++) {
    const out = await llm(env, m, gkey); if (!out) { const e = ERRS.join(" | "); return /neuron|limit|quota|capacity|3040|4006/i.test(e) ? "מכסת ה-AI היומית של Cloudflare נגמרה (מתאפסת בחצות UTC). פתרון קבוע: הוסף מפתח Groq בהגדרות האפליקציה (⚙), שזה מודל חינמי נפרד." : "המודל לא זמין כרגע (" + e.slice(0, 120) + "). נסה שוב בעוד דקה."; }
    let j = null; const mt = out.match(/\{[\s\S]*\}/); try { j = JSON.parse(mt ? mt[0] : out); } catch { return out.trim(); }
    if (j.reply) return j.reply;
    if (j.tool && TOOLS[j.tool]) {
      let res; try { res = await TOOLS[j.tool](j.args || {}, tok); } catch (e) { res = "שגיאה: " + e.message; }
      m.push({ role: "assistant", content: JSON.stringify(j) }, { role: "user", content: "תוצאת הכלי " + j.tool + ": " + clip(typeof res === "string" ? res : JSON.stringify(res)) });
    } else return out.trim();
  }
  return "לא הצלחתי לסיים. נסה לנסח אחרת.";
}
async function auth(req, env) {
  const pw = req.headers.get("x-pass") || ""; const salt = await env.KV.get("salt"), h = await env.KV.get("pw");
  if (!h) return "setup";
  const ip = req.headers.get("cf-connecting-ip") || "x", k = "fail:" + ip; const f = parseInt((await env.KV.get(k)) || "0");
  if (f >= 15) return "locked";
  if ((await sha(salt + pw)) === h) return "ok";
  await env.KV.put(k, String(f + 1), { expirationTtl: 3600 }); return "bad";
}
export default {
  async fetch(req, env) {
    const u = new URL(req.url), p = u.pathname;
    if (p === "/" || p === "/index.html") return new Response(HTML, { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-cache" } });
    if (p === "/manifest.webmanifest") return J({ name: "ODED HIGHLIGHTS", short_name: "ODED HL", start_url: "/", display: "standalone", background_color: "#0b0f0d", theme_color: "#0b0f0d", lang: "he", dir: "rtl", icons: [{ src: "/icon.png", sizes: "192x192", type: "image/png", purpose: "any maskable" }] });
    if (p === "/icon.png") return new Response(Uint8Array.from(atob(ICON), (c) => c.charCodeAt(0)), { headers: { "content-type": "image/png", "cache-control": "public, max-age=86400" } });
    if (p === "/sw.js") return new Response("self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('fetch',()=>{});", { headers: { "content-type": "application/javascript" } });
    if (p === "/api/state") return J({ setup: !(await env.KV.get("pw")) });
    if (p === "/api/setup" && req.method === "POST") {
      if (await env.KV.get("pw")) return J({ error: "already set" }, 403);
      const b = await req.json(); if (!b.password || b.password.length < 8) return J({ error: "סיסמה קצרה מדי (מינימום 8 תווים)" }, 400);
      const salt = crypto.randomUUID(); await env.KV.put("salt", salt); await env.KV.put("pw", await sha(salt + b.password)); return J({ ok: true });
    }
    const a = await auth(req, env); if (a !== "ok") return J({ error: a }, a === "locked" ? 429 : 401);
    const tok = req.headers.get("x-gh") || "";
    if (p === "/api/feed") {
      const since = u.searchParams.get("since") || "1970"; const [live, ev] = await Promise.all([ghJson("state/live_status.json", tok), ghRead("state/events.jsonl", tok)]);
      const events = (ev || "").trim().split("\n").map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter((e) => e && e.t > since).slice(-10);
      return J({ live: live && live.live, title: live && live.title, events, now: new Date().toISOString() });
    }
    if (p === "/api/chat" && req.method === "POST") { const b = await req.json(); const reply = await agent(env, b.messages || [], tok, req.headers.get("x-groq") || ""); return J({ reply, ...(ERRS.length ? { debug: ERRS } : {}) }); }
    return J({ error: "not found" }, 404);
  },
};
