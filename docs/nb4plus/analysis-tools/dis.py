# SPDX-License-Identifier: GPL-2.0-only
import sys,struct,capstone
d=open(sys.argv[1],'rb').read();b=0x08008000
s=int(sys.argv[2],16);e=int(sys.argv[3],16)
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS)
md.detail=False
a=s
while a<e:
    ok=False
    for i in md.disasm(d[a-b:e-b], a):
        extra=''
        if i.mnemonic.startswith('ldr') and '[pc' in i.op_str:
            try:
                off=int(i.op_str.split('#')[-1].rstrip(']'),0)
                la=((i.address+4)&~3)+off
                extra='  ; ='+hex(struct.unpack_from('<I',d,la-b)[0])
            except Exception: pass
        print(f"{i.address:#x}: {i.mnemonic:8s} {i.op_str}{extra}")
        a=i.address+i.size; ok=True
    if a<e:
        print(f"{a:#x}: .word? {d[a-b:a-b+2].hex()}"); a+=2
