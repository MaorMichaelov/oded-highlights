# What to cut (topic judge: Claude session or the LLM stage)
Owner (14 Nov): "you decide which clips are worth uploading: dramas, GTA moments, a talk about something, a launch". Every RELEVANT topic gets a clip, also when Ronen or friends are on Oded's stream. Long videos only (6-25 min). One complete topic = setup + build-up + payoff, ending at a natural conclusion.

## A. Always cut (highest priority)
1. FIRST TIME moments: first reaction to GTA 6, first car / chase / mission / heist / death / wanted level, first time with a new game, new gear, new guest.
2. DRAMA: arguments, fights with chat or friends, a guest that changes the mood, a rumor / "who said what", a call with a named person (Eitan Nissim, Biggie, Amit Shiber...), apologies, bans, lawsuits.
3. BIG REACTIONS: shock, rage, huge laugh, silence-then-explosion, the chat spikes (state/chat, chat_spikes>=3 or z>=4).
4. MONEY / LUCK: big win or loss, gambling, packs openings, donations that change something.
5. LAUNCHES / EVENTS: subathon start, goals (hours, subs, viewers record), announcements, giveaways, a new rule or bet, a visitor arrives.
6. STORY GAMEPLAY: a GTA mission or chaos sequence with a clear arc (plan -> things go wrong -> result), a chase that ends, a funny fail chain.
7. TALKS: Oded tells a story or rants about ONE subject for 6+ minutes (food, women, army, Israel-life stuff, creators, news) with strong opinions.
8. REACTION VIDEOS / clips he watches and comments.

## B. Cut only if strong (score >= 22 or chat reaction)
challenge or bet without payoff yet, long shopping / customization, long driving with real conversation, interaction with chat Q&A that has a joke running.

## C. Never cut
dead air / AFK / "brb", setup and tech problems, repeating donation reading, the same moment twice, less than 6 min or no arc, any moment already uploaded in the last 7 days (scripts/yt_research.py own).
Safety (YouTube policy): no sexual content, hate, graphic violence, private personal info (phone numbers, addresses, full names of private people), minors in vulnerable situations, medical emergencies, loud copyrighted music; if a strong topic has a risky part, cut around it or skip.

## Subathon GTA 6 (19 Nov, 48 h, 24/7)
Cut continuously, do not wait for the end of the stream: after a topic has been silent/closed for ~5 min it becomes a draft. Typical GTA clips: first reaction; first chase; first big crash; heist / robbery; a mission fail rage; a funny NPC moment; Oded vs a friend in the game; "he dies 10 times in a row". Night hours (2-8) usually mean calm talk: cut only real topics.

## Title / brief
Hebrew title 40-55 chars ending ! or ?!, names + the hook ("עודד ורונן שודדים ... ומרוויחים המון כסף!"). Brief in spec.json: about / who / peak (the strongest 10 seconds), so the thumbnail bot can match it.
