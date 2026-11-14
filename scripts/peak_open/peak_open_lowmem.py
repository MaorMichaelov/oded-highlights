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
CW,CH=1280,720  # premise card / peak popup are drawn at 720p and scaled to W,H
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
        im=Image.new('RGBA',(CW,CH),(14,8,4,255)); d=ImageDraw.Draw(im)
        off=(t*120)%120
        for k in range(-8,22):
            x=k*120+off
            d.polygon([(x,0),(x+46,0),(x+46-CH*0.6,H),(x-CH*0.6,H)],fill=(48,24,6,255))
        # vignette glow behind circle
        cx,cy=270,330
        glow=Image.new('RGBA',(CW,CH),(0,0,0,0)); g=ImageDraw.Draw(glow)
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
            s=1.12-0.12*z; big=im.resize((int(CW*s),int(CH*s)),Image.BILINEAR)
            im2=big.crop(((big.width-W)//2,(big.height-H)//2,(big.width-CW)//2+CW,(big.height-CH)//2+CH))
            im=Image.blend(Image.new('RGBA',(CW,CH),(0,0,0,255)),im2,0.35+0.65*z)
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
        t=i/FPS; im=Image.new('RGBA',(CW,CH),(0,0,0,0))
        pin=back(t/0.35); pout=ease((t-(n/FPS-0.35))/0.35)
        dx=int((1-pin)*700+pout*900)
        L=Image.new('RGBA',(CW,CH),(0,0,0,0)); d=ImageDraw.Draw(L)
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
        L.alpha_composite(a,(CW-a.width-5,CH-fh+10))
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
        im.alpha_composite(L,(dx,0)) if dx<CW else None
        im.save(out/f'p{i:04d}.png',compress_level=1)
    return out/'p%04d.png',clickA,clickB

# ---- Nov 13b caption style "ref5" (matched 1:1 to Maor's reference 5zTSmoByVyA, measured at 1920x1080) ----
# Heebo Black, glyph height ~7.5% H (font size 0.123H, x-squeezed 0.93), ONE line of max 3 words, words revealed one by one
# in place (phrase layout fixed, centered), white fill + yellow hard offset shadow; highlighted word = yellow fill + black
# hard offset shadow; black outline 0.0075H; offset (0.005H,0.0065H). Phrase pops in 1.28x->1.0 (0.2s ease-out, alpha
# 0.35->1 in 0.07s); every added word re-pops the line 1.08x->1.0 (0.13s); old phrase fades out over 0.07s.
REF_YEL=(120,230,40)  # brand green (was reference yellow); Maor asked for green captions
def _ref_font(H_):
    return font(max(10,int(round(0.123*H_))))
def ref_phrases(cap,H_,W_,maxw=3,maxfrac=0.62):
    f=_ref_font(H_); d=ImageDraw.Draw(Image.new('L',(1,1))); out=[[]]
    for w in cap.split():
        test=' '.join(out[-1]+[w])
        if out[-1] and (len(out[-1])>=maxw or out[-1][-1][-1:] in '!?.,' or d.textlength(test,font=f,direction='rtl')*0.93>W_*maxfrac): out.append([w])
        else: out[-1].append(w)
    return out
def ref_phrase_img(words,hl,nvis,H_):
    """full-phrase layout (RTL, first word rightmost), only first nvis words drawn. RGBA, tight-ish with pad."""
    f=_ref_font(H_); d=ImageDraw.Draw(Image.new('L',(1,1)))
    st=max(2,int(round(0.0075*H_))); ox,oy=max(1,int(round(0.005*H_))),max(1,int(round(0.0065*H_)))
    sp=d.textlength(' ',font=f)*0.9
    ws=[d.textlength(w,font=f,direction='rtl') for w in words]; tot=sum(ws)+sp*(len(words)-1)
    pad=st+max(ox,oy)+6; asc,desc=f.getmetrics()
    Wi=int(tot+2*pad); Hi=int(asc+desc+2*pad)
    A=Image.new('RGBA',(Wi,Hi),(0,0,0,0)); dA=ImageDraw.Draw(A)
    B=Image.new('RGBA',(Wi,Hi),(0,0,0,0)); dB=ImageDraw.Draw(B)
    C=Image.new('RGBA',(Wi,Hi),(0,0,0,0)); dC=ImageDraw.Draw(C)
    x=pad+tot
    for k,(w,wl) in enumerate(zip(words,ws)):
        if k<nvis:
            h=any(t and t.strip('!?.,') and t.strip('!?.,') in w for t in hl)
            fill=REF_YEL if h else (255,255,255); acc=(0,0,0) if h else REF_YEL
            dA.text((x-wl,pad),w,font=f,fill=(0,0,0),stroke_width=st,stroke_fill=(0,0,0),direction='rtl')
            dB.text((x-wl+ox,pad+oy),w,font=f,fill=acc,direction='rtl')
            dC.text((x-wl,pad),w,font=f,fill=fill,direction='rtl')
        x-=wl+sp
    A.alpha_composite(B); A.alpha_composite(C)
    return A.resize((max(1,int(A.width*0.93)),A.height),Image.LANCZOS)
def ref_schedule(m,H_,W_):
    """-> list of phrases: (words, [word_start_times rel. to segment]). spec may give m['words']=[[t,'w'],...]"""
    if m.get('words'):
        tw=[(float(t),w) for t,w in m['words']]; cap=' '.join(w for _,w in tw)
    else:
        ww=m['cap'].split(); L=[max(2,len(w)) for w in ww]; T=sum(L); span=max(0.3,m['d']-0.25); acc=0; tw=[]
        for w,l in zip(ww,L): tw.append((0.05+span*acc/T,w)); acc+=l
        cap=m['cap']
    phr=ref_phrases(cap,H_,W_); out=[]; i=0
    for p in phr: out.append((p,[t for t,_ in tw[i:i+len(p)]])); i+=len(p)
    return out
# ---- Nov 13b transitions (ref 5zTSmoByVyA): white flash on every montage cut (1 full-white frame, decays in ~0.22s),
# no whooshes on cuts; channel logo pops in bottom-right ~0.6s before the sting, rides a two-colour curved wipe
# (accent band leading, dark fill behind) right->left over the last 0.45s and lands centred at the sting's logo size;
# after the sting a reverse wipe (dark then accent band) uncovers the content in 0.35s.
WIPE_IN=0.45; WIPE_OUT=0.35; LOGO_IN=0.6; STING_BG=(8,6,10)
def _wipe_layer(edge,band,acc,lead_dark,fill_img=None):
    """RGBA W x H. region x>=curve(edge) covered. lead_dark False: accent band [edge,edge+band] then dark; True: reverse"""
    L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L)
    bow=0.10*W; ys=list(range(0,H+1,max(4,H//90)))
    def poly(x0,x1,col):
        pts=[(x0+bow*((y-H/2)/(H/2))**2,y) for y in ys]+[(x1+bow*((y-H/2)/(H/2))**2,y) for y in reversed(ys)]
        d.polygon(pts,fill=col)
    c1,c2=((STING_BG,acc) if lead_dark else (acc,STING_BG))
    if fill_img is not None and not lead_dark:  # covered side shows the sting's first frame (seamless hand-off)
        m=Image.new('L',(W,H),0); ImageDraw.Draw(m).polygon([(edge+band+bow*((y-H/2)/(H/2))**2,y) for y in ys]+[(W*2,H),(W*2,0)],fill=255)
        L.paste(fill_img,(0,0),m); d=ImageDraw.Draw(L)
    else: poly(edge+band,W*2,c2+(255,))
    poly(edge,edge+band,c1+(255,))
    lw=max(2,int(H*0.004))
    for e in (edge,edge+band):
        d.line([(e+bow*((y-H/2)/(H/2))**2,y) for y in ys],fill=(0,0,0,255),width=lw)
    return L
def wipe_out_frames(work,acc,bg=None):
    """bg: RGBA W x H shown on the still-covered side (= last sting frame, so the sting itself is wiped away)"""
    out=work/'wout'; out.mkdir(exist_ok=True); n=int(round(WIPE_OUT*FPS))
    for i in range(n+1):
        p=ease(i/n); band=0.16*W
        # trailing edge travels W -> -0.35W ; content visible to the right of trailing edge
        te=W*(1-1.4*p)
        L=Image.new('RGBA',(W,H),(0,0,0,0)); d=ImageDraw.Draw(L); bow=0.10*W; ys=list(range(0,H+1,max(4,H//90)))
        cv=lambda e:[(e+bow*((y-H/2)/(H/2))**2,y) for y in ys]
        if bg is not None:
            m=Image.new('L',(W,H),0); ImageDraw.Draw(m).polygon([(-W,0)]+cv(te-band)+[(-W,H)],fill=255)
            L.paste(bg,(0,0),m); d=ImageDraw.Draw(L)
        else: d.polygon([(-W,0)]+cv(te-band)+[(-W,H)],fill=STING_BG+(255,))
        d.polygon(cv(te-band)+list(reversed(cv(te))),fill=acc+(255,))
        for e in (te-band,te): d.line(cv(e),fill=(0,0,0,255),width=max(2,int(H*0.004)))
        L.save(out/f'w{i:04d}.png',compress_level=1)
    return out/'w%04d.png'
def montage_caps_ref(work,montage,M,cap_y=0.80,flash=True,wipe=None):
    """wipe: None or dict(acc=(r,g,b), logo=path) -> wipe-in + logo ride into the sting"""
    out=work/'cap'; out.mkdir(exist_ok=True)
    starts=[];acc=0
    for m in montage: starts.append(acc); acc+=m['d']
    scheds=[ref_schedule(m,H,W) for m in montage]; cache={}
    lg_cache={}
    if wipe:
        sys.path.insert(0,'/workspace/kick_clipper'); from branding import _circle_logo
        LS=int(H*0.46*0.75)  # = first-frame logo size of branding.intro_frame
        lg_full=_circle_logo(wipe['logo'],LS); ring=int(LS*0.035)+4
        lgr=Image.new('RGBA',(LS+2*ring,LS+2*ring),(0,0,0,0)); ImageDraw.Draw(lgr).ellipse((0,0,LS+2*ring-1,LS+2*ring-1),fill=wipe['acc']+(255,))
        lgr.alpha_composite(lg_full,(ring,ring))
    n=int(round(M*FPS))
    for i in range(n):
        t=i/FPS; im=Image.new('RGBA',(W,H),(0,0,0,0))
        k=max(j for j,s0 in enumerate(starts) if s0<=t+1e-6); lt=t-starts[k]; sc=scheds[k]
        pi=None
        for j,(ws,ts) in enumerate(sc):
            if lt>=ts[0]-1e-6: pi=j
        if pi is not None:
            ws,ts=sc[pi]; nv=sum(1 for x in ts if lt>=x-1e-6)
            nxt=sc[pi+1][1][0] if pi+1<len(sc) else None
            key=(k,pi,nv)
            if key not in cache: cache={key:ref_phrase_img(ws,montage[k].get('hl',[]),nv,H)}
            c=cache[key]
            p0=lt-ts[0]; pl=lt-ts[nv-1]
            s=1+0.28*(1-ease(p0/0.2)) if nv==1 or p0<0.2 else 1+0.08*(1-ease(pl/0.13))
            al=min(1.0,0.35+0.65*min(p0,pl if nv>1 else p0)/0.07) if p0<0.07 else 1.0
            if nxt is not None and lt>nxt-0.07: al=min(al,max(0.0,(nxt-lt)/0.07))
            cc=c.resize((max(1,int(c.width*s)),max(1,int(c.height*s))),Image.BILINEAR) if abs(s-1)>1e-3 else c
            if al<0.999:
                a=cc.getchannel('A').point(lambda v:int(v*al)); cc=cc.copy(); cc.putalpha(a)
            y=int(H*cap_y-cc.height/2); y=max(0,min(y,H-cc.height))
            im.alpha_composite(cc,(int(W/2-cc.width/2),y))
        if flash and k>0 and lt<0.22:
            a=int(255*0.97*(1-lt/0.22)**1.4)
            im.alpha_composite(Image.new('RGBA',(W,H),(255,255,255,a)))
        if wipe and t>=M-LOGO_IN:
            tw=t-(M-WIPE_IN)
            if tw>=0:
                p=ease(tw/WIPE_IN); band=0.16*W; edge=W*(1.02-1.4*p)
                im.alpha_composite(_wipe_layer(edge,band,wipe['acc'],False,wipe.get('fill')))
            # logo: pops in bottom-right, then rides to centre growing to the sting logo size
            tl=t-(M-LOGO_IN); pop=back(tl/0.18)
            q=min(1.0,ease(max(0.0,tw)/WIPE_IN)/0.45) if tw>0 else 0.0  # lands centred before the wipe uncovers the sting's own (same-size) logo
            sz=max(4,int(lgr.width*(0.42+0.58*q)*pop))
            cx=(W*0.86)+(W/2-W*0.86)*q; cy=(H*0.80)+(H*0.45-H*0.80)*q
            key=sz
            if key not in lg_cache: lg_cache={key:lgr.resize((sz,sz),Image.LANCZOS)}
            im.alpha_composite(lg_cache[key],(int(cx-sz/2),int(cy-sz/2)))
        im.save(out/f'k{i:04d}.png',compress_level=1)
    return out/'k%04d.png',starts

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
    global W,H
    sp=json.load(open(sys.argv[1])); work=Path(sp.get('work','/tmp/peak_open')); work.mkdir(parents=True,exist_ok=True)
    if sp.get('res'): W,H=int(sp['res'][0]),int(sp['res'][1])
    # Nov 13b rule: premise card OFF by default (Maor: "terrible"); legacy specs can set "card":true
    use_card=bool(sp.get('card',False))
    mon=sp['montage']; M=sum(m['d'] for m in mon); CARD=4.0 if use_card else 0.0; POP=4.0
    cap_style=sp.get('cap_style','ref5')
    brand=bool(sp.get('brand_sting',True)); ref5=cap_style=='ref5'
    sys.path.insert(0,'/workspace/kick_clipper')
    if ref5:
        from branding import THEMES as _TH
        th=_TH['odedsvr']; wipe={'acc':tuple(th['accent']),'logo':th['logo']} if (brand and sp.get('wipe',True)) else None
        if wipe:
            from branding import intro_frame as _IF
            from config import STREAMER_NAME_HE as _NH0
            f0=_IF(0,60,W,H,th,_NH0,fades=False).convert('RGBA')
            # sting frame 0 without its (smaller, 0.75x) logo would double the logo; our riding logo lands on top anyway
            wipe['fill']=f0
        capseq,starts=montage_caps_ref(work,mon,M,float(sp.get('cap_y',0.80)),flash=sp.get('flash',True),wipe=wipe)
        bgl=None
        if wipe:
            from branding import intro_frame, INTRO_SEC as _IS
            from config import STREAMER_NAME_HE as _NH
            bgl=intro_frame(int(round(_IS*60))-1,60,W,H,th,_NH,fades=False).convert('RGBA')
        woutseq=wipe_out_frames(work,tuple(th['accent']),bgl) if wipe else None
    else:
        capseq,starts=montage_caps(work,mon,M,float(sp.get('cap_y',0.80))); woutseq=None
    cardseq=card_frames(work,sp['premise'],sp['headshot'],int(4.0*FPS)) if use_card else None
    # Nov 13 rule (Maor): green ODED HIGHLIGHTS sting (branding.make_intro, 2.6s, logo+whoosh) right after the
    # cold-open montage, and the old branding_v2 like/sub/bell overlay (5s) instead of the peak popup.
    oldsub=sp.get('sub_style','v2')=='v2'
    I=0.0
    if brand:
        from branding import make_intro, THEMES, INTRO_SEC
        from config import STREAMER_NAME_HE
        intro_mp4=work/'intro_sting.mp4'
        make_intro(intro_mp4,W,H,60,48000,2,THEMES['odedsvr'],STREAMER_NAME_HE,fades=not (ref5 and wipe)); I=INTRO_SEC
    if oldsub:
        from branding_v2 import sub_overlay_frames, SUB_SEC
        subseq,subfps=sub_overlay_frames(work/'sub',W,H,fps=30)
        SUB_AT=float(sp.get('sub_at',4.0))  # body time (= seconds after the sting when no card)
    if oldsub: popseq,cA,cB=None,0,0
    else: popseq,cA,cB=popup_frames(work,sp['popup_face'],int(POP*FPS),sp.get('pop_line','תנו לייק וסאב,'),sp.get('pop_hl','די להיות קמצנים!'))
    body=sp['body']
    nul=['-f','lavfi','-t','0.1','-i',f'color=black:s={CW}x{CH}:r={FPS}']
    args=['ffmpeg','-y','-v','error','-i',body,'-framerate',str(FPS),'-i',str(capseq)]+(['-framerate',str(FPS),'-i',str(cardseq)] if cardseq else nul)+\
         (['-framerate',str(FPS),'-i',str(popseq)] if popseq else nul)+['-i',f'{SFX}/whoosh.wav','-i',f'{SFX}/ding.wav','-i',f'{SFX}/boing.wav']
    for m in mon: args+=['-ss',f"{m['t']:.3f}",'-t',f"{m['d']+0.5:.3f}",'-i',sp.get('montage_src',body)]  # montage shots come from anywhere in the FULL body, the main body input may be only its first seconds
    nx=7+len(mon); ix_intro=ix_sub=None
    if brand: args+=['-i',str(intro_mp4)]; ix_intro=nx; nx+=1
    if oldsub: args+=['-framerate',str(subfps),'-i',str(subseq)]; ix_sub=nx; nx+=1
    ix_wout=None
    if woutseq: args+=['-framerate',str(FPS),'-i',str(woutseq)]; ix_wout=nx; nx+=1
    fc=[]; vs=[];as_=[]
    SC=f',scale={W}:{H}:flags=lanczos,setsar=1'  # no-op when body already W x H (e.g. 1080p body)
    for j,m in enumerate(mon):
        fc.append(f"[{7+j}:v]trim=start=0:duration={m['d']},setpts=PTS-STARTPTS,fps=60{SC},format=yuv420p[mv{j}]")
        fc.append(f"[{7+j}:a]atrim=start=0:duration={m['d']},asetpts=PTS-STARTPTS,afade=t=in:d=0.03,afade=t=out:st={m['d']-0.04}:d=0.04[ma{j}]")
    fc.append(''.join(f'[mv{j}]' for j in range(len(mon)))+f'concat=n={len(mon)}:v=1:a=0[mvc]')
    fc.append(''.join(f'[ma{j}]' for j in range(len(mon)))+f'concat=n={len(mon)}:v=0:a=1[mac]')
    fc.append('[1:v]fps=60,format=rgba[capv]')
    fc.append('[mvc][capv]overlay=0:0:eof_action=pass,format=yuv420p[mvo]')
    if use_card: fc.append(f'[2:v]fps=60,scale={W}:{H},format=yuv420p,setsar=1[cv]')
    BD=sp.get('body_dur')  # test only: limit body length
    fc.append(f'[0:v]trim=start={CARD}'+(f':end={BD}' if BD else '')+f',setpts=PTS-STARTPTS{SC},format=yuv420p[bv00]')
    if ix_wout is not None:
        fc.append(f'[{ix_wout}:v]fps=60,format=rgba[wo]')
        fc.append('[bv00][wo]overlay=0:0:eof_action=pass,format=yuv420p[bv0]')
    else: fc.append('[bv00]null[bv0]')
    if oldsub:
        off=SUB_AT-CARD
        fc.append(f'[{ix_sub}:v]format=rgba,setpts=PTS-STARTPTS+{off:.3f}/TB[pv]')
        fc.append(f"[bv0][pv]overlay=0:0:eof_action=pass:enable='between(t,{off:.3f},{off+SUB_SEC:.3f})',format=yuv420p,setsar=1[bvo]")
    else:
        fc.append(f'[3:v]fps=60,scale={W}:{H},format=rgba[pv]')
        fc.append('[bv0][pv]overlay=0:0:eof_action=pass,format=yuv420p,setsar=1[bvo]')
    if brand:
        fc.append(f'[{ix_intro}:v]fps=60,format=yuv420p,setsar=1[iv]')
        fc.append(f'[{ix_intro}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,asetpts=PTS-STARTPTS[ia]')
    fc.append('[mvo]setsar=1[mvs]')
    segs=['[mvs]']+(['[iv]'] if brand else [])+(['[cv]'] if use_card else [])+['[bvo]']
    fc.append(''.join(segs)+f'concat=n={len(segs)}:v=1:a=0[vout]')
    fc.append('[0:a]'+(f'atrim=end={BD},' if BD else '')+'asetpts=PTS-STARTPTS[ba]')
    fc.append(('[mac][ia][ba]concat=n=3' if brand else '[mac][ba]concat=n=2')+':v=0:a=1,aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[amain]')
    # sfx
    sfx=[]
    if ref5: wh=([M-WIPE_IN] if woutseq else [])+([M+I] if woutseq else [])  # ref: silent flash cuts; soft whoosh on wipe in/out
    else: wh=[s for s in starts]+([M+I] if use_card else [])  # card whoosh (intro sting has its own whoosh)
    if wh: fc.append(f'[4:a]aformat=sample_rates=48000:channel_layouts=stereo,volume={0.35 if ref5 else 0.55},asplit={len(wh)}'+''.join(f'[w{k}]' for k in range(len(wh))))
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
    info={'montage_sec':M,'brand_sting':[M,M+I] if brand else None,'card':[M+I,M+I+CARD] if use_card else None,'res':[W,H],'cap_style':cap_style,
          'popup':None if oldsub else [M+I+CARD,M+I+CARD+POP],
          'sub_v2':[M+I+SUB_AT,M+I+SUB_AT+SUB_SEC] if oldsub else None,'cap_y':float(sp.get('cap_y',0.80)),
          'body_offset_in_out':M+I,'note':'output time = montage + sting + body time (for body t>=0)'}
    json.dump(info,open(sp['out']+'.open.json','w'),indent=1); print(json.dumps(info))
if __name__=='__main__': main()
