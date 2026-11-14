"""Cinematic post for a raw Cycles plate: bloom, lens blur, left-dark gradient, vignette, split-tone, grain.
   python post.py in.png out.png"""
import sys, numpy as np
from PIL import Image, ImageFilter
im = Image.open(sys.argv[1]).convert('RGB'); W,H = im.size
a = np.asarray(im).astype(np.float32)/255
# 1) photographic lens blur (hides low-poly flaws); keep a bit of sharpness via mix
blur = np.asarray(im.filter(ImageFilter.GaussianBlur(1.6))).astype(np.float32)/255
a = .55*a + .45*blur
# 2) bloom: threshold highlights -> wide blur -> screen
lum = a.mean(2, keepdims=True)
hi = np.clip(a*(lum>.62), 0, 1)
bl = np.zeros_like(a)
for r,wt in ((6,.5),(18,.35),(48,.25)):
    h = Image.fromarray((hi*255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(r))
    bl += wt*np.asarray(h).astype(np.float32)/255
a = 1-(1-a)*(1-np.clip(bl,0,1)*.9)
# 3) split-tone grade: teal shadows, warm highlights, mild contrast S-curve
l = a.mean(2, keepdims=True)
a = a + (1-l)**2*np.array([-.02,.015,.03]) + l**2*np.array([.04,.015,-.03])
a = np.clip(a,0,1); a = a*a*(3-2*a)*.6 + a*.4
# 4) calm left 45%: darken + desaturate a smooth ramp (portrait zone)
x = np.linspace(0,1,W)[None,:,None]
ramp = np.clip(x/.5,0,1); ramp = ramp*ramp*(3-2*ramp)
k = .52 + .48*ramp                         # 0.52 at far left -> 1.0 at x>=50%
g = a.mean(2,keepdims=True); sat = .6 + .4*ramp
a = (g + (a-g)*sat)*k
# 5) vignette
yy,xx = np.mgrid[0:H,0:W]; d = ((xx-W*.58)/(W*.75))**2 + ((yy-H*.5)/(H*.8))**2
a *= (1-.45*np.clip(d,0,1.2)**1.3)[...,None]
# 6) film grain
rng = np.random.default_rng(3); n = rng.normal(0,.018,(H,W,1)).astype(np.float32)
a = np.clip(a + n*(1.2-a.mean(2,keepdims=True)),0,1)
Image.fromarray((a*255+.5).astype(np.uint8)).save(sys.argv[2])
