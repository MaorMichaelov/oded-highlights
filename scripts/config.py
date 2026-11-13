import os
#!/usr/bin/env python3
"""Shared paths and defaults for the Kick clipper pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STREAMS = ROOT / "streams"
SAMPLES = ROOT / "samples"
LOGS = ROOT / "logs"
STATE = ROOT / "state"
VENV_PY = ROOT / "venv" / "bin" / "python"
CHECK_LIVE = ROOT / "check_live.sh"
RECORD_SH = ROOT / "record.sh"

CHANNEL = "odedsvr"
CHANNEL_ID = 7685090
CHATROOM_ID = 7592221
QUALITY = "720p60"
SEGMENT_TIME = 300
POLL_MIN = 60
POLL_MAX = 120
GRACE_SEC = 180  # brief drops resume into the same folder
IDLE_RETRIES = 8

KICK_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
KICK_ORIGIN = "https://kick.com"

HEBREW_FONT = (
    "/usr/share/fonts/truetype/sand-box/google/"
    "IBM Plex Sans Hebrew/IBMPlexSansHebrew-Bold.ttf"
)
HEBREW_FONT_NAME = "IBM Plex Sans Hebrew"

# Measured from odedsvr latest VOD frame at t=1800s (1920x1080 desktop capture,
# facecam window in the upper right, Minecraft in the main browser).
# Fractions of frame width/height so they work at 720p and 1080p.
DEFAULT_LAYOUT = {
    "facecam": {"x": 0.7438, "y": 0.0926, "w": 0.2562, "h": 0.2269},
    "content": {"x": 0.1042, "y": 0.1019, "w": 0.6042, "h": 0.7315},
    "source": "default_measured_vod_1080_t1800",
}

# Hebrew / mixed keywords used as clip signals. Matching is case-insensitive
# and ignores surrounding punctuation.
KEYWORD_GROUPS = {
    "reaction": [
        "וואו", "ואו", "wow", "מה", "מה זה", "איזה", "מטורף", "נדיר",
        "לא נורמלי", "בחייאת", "בחיאת", "וואלה", "יאללה", "אין מצב",
        "לא יכול", "חחח", "ההה", "אחלה", "גאון", "מדהים", "בואנה",
        "פדיחה", "התפוצץ", "מתפוצץ", "צעקות", "צוחק",
    ],
    "curse": [
        "מניאק", "מטומטם", "דביל", "זונה", "כוס", "תזדיין", "לעזאזל",
        "חרא", "זין", "שרמוטה", "בן זונה",
    ],
    "names": [
        "עודד", "רונן", "בן גורדון", "גורדון", "אינדה", "inde", "ronen",
        "oded",
    ],
    "game": [
        "מיינקראפט", "minecraft", "gta", "פורטנייט", "fortnite",
        "פיפא", "fifa", "רד זון", "ואלו", "valo", "רוקט",
    ],
}

LAUGHTER_MARKERS = ["חחח", "חהחה", "הההה", "אחחח", "lol", "lmao", "צוחק"]

SHORT_MIN = 12.0
SHORT_MAX = 40.0
SHORT_TARGET = 25.0
LONG_MIN = 360.0  # topic videos: at least ~6 minutes
LONG_MAX = 7200.0  # a whole topic, up to 2 hours

# Ready-queue directory: one JSON per finished clip, for review/upload.
READY = ROOT / "ready"

# Common/weak tokens that must not, on their own, make a window a clip.
# "מה" and "איזה" appear constantly in Hebrew speech.
WEAK_KEYWORDS = {"מה", "איזה", "יאללה", "וואלה", "אחלה", "oded", "עודד"}

# --- Strict moment selection ---
# A clip is kept only if it passes the multi-signal gate AND ranks near the top.
# Signals counted: loudness spike, chat-rate spike (when chat exists), transcript cue.
SHORT_SCORE_MIN = 0.40
LONG_SCORE_MIN = 0.48
SHORT_MAX_PER_HOUR = 2
LONG_MAX_PER_HOUR = 2  # unused: longs are now one per finished topic, not per hour
TOPIC_MIN_SEC = 360.0
SHORT_NMS_GAP = 20.0
SHORT_TOP_K_PER_SEGMENT = 2
# Loudness: LU above session median to count as a spike (6 LU => loud_z 1.0)
LOUD_SPIKE_LU = 2.5
# Real shout is a stronger spike than a mere "above -14 LUFS" (which is typical speech here)
SHOUT_LU = 4.0
CHAT_SPIKE_Z = 0.5

# --- Precise cuts ---
# Pad around snapped sentence/word boundaries. Only cut real dead air.
CUT_PAD_SEC = 0.2
SNAP_MAX_EXPAND = 4.0
SILENCE_MIN_DUR = 0.90
SILENCE_NOISE_DB = -38.0

# ASR: small int8 for live detection (keeps up with 5-min segments).
# medium int8 is tried only when rendering a finished Short's captions.
LIVE_WHISPER_MODEL = "small"
FINAL_WHISPER_MODEL = "medium"


# Streamer display name for titles/descriptions, per channel (never hardcode).
_STREAMER_NAMES_HE = {"odedsvr": "עודד", "ronengg": "רונן"}
STREAMER_NAME_HE = os.environ.get("KICK_STREAMER_HE") or _STREAMER_NAMES_HE.get(CHANNEL, CHANNEL)

# Spoken / Hebrew aliases of YouTube creators -> canonical channel name.
# Used for title wording and as a low-confidence transcript hint only.
CREATOR_ALIASES = {
    "אינדה גיים": "Inde Game", "אינדה": "Inde Game", "inde game": "Inde Game",
}
# Hebrew display names for creators in titles (credit line keeps the official name).
CREATOR_NAME_HE = {"Inde Game": "אינדה גיים"}

# Maor: long videos only. Shorts are not rendered (saves compute).
ENABLE_SHORTS = False

# Long-video enhance (edit_long.py): hook + ODED HIGHLIGHTS intro/like-sub + optional zooms.
# Default on for a *future* watcher restart. Today's live process already imported
# cut_clip without this hook — the upload routine must run enhance_ready.py instead.
# Set ODED_EDIT_ENHANCE=0 to disable.
ENABLE_EDIT_ENHANCE = True
