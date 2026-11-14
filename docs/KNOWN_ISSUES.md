# Known issues / next improvements (14 Nov 2026)
1. SCREEN-SHARE LAYOUT (EXPERIMENTAL, scripts/smart_reframe.py, OFF by default): tested 14 Nov: on the full 271 s clip the webcam was found correctly, on a 20 s slice detection was unstable and the composed frame was wrong. Needs per-scene stabilisation before enabling.
   Original note: when the streamer shares the whole desktop (Kick page, tier list, tiny webcam) the content is small in the 1920x1080 frame.
   Needs a smart reframe (detect content window + facecam, crop with purpose; NO arbitrary zooms). Plan: YuNet for facecam + frame-difference for the active window, stable crop with hold-then-glide.
2. Topic judge is a scheduled Claude session (docs/TOPIC_SESSION_PROMPT.md). Heuristic candidates (scripts/topic_scan.py) remain as fallback when the usage limit is hit.
3. Kick in-progress VOD playlist growth during a live stream is UNVERIFIED (test on the next real live).
4. YouTube refresh token must be copied into GitHub secrets (YT_REFRESH_TOKEN, YT_CLIENT_ID, YT_CLIENT_SECRET) for upload from Actions; CF_API_TOKEN for thumbnails.
5. Identity of generated thumbnails: pick best of 3 seeds by eye (automatic similarity check not built).
