"""Eitan thumbs C/D: AI scene (GenerateImage w/ real-frame refs, per Maor's new OK) + Heebo Black headline overlay."""
import sys,random
sys.path.insert(0,'/workspace/kick_clipper/thumbs_onetoone')
from common import *
W,H=1280,720
def build(src,out,l1,l2,s1,s2,right,y1,y2,rot,ban_box,seed=7,bcol=(225,28,24,255)):
    img=Image.open(src).convert('RGB').resize((W,H),Image.LANCZOS)
    img=ImageEnhance.Contrast(img).enhance(1.06);img=ImageEnhance.Color(img).enhance(1.08)
    img=img.convert('RGBA')
    T=Image.new('RGBA',(W,H),(0,0,0,0))
    br=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(br);random.seed(seed)
    bx=ImageDraw.Draw(Image.new('L',(1,1))).textbbox((right-10,y2),l2,font=font(s2),anchor='rs',direction='rtl')
    x0,y0,x1,y1b=bx[0]-30,bx[1]-14,min(bx[2]+22,W-6),bx[3]+16
    d.polygon([(x0+20,y0+10),(x1,y0-15),(x1+10,(y0+y1b)//2),(x1-10,y1b),(x0,y1b+10),(x0-15,(y0+y1b)//2)],fill=bcol)
    for i in range(60):
        x=random.randint(x0,x1);y=random.choice([random.randint(y0-15,y0+20),random.randint(y1b-20,y1b+12)])
        d.ellipse((x-18,y-10,x+18,y+10),fill=bcol)
    T=Image.alpha_composite(T,br.filter(ImageFilter.GaussianBlur(1.2)))
    T=Image.alpha_composite(T,text_layer(W,H,l1,s1,(255,255,255),stroke=12,pos=(right,y1),anchor='rs'))
    f=font(s2);Y=text_layer(W,H,l2,s2,(0,0,0),stroke=16,pos=(right-10,y2),anchor='rs')
    mk=Image.new('L',(W,H),0);ImageDraw.Draw(mk).text((right-10,y2),l2,font=f,fill=255,anchor='rs',direction='rtl')
    yy=np.arange(H,dtype=np.float32)[:,None,None];t=np.clip((yy-(y2-s2*0.8))/(s2*0.8),0,1)
    gr=np.zeros((H,W,4),np.uint8);gr[...,:3]=(np.array([255,245,50])*(1-t)+np.array([255,150,10])*t).astype(np.uint8);gr[...,3]=np.asarray(mk)
    T=Image.alpha_composite(T,Image.alpha_composite(Y,Image.fromarray(gr,'RGBA')))
    T=T.rotate(rot,center=((x0+x1)//2,(y1+y2)//2),resample=Image.BICUBIC)
    img=Image.alpha_composite(img,T).convert('RGB').filter(ImageFilter.UnsharpMask(1.0,50,2))
    img.save(out,quality=92,optimize=True)
    img.resize((168,94),Image.LANCZOS).save(out.replace('.jpg','_168.png'))
    print(out)
R='/workspace/kick_clipper/ready/20261111_160407_eitan_nissim_thumb_'
which=sys.argv[1:] or ['c','d']
if 'c' in which: build('gen_c.jpg',R+'c.jpg','איתן התקשר','והתחנן!',104,172,1262,108,272,4,(690,170,1262,330))
if 'd' in which: build('gen_d.jpg',R+'d.jpg','יש לך דקה','לשכנע!',112,190,1262,120,305,5,(720,160,1262,320))
