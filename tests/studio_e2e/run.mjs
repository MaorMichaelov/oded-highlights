// Scripted user journey against the Studio (deployed Worker or the local stand-in). Playwright + Chromium.
//   BASE=https://studio-app.odedhl.workers.dev  OUT=state/studio_e2e  node tests/studio_e2e/run.mjs
//   env: PROFILES=mobile-he,mobile-en,desktop-he,desktop-en  WORKER_KEY=<x-worker-key, optional: enables the verified-channel part>  LOCAL=1 (talks to tests/studio_e2e/local_server.mjs controls)
//   CHROME=/usr/bin/google-chrome (optional)  ONLY=<step-name substring>
// Output: OUT/report.json (+ screenshots). Exit code 1 when any step failed or any error-level issue was collected.
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

const BASE = (process.env.BASE || "http://localhost:8787").replace(/\/+$/, "");
const OUT = process.env.OUT || "state/studio_e2e";
const LOCAL = process.env.LOCAL === "1" || /localhost|127\.0\.0\.1/.test(BASE);
const WORKER_KEY = process.env.WORKER_KEY || (LOCAL ? "wk_local_e2e" : "");
const ALL = { "mobile-he": { w: 390, h: 844, lang: "he", mobile: true }, "mobile-en": { w: 390, h: 844, lang: "en", mobile: true }, "desktop-he": { w: 1280, h: 800, lang: "he", mobile: false }, "desktop-en": { w: 1280, h: 800, lang: "en", mobile: false } };
const PROFILES = (process.env.PROFILES || Object.keys(ALL).join(",")).split(",").filter((x) => ALL[x]);
const ONLY = process.env.ONLY || "";
fs.mkdirSync(OUT, { recursive: true });
for (const f of fs.readdirSync(OUT)) if (/\.(png|json)$/.test(f)) fs.rmSync(path.join(OUT, f));

const report = { base: BASE, started: new Date().toISOString(), profiles: {}, summary: {} };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const rnd = () => Math.random().toString(36).slice(2, 8);

async function ctl(q) { if (LOCAL) await fetch(BASE + "/__ctl?" + new URLSearchParams(q)); }
async function wapi(p, body) { const r = await fetch(BASE + "/studio/worker" + p, { method: "POST", headers: { "content-type": "application/json", "x-worker-key": WORKER_KEY }, body: JSON.stringify(body || {}) }); return { s: r.status, j: await r.json().catch(() => ({})) }; }
async function sapi(token, method, p, body) { const r = await fetch(BASE + "/studio/api" + p, { method, headers: { "content-type": "application/json", authorization: "Bearer " + token }, body: body ? JSON.stringify(body) : undefined }); return { s: r.status, j: await r.json().catch(() => ({})) }; }

// ---- in-page checks (serialised into the page)
const LAYOUT = () => {
  const W = innerWidth, out = [], desc = (el) => el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") + (el.className && typeof el.className === "string" ? "." + el.className.trim().split(/\s+/).slice(0, 3).join(".") : "") + " \"" + (el.textContent || "").trim().slice(0, 30) + "\"";
  const vis = (el) => { const cs = getComputedStyle(el); if (cs.display === "none" || cs.visibility === "hidden" || +cs.opacity === 0) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  if (document.documentElement.scrollWidth > W + 1) out.push({ k: "page-overflow", sw: document.documentElement.scrollWidth, w: W });
  const skip = ".chipscroll,#toasts,.skip,.sr,.stage,.rv-stamp,.ring,.pips,.pwrap";
  for (const el of document.querySelectorAll("body *")) {
    if (!vis(el) || el.closest(skip) || el.closest("svg") || el.closest("details:not([open]) > :not(summary)")) continue; const r = el.getBoundingClientRect(), cs = getComputedStyle(el);
    if ((r.right > W + 1 || r.left < -1) && !el.closest(".rv-card.settle,.rv-card.dragging")) out.push({ k: "offscreen", el: desc(el), l: Math.round(r.left), r: Math.round(r.right) });
    if (el.scrollWidth > el.clientWidth + 2 && el.clientWidth > 0 && cs.overflowX === "hidden" && cs.textOverflow !== "ellipsis" && !el.matches("body,html,.shell,.content,.tabbar,.rv-card,.rv-media,.player,.poster,.bar,.bar i,.live-card,.card,.auth,.visual,.landing,.stage")) out.push({ k: "clipped", el: desc(el), sw: el.scrollWidth, cw: el.clientWidth });
  }
  const ints = [...document.querySelectorAll("button,a[href],input:not([type=hidden]):not([type=radio]):not([type=checkbox]),textarea,select")].filter((e) => vis(e) && !e.closest(skip) && !e.closest("details:not([open]) > :not(summary)") && !e.disabled);
  for (let i = 0; i < ints.length; i++) for (let j = i + 1; j < ints.length; j++) { const a = ints[i], b = ints[j]; if (a.contains(b) || b.contains(a)) continue; if (a.closest(".tabbar,header.top") || b.closest(".tabbar,header.top")) continue; const x = a.getBoundingClientRect(), y = b.getBoundingClientRect(); const ox = Math.min(x.right, y.right) - Math.max(x.left, y.left), oy = Math.min(x.bottom, y.bottom) - Math.max(x.top, y.top); if (ox > 4 && oy > 4 && ox * oy > 0.3 * Math.min(x.width * x.height, y.width * y.height)) out.push({ k: "overlap", a: desc(a), b: desc(b) }); }
  window.scrollTo(0, document.body.scrollHeight);   // second pass at the bottom of the page: nothing may hide behind the tab bar / dock / composer
  for (const e of ints) { const r = e.getBoundingClientRect(); if (r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > W) continue; const cx = Math.min(Math.max(r.left + r.width / 2, 1), W - 1), cy = Math.min(Math.max(r.top + r.height / 2, 1), innerHeight - 1); const top = document.elementFromPoint(cx, cy); if (top && !top.closest("#toasts,header.top") && !e.contains(top) && !top.contains(e) && !(e.closest("label") && e.closest("label").contains(top))) out.push({ k: "covered", el: desc(e), by: desc(top) }); }
  window.scrollTo(0, 0); return out.slice(0, 40);
};
const TEXTS = (lang) => {
  const out = [], seen = new Set(); const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) { const n = w.currentNode, tx = (n.nodeValue || "").trim(); if (!tx || n.parentElement.closest("script,style,noscript,code,.ltr,.mail,#toasts,[aria-hidden=true]")) continue; const el = n.parentElement, cs = getComputedStyle(el); if (cs.display === "none" || cs.visibility === "hidden") continue; if (seen.has(tx)) continue; seen.add(tx);
    if (/^[a-z]+(_[a-z0-9]+)+$/.test(tx)) out.push({ k: "i18n-key", tx });
    else if (lang === "he") { const lat = tx.replace(/https?:\S+|\S+@\S+|ODH-\w+|kick\.com\S*|twitch\.tv\S*/gi, "").match(/[A-Za-z]{4,}/g) || []; const bad = lat.filter((x) => !/^(Studio|Kick|Twitch|YouTube|Shorts|Short|WhatsApp|Google|Guest|OdedSVR|Plan|Noa|Auto|Tap|Enter|Esc|Edit|Client|Team|kaicenat|odedsvr|nobody|here|team|mobile\w*|desktop\w*)$/i.test(x)); if (bad.length && !/[֐-׿]/.test(tx) ? true : bad.length) out.push({ k: "latin-in-he", tx: tx.slice(0, 60) }); }
    else if (lang === "en" && /[֐-׿]/.test(tx) && !/^(עב|עברית)$/.test(tx)) out.push({ k: "hebrew-in-en", tx: tx.slice(0, 60) }); }
  return out.slice(0, 20);
};

