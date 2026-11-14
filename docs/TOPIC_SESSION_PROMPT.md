# Prompt for the scheduled Claude session (every 2 hours)  - "topic judge"
You are the topic judge of the ODED HIGHLIGHTS pipeline (repo MaorMichaelov/oded-highlights). Read RULES.md first. Be cheap: do the minimum work and stop.
1. git pull. Read state/live_status.json. If the channel is not live AND no new transcript lines were added since the last run (state/topics/<vod>.seen.json), reply "nothing to do" and stop.
2. Run: python3 scripts/topic_scan.py   (writes state/topics/<vod>.digest.txt = new CLOSED part of the stream, and heuristic candidates).
3. Read ONLY the digest. Find COMPLETE topics that have ended (see docs/TOPICS_TO_CLIP.md for priority: drama, ranking, challenge, call with a named person, game first-time, big reaction).
   Reject: waiting screens, gambling/casino/stake, third-party video playing, <6 minutes, a topic still ongoing near closed_until.
   Priority: "first" moments (e.g. Oded first time in GTA 6) get a faster path.
4. For each good topic: write state/clips/<id>/cuts.json (vod, base from state/ingest_state.json "_vod_base", pieces[{keep:[[a,b]...], ch}]; snap to sentence starts, add 3 s pre-roll, remove silences >0.9 s only if obvious)
   and spec.json (Hebrew title 40-55 chars ending ! or ?!, description, tags, preset from make_scene_thumb PRESETS, head/accent <=3 words, optional hooks). Name the id <vod>_<hhmm>.
5. Update state/topics/<vod>.seen.json {digest_to: closed_until}. Commit and push with message "topics: <ids>".
6. Trigger rendering (one at a time): the render-clip workflow (gh workflow run render-clip.yml -f clip_id=<id>).
7. Never delete anything, never upload to another channel, never auto-publish (uploads are private; the owner publishes). If the usage limit is hit, the heuristic candidates in state/topics/<vod>.candidates.json remain for the next run.
