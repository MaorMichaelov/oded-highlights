// AGENT <-> STUDIO glue (design: docs/AGENT_DESIGN.md section 9). Adapts the generic agent (app/agent.js) to the customer area (app/studio.js) WITHOUT importing studio.js:
// studio.js hands in its own helpers (`h`), so this file has no circular import and can be tested with fakes. Wired by the documented patch docs/agent_hooks/studio.patch (not applied by default).
//
//   h = { kget, kput, klist, K, createJob, estimateCredits, can, now }   (exactly the names studio.js already has)
import { handleMessage, recordSignal, defaultProviders, createLLM, pipelineView, loadProfile, safeCid, scheduledTick, triggerStreamEnded, KEY } from "./agent.js";

const txt = (v, n) => String(v == null ? "" : v).replace(/\s+/g, " ").trim().slice(0, n);
export const agentCid = (orgId, channelId) => safeCid(`${orgId}-${channelId || "main"}`);   // one profile per channel: the taste belongs to the channel, not to the login

// Ops the agent tools call. Everything is scoped to ONE org (closure), so a tool can never see another customer's jobs.
export function studioOps(env, org, ch, h) {
  const jobsOf = async () => { const keys = await h.klist(env, h.K.jobsOfOrg(org.id), 500); const jobs = (await Promise.all(keys.map((k) => h.kget(env, h.K.job(k.split(":")[3]))))).filter((j) => j && j.org === org.id && j.channel === ch.id); return jobs.sort((a, b) => (a.created < b.created ? 1 : -1)); };
  const shape = (job, d, i) => ({ id: `${job.id}:${i}`, job: job.id, title: d.title, kind: d.content_kind || d.kind, format: d.kind, topic: d.topic || "", decision: d.decision || null, qa_ok: !!d.qa_ok, qa_score: typeof d.qa_score === "number" ? d.qa_score : null, visibility: d.private === false ? "public" : "private" });
  return {
    async listDrafts(cid, { limit = 10 } = {}) { const out = []; for (const j of await jobsOf()) { (j.result.drafts || []).forEach((d, i) => out.push(shape(j, d, i))); if (out.length >= limit) break; } return out.slice(0, limit); },
    async getDraft(cid, id) {
      const m = String(id).match(/^(j_[a-f0-9]+):(\d{1,2})$/); if (!m) return null; const job = await h.kget(env, h.K.job(m[1])); if (!job || job.org !== org.id) return null; const d = (job.result.drafts || [])[+m[2]]; if (!d) return null;
      return { ...shape(job, d, +m[2]), reasons: d.why || (job.hints && job.hints.text) || null, transcript_excerpt: d.excerpt || "", qa_notes: d.qa_notes || "" };
    },
    async startJob(cid, spec) {
      const range = spec.from_min != null && spec.to_min != null ? [spec.from_min, spec.to_min] : null; const source = { type: "auto", when: spec.when, ...(range ? { range_min: range } : {}), duration_min: range ? Math.ceil(range[1] - range[0]) : null };
      const credits = h.estimateCredits(source); const fresh = await h.kget(env, h.K.org(org.id)); if (!fresh || fresh.credits < credits) return { error: "insufficient_credits", need: credits, have: fresh ? fresh.credits : 0 };
      const job = await h.createJob(env, org, { channel_id: ch.id, kind: "edit", source, style_id: ch.style_id, outputs: { shorts: spec.shorts, long: spec.long }, credits, hints: { mood: spec.mood || null, text: spec.note || "", requested_by: spec.requested_by || "agent", profile: spec.profile } });
      return { job_id: job.id, credits };
    },
    async setPaused(cid, paused) { if (paused) await h.kput(env, `studio:paused:${org.id}`, { t: new Date().toISOString() }); else await env.KV.delete(`studio:paused:${org.id}`); return { paused }; },
    // publishDraft: deliberately absent until the YouTube OAuth flow exists (studio.js TODO(youtube)); the publish_draft tool then answers "not_supported_here".
  };
}
const hasAI = (env) => !!(env.AI || env.GROQ_API_KEY || env.GEMINI_API_KEY);

