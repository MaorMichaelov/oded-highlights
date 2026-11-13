#!/usr/bin/env python3
"""Nov 13b: word-level timings for cold-open montage captions, from the VOD's ivrit-ai transcript (ac/aNNNNN.txt.jsonl,
t0 in aNNNNN.wav.json) via the clip's cut map (cuts json: pieces[].keep = VOD ranges concatenated into the body).
fill(spec): for each montage item without 'words', set m['words']=[[t_rel,word],...] (t_rel = seconds from snippet start).
If the hand-written caption has the same word count, its words (spelling/punct) are kept; else the transcript words are used."""
import json,glob,os,re
def _body2vod(cuts):
    segs=[];acc=0
    for p in cuts['pieces']:
        for a,b in p['keep']: segs.append((acc,acc+b-a,a)); acc+=b-a
    return segs
def _vod_words(vod_dir):
    W=[]
    for j in sorted(glob.glob(os.path.join(vod_dir,'ac','a*.txt.jsonl'))):
        meta=j.replace('.txt.jsonl','.wav.json')
        try: t0=json.load(open(meta))['t0']
        except Exception: t0=float(re.search(r'a(\d+)',os.path.basename(j)).group(1))
        for ln in open(j):
            try: r=json.loads(ln)
            except Exception: continue
            for s,e,w in r.get('words') or []: W.append((t0+s,t0+e,w.strip()))
    W.sort(); return W
def _norm(w): return re.sub(r'[^\u05d0-\u05eaA-Za-z0-9]','',w)
def _align(hand,tr,d):
    """keep the hand-written words; take times from matching transcript words (matched from the END, since snippets
    often contain a repeat before the captioned line); unmatched words are interpolated."""
    T=[None]*len(hand); j=len(tr)-1
    for i in range(len(hand)-1,-1,-1):
        k=j
        while k>=0 and _norm(tr[k][1])!=_norm(hand[i]): k-=1
        if k>=0: T[i]=tr[k][0]; j=k-1
    known=[(i,t) for i,t in enumerate(T) if t is not None]
    if not known: return [[0.05+(d-0.3)*i/len(hand),w] for i,w in enumerate(hand)]
    for i in range(len(hand)):
        if T[i] is None:
            prv=[(a,t) for a,t in known if a<i]; nxt=[(a,t) for a,t in known if a>i]
            if prv and nxt: (a0,t0),(a1,t1)=prv[-1],nxt[0]; T[i]=t0+(t1-t0)*(i-a0)/(a1-a0)
            elif prv: T[i]=min(d-0.2,prv[-1][1]+0.25*(i-prv[-1][0]))
            else: T[i]=max(0.0,nxt[0][1]-0.25*(nxt[0][0]-i))
    for i in range(1,len(T)): T[i]=max(T[i],T[i-1]+0.04)
    return [[round(t,3),w] for t,w in zip(T,hand)]
def fill(spec):
    vd,cj=spec.get('vod_dir'),spec.get('cuts')
    if not (vd and cj and os.path.exists(cj)): return spec
    segs=_body2vod(json.load(open(cj))); VW=None
    for m in spec['montage']:
        if m.get('words'): continue
        if VW is None: VW=_vod_words(vd)
        t0,t1=m['t'],m['t']+m['d']; out=[]
        for b0,b1,va in segs:
            lo,hi=max(t0,b0),min(t1,b1)
            if hi<=lo: continue
            v0=va+(lo-b0); v1=va+(hi-b0)
            for s,e,w in VW:
                if v0-0.05<=s<v1-0.08 and w: out.append([round(lo+(s-v0)-t0,3),w])
        if not out: continue
        hand=m.get('cap','').split()
        if len(hand)==len(out): out=[[t,h] for (t,_),h in zip(out,hand)]
        elif hand: out=_align(hand,out,m['d'])
        m['words']=out
    return spec
if __name__=='__main__':
    import sys; s=json.load(open(sys.argv[1])); fill(s); print(json.dumps([m.get('words') for m in s['montage']],ensure_ascii=False,indent=0))
