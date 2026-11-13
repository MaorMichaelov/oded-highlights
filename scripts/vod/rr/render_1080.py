# 1080p60 re-render of the ROB RUN v2 body: identical cuts to render_v2.py (cuts_k.json), 1080 VOD segments, trim filter (no -ss on concat)
import json,subprocess,os
from concurrent.futures import ThreadPoolExecutor
cum=json.load(open('../cum720.json'))   # same segment table for p1080 (EXTINF identical)
C=json.load(open('cuts_k.json'))
os.makedirs('build/parts_1080',exist_ok=True)
jobs=[];i=0
def files(a,b): return [(n,s,d) for n,s,d in cum if s+d>a and s<b]
for p in C['pieces']:
    for a,b in p['keep']:
        fs=files(a,b); s0=fs[0][1]; x=a-s0; d=b-a
        out=f'build/parts_1080/p{i:03d}.mov'; i+=1
        jobs.append((fs,x,d,out))
def run(j):
    fs,x,d,out=j
    if os.path.exists(out): return out
    inp='concat:'+'|'.join('../v1080/'+n for n,_,_ in fs)
    subprocess.run(['nice','-n','10','ffmpeg','-v','error','-y','-i',inp,'-map','0:v:0','-map','0:a:0',
      '-vf',f'trim=start={x:.3f}:duration={d:.3f},setpts=PTS-STARTPTS,fps=60,format=yuv420p,setsar=1',
      '-af',f'atrim=start={x:.3f}:duration={d:.3f},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.02,afade=t=out:st={max(0,d-0.04):.3f}:d=0.04',
      '-c:v','libx264','-preset','veryfast','-crf','12','-g','120','-threads','4','-c:a','pcm_s16le','-ar','48000','-ac','2',out+'.tmp.mov'],check=True)
    os.rename(out+'.tmp.mov',out); return out
with ThreadPoolExecutor(2) as ex: lst=list(ex.map(run,jobs))
open('build/list_1080.txt','w').write(''.join(f"file '{os.path.abspath(x)}'\n" for x in lst))
subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i','build/list_1080.txt','-c','copy','build/body_1080.mov'],check=True)
print('parts',len(lst))