// The LLM replacement for studio.js `assistant()`. Returns null when it cannot serve (no model configured / no verified channel) so the caller falls back to the rule-based assistant.
export async function agentAssistant({ env, org, me, role, b, h, fetchImpl, llm }) {
  if (!hasAI(env) && !llm) return null; const text = txt(b.message, 1000); if (!text) return null;
  const chans = (await Promise.all((await h.klist(env, h.K.chansOfOrg(org.id))).map((k) => h.kget(env, k)))).filter((c) => c && c.status === "verified"); const ch = chans.find((c) => c.id === b.channel_id) || chans[0]; if (!ch) return null;
  const cid = agentCid(org.id, ch.id); const byo = (b.byo && typeof b.byo === "object") ? { groq: txt(b.byo.groq, 200) || undefined, gemini: txt(b.byo.gemini, 200) || undefined } : {};   // the customer's OWN free key (header/body from the UI), never stored here
  llm = llm || createLLM({ providers: defaultProviders(env, { byo, fetchImpl }), kv: env.KV, now: () => Date.now() }); if (!llm.providers || !llm.providers.length) return null;
  const deps = { kv: env.KV, llm, ops: studioOps(env, org, ch, h), now: () => Date.now() }; await h.kput(env, KEY.who(cid), { org: org.id, channel: ch.id });
  const hist = ((await h.kget(env, h.K.chat(org.id))) || []).slice(-12).map((x) => ({ role: x.r === "bot" ? "assistant" : "user", content: x.text }));
  const r = await handleMessage(deps, { cid, messages: [...hist, { role: "user", content: text }], capLevel: h.can(role, "job.create") ? undefined : 0 });   // a viewer gets a read-only assistant
  const chat = (await h.kget(env, h.K.chat(org.id))) || []; const t = new Date().toISOString(); chat.push({ r: "user", t, text }, { r: "bot", t, text: r.reply }); await h.kput(env, h.K.chat(org.id), chat.slice(-40));
  return { reply: r.reply, actions: r.actions.filter((a) => a.job_id).map((a) => ({ type: "job_created", job_id: a.job_id })), pending: r.pending.map((p) => ({ id: p.id, summary: p.summary })), parsed: { agent: true, steps: r.steps } };
}

// Called by the approve/reject endpoint for each decided draft. No LLM, never throws into the request: learning is best effort.
export async function onDraftDecision({ env, org, job, indexes, verdict, reason, h }) {
  try {
    const cid = agentCid(org.id, job.channel);
    for (const i of indexes) { const d = (job.result.drafts || [])[i]; if (!d) continue; await recordSignal({ kv: env.KV, now: () => Date.now() }, cid, { action: verdict === "approved" ? "approve" : "reject", reason: txt(reason, 200), draft: { id: `${job.id}:${i}`, title: d.title, kind: d.content_kind || d.kind, topic: d.topic, duration_s: d.duration_s } }); }
    return true;
  } catch { return false; }
}
// The compact profile a new job carries (job.hints.profile) so the render worker can run pick.py with CUSTOMER_PROFILE=<file>. Active rules only, no autonomy settings.
export async function profileHint(env, orgId, channelId, h) { try { return pipelineView(await loadProfile({ kv: env.KV, now: () => Date.now() }, agentCid(orgId, channelId))); } catch { return null; } }
// Worker cron (every 5 min): schedules + weekly distillation for every customer that ever talked to the agent. `makeCtx(org, channel)` supplies {ch, h}.
export async function agentCron(env, { h, fetchImpl, llm }) {
  const keys = (await env.KV.list({ prefix: KEY.whoPrefix, limit: 200 })).keys; const out = [];
  for (const k of keys) {
    const cid = k.name.slice(KEY.whoPrefix.length); const who = await env.KV.get(k.name, "json"); if (!who) continue; const org = await h.kget(env, h.K.org(who.org)); const ch = org && await h.kget(env, h.K.chan(who.org, who.channel)); if (!ch) continue;
    const l = llm || createLLM({ providers: defaultProviders(env, { fetchImpl }), kv: env.KV, now: () => Date.now() });
    out.push(...(await scheduledTick({ kv: env.KV, llm: l, now: () => Date.now() }, [cid], { ops: studioOps(env, org, ch, h) })));
  }
  return out;
}
export { triggerStreamEnded, KEY };