// ---- per-profile journey
async function runProfile(browser, name, P) {
  const R = { steps: [], issues: [], layout: [], texts: [], notes: [], skipped: [] }; report.profiles[name] = R;
  const mkctx = async (extra = {}) => { const c = await browser.newContext({ viewport: { width: P.w, height: P.h }, isMobile: P.mobile, hasTouch: P.mobile, deviceScaleFactor: 1, locale: P.lang === "he" ? "he-IL" : "en-US", timezoneId: "Asia/Jerusalem", ...extra }); c.setDefaultTimeout(12000); return c; };
  let cur = "init", allow = [];
  const note = (type, text, extra) => { const t = String(text).slice(0, 300); if (allow.some((a) => a.test(type + " " + t))) return; R.issues.push({ step: cur, type, text: t, ...extra }); };
  const hook = (page, tag) => {
    page.on("console", (m) => { if (m.type() === "error") note("console-error", (tag ? tag + ": " : "") + m.text() + " " + (m.location().url || "").replace(BASE, "")); else if (m.type() === "warning" && !/font|preload|GPU|deprecat|Permissions policy/i.test(m.text())) note("console-warn", m.text()); });
    page.on("pageerror", (e) => note("uncaught-exception", (tag ? tag + ": " : "") + (e.stack || e.message)));
    page.on("requestfailed", (r) => { const u = r.url(); if (/fonts\.(googleapis|gstatic)/.test(u) || /ERR_ABORTED/.test(r.failure()?.errorText || "")) return; note("request-failed", r.method() + " " + u.replace(BASE, "") + " " + (r.failure() || {}).errorText); });
    page.on("response", (r) => { if (r.status() >= 400 && !/fonts\./.test(r.url())) note("http-" + r.status(), r.request().method() + " " + r.url().replace(BASE, ""), { kind: "response" }); });
    page.on("response", async (r) => { const u = r.url(); if (!/\/studio\/(api|yt)\//.test(u)) return; const e = { step: cur, m: r.request().method(), p: u.replace(BASE, "").replace(/\?.*/, "").replace(/o_[a-f0-9]{16}/, "o_*"), s: r.status(), t: Math.round(Date.now() / 1000) % 100000 }; if (/\/channels(\/[a-z0-9_]+)?$/.test(e.p) && r.request().method() !== "OPTIONS") { try { const b = await r.text(); e.b = b.replace(/"verify_code":"[^"]+"/, "").slice(0, 160); } catch {} } (R.net = R.net || []).push(e); if (R.net.length > 600) R.net.shift(); });
    page.on("dialog", (d) => d.accept().catch(() => {}));
  };
  const shot = async (page, label, key) => { const f = `${name}-${label}.png`; try { await sleep(450); await page.screenshot({ path: path.join(OUT, f), fullPage: false }); if (key) (report.keyShots = report.keyShots || []).push(f); } catch {} };
  const check = async (page, label) => { try { const l = await page.evaluate(LAYOUT); for (const x of l) R.layout.push({ at: label, ...x }); const tx = await page.evaluate(TEXTS, await page.evaluate(() => document.documentElement.lang)); for (const x of tx) R.texts.push({ at: label, ...x }); } catch (e) { R.notes.push("check failed at " + label + ": " + e.message); } };
  const step = async (title, fn, opt = {}) => {
    if (ONLY && !title.includes(ONLY)) return; cur = title; allow = opt.allow || []; const t0 = Date.now();
    if (opt.needs === "channel" && !state.verified) { R.skipped.push(title + " (no verified channel)"); return; }
    try { await fn(); R.steps.push({ name: title, ok: true, ms: Date.now() - t0 }); } catch (e) { R.steps.push({ name: title, ok: false, ms: Date.now() - t0, error: String(e.message || e).split("\n")[0].slice(0, 300) }); if (state.page) await shot(state.page, "FAIL-" + title.replace(/\W+/g, "_")); }
    allow = [];
  };
  const bug = (msg) => { R.bugs = R.bugs || []; R.bugs.push({ step: cur, msg }); };
  const slug = LOCAL ? "odedsvr-" + name.replace(/\W/g, "") : "odedsvr";   // the local stand-in keeps channel claims between profiles, the deployed app gets the real name
  const state = { page: null, verified: false, token: null, orgId: null, chId: null, jobs: [] };
  const ctx = await mkctx(); const page = await ctx.newPage(); hook(page); state.page = page;
  const tx = (he, en) => (P.lang === "he" ? he : en);
  const settle = async (ms = 400) => { await page.waitForLoadState("networkidle").catch(() => {}); await sleep(ms); };
  const exp = async (cond, msg, ms = 10000) => { const t0 = Date.now(); while (Date.now() - t0 < ms) { try { if (await cond()) return; } catch {} await sleep(150); } throw new Error("timeout: " + msg); };
  const txt = async (sel) => (await page.locator(sel).first().innerText().catch(() => "")).trim();
  const ev = (f, a) => page.evaluate(f, a);
  const hash = () => page.evaluate(() => location.hash);
  const bottomNav = (r) => (P.mobile ? page.locator(`.tabbar a.tab[data-r="${r}"]`) : page.locator(`.side a.tab[data-r="${r}"]`));
  const goTo = async (r) => { if (P.mobile && ["team", "credits", "settings"].includes(r)) { await page.locator('.tabbar a.tab[data-r="more"]').click(); await exp(async () => (await hash()) === "#/more", "more"); await page.locator(`.menu-item[href="#/${r}"]`).click(); } else await bottomNav(r).click(); await exp(async () => (await hash()).startsWith("#/" + r), "route " + r); await sleep(250); };
  const jobsApi = async () => (await sapi(state.token, "GET", `/orgs/${state.orgId}/jobs`)).j.jobs || [];
  const prefix = (s) => s + "-" + name;

  // 1 -------------------------------------------------------------------------------------------------------------------------------
  await step("landing", async () => {
    await page.goto(BASE + "/studio", { waitUntil: "domcontentloaded" }); await page.waitForSelector(".authcard"); await settle();
    const [lang, dir] = await ev(() => [document.documentElement.lang, document.documentElement.dir]); if (lang !== P.lang || dir !== (P.lang === "he" ? "rtl" : "ltr")) throw new Error(`html lang/dir wrong: ${lang}/${dir}`);
    if (!(await txt(".display"))) throw new Error("no hero title"); await check(page, "landing"); await shot(page, "01-landing", true);
    const other = P.lang === "he" ? "en" : "he"; await page.locator(`.auth-top .seg button[aria-label="${other === "he" ? "עברית" : "English"}"]`).click(); await settle(200);
    if ((await ev(() => document.documentElement.dir)) !== (other === "he" ? "rtl" : "ltr")) throw new Error("language switch did not flip dir"); await check(page, "landing-switched"); await shot(page, "01b-landing-other-lang");
    await page.locator(`.auth-top .seg button[aria-label="${P.lang === "he" ? "עברית" : "English"}"]`).click(); await settle(200);
    const th0 = await ev(() => document.documentElement.getAttribute("data-theme")); await page.locator(".auth-top .iconbtn").click(); const th1 = await ev(() => document.documentElement.getAttribute("data-theme")); if (th0 === th1) throw new Error("theme button did nothing"); await page.locator(".auth-top .iconbtn").click();
    const emailBox = page.locator("details.emailbox summary"); await emailBox.click(); await check(page, "landing-email-form");
    await page.locator("#email").fill("not-an-email"); await page.locator("#pw").fill("12345678"); await page.locator('form button[type=submit]').click(); if (!(await txt(".errtxt"))) throw new Error("no error for bad email");
    await page.locator("#email").fill(`x${rnd()}@example.com`); await page.locator("#pw").fill("short"); await page.locator('form button[type=submit]').click(); if (!(await txt(".errtxt"))) throw new Error("no error for short password");
    await emailBox.click();
  });

  await step("guest-entry", async () => {
    await page.locator(".authcard button.btn.lg").first().click(); await page.waitForSelector(".shell"); await settle(500);
    state.token = await ev(() => localStorage.getItem("studio_token")); state.orgId = await ev(() => S.org && S.org.id); if (!state.token || !state.orgId) throw new Error("no token/org after guest entry");
    if (!(await hash()).startsWith("#/setup")) throw new Error("owner without channel should land on setup, got " + (await hash())); await check(page, "setup-1"); await shot(page, "02-setup-channel", true);
  });

  await step("setup-channel-errors", async () => {
    const inp = page.locator("#chIn"); await inp.fill("hello world"); await page.locator("form button[type=submit]").click(); if (!(await txt(".errtxt"))) throw new Error("no error for garbage channel");
    await inp.fill("https://www.kick.com/" + slug.toUpperCase() + "/videos"); await exp(async () => new RegExp(slug, "i").test(await txt(".detect")), "detect chip shows slug"); await check(page, "setup-1-detected");
  });

  await step("setup-wrong-channel-then-back", async () => {   // add a channel that does not exist on Kick, see the friendly error, change it
    await page.locator("#chIn").fill("kick.com/zz-nochan-" + rnd()); await page.locator("form button[type=submit]").click(); await page.waitForSelector(".code-box code"); await check(page, "setup-2"); await shot(page, "03-setup-verify", true);
    const code = await txt(".code-box code"); if (!/^ODH-[A-Z2-9]{8}$/.test(code)) throw new Error("bad code " + code);
    await page.locator('.card button.btn:not(.ghost):not(.secondary)').last().click(); await exp(async () => (await txt('[role="status"].small')).length > 3, "verify message", 15000);
    R.notes.push("verify message for a non-existing Kick channel: " + (await txt('[role="status"].small')));
    await page.locator("button.btn.ghost.sm").click(); await page.waitForSelector("#chIn");
  }, { allow: [/502|404/] });

  await step("verify-real-channel-states", async () => {
    await ctl({ kick_bio: "" }); await page.locator("#chIn").fill("kick.com/" + slug); await page.locator("form button[type=submit]").click(); await page.waitForSelector(".code-box code");
    state.code = await txt(".code-box code"); await page.locator('.card button.btn:not(.ghost):not(.secondary)').last().click();
    await exp(async () => (await txt('[role="status"].small')).length > 3, "verify message", 20000); const msg = await txt('[role="status"].small'); R.notes.push("verify message for kick.com/odedsvr without the code: " + msg);
    if (/^(generic|משהו השתבש)/.test(msg)) throw new Error("verify shows a generic error: " + msg);
    await page.locator('button:has-text("' + tx("העתקה", "Copy") + '")').first().click(); await exp(async () => (await page.locator(".toast").count()) > 0, "copy toast");
    await check(page, "setup-2-message"); await shot(page, "04-verify-not-found");
  }, { allow: [/502|403/] });

  await step("setup-timer-polls-and-cleanup", async () => {   // the page re-checks on its own every few seconds
    const cnt = () => ev(() => performance.getEntriesByType("resource").filter((r) => /verify/.test(r.name)).length); const before = await cnt();
    await exp(async () => (await cnt()) > before, "auto check fires within ~30s", 32000);
  }, { allow: [/502|403/] });

  await step("reload-mid-verification", async () => {
    await page.reload(); await page.waitForSelector(".code-box code"); if ((await txt(".code-box code")) !== state.code) throw new Error("code changed after reload"); await settle();
  }, { allow: [/502|403/] });

  await step("verify-success", async () => {
    if (LOCAL) { await ctl({ kick_bio: "bio " + state.code.toLowerCase() }); await page.locator('.card button.btn:not(.ghost):not(.secondary)').last().click(); await exp(async () => !(await page.locator(".code-box").count()), "left verify step", 15000); state.verified = true; }
    else if (WORKER_KEY) { const ch = (await sapi(state.token, "GET", `/orgs/${state.orgId}/channels`)).j.channels.find((c) => c.slug === slug); state.chId = ch.id; const r = await wapi("/e2e/verify", { org: state.orgId, channel: ch.id }); if (r.s !== 200) throw new Error("e2e verify hook " + r.s + " " + JSON.stringify(r.j)); await page.reload(); state.verified = true; await page.waitForSelector(".shell"); }
    else { R.skipped.push("verification success + everything after it: no WORKER_KEY (the real owner of the channel must put the code in the bio)"); return; }
    await settle(500); state.chId = state.chId || (await sapi(state.token, "GET", `/orgs/${state.orgId}/channels`)).j.channels[0].id;
  }, { allow: [/502|403/] });

  await step("setup-youtube-step", async () => {
    await page.goto(BASE + "/studio#/setup"); await page.reload(); await page.waitForSelector(".shell"); await settle();
    await page.locator("button.btn.lg.block").first().click(); await sleep(700); await check(page, "setup-3-yt"); await shot(page, "05-setup-youtube");
    R.notes.push("youtube connect answer: " + ((await page.locator(".notice.warn").count()) ? "soon-notice shown" : "no notice (redirect or error?) url=" + page.url()));
    await page.locator("button.btn.ghost.block").click(); await exp(async () => (await hash()).startsWith("#/home"), "home after skip");
  }, { needs: "channel", allow: [/404|501|503/] });

  await step("home-checklist-and-chips", async () => {
    await settle(); await check(page, "home"); await shot(page, "06-home", true); if (!(await page.locator(".check-item").count())) throw new Error("no onboarding checklist"); if ((await page.locator(".chips .chip").count()) < 3) throw new Error("one-tap chips missing");
    const done = await page.locator(".check-item.done").count(); if (done < 4) bug("onboarding checklist: account+channel+verify+youtube(skipped) should be 4 done, got " + done);
    await page.locator(".chips .chip").first().click(); await exp(async () => (await hash()) === "#/chat", "chip -> chat"); await exp(async () => (await page.locator(".msg.bot").count()) >= 2 && (await page.locator(".typing").count()) === 0, "bot reply after chip", 15000);
    const reply = await txt(".msg.bot:last-child .bub"); R.notes.push("chip reply: " + reply); if (/טעינה|went wrong|משהו השתבש/.test(reply)) throw new Error("chip got an error reply: " + reply); await check(page, "chat-after-chip"); await shot(page, "07-chat", true);
    const jobs = await jobsApi(); if (jobs.length !== 1) throw new Error("expected 1 job after chip, have " + jobs.length); state.jobs.push(jobs[0].id);
    if (jobs[0].outputs.shorts !== 5 || jobs[0].source.when !== "yesterday" || jobs[0].hints.mood !== "funny") throw new Error("chip1 parsed wrong: " + JSON.stringify([jobs[0].outputs, jobs[0].source, jobs[0].hints]));
  }, { needs: "channel" });

  await step("chat-typed-request-and-limits", async () => {
    const ta = page.locator("#chatIn"); await ta.fill(tx("תכין 3 שורטס מטורפים מהשבוע", "make 3 hype shorts from last week")); await ta.press("Enter");
    await exp(async () => (await page.locator(".msg.me").count()) >= 2 && (await page.locator(".typing").count()) === 0 && (await page.locator(".msg.bot").count()) >= 3, "reply 2", 15000);
    const jobs = await jobsApi(); const j2 = jobs.find((j) => !state.jobs.includes(j.id)); if (!j2) throw new Error("typed request created no job"); state.jobs.push(j2.id);
    if (j2.source.when !== "week") throw new Error("'from last week' parsed as " + j2.source.when + " (" + tx("מהשבוע", "last week") + ")"); if (j2.hints.mood !== "hype") throw new Error("mood parse: " + j2.hints.mood);
    await ta.fill(tx("תכין 2 שורטס", "make 2 shorts")); await ta.press("Enter"); await exp(async () => (await page.locator(".msg.bot").count()) >= 4 && (await page.locator(".typing").count()) === 0, "out-of-credits reply", 15000);
    const last = await txt(".msg.bot:last-child .bub"); if (!/(נגמרו|out of credits)/i.test(last)) throw new Error("expected out-of-credits answer, got: " + last); if ((await jobsApi()).length !== 2) throw new Error("job created without credits");
    await page.locator(".chipscroll .chip").nth(3).click(); await exp(async () => (await page.locator(".msg.bot").count()) >= 5 && (await page.locator(".typing").count()) === 0, "status reply", 15000); await check(page, "chat-conversation"); await shot(page, "08-chat-conversation");
    await ta.fill("x".repeat(600)); if ((await ta.inputValue()).length > 500) throw new Error("textarea accepts more than 500 chars"); await ta.fill("");
    await ta.fill(" "); if (!(await page.locator(".send").isDisabled())) throw new Error("send enabled for blank text");
  }, { needs: "channel" });

  await step("activity-timeline-cancel-refund", async () => {
    await goTo("jobs"); await exp(async () => (await page.locator("article.job").count()) === 2, "2 job cards"); await check(page, "activity"); await shot(page, "09-activity", true);
    const pill0 = await txt("#creditPill"); if (parseInt(pill0.replace(/\D/g, "") || "x", 10) !== 0) throw new Error("credit pill should read 0, reads " + pill0);
    const j2 = state.jobs[1]; await page.locator(`#job-${j2} button:has-text("${tx("ביטול הבקשה", "Cancel request")}")`).click(); await exp(async () => (await page.locator(`#job-${j2} .chip`).first().innerText()).toLowerCase().includes(tx("בוטל", "cancelled")), "job shows cancelled", 8000);
    await exp(async () => parseInt((await txt("#creditPill")).replace(/\D/g, ""), 10) === 1, "credit refunded in the pill"); const org = (await sapi(state.token, "GET", `/orgs/${state.orgId}`)).j.org; if (org.credits !== 1) throw new Error("server credits after cancel " + org.credits);
    if (await page.locator(`#job-${state.jobs[1]} button:has-text("${tx("ביטול הבקשה", "Cancel request")}")`).count()) throw new Error("cancel button still shown on a cancelled job");
  }, { needs: "channel" });

  await step("job-progress-polling", async () => {
    const id = state.jobs[0]; const c = await wapi("/claim", { job_id: id }); if (!c.j.job || c.j.job.id !== id) throw new Error("claim failed " + c.s + JSON.stringify(c.j));
    await page.goto(BASE + "/studio#/jobs/" + id); await page.reload(); await page.waitForSelector(`#job-${id}`);
    const seen = new Set(); const watch = async (label) => { await exp(async () => { const t = await txt(`#job-${id} .live`); if (t && !seen.has(t)) { seen.add(t); return true; } return false; }, "status text change: " + label, 12000); };
    await wapi("/jobs/" + id, { progress: 12, msg: "downloading" }); await watch("downloading"); await shot(page, "10-job-running", true);
    await wapi("/jobs/" + id, { progress: 30, msg: "transcribing", vars: { pct: 40 } }); await watch("transcribing"); if ((await page.locator(`#job-${id} .tl li.now`).count()) !== 1) throw new Error("timeline has no current step");
    await wapi("/jobs/" + id, { progress: 55, msg: "found_moments", vars: { n: 5 } }); await watch("found_moments");
    await wapi("/jobs/" + id, { progress: 70, msg: "rendering", vars: { i: 2, n: 5 } }); await watch("rendering"); await check(page, "activity-running");
    const pw = await ev((i) => +(document.querySelector(`#job-${i} [role=progressbar]`) || {getAttribute: () => -1}).getAttribute("aria-valuenow"), id); if (pw < 60 || pw > 79) throw new Error("progress bar value " + pw);
    await wapi("/jobs/" + id, { status: "qa", progress: 90 }); await exp(async () => /(בדיקת איכות|Quality)/.test(await txt(`#job-${id}`)), "qa state shown");
    const drafts = (P.lang === "he" ? [["הקלאץ' המטורף", "short"], ["הצ'אט השתגע", "short"], ["ריי-קוויט", "short"], ["ניצחון עם חיים אחד", "short"], ["הלייטס המלא", "long"]] : [["Epic clutch", "short"], ["Chat went wild", "short"], ["Rage quit", "short"], ["One HP win", "short"], ["Full highlights", "long"]]).map(([title, kind], i) => ({ kind, title, qa_ok: i !== 2, qa_notes: i === 2 ? "captions near edge" : "", qa_score: 90 - i, duration_s: 30 + i, local_id: id + "/f" + i + ".mp4", hook: "h" }));
    await wapi("/jobs/" + id, { status: "draft_ready", progress: 100, drafts }); await exp(async () => (await page.locator(".toast").count()) > 0 || /(Ready to review|מוכן לאישור)/.test(await txt(`#job-${id}`)), "draft_ready shown without reload", 12000);
    await shot(page, "11-job-ready");
  }, { needs: "channel" });

  await step("review-buttons-undo-title-keyboard-swipe-bulk", async () => {
    await goTo("review"); await page.waitForSelector(".rv-card"); await check(page, "review"); await shot(page, "12-review", true);
    const count = async () => parseInt((await txt(".rv-top .chip")).split(/\D+/).filter(Boolean).pop() || "0");
    if ((await count()) !== 5) throw new Error("review count " + (await count()));
    if (P.mobile) { if (await page.locator(".rv-dock").count() !== 1) throw new Error("mobile dock missing"); } else if (await page.locator(".rv-inline").count() !== 1) throw new Error("desktop inline actions missing");
    // title edit
    await page.locator('.title-edit .iconbtn').click(); const nt = tx("כותרת חדשה ", "Edited ") + rnd(); await page.locator("#tIn").fill(nt); await page.locator(".title-form button[type=submit]").click(); await exp(async () => (await txt(".title-edit h2")) === nt, "title updated in UI"); const d0 = (await jobsApi()).find((j) => j.id === state.jobs[0]).result.drafts[0]; if (d0.title !== nt) throw new Error("title not saved on server: " + d0.title);
    await page.locator('.title-edit .iconbtn').click(); await page.locator("#tIn").press("Escape"); await exp(async () => (await page.locator("#tIn").count()) === 0, "escape closes title editor");
    // approve + undo
    await page.locator(".btn.yes").click(); await exp(async () => (await count()) === 4, "card advanced after approve"); await page.locator('.toast button').last().click(); await exp(async () => (await count()) === 5, "undo brought the card back"); if ((await txt(".title-edit h2")) !== nt) throw new Error("undo restored a different card");
    await page.locator(".btn.yes").click(); await exp(async () => (await count()) === 4, "approve again");
    // keyboard reject (physical left) on card #2
    await page.keyboard.press("ArrowLeft"); await exp(async () => (await count()) === 3, "ArrowLeft rejected"); await sleep(5600);
    let jd = (await jobsApi()).find((j) => j.id === state.jobs[0]).result.drafts; if (jd[0].decision !== "approved" || jd[1].decision !== "rejected") throw new Error("decisions not persisted: " + JSON.stringify(jd.map((d) => d.decision)));
    // swipe right on card #3
    const box = await page.locator(".rv-card").boundingBox(); await ev(({ x, y }) => { const c = document.querySelector(".rv-card"); const f = (t, dx) => c.dispatchEvent(new PointerEvent(t, { pointerId: 5, bubbles: true, clientX: x + dx, clientY: y, button: 0, pointerType: "touch" })); f("pointerdown", 0); for (let i = 1; i <= 8; i++) f("pointermove", i * 22); f("pointerup", 176); }, { x: box.x + box.width / 2 - 100, y: box.y + 60 });
    await exp(async () => (await count()) === 2, "swipe approved the card", 5000); await sleep(5600); jd = (await jobsApi()).find((j) => j.id === state.jobs[0]).result.drafts; if (jd[2].decision !== "approved") throw new Error("swipe decision not persisted " + jd[2].decision);
    // bulk (2 left, same job)
    const bulk = page.locator("button.bulk"); await bulk.click(); await bulk.click(); await exp(async () => (await page.locator(".rv-card").count()) === 0, "bulk approved everything", 10000); await check(page, "review-empty"); await shot(page, "13-review-empty");
    const job = (await jobsApi()).find((j) => j.id === state.jobs[0]); if (job.status !== "approved" || job.result.drafts.some((d) => !d.decision)) throw new Error("job not closed: " + job.status);
    const j2 = (await sapi(state.token, "POST", `/orgs/${state.orgId}/jobs/${state.jobs[0]}/drafts/0/approve`)); if (j2.s !== 409) throw new Error("approving a closed job should be 409, got " + j2.s);
  }, { needs: "channel", allow: [/409/] });

  await step("credits-page", async () => {
    await goTo("credits"); await check(page, "credits"); await shot(page, "14-credits"); if (!(await txt(".big-num"))) throw new Error("no credit number");
    await page.locator('.card button.btn:has-text("' + tx("קניית קרדיטים", "Buy credits") + '")').click(); await exp(async () => (await page.locator("#buyMsg .notice").count()) === 1, "buy notice");
  }, { needs: "channel", allow: [/501/] });

  // team: invite -> second browser context accepts -> role change -> removal
  let ctx2 = null, page2 = null; const mail = `e2e-${name}-${rnd()}@example.com`; let inviteUrl = "";
  await step("team-invite-link", async () => {
    await goTo("team"); await check(page, "team"); await page.locator("#invEmail").fill("bad@x"); await page.locator("form button[type=submit]").click(); if (!(await txt(".errtxt"))) throw new Error("bad invite email not rejected");
    await page.locator("#invEmail").fill(mail); await page.locator('input[name=role][value=viewer]').check({ force: true }); await page.locator("form button[type=submit]").click(); await page.waitForSelector(".linkbox code"); inviteUrl = await txt(".linkbox code");
    if (!/#invite=inv_[a-f0-9]+$/.test(inviteUrl)) throw new Error("bad invite url " + inviteUrl); await page.locator(".linkbox button").click(); await exp(async () => (await page.locator(".toast").count()) > 0, "copy toast"); await check(page, "team-invite-created"); await shot(page, "15-team-invite", true);
    if (!(await page.locator("section:has-text('" + mail + "')").count())) throw new Error("pending invite not listed");
  }, { needs: "channel" });

  await step("invitee-signs-up-and-joins", async () => {
    ctx2 = await mkctx(); page2 = await ctx2.newPage(); hook(page2, "invitee"); await page2.goto(inviteUrl); await page2.waitForSelector(".authcard"); await sleep(600);
    if (!(await page2.locator(".notice").count())) throw new Error("invite banner missing on the landing");
    await page2.locator("details.emailbox summary").click(); const prefilled = await page2.locator("#email").inputValue(); if (prefilled !== mail) throw new Error("invite email not prefilled: " + prefilled);
    await page2.locator("#pw").fill("password-" + rnd()); state.pw2 = await page2.locator("#pw").inputValue(); await page2.locator("form button[type=submit]").click(); await page2.waitForSelector(".authcard .btn.lg.block"); await sleep(300);
    await page2.locator(".authcard .btn.lg.block").first().click(); await page2.waitForSelector(".shell"); await sleep(600);
    const orgName = await page2.evaluate(() => S.org.name), role = await page2.evaluate(() => S.org.role); const ownerOrg = await page.evaluate(() => S.org.name);
    if (orgName !== ownerOrg) throw new Error(`after joining, the active workspace is "${orgName}" instead of the invited "${ownerOrg}"`); if (role !== "viewer") throw new Error("role " + role);
    await page2.screenshot({ path: path.join(OUT, `${name}-16-viewer-home.png`) }); const l = await page2.evaluate(LAYOUT); for (const x of l) R.layout.push({ at: "viewer-home", ...x });
    if (await page2.locator(".chips .chip").count()) throw new Error("viewer sees request chips"); if (await page2.locator(".check-item").count()) bug("a viewer sees the owner's onboarding checklist");
  }, { needs: "channel", allow: [/401|404/] });

  await step("viewer-permissions", async () => {
    await page2.goto(BASE + "/studio#/chat"); await page2.reload(); await page2.waitForSelector("#chatIn"); if (!(await page2.locator("#chatIn").isDisabled())) throw new Error("viewer can type in the chat");
    await page2.goto(BASE + "/studio#/team"); await page2.reload(); await page2.waitForSelector(".notice"); if (await page2.locator("#invEmail").count()) throw new Error("viewer sees the invite form");
    const r = await sapi(await page2.evaluate(() => localStorage.getItem("studio_token")), "POST", `/orgs/${state.orgId}/jobs`, { channel_id: state.chId, source: { type: "auto" } }); if (r.s !== 403) throw new Error("viewer job create gave " + r.s);
  }, { needs: "channel", allow: [/403/] });

  await step("team-role-change-and-remove", async () => {
    await page.reload(); await page.waitForSelector(".shell"); await goTo("team").catch(() => {}); await page.waitForSelector("select.input.sel"); await page.locator("select.input.sel").selectOption("editor"); await exp(async () => (await page.locator(".toast").count()) > 0, "role toast");
    await page2.goto(BASE + "/studio#/home"); await page2.reload(); await page2.waitForSelector(".shell"); await sleep(500); if ((await page2.evaluate(() => S.org.role)) !== "editor") throw new Error("invitee did not become editor"); if (!(await page2.locator(".chips .chip").count())) throw new Error("editor sees no chips");
    await page.locator('.li button.iconbtn').first().click(); await exp(async () => (await page.locator("select.input.sel").count()) === 0, "member removed from the list");   // confirm() is auto-accepted
    await page2.reload(); await page2.waitForSelector(".shell, .auth, .boot"); await sleep(800); const stillIn = await page2.evaluate(() => S.orgs && S.orgs.some((o) => o.id === window.__x)); void stillIn;
    const r = await sapi(await page2.evaluate(() => localStorage.getItem("studio_token")), "GET", `/orgs/${state.orgId}/jobs`); if (r.s !== 404) throw new Error("removed member still reads jobs: " + r.s);
  }, { needs: "channel", allow: [/404/] });

  await step("settings-language-theme", async () => {
    await goTo("settings"); await check(page, "settings"); await shot(page, "17-settings", true); if ((await page.locator("body").innerText()).includes("guest.invalid")) bug("guest placeholder address shown to the user");
    const other = P.lang === "he" ? "en" : "he"; await page.locator(`.seg button[aria-label="${other === "he" ? "עברית" : "English"}"]`).first().click(); await sleep(300);
    if ((await ev(() => document.documentElement.lang)) !== other) throw new Error("language not switched"); if ((await hash()) !== "#/settings") throw new Error("language switch changed the route: " + (await hash())); await check(page, "settings-switched");
    await page.locator(`.seg button[aria-label="${P.lang === "he" ? "עברית" : "English"}"]`).first().click(); await sleep(300);
    for (const m of [tx("בהיר", "Light"), tx("כהה", "Dark"), tx("אוטומטי", "Auto")]) { await page.locator(`.seg button:has-text("${m}")`).click(); await sleep(150); }
    await page.reload(); await page.waitForSelector(".shell"); if ((await ev(() => document.documentElement.lang)) !== P.lang) throw new Error("language did not persist across reload");
  }, { needs: "channel" });

  await step("workspace-create-switch", async () => {
    await goTo("settings"); const nm = tx("לקוח ", "Client ") + rnd(); await page.locator("#orgName").fill(nm); await page.locator("form:has(#orgName) button[type=submit]").click(); await page.waitForSelector(".shell"); await sleep(600);
    if ((await ev(() => S.org.name)) !== nm) throw new Error("new workspace not active"); if (!(await hash()).startsWith("#/setup")) R.notes.push("new empty workspace opens at " + (await hash()));
    await goTo("settings").catch(async () => { await page.goto(BASE + "/studio#/settings"); }); await page.waitForSelector("select.input.sel"); await check(page, "settings-two-orgs");
    const first = await ev((id) => id, state.orgId); await page.locator("select.input.sel").selectOption(first); await page.waitForSelector(".shell"); await sleep(700); if ((await ev(() => S.org.id)) !== first) throw new Error("switch back failed"); if ((await ev(() => S.channels.length)) < 1) throw new Error("channels not reloaded after switching");
  }, { needs: "channel" });

  await step("channel-remove", async () => {
    await goTo("settings"); const n0 = await page.locator(".li.wrapli").count(); if (!n0) throw new Error("no channel row"); await page.locator('.li.wrapli button.iconbtn').click(); await exp(async () => (await page.locator(".li.wrapli").count()) === 0, "channel row removed"); await sleep(500);
    await page.goto(BASE + "/studio#/home"); await page.reload(); await page.waitForSelector(".shell"); if (!(await hash()).startsWith("#/setup")) throw new Error("after removing the only channel the owner should be sent to setup, at " + (await hash()));
  }, { needs: "channel" });

  await step("logout", async () => {
    await goTo(P.mobile ? "settings" : "settings"); await page.locator('button:has-text("' + tx("יציאה", "Sign out") + '")').first().click(); await page.waitForSelector(".authcard"); if (await ev(() => localStorage.getItem("studio_token"))) throw new Error("token still stored"); await check(page, "after-logout");
    const r = await sapi(state.token, "GET", "/me"); if (r.s !== 401) throw new Error("session still valid server side: " + r.s);
  }, { allow: [/401/] });

  await step("email-signup-login-wrong-password", async () => {
    const mail2 = `login-${name}-${rnd()}@example.com`, pw = "correct-horse-" + rnd();
    await page.locator("details.emailbox summary").click(); await page.locator("#email").fill(mail2); await page.locator("#pw").fill(pw); await page.locator("form button[type=submit]").click(); await page.waitForSelector(".shell"); await sleep(400);
    await goTo("settings"); await page.locator('button:has-text("' + tx("יציאה", "Sign out") + '")').first().click(); await page.waitForSelector(".authcard");
    await page.locator("details.emailbox summary").click(); await page.locator("#email").fill(mail2); await page.locator("#pw").fill(pw + "x"); await page.locator("form button[type=submit]").click(); await exp(async () => (await txt(".errtxt")).length > 3, "wrong password message"); R.notes.push("wrong password message: " + (await txt(".errtxt")));
    await page.locator("#pw").fill(pw); await page.locator("form button[type=submit]").click(); await page.waitForSelector(".shell"); state.token = await ev(() => localStorage.getItem("studio_token"));
  }, { allow: [/401|409/] });

  await step("token-expiry", async () => {
    await page.route("**/studio/api/**", (r) => { if (/\/(login|signup|guest)/.test(r.request().url())) return r.continue(); r.fulfill({ status: 401, contentType: "application/json", body: '{"error":"unauthorized"}' }); });
    await ev(() => document.dispatchEvent(new Event("visibilitychange"))); await page.waitForSelector(".authcard", { timeout: 10000 }); await shot(page, "18-session-expired"); const msg = await page.locator(".toast").count(); if (!msg) throw new Error("session expiry was silent: the user lands on the landing page with no explanation");
  }, { allow: [/401/] });
  await page.unroute("**/studio/api/**").catch(() => {});

  await step("deep-links-and-back", async () => {
    await page.goto(BASE + "/studio"); await page.waitForSelector(".authcard"); await page.locator(".authcard button.btn.lg").first().click(); await page.waitForSelector(".shell"); await sleep(400); state.token = await ev(() => localStorage.getItem("studio_token")); state.orgId = await ev(() => S.org.id);
    for (const h of ["#/team", "#/credits", "#/settings", "#/chat", "#/jobs", "#/review", "#/bogus", "#/jobs/j_doesnotexist", "#/more", "#/"]) { await page.goto(BASE + "/studio" + h); await page.reload(); await page.waitForSelector(".shell", { timeout: 8000 }).catch(() => { throw new Error("deep link " + h + " did not render the app"); }); await sleep(250); const t = await ev(() => document.querySelector("#view") && document.querySelector("#view").innerText.length); if (!t) throw new Error("deep link " + h + " renders an empty view"); await check(page, "deeplink" + h); }
    await page.goto(BASE + "/studio#/settings"); await page.reload(); await page.waitForSelector(".shell"); await ev(() => { location.hash = "#/credits"; }); await exp(async () => (await hash()) === "#/credits", "credits"); await ev(() => { location.hash = "#/team"; }); await exp(async () => (await hash()) === "#/team", "team"); await page.goBack(); await exp(async () => (await hash()) === "#/credits", "back returns to credits"); await page.goBack(); await exp(async () => (await hash()) === "#/settings", "back returns to settings"); await page.goForward(); await exp(async () => (await hash()) === "#/credits", "forward");
    const r404 = await fetch(BASE + "/studio/nope"); if (r404.status !== 404) throw new Error("/studio/nope gave " + r404.status); const h = await fetch(BASE + "/studio/api/health"); if (!h.ok) throw new Error("health " + h.status);
    await page.goto(BASE + "/studio#invite=inv_" + "0".repeat(48)); await page.reload(); await sleep(1200); R.notes.push("bad invite link while signed in: " + (await ev(() => document.body.innerText.slice(0, 80).replace(/\s+/g, " "))));
  }, { allow: [/404/] });

  await step("offline-and-slow-network", async () => {
    await page.goto(BASE + "/studio#/home"); await page.reload(); await page.waitForSelector(".shell"); await goTo("chat"); await ctx.setOffline(true); const ta = page.locator("#chatIn"); await ta.fill("hello"); await ta.press("Enter");
    await exp(async () => (await page.locator(".msg.bot").count()) >= 2 && (await page.locator(".typing").count()) === 0, "offline reply"); const t = await txt(".msg.bot:last-child .bub"); if (!/(חיבור|connection)/i.test(t)) throw new Error("offline error not friendly: " + t); await shot(page, "19-offline-chat");
    await page.reload().catch(() => {}); await ctx.setOffline(false); await sleep(300);
    await page.route("**/studio/api/me", async (r) => { await sleep(3500); r.continue(); }); await page.goto(BASE + "/studio#/home"); await page.reload(); await page.waitForSelector(".boot .spin", { timeout: 4000 }); await shot(page, "20-slow-boot"); await page.waitForSelector(".shell", { timeout: 15000 }); await page.unroute("**/studio/api/me");
    await page.route("**/studio/api/me", (r) => r.abort("failed")); await page.reload(); await exp(async () => (await page.locator(".boot button").count()) === 1, "retry button after failed boot", 8000); await shot(page, "21-boot-failed"); await check(page, "boot-failed");
    await page.unroute("**/studio/api/me"); await page.locator(".boot button").click(); await page.waitForSelector(".shell", { timeout: 10000 });
  }, { allow: [/Failed to load resource|net::ERR|failed/i] });

  if (state.verified) {   // clean the E2E channel's jobs out of the queue (never leave queued jobs behind: they would clog the claim list)
    for (const id of state.jobs) await wapi("/jobs/" + id, { status: "failed", error: "e2e cleanup" }).catch(() => {});
  }
  await ctx.close(); if (ctx2) await ctx2.close();
}

const browser = await chromium.launch({ executablePath: process.env.CHROME || (fs.existsSync("/usr/bin/google-chrome") && LOCAL ? "/usr/bin/google-chrome" : undefined), args: ["--no-sandbox"] });
for (const p of PROFILES) { console.log("== profile", p); try { await runProfile(browser, p, ALL[p]); } catch (e) { report.profiles[p] = Object.assign(report.profiles[p] || {}, { fatal: String(e.stack || e) }); } }
await browser.close();
// ---- summary
let failed = 0, errs = 0; const sum = {};
for (const [n, R] of Object.entries(report.profiles)) { const f = (R.steps || []).filter((s) => !s.ok).length; const e = (R.issues || []).filter((i) => i.type !== "console-warn").length; failed += f + (R.fatal ? 1 : 0) + (R.bugs || []).length; errs += e; sum[n] = { steps: (R.steps || []).length, failed: f, bugs: (R.bugs || []).length, issues: (R.issues || []).length, layout: (R.layout || []).length, texts: (R.texts || []).length, skipped: (R.skipped || []).length, fatal: !!R.fatal }; }
for (const R of Object.values(report.profiles)) { const bad = new Set([...(R.steps || []).filter((x) => !x.ok).map((x) => x.name), ...(R.bugs || []).map((x) => x.step)]); R.net = (R.net || []).filter((e) => bad.has(e.step)).slice(-120); }   // network trace only for the steps that failed
report.summary = { failedSteps: failed, errorIssues: errs, perProfile: sum }; report.finished = new Date().toISOString();
fs.writeFileSync(path.join(OUT, "report.json"), JSON.stringify(report, null, 1));
for (const [n, R] of Object.entries(report.profiles)) { console.log(`\n--- ${n}`); for (const s of R.steps || []) console.log((s.ok ? "ok   " : "FAIL ") + s.name + (s.ok ? "" : "  -> " + s.error)); for (const s of R.skipped || []) console.log("skip " + s); for (const b of R.bugs || []) console.log("BUG  " + b.step + " -> " + b.msg); if (R.fatal) console.log("FATAL", R.fatal.slice(0, 300)); }
console.log("\n" + JSON.stringify(report.summary));
process.exit(failed || errs ? 1 : 0);
