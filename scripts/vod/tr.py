import sys,json,os
from faster_whisper import WhisperModel
M="/home/box/.cache/huggingface/hub/models--ivrit-ai--whisper-large-v3-turbo-ct2/snapshots/72ad623a37947395efcc3933132353790e5a12f5"
m=WhisperModel(M,device="cpu",compute_type="int16",cpu_threads=int(sys.argv[3]))
import wave,numpy as np
w=wave.open(sys.argv[1]);a=np.frombuffer(w.readframes(w.getnframes()),np.int16).astype(np.float32)/32768
segs,info=m.transcribe(a,language="he",beam_size=int(os.environ.get("BEAM","1")),vad_filter=True,condition_on_previous_text=False,word_timestamps=True)
with open(sys.argv[2],"w") as o, open(sys.argv[2]+'.jsonl','w') as oj:
    for s in segs:
        o.write(f"[{s.start:8.2f}-{s.end:8.2f}] {s.text.strip()}\n"); o.flush()
        oj.write(json.dumps({"start":s.start,"end":s.end,"text":s.text.strip(),"words":[[w.start,w.end,w.word] for w in (s.words or [])]},ensure_ascii=False)+"\n"); oj.flush()
