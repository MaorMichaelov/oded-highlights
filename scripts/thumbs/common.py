from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
import numpy as np, math
HEEBO='/usr/share/fonts/truetype/sand-box/google/Heebo/Heebo-VariableFont_wght.ttf'
def font(size, var='Black'):
    f=ImageFont.truetype(HEEBO,size,layout_engine=ImageFont.Layout.RAQM)
    try: f.set_variation_by_name(var)
    except Exception: pass
    return f
def text_layer(W,H,txt,size,fill,stroke=10,stroke_fill=(0,0,0),shadow=(8,8),pos=(0,0),anchor='la'):
    L=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(L);f=font(size)
    if shadow:
        S=Image.new('RGBA',(W,H),(0,0,0,0));ds=ImageDraw.Draw(S)
        ds.text((pos[0]+shadow[0],pos[1]+shadow[1]),txt,font=f,fill=(0,0,0,200),stroke_width=stroke,stroke_fill=(0,0,0,200),direction='rtl',anchor=anchor)
        S=S.filter(ImageFilter.GaussianBlur(6));L=Image.alpha_composite(L,S);d=ImageDraw.Draw(L)
    d.text(pos,txt,font=f,fill=fill,stroke_width=stroke,stroke_fill=stroke_fill,direction='rtl',anchor=anchor)
    return L
def bbox(txt,size):
    f=font(size);return ImageDraw.Draw(Image.new('L',(1,1))).textbbox((0,0),txt,font=f,direction='rtl')
def curved_arrow(W,H,p0,p1,p2,width=34,head=70,color=(235,40,35),outline=(20,0,0),ow=7):
    L=Image.new('RGBA',(W,H),(0,0,0,0));d=ImageDraw.Draw(L)
    pts=[]
    for i in range(41):
        t=i/40;x=(1-t)**2*p0[0]+2*(1-t)*t*p1[0]+t*t*p2[0];y=(1-t)**2*p0[1]+2*(1-t)*t*p1[1]+t*t*p2[1];pts.append((x,y))
    # stop shaft before head
    ex,ey=pts[-1];bx,by=pts[-4];ang=math.atan2(ey-by,ex-bx)
    shaft=pts[:-3]
    def poly(wd):
        left=[];right=[]
        for i in range(len(shaft)):
            a=shaft[min(i+1,len(shaft)-1)];b=shaft[max(i-1,0)];g=math.atan2(a[1]-b[1],a[0]-b[0])
            w=wd*(0.55+0.45*i/len(shaft))
            left.append((shaft[i][0]+w/2*math.sin(g),shaft[i][1]-w/2*math.cos(g)));right.append((shaft[i][0]-w/2*math.sin(g),shaft[i][1]+w/2*math.cos(g)))
        return left+right[::-1]
    hx,hy=shaft[-1]
    def headp(h,wd):
        tip=(hx+h*math.cos(ang),hy+h*math.sin(ang))
        return [tip,(hx+wd*math.sin(ang),hy-wd*math.cos(ang)),(hx-wd*math.sin(ang),hy+wd*math.cos(ang))]
    d.polygon(poly(width+2*ow),fill=outline);d.polygon(headp(head+ow*1.6,head*0.75+ow),fill=outline)
    d.polygon(poly(width),fill=color);d.polygon(headp(head,head*0.75),fill=color)
    return L
def save(img,path):
    img.convert('RGB').save(path,quality=92,optimize=True)
