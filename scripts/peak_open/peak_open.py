#!/usr/bin/env python3
"""RonenGG-Peak style opening (0vRn5KLKyjE) for ODED HIGHLIGHTS long clips.
0-M s : cold-open montage (snippets of THIS clip) + popping white/orange captions + whoosh per cut
M-M+4 : branded premise card (orange stripes, glowing headshot, channel name, premise) over body audio 0-4s
M+4.. : body continues from 4s; like/sub popup (round headshot, cheeky line, cursor clicks Subscribe+bell, click+ding)
usage: python peak_open.py spec.json
Nov 13 rule spec keys (defaults ON): "brand_sting":true (green logo sting after montage), "sub_style":"v2" (old branding_v2 like/sub/bell overlay at body "sub_at" s, default 4 = after card; "peak" = old peak popup), "cap_y":0.80
spec: {"body":mp4,"out":mp4,"montage":[{"t":s,"d":s,"cap":"..","hl":["word"]}],"premise":["l1","l2"],
       "headshot":png,"popup_face":png,"work":dir}
"""
import json,sys,os,math,subprocess,random
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import numpy as np
HEEBO='/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf'
SFX='/workspace/youtube/rank_13/sfx'
W,H,FPS=1280,720,30
ORANGE=(255,140,20); YEL=(255,200,40)
def font(sz,var='Black'):
    f=ImageFont.truetype(HEEBO,sz,layout_engine=ImageFont.Layout.RAQM)
    try:f.set_variation_by_name(var)
    except Exception:pass
    return f
def ease(x): x=max(0,min(1,x)); return 1-(1-x)**3
def back(x):
    x=max(0,min(1,x)); c=1.9; return 1+(c+1)*(x-1)**3+c*(x-1)**2

def caption_img(cap,hl,size=108):
    """words RTL; highlighted words orange; thick black outline. returns RGBA tight image"""
    words=cap.split()
    f=font(size); d=ImageDraw.Draw(Image.new('L',(1,1)))
    # wrap to max 2 lines ~1100px
    lines=[[]]
    for w in words:
        test=' '.join(lines[-1]+[w])
        if lines[-1] and d.textlength(test,font=f,direction='rtl')>1100: lines.append([w])
        else: lines[-1].append(w)
    sp=d.textlength(' ',font=f)
    lh=int(size*1.18); pad=24
    img=Image.new('RGBA',(1240,lh*len(lines)+pad*2),(0,0,0,0)); dr=ImageDraw.Draw(img)
    for li,ln in enumerate(lines):
        ws=[d.textlength(w,font=f,direction='rtl') for w in ln]; tot=sum(ws)+sp*(len(ln)-1)
        x=img.width/2+tot/2; y=pad+li*lh
        for w,wl in zip(ln,ws):
            col=ORANGE if any(h in w for h in hl) else (255,255,255)
            # shadow
            dr.text((x-wl+6,y+7),w,font=f,fill=(0,0,0,160),stroke_width=16,stroke_fill=(0,0,0,160),direction='rtl')
            dr.text((x-wl,y),w,font=f,fill=col,stroke_width=13,stroke_fill=(0,0,0),direction='rtl')
            x-=wl+sp
    return img

