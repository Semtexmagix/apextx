# SPDX-License-Identifier: GPL-2.0-only
import sys,struct,capstone,re
d=open(sys.argv[1],'rb').read();b=0x08008000
tgt=int(sys.argv[2],16)
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS)
calls=[]
for o in range(0,len(d)-4,2):
    h1,h2=struct.unpack_from('<HH',d,o)
    if (h1&0xf800)==0xf000 and (h2&0xd000)==0xd000:
        S=(h1>>10)&1; imm10=h1&0x3ff; J1=(h2>>13)&1; J2=(h2>>11)&1; imm11=h2&0x7ff
        I1=1-(J1^S); I2=1-(J2^S)
        off=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
        if S: off-=1<<25
        if b+o+4+off==tgt: calls.append(b+o)
for c in calls:
    best=None
    for back in range(40,4,-2):
        ins=list(md.disasm(d[c-b-back:c-b],c-back))
        if ins and ins[-1].address+ins[-1].size==c and sum(i.size for i in ins)==back: best=ins;break
    regs={}
    for i in best or []:
        m=re.match(r'(r[0-3]), #(0x[0-9a-f]+|\d+)$',i.op_str)
        if i.mnemonic in('movs','mov','mov.w','movw') and m: regs[m.group(1)]=int(m.group(2),0)
        elif re.match(r'(r[0-3]),',i.op_str):
            r=i.op_str.split(',')[0]
            if i.mnemonic not in('str','strb','strh','cmp','cbz','cbnz'): regs.pop(r,None)
    print(f"{c:#x} a={regs.get('r0','?')} b={regs.get('r1','?')} type={regs.get('r2','?')} cmd={regs.get('r3','?')}")
