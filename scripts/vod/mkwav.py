import json,subprocess,sys,os
cum=json.load(open('cum160.json'))
def mk(a,b):
    sel=[s for s in cum if s[1]>=a-0.01 and s[1]<b-0.01]
    t0=sel[0][1]; name=f"ac/a{int(round(t0)):05d}.wav"
    if os.path.exists(name): return name
    lst=name+'.list'; open(lst,'w').write(''.join(f"file '../a160/{s[0]}'\n" for s in sel))
    for s in sel:
        assert os.path.getsize('a160/'+s[0])>0, s
    subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',lst,'-vn','-ac','1','-ar','16000',name+'.tmp.wav'],check=True)
    os.rename(name+'.tmp.wav',name); json.dump({'t0':t0,'segs':[s[0] for s in sel]},open(name+'.json','w'))
    return name
a,b,step=map(float,sys.argv[1:4])
x=a
while x<b:
    print(mk(x,min(x+step,b)),flush=True); x+=step
