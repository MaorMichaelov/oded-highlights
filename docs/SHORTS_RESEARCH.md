# Shorts research (16 Nov 2026) - agent reports, saved for the implementation

## A. Where to start/stop a clip (agent report 1)
Evidence is thin: no source gives numeric thresholds; the parameters below are engineering defaults to be tuned on 20-30 clips rated by the owner.
Signals: chat rate (standard; only approximate position, chat lags the action ~3-4 s), emote spikes, audio energy, laughter/scream classifier (YAMNet/AudioSet; screams have many false alarms), transcript as semantic filter. Raids/giveaways/sub trains/bots create false spikes; loud audio can be music/cutscenes/alerts.
Algorithm:
1. 1 s bins: chat msgs/s, emotes/s, RMS audio energy, YAMNet laughter/scream prob, words/s.
2. Robust z-score (median/MAD) over a rolling 10 min window, 5 s smoothing, shift chat 4 s earlier.
3. S = 0.35 z_chat + 0.15 z_emote + 0.30 z_audio + 0.20 z_laugh_or_scream (clip z at 6); drop bins with raid/sub/bot rate > 3x normal.
4. Peaks: local maxima S > 2.5, >= 45 s apart, top N per hour.
5. LLM scores the transcript window [peak-30 s, peak+15 s] 1-10 and returns setup sentence + payoff sentence; F = 0.6 S_norm + 0.4 llm/10.
6. START: setup sentence start (else peak-12 s), snap to the preceding word start minus 0.2 s, lead-in 8-25 s (Shorts), up to 45 s for long clips.
7. END: peak+3 s moved to the sentence end + 0.4 s; extend while audio energy > 60% of the peak, up to 6 s. Never end on trailing silence.
8. Length: Shorts 20-58 s; longer clips 60-180 s.
9. Reject: z_audio < 1.5 and z_chat < 1.5; LLM score < 6; > 25% silence or < 0.5 words/s outside the peak; mid-word start/end; overlaps a stronger clip; within 2 min of a raid/giveaway/sub event.
First-time-reaction structure: 0-3 s hook, 3-20 s buildup (10-25 s for jump scares), peak, 3-5 s aftermath, cut.
Word timing: Whisper is coarse; WhisperX / stable-ts / whisper-timestamped are better.
