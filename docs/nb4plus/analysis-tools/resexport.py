# SPDX-License-Identifier: GPL-2.0-only
# Export all images of a FlySky Noble resource package (loaded at 0xC0280000) as PNG.
import sys,struct,os,json
from PIL import Image
src,outdir=sys.argv[1],sys.argv[2]
d=open(src,'rb').read(); B=0xC0280000
os.makedirs(outdir,exist_ok=True)
assert d[:2]==b'ZZ'
# top-level table entries at 0x14: (ptrA,count,ptrB) x3 ; images = entry with largest count
tabs=[struct.unpack_from('<III',d,0x14+12*k) for k in range(3)]
imgtab=max(tabs,key=lambda t:t[1])
n=imgtab[1]; idx=imgtab[2]-B
meta=[]
for k in range(n):
    i,p=struct.unpack_from('<II',d,idx+8*k)
    if not(B<=p<B+len(d)): continue
    w,h,key,dp=struct.unpack_from('<IIII',d,p-B)
    o=dp-B
    if not(0<w<=1024 and 0<h<=1024 and 0<=o and o+w*h*2<=len(d)): meta.append(dict(id=i,bad=True)); continue
    px=struct.unpack_from(f'<{w*h}H',d,o)
    im=Image.new('RGBA',(w,h))
    im.putdata([(((v>>11)&31)*255//31,((v>>5)&63)*255//63,(v&31)*255//31,0 if (key and v==key) else 255) for v in px])
    fn=f'img_{i:03d}_{w}x{h}.png'; im.save(os.path.join(outdir,fn))
    meta.append(dict(id=i,w=w,h=h,key=key,file=fn))
json.dump(meta,open(os.path.join(outdir,'meta.json'),'w'))
print('tables',[(hex(a),c,hex(b)) for a,c,b in tabs],'exported',sum(1 for m in meta if 'file' in m),'bad',sum(1 for m in meta if m.get('bad')))
