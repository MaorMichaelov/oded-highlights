"""Download a Poly Haven model (glTF, 1k) -> dir. usage: ph_get.py asset_id outdir"""
import sys, os, json, urllib.request
aid, out = sys.argv[1], sys.argv[2]
H={'User-Agent':'plate-pipeline'}
rq=lambda u: urllib.request.urlopen(urllib.request.Request(u,headers=H),timeout=60).read()
f=json.loads(rq(f'https://api.polyhaven.com/files/{aid}'))['gltf']['1k']['gltf']
os.makedirs(out,exist_ok=True)
open(f'{out}/{aid}.gltf','wb').write(rq(f['url']))
for rel,i in f['include'].items():
    p=os.path.join(out,rel); os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'wb').write(rq(i['url']))
print('ok',aid,sum(i['size'] for i in f['include'].values())//1024,'KB textures')
