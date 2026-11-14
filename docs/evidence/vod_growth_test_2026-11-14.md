# In-progress Kick VOD behaviour (tested 14 Nov 2026 on a live channel, public playlist only)
- videos list entry for a live stream: is_live=true, duration=0, `source` master.m3u8 present.
- 480p30 playlist: 833 -> 837 segments in 75 s (EVENT type) -> it GROWS during the live.
- `#EXT-X-ENDLIST` is present even while the stream is live -> NEVER use ENDLIST to decide that a stream ended.
- VOD end vs wall clock: lag = 8 s. Newest segments (last and last-3) download with HTTP 200 (~2.4 MB each at 480p).
=> clipping during a live stream is possible; no need to wait for the end of the live.
