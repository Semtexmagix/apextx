# SPDX-License-Identifier: GPL-2.0-only
import sys,struct,os
for f in sys.argv[1:]:
    d=open(f,'rb').read()
    pat=bytes([7,10,0,0])+struct.pack('<I',0x1000)
    i=d.find(pat)
    print(os.path.basename(f), hex(0x08008000+i) if i>=0 else None)
    if i>=0:
        for k in range(6):
            p,pin,_,_,m=struct.unpack_from('<BBBBI',d,i+8*k)
            if p>10 or m==0: break
            print('  P'+'ABCDEFGHIJK'[p]+str(pin), hex(m))
