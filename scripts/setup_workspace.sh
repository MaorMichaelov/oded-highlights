#!/usr/bin/env bash
# Recreates the /workspace layout the editing scripts expect (fonts, logo, sfx, symlinks). Idempotent. Works on a GitHub runner and locally.
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
sudo mkdir -p /workspace/youtube/rank_13 /workspace/oded_research /usr/share/fonts/truetype/sand-box/google/Heebo "/usr/share/fonts/truetype/sand-box/google/IBM Plex Sans Hebrew" 2>/dev/null || mkdir -p /workspace/youtube/rank_13 /workspace/oded_research
sudo ln -sfn "$REPO/scripts" /workspace/kick_clipper 2>/dev/null || ln -sfn "$REPO/scripts" /workspace/kick_clipper
sudo ln -sfn "$REPO/assets/sfx" /workspace/youtube/rank_13/sfx 2>/dev/null || ln -sfn "$REPO/assets/sfx" /workspace/youtube/rank_13/sfx
sudo cp -f "$REPO/assets/oded_highlights_logo.jpg" /workspace/oded_research/ 2>/dev/null || cp -f "$REPO/assets/oded_highlights_logo.jpg" /workspace/oded_research/
H=/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf
[ -s "$H" ] || sudo curl -sSL -o "$H" "https://raw.githubusercontent.com/google/fonts/main/ofl/heebo/Heebo%5Bwght%5D.ttf"
P="/usr/share/fonts/truetype/sand-box/google/IBM Plex Sans Hebrew/IBMPlexSansHebrew-Bold.ttf"
[ -s "$P" ] || sudo curl -sSL -o "$P" "https://raw.githubusercontent.com/google/fonts/main/ofl/ibmplexsanshebrew/IBMPlexSansHebrew-Bold.ttf"
echo workspace-ready