def circle_head(path,size):
    a=Image.open(path).convert('RGBA')
    # crop square around top (face) region
    bb=a.getbbox() or (0,0,*a.size); a=a.crop(bb); w,h=a.size; s=int(min(w,h)*0.78); cxx=int(w*float(os.environ.get('HEAD_CX','0.5'))); box=(max(0,cxx-s//2),int(h*0.02),max(0,cxx-s//2)+s,int(h*0.02)+s)
    a=a.crop(box).resize((size,size),Image.LANCZOS)
    bg=Image.new('RGBA',(size,size),(40,22,10,255)); bg.alpha_composite(a)
    m=Image.new('L',(size,size),0); ImageDraw.Draw(m).ellipse((0,0,size-1,size-1),fill=255)
    bg.putalpha(m); return bg

def card_frames(work,premise,headshot,n):
    out=work/'card'; out.mkdir(exist_ok=True)
    hs=circle_head(headshot,330)
    random.seed(3); sparks=[(random.randint(60,470),random.randint(110,560),random.random()*6.28) for _ in range(9)]
    dd=ImageDraw.Draw(Image.new('L',(1,1))); fits=[]
    for li,line in enumerate(premise):
        sz=68 if li==0 else 62
        while sz>34 and dd.textlength(line,font=font(sz),direction='rtl')>760: sz-=2
        fits.append(font(sz))
    for i in range(n):
        t=i/FPS
        im=Image.new('RGBA',(W,H),(14,8,4,255)); d=ImageDraw.Draw(im)
        off=(t*120)%120
        for k in range(-8,22):
            x=k*120+off
            d.polygon([(x,0),(x+46,0),(x+46-H*0.6,H),(x-H*0.6,H)],fill=(48,24,6,255))
        # vignette glow behind circle
        cx,cy=270,330
        glow=Image.new('RGBA',(W,H),(0,0,0,0)); g=ImageDraw.Draw(glow)
        pr=1+0.06*math.sin(t*2*math.pi*1.6)
        r=int(205*pr); g.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(255,120,10,200))
        glow=glow.filter(ImageFilter.GaussianBlur(28)); im.alpha_composite(glow)
        d=ImageDraw.Draw(im)
        d.ellipse((cx-181,cy-181,cx+181,cy+181),fill=(255,150,30,255))
        d.ellipse((cx-171,cy-171,cx+171,cy+171),fill=(20,10,4,255))
        im.alpha_composite(hs,(cx-165,cy-165))
        for (sx,sy,ph) in sparks:
            a=int(255*(0.5+0.5*math.sin(t*7+ph))); s=10+int(6*math.sin(t*5+ph))
            d.polygon([(sx,sy-s),(sx+s//3,sy),(sx,sy+s),(sx-s//3,sy)],fill=(255,240,200,a))
            d.polygon([(sx-s,sy),(sx,sy-s//3),(sx+s,sy),(sx,sy+s//3)],fill=(255,240,200,a))
        # channel name
        fn=font(50); x0=cx; y0=548
        wa=d.textlength('ODED ',font=fn); wb=d.textlength('HIGHLIGHTS',font=fn); sx=x0-(wa+wb)/2
        d.text((sx,y0),'ODED ',font=fn,fill=(255,255,255),stroke_width=5,stroke_fill=(0,0,0))
        d.text((sx+wa,y0),'HIGHLIGHTS',font=fn,fill=ORANGE,stroke_width=5,stroke_fill=(0,0,0))
        # premise text right, slides in
        p=ease((t-0.15)/0.45)
        for li,line in enumerate(premise):
            ff=fits[li]
            col=(255,255,255) if li==0 else YEL
            x=1230+int((1-p)*400); y=240+li*100
            d.text((x,y),line,font=ff,fill=col+(int(255*p),),stroke_width=6,stroke_fill=(0,0,0,int(255*p)),direction='rtl',anchor='ra')
        # whoosh in: whole card zoom/fade first 0.25s
        z=ease(t/0.25)
        if z<1:
            s=1.12-0.12*z; big=im.resize((int(W*s),int(H*s)),Image.BILINEAR)
            im2=big.crop(((big.width-W)//2,(big.height-H)//2,(big.width-W)//2+W,(big.height-H)//2+H))
            im=Image.blend(Image.new('RGBA',(W,H),(0,0,0,255)),im2,0.35+0.65*z)
        im.convert('RGB').save(out/f'c{i:04d}.png',compress_level=1)
    return out/'c%04d.png'

def cursor_img(sz=46):
    im=Image.new('RGBA',(sz,sz),(0,0,0,0)); d=ImageDraw.Draw(im)
    pts=[(4,2),(4,36),(13,28),(20,43),(27,40),(20,26),(32,26)]
    d.polygon(pts,fill=(255,255,255),outline=(0,0,0)); d.line(pts+[pts[0]],fill=(0,0,0),width=3)
    return im

def popup_frames(work,face,n,line1,hlword):
    out=work/'pop'; out.mkdir(exist_ok=True)
    a=Image.open(face).convert('RGBA'); fh=440; a=a.resize((int(a.width*fh/a.height),fh),Image.LANCZOS)
    cur=cursor_img()
    f=font(44); fb=font(34)
    clickA,clickB=1.55,2.25
    for i in range(n):
        t=i/FPS; im=Image.new('RGBA',(W,H),(0,0,0,0))
        pin=back(t/0.35); pout=ease((t-(n/FPS-0.35))/0.35)
        dx=int((1-pin)*700+pout*900)
        L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
        # banner (slanted orange)
        bx0,by0,bx1,by1=500,470,1010,610
        d.polygon([(bx0+20,by0),(bx1,by0-8),(bx1-12,by1),(bx0,by1+6)],fill=ORANGE+(255,),outline=(0,0,0),width=4)
        tx=bx1-26
        d.text((tx,by0+8),line1,font=f,fill=(255,255,255),stroke_width=4,stroke_fill=(0,0,0),direction='rtl',anchor='ra')
        hw=d.textlength(hlword,font=f,direction='rtl')
        d.rectangle((tx-hw-14,by0+68,tx+6,by0+128),fill=(15,10,5))
        d.text((tx-4,by0+70),hlword,font=f,fill=ORANGE,stroke_width=2,stroke_fill=(0,0,0),direction='rtl',anchor='ra')
        # subscribe button + like
        subd=t>=clickA
        sx0,sy0,sx1,sy1=560,620,770,680
        d.rounded_rectangle((sx0,sy0,sx1,sy1),18,fill=(90,90,90) if subd else (230,30,30),outline=(0,0,0),width=3)
        d.text(((sx0+sx1)//2,(sy0+sy1)//2),'נרשמת' if subd else 'הירשם',font=fb,fill=(255,255,255),anchor='mm',direction='rtl')
        # bell
        bcx,bcy=820,650; rung=t>=clickB
        sw=math.sin((t-clickB)*30)*12*max(0,1-(t-clickB)/0.8) if rung else 0
        bell=Image.new('RGBA',(70,70),(0,0,0,0)); bd=ImageDraw.Draw(bell)
        bd.ellipse((3,3,67,67),fill=(255,210,40) if rung else (40,40,40),outline=(0,0,0),width=3)
        bd.pieslice((19,16,51,50),180,360,fill=(255,255,255)); bd.rectangle((19,32,51,46),fill=(255,255,255)); bd.ellipse((30,46,40,56),fill=(255,255,255))
        bell=bell.rotate(sw,resample=Image.BICUBIC); L.alpha_composite(bell,(bcx-35,bcy-35))
        # like pill
        d.rounded_rectangle((880,620,1000,680),18,fill=(30,30,30),outline=(0,0,0),width=3)
        d.text((940,650),'לייק',font=font(30),fill=(255,255,255),anchor='mm',direction='rtl')
        # face bottom-right
        L.alpha_composite(a,(W-a.width-5,H-fh+10))
        # cursor path
        p0=(1200,300); pA=(sx0+120,sy0+38); pB=(bcx+6,bcy+8)
        if t<clickA: k=ease((t-0.4)/(clickA-0.45)); cp=(p0[0]+(pA[0]-p0[0])*k,p0[1]+(pA[1]-p0[1])*k)
        else: k=ease((t-clickA-0.15)/(clickB-clickA-0.2)); cp=(pA[0]+(pB[0]-pA[0])*k,pA[1]+(pB[1]-pA[1])*k)
        csz=1.0
        for c in (clickA,clickB):
            if 0<=t-c<0.15: csz=0.8
            if 0<=t-c<0.3:
                rr=int(10+80*(t-c)); al=int(255*(1-(t-c)/0.3)); d.ellipse((cp[0]-rr,cp[1]-rr,cp[0]+rr,cp[1]+rr),outline=(255,255,255,al),width=4)
        cc=cur.resize((int(46*csz),int(46*csz)))
        L.alpha_composite(cc,(int(cp[0]),int(cp[1])))
        im.alpha_composite(L,(dx,0)) if dx<W else None
        im.save(out/f'p{i:04d}.png',compress_level=1)
    return out/'p%04d.png',clickA,clickB

def montage_caps(work,montage,M,cap_y=0.80):
    out=work/'cap'; out.mkdir(exist_ok=True)
    caps=[caption_img(m['cap'],m.get('hl',[])) for m in montage]
    starts=[];acc=0
    for m in montage: starts.append(acc); acc+=m['d']
    n=int(round(M*FPS))
    for i in range(n):
        t=i/FPS; im=Image.new('RGBA',(W,H),(0,0,0,0))
        k=max(j for j,s in enumerate(starts) if s<=t+1e-6)
        lt=t-starts[k]
        if lt>=0.05:
            c=caps[k]; s=back((lt-0.05)/0.16)*1.0; s=max(0.3,s)
            cc=c.resize((max(1,int(c.width*s)),max(1,int(c.height*s))),Image.BILINEAR)
            # Nov 13 rule: captions lower (default H*0.80), clamped fully on screen (caption png has 24px transparent pad)
            y=min(int(H*cap_y-cc.height/2),H-cc.height+6)
            im.alpha_composite(cc,(int(W/2-cc.width/2),max(0,y)))
        im.save(out/f'k{i:04d}.png',compress_level=1)
    return out/'k%04d.png',starts

def main():
    sp=json.load(open(sys.argv[1])); work=Path(sp.get('work','/tmp/peak_open')); work.mkdir(parents=True,exist_ok=True)
    mon=sp['montage']; M=sum(m['d'] for m in mon); CARD=4.0; POP=4.0
    capseq,starts=montage_caps(work,mon,M,float(sp.get('cap_y',0.80)))
    cardseq=card_frames(work,sp['premise'],sp['headshot'],int(CARD*FPS))
    # Nov 13 rule (Maor): green ODED HIGHLIGHTS sting (branding.make_intro, 2.6s, logo+whoosh) right after the
    # cold-open montage, and the old branding_v2 like/sub/bell overlay (5s) instead of the peak popup.
    brand=bool(sp.get('brand_sting',True)); oldsub=sp.get('sub_style','v2')=='v2'
    sys.path.insert(0,'/workspace/kick_clipper')
    I=0.0
    if brand:
        from branding import make_intro, THEMES, INTRO_SEC
        from config import STREAMER_NAME_HE
        intro_mp4=work/'intro_sting.mp4'
        make_intro(intro_mp4,W,H,60,48000,2,THEMES['odedsvr'],STREAMER_NAME_HE); I=INTRO_SEC
    if oldsub:
        from branding_v2 import sub_overlay_frames, SUB_SEC
        subseq,subfps=sub_overlay_frames(work/'sub',W,H,fps=30)
        SUB_AT=float(sp.get('sub_at',CARD))  # body time; default = right after the premise card
    popseq,cA,cB=popup_frames(work,sp['popup_face'],int(POP*FPS),sp.get('pop_line','תנו לייק וסאב,'),sp.get('pop_hl','די להיות קמצנים!'))
    body=sp['body']
    args=['ffmpeg','-y','-v','error','-i',body,'-framerate',str(FPS),'-i',str(capseq),'-framerate',str(FPS),'-i',str(cardseq),
          '-framerate',str(FPS),'-i',str(popseq),'-i',f'{SFX}/whoosh.wav','-i',f'{SFX}/ding.wav','-i',f'{SFX}/boing.wav']
    nx=7+len(mon); ix_intro=ix_sub=None
    if brand: args+=['-i',str(intro_mp4)]; ix_intro=nx; nx+=1
    if oldsub: args+=['-framerate',str(subfps),'-i',str(subseq)]; ix_sub=nx; nx+=1
    fc=[]; vs=[];as_=[]
    for j,m in enumerate(mon):
        fc.append(f"[0:v]trim=start={m['t']}:duration={m['d']},setpts=PTS-STARTPTS,fps=60,format=yuv420p[mv{j}]")
        fc.append(f"[0:a]atrim=start={m['t']}:duration={m['d']},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={m['d']-0.04}:d=0.04[ma{j}]")
    fc.append(''.join(f'[mv{j}]' for j in range(len(mon)))+f'concat=n={len(mon)}:v=1:a=0[mvc]')
    fc.append(''.join(f'[ma{j}]' for j in range(len(mon)))+f'concat=n={len(mon)}:v=0:a=1[mac]')
    fc.append('[1:v]fps=60,format=rgba[capv]')
    fc.append('[mvc][capv]overlay=0:0:eof_action=pass,format=yuv420p[mvo]')
    fc.append('[2:v]fps=60,format=yuv420p,setsar=1[cv]')
    fc.append(f'[0:v]trim=start={CARD},setpts=PTS-STARTPTS,format=yuv420p[bv0]')
    if oldsub:
        off=SUB_AT-CARD
        fc.append(f'[{ix_sub}:v]format=rgba,setpts=PTS-STARTPTS+{off:.3f}/TB[pv]')
        fc.append(f"[bv0][pv]overlay=0:0:eof_action=pass:enable='between(t,{off:.3f},{off+SUB_SEC:.3f})',format=yuv420p,setsar=1[bvo]")
    else:
        fc.append('[3:v]fps=60,format=rgba[pv]')
        fc.append('[bv0][pv]overlay=0:0:eof_action=pass,format=yuv420p,setsar=1[bvo]')
    if brand:
        fc.append(f'[{ix_intro}:v]fps=60,format=yuv420p,setsar=1[iv]')
        fc.append(f'[{ix_intro}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[ia]')
    fc.append('[mvo]setsar=1[mvs]')
    if brand: fc.append('[mvs][iv][cv][bvo]concat=n=4:v=1:a=0[vout]')
    else: fc.append('[mvs][cv][bvo]concat=n=3:v=1:a=0[vout]')
    fc.append('[0:a]asetpts=PTS-STARTPTS[ba]')
    fc.append(('[mac][ia][ba]concat=n=3' if brand else '[mac][ba]concat=n=2')+':v=0:a=1,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[amain]')
    # sfx
    sfx=[]
    wh=[s for s in starts]+[M+I]  # card whoosh (intro sting has its own whoosh)
    fc.append(f'[4:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.55,asplit={len(wh)}'+''.join(f'[w{k}]' for k in range(len(wh))))
    for k,s in enumerate(wh):
        ms=int(max(0,s-0.12)*1000); fc.append(f'[w{k}]adelay={ms}|{ms}[wd{k}]'); sfx.append(f'[wd{k}]')
    if not oldsub:  # click+ding only belong to the peak popup (old v2 sub overlay is SFX-free)
        clickT=[M+I+CARD+cA,M+I+CARD+cB]
        fc.append('[6:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:0.12,volume=0.6,asplit=2[c0][c1]')
        for k,s in enumerate(clickT):
            ms=int(s*1000); fc.append(f'[c{k}]adelay={ms}|{ms}[cd{k}]'); sfx.append(f'[cd{k}]')
        ms=int((clickT[1]+0.05)*1000); fc.append(f'[5:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=0.7,adelay={ms}|{ms}[dd]'); sfx.append('[dd]')
    fc.append('[amain]'+''.join(sfx)+f'amix=inputs={1+len(sfx)}:normalize=0:duration=first[aout]')
    args+=['-filter_complex',';'.join(fc),'-map','[vout]','-map','[aout]','-c:v','libx264','-preset',sp.get('preset','veryfast'),'-b:v','12M','-maxrate','16M','-bufsize','24M','-g','120','-keyint_min','120','-sc_threshold','0','-pix_fmt','yuv420p','-r','60','-ar','48000','-ac','2',
           '-c:a','aac','-b:a','192k','-movflags','+faststart',sp['out']]
    subprocess.run(args,check=True)
    info={'montage_sec':M,'brand_sting':[M,M+I] if brand else None,'card':[M+I,M+I+CARD],
          'popup':None if oldsub else [M+I+CARD,M+I+CARD+POP],
          'sub_v2':[M+I+SUB_AT,M+I+SUB_AT+SUB_SEC] if oldsub else None,'cap_y':float(sp.get('cap_y',0.80)),
          'body_offset_in_out':M+I,'note':'output time = montage + sting + body time (for body t>=0)'}
    json.dump(info,open(sp['out']+'.open.json','w'),indent=1); print(json.dumps(info))
if __name__=='__main__': main()
