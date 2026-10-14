# SPDX-License-Identifier: GPL-2.0-only
import sys,collections
regs=collections.defaultdict(int)
seen=set()
for l in open(sys.argv[1]):
    p=l.split()
    if p[0]!='W': continue
    a=int(p[2],16); sz=int(p[3]); v=int(p[4],16)
    if 0x40020000<=a<0x40022C00:
        base=a&~0x3ff; off=a&0x3ff
        if sz==4: regs[(base,off)]=v
        else:
            sh=(a&3)*8; m=((1<<(8*sz))-1)<<sh
            k=(base,off&~3); regs[k]=(regs[k]&~m)|(v<<sh)
        seen.add(base)
ports='ABCDEFGHIJK'
MODE=['in','out','AF','analog']
for base in sorted(seen):
    pn=ports[(base-0x40020000)//0x400]
    moder=regs[(base,0)]; otyper=regs[(base,4)]; pupd=regs[(base,0xc)]; afl=regs[(base,0x20)]; afh=regs[(base,0x24)]
    row=[]
    for pin in range(16):
        m=(moder>>(2*pin))&3
        if m==0 and ((pupd>>(2*pin))&3)==0: continue
        af=((afl>>(4*pin))&0xf) if pin<8 else ((afh>>(4*(pin-8)))&0xf)
        pu=['','PU','PD','?'][(pupd>>(2*pin))&3]
        s=f"P{pn}{pin}:{MODE[m]}"+(f"{af}" if m==2 else '')+(f",{pu}" if pu else '')+(',OD' if (otyper>>pin)&1 else '')
        row.append(s)
    print(' '.join(row))
