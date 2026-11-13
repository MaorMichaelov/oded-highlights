#!/usr/bin/env python3
"""Nov 13 rule (Maor) opening for ODED HIGHLIGHTS long clips.
Takes an existing peak_open spec json (body = zoomed body from `enhance_ready.py ... --no-hook --no-brand`),
forces brand_sting=True (green branding.make_intro logo sting right after the cold-open montage),
sub_style='v2' (old branding_v2 like/sub/bell overlay, 5s, at body t=sub_at, default 4 = right after the
premise card; replaces the peak popup so there is only ONE sub element), cap_y=0.80 (lower montage captions),
writes SPEC_v2-like spec next to it and runs the low-memory renderer.
usage: venv/bin/python peak_open/nov13_open.py IN_SPEC.json OUT.mp4 [OUT_SPEC.json]
Nov 13b rule (16:46): defaults card=false (NO premise card; sting -> body directly, v2 sub at body t=sub_at=4 = 4s after
the sting), cap_style="ref5" (captions matched to ref 5zTSmoByVyA: 1-3 words/line, word-by-word, small, Heebo Black,
white+yellow offset shadow / highlighted yellow+black shadow). "res":[1920,1080] renders 1080p (body upscaled if 720p).
Legacy look: set "card":true and/or "cap_style":"v1" in the spec.
"""
import json,sys,subprocess,os
from pathlib import Path
src,out=sys.argv[1],sys.argv[2]
dst=sys.argv[3] if len(sys.argv)>3 else str(Path(src).with_name(Path(src).stem+'_nov13.json'))
s=json.load(open(src)); s['out']=os.path.abspath(out); s['work']=s.get('work','/tmp/peak_open')+'_nov13'
s.setdefault('brand_sting',True); s.setdefault('sub_style','v2'); s.setdefault('sub_at',4.0); s.setdefault('cap_y',0.80)
s.setdefault('card',False); s.setdefault('cap_style','ref5')
sys.path.insert(0,str(Path(__file__).resolve().parent))
if s.get('cap_style')=='ref5':
    import vod_words; vod_words.fill(s)  # word timings from VOD transcript when spec has vod_dir+cuts
    lm=s['montage'][-1]  # last caption word must stay readable before the wipe covers it (ref: >=0.6s)
    if lm.get('words') and lm['words'][-1][0]+0.75>lm['d']: lm['d']=round(lm['words'][-1][0]+0.75,2); print('Nov13b: last shot extended to',lm['d'],'s',file=sys.stderr)
    if len(s['montage'])!=3 or not (7.0<=sum(m['d'] for m in s['montage'])<=9.5):
        print('WARN Nov13b: reference cold open = 3 shots of ~2.6-2.9s (~8s total); this spec has',len(s['montage']),'shots /',round(sum(m['d'] for m in s['montage']),2),'s',file=sys.stderr)
json.dump(s,open(dst,'w'),ensure_ascii=False,indent=1)
here=Path(__file__).resolve().parent
r=subprocess.run([sys.executable,str(here/'peak_open_lowmem.py'),dst])
if r.returncode==0: subprocess.run(['rm','-rf',s['work']])  # temp PNG frames only
sys.exit(r.returncode)
