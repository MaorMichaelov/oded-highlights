import json,subprocess,os
cum=json.load(open('../cum720.json'))
C=json.load(open('cuts_k.json'))
os.makedirs('build/parts4',exist_ok=True)
lst=[];i=0
def files(a,b): return [(n,s,d) for n,s,d in cum if s+d>a and s<b]
for p in C['pieces']:
    for a,b in p['keep']:
        fs=files(a,b); s0=fs[0][1]; x=a-s0; d=b-a
        out=f'build/parts4/p{i:03d}.mp4'; i+=1
        if not os.path.exists(out):
            inp='concat:'+'|'.join('../v720/'+n for n,_,_ in fs)
            subprocess.run(['ffmpeg','-v','error','-y','-i',inp,'-map','0:v:0','-map','0:a:0',
              '-vf',f'trim=start={x:.3f}:duration={d:.3f},setpts=PTS-STARTPTS,fps=60,format=yuv420p,setsar=1',
              '-af',f'atrim=start={x:.3f}:duration={d:.3f},asetpts=PTS-STARTPTS,aresample=48000,afade=t=in:d=0.02,afade=t=out:st={max(0,d-0.04):.3f}:d=0.04',
              '-c:v','libx264','-preset','veryfast','-crf','19','-g','120','-c:a','aac','-b:a','192k','-ar','48000','-ac','2',out],check=True)
        lst.append(out)
open('build/list4.txt','w').write(''.join(f"file '{os.path.abspath(x)}'\n" for x in lst))
subprocess.run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i','build/list4.txt','-c','copy','-movflags','+faststart','build/body4.mp4'],check=True)
print('parts',len(lst))
