import json,glob,re,sys,collections
A,B=float(sys.argv[1]),float(sys.argv[2])
segs=[]
for f in sorted(glob.glob('ac/a*.txt.jsonl')):
    t0=json.load(open(f.replace('.txt.jsonl','.wav.json')))['t0']
    for l in open(f):
        s=json.loads(l); segs.append((t0+s['start'],t0+s['end'],s['text']))
segs.sort()
L={int(round(float(k))):v for k,v in json.load(open("loud_all.json")).items()}
bins=collections.defaultdict(lambda:[0,[]])
for a,b,t in segs:
    if a<A or a>B: continue
    k=int(a//60)*60; sc=0; why=[]
    if re.search(r'(.)\1{7,}',t): sc+=3; why.append('WOW')
    for m in re.finditer(r'(\d+(?:[.,]\d+)?)\s*(דולר|\$)',t):
        try:
            v=float(m.group(1).replace(',','.'))
            if v>=15: sc+=2+min(v,200)/25; why.append(f'${v}')
        except: pass
    n=len(re.findall(r'לחיים',t)); 
    if n: sc+=0.5*n; why.append(f'l{n}')
    for kw in ['שיכור','שיכורים','מטורף','פסיכי','אין מצב','אומייגאד','טופ היט','סיקרט','אלטרנטיב']:
        if kw in t: sc+=1; why.append(kw)
    bins[k][0]+=sc; bins[k][1]+=why
for k in sorted(bins):
    ld=[L.get(x,-40) for x in range(k,k+60)]
    top=sorted(ld)[-5:]; lo=sum(top)/5
    if bins[k][0]>=3: print(k, round(bins[k][0],1), round(lo,1), ' '.join(bins[k][1])[:150])
