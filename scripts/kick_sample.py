import subprocess, json, sys, os, time, re
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
base=open("../kick/base2.url").read().strip()
pl=open("../kick/p2_160.m3u8").read().splitlines()
segs=[];cum=0.0;d=None
for l in pl:
    if l.startswith("#EXTINF:"): d=float(l[8:].split(",")[0])
    elif l and not l.startswith("#") and d is not None: segs.append((l,cum,d)); cum+=d; d=None
def window(t,dur):
    return [s for s in segs if s[1]+s[2]>t and s[1]<t+dur]
def fetch(t,dur,quality="160p30",out=None):
    ws=window(t,dur); os.makedirs(f"seg_{quality}",exist_ok=True)
    files=[]
    for name,st,d in ws:
        f=f"seg_{quality}/{name}"
        if not os.path.exists(f) or os.path.getsize(f)<500:
            subprocess.run(["curl","-sS","-A",UA,"-m","60","-o",f,f"{base}/{quality}/{name}"])
        files.append(f)
    return files, (ws[0][1] if ws else t)
if __name__=="__main__":
    starts=[int(x) for x in sys.argv[1].split(",")]; dur=int(sys.argv[2])
    for t in starts:
        out=f"w_{t:06d}.mp3"
        files,off=fetch(t,dur)
        if not files: print(t,"no segments"); continue
        lst=f"list_{t}.txt"; open(lst,"w").write("".join(f"file '{os.path.abspath(f)}'\n" for f in files))
        subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",lst,"-vn","-ac","1","-ar","16000","-b:a","32k",out])
        if not os.path.exists(out) or os.path.getsize(out)<1000: print(t,"audio failed"); continue
        r=subprocess.run(["curl","-sS","-m","180","https://api.groq.com/openai/v1/audio/transcriptions","-F","model=whisper-large-v3-turbo","-F","language=he","-F","response_format=verbose_json","-F",f"file=@{out}"],capture_output=True,text=True)
        try: dd=json.loads(r.stdout)
        except Exception: print(t,"bad response",r.stdout[:200]); continue
        if "error" in dd: print(t,"ERR",dd["error"].get("message","")[:150]); continue
        for s in dd.get("segments",[]): s["start"]+=off; s["end"]+=off
        json.dump(dd,open(f"w_{t:06d}.json","w"),ensure_ascii=False)
        txt=" ".join(s["text"].strip() for s in dd.get("segments",[]))
        print(f"[{t//3600}:{(t%3600)//60:02d}] {txt[:450]}",flush=True)
