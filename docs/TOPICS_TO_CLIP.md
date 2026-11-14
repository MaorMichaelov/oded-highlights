# What to cut (topic judge: Claude session or the LLM stage)
Source: the owner's / Grok Bot's topic guide (14 Nov 2026), merged with our rules. Every RELEVANT topic of the stream gets a clip (not only 2-3), also when Ronen or friends are on Oded's stream (that is still Oded's content). Long videos only (>= 6 min, no shorts). ONE topic per video.

## What worked so far (cut more of this)
- Oded tells a funny personal story with a beginning and an end (the crazy night out with Ben and Ohad).
- Guest moments (Sensei measures Oded's shirt live, Eitan Nissim as a guest, Inda and the shawarma).
- Games with friends (Rob Run, ...), ranking / tier-list with strong opinions (animals).
- Group challenge with energy: Oded, Sensei and Biggie open 36 Pokemon packs and drink (the strongest one).
- A crazy real moment: Sensei falls asleep drunk, Oded and Biggie try to wake him.
- A live phone call with a celebrity (Oded looks for Biggie's number and calls Amit Shiber).

## Never cut (rejected, with reasons)
- Starting Soon / waiting / BRB screens, long silent minutes (e.g. waiting for the GTA 6 preload).
- Reactions to someone else's video where Oded barely talks (the video plays, he is silent): not a clip.
- MIXED topics (a toast + a map + messages + a reaction in one clip): rejected. One topic per video.
- Preparations before an event (connecting Discord, waiting for a guest).
- Duplicates of a topic already uploaded (check scripts/yt_research.py own).
- Drunk talk without a clear topic, and always cut out the hard lines (Ethiopians, Holocaust, Hitler, suicide, death). If a strong topic contains such lines, cut around them.
- Gambling on the main screen.
- The Rob Run cheater angle (Oded and Ronen get wiped by a cheater) was rejected by the owner: do NOT repeat that angle.
- Dead air / AFK, tech problems, repeated donation reading, the same moment twice, anything < 6 min or without an arc.
- YouTube policy risks: sexual content, hate, graphic violence, private personal info (phones, addresses, private people's full names), minors in vulnerable situations, medical emergencies, loud copyrighted music.

## REACTIONS TO SOMEONE ELSE'S VIDEO (owner decision 14 Nov: DO cut them, whoever made the video, e.g. Franzi)
When Oded reacts to a video / clip of anyone, it is a clip topic. Conditions: Oded talks and reacts most of the time (commentary dominates; if the video plays in silence for minutes, cut those minutes out), one video per clip, 6-25 min. Title names the creator and what happens ("עודד מגיב לפרנזי ...!"). The description credits the original creator and video (name + link if visible). Copyright is the owner's risk decision; reduce it by keeping the other video's own audio short and the commentary long.

## How to recognise a good topic
1. A story with beginning, middle and punchline, not just a moment.
2. Oded talks and reacts strongly (laughter, shouting, shock).
3. A guest or friends (Sensei, Biggie, Ronen, Amit Shiber, phone calls).
4. Describable in ONE simple title with names ("עודד ו-X עושים Y!"), Hebrew 40-55 chars ending ! or ?!.
5. Length >= 6 min (6-25 min), complete: setup -> build-up -> payoff, 3 s pre-roll, ends at the natural conclusion.
6. Chat reaction supports it (state/chat spikes: chat_spikes>=3 or z>=4).
7. Take every relevant topic, not just 2-3.

## GTA 6 subathon (release 18 Nov at midnight, subathon ~19 Nov, can last several days, 24/7)
Cut continuously during the live, do not wait for the end: when a topic has been closed ~5 min it becomes a draft. Topics to look for:
- Oded's FIRST entry into GTA 6: the excitement, the opening, the first impression. THE most important clip: it must come out first and fast.
- First reactions to the graphics, the map (Vice City) and the characters Lucia and Jason.
- The first mission, and funny / hard missions where Oded gets stuck.
- Chaos: police chases, wanted levels, crashes, stupid deaths, funny bugs.
- Oded compares to GTA 5 or ranks things in the game (cars, weapons, characters).
- "Wow" moments: cutscenes, a big heist, buying a car or a house.
- Guests and phone calls during the subathon.
- Subathon milestones: timer extensions, sub goals, Oded tired or asleep after hours, reactions to BIG donations (only with a real moment, not dry reading).
- "Oded despairs" and "Oded goes crazy": real outbursts of rage or laughter.
Do NOT take: silent gameplay without talking, loading screens, downloads and updates, waiting-for-release screens, mixed topics. Night hours (2-8): usually calm, cut only real topics.

## Draft marking (brief)
In spec.json: "brief": {"about": what the clip is about, "who": who appears, "peak": the strongest moment WITH a timestamp (mm:ss in the clip)} so the other bot makes a matching thumbnail. The draft description starts with "[טיוטה - למחוק לפני פרסום] על מה: ... | מופיעים: ... | הרגע החזק: ...".
