import json,sys,glob
# usage: cond.py A B [gap]  -> condensed transcript lines with abs VOD seconds
A,B=float(sys.argv[1]),float(sys.argv[2]); G=float(sys.argv[3]) if len(sys.argv)>3 else 12
out=[]
for f in sorted(glob.glob('ac/a*.txt.jsonl')):
    t0=json.load(open(f.replace('.txt.jsonl','.wav.json')))['t0']
    for l in open(f):
        s=json.loads(l); a=t0+s['start']; b=t0+s['end']
        if b<A or a>B: continue
        out.append((a,b,s['text']))
out.sort(); cur=None
for a,b,t in out:
    if cur and a-cur[0]<G and a-cur[1]<3: cur[1]=b; cur[2]+=' '+t
    else:
        if cur: print(f"{int(cur[0])}| {cur[2]}")
        cur=[a,b,t]
if cur: print(f"{int(cur[0])}| {cur[2]}")
