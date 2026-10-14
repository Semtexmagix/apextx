# SPDX-License-Identifier: GPL-2.0-only
import sys,capstone
d=open(sys.argv[1],'rb').read();b=0x08008000
targets=[int(x,16) for x in sys.argv[2:]]
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS)
# scan for BL instructions at every halfword
import struct
res={t:[] for t in targets}
for o in range(0,len(d)-4,2):
    h1,h2=struct.unpack_from('<HH',d,o)
    if (h1&0xf800)==0xf000 and (h2&0xd000)==0xd000:
        S=(h1>>10)&1; imm10=h1&0x3ff; J1=(h2>>13)&1; J2=(h2>>11)&1; imm11=h2&0x7ff
        I1=1-(J1^S); I2=1-(J2^S)
        off=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
        if S: off-=1<<25
        t=b+o+4+off
        if t in res: res[t].append(b+o)
for t,l in res.items(): print(hex(t), ' '.join(hex(x) for x in l))
