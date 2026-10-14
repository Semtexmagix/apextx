# SPDX-License-Identifier: GPL-2.0-only
# list calls to target with r0..r3 values tracked over the preceding straight-line code
import sys,struct,capstone,re
d=open(sys.argv[1],'rb').read();b=0x08008000
tgts=[int(x,16) for x in sys.argv[2:]]
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS)
P='ABCDEFGHIJK'
for o in range(0,len(d)-4,2):
    h1,h2=struct.unpack_from('<HH',d,o)
    if not((h1&0xf800)==0xf000 and (h2&0xd000)==0xd000): continue
    S=(h1>>10)&1; imm10=h1&0x3ff; J1=(h2>>13)&1; J2=(h2>>11)&1; imm11=h2&0x7ff
    I1=1-(J1^S); I2=1-(J2^S)
    off=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
    if S: off-=1<<25
    t=b+o+4+off
    if t not in tgts: continue
    c=b+o; ins=None
    for back in range(24,2,-2):
        x=list(md.disasm(d[c-b-back:c-b],c-back))
        if x and sum(i.size for i in x)==back: ins=x;break
    regs={}
    for i in ins or []:
        ops=i.op_str
        m=re.match(r'(r[0-3]), #(0x[0-9a-f]+|\d+)$',ops)
        m2=re.match(r'(r[0-3]), (r[0-3])$',ops)
        if i.mnemonic in('movs','mov','mov.w','movw') and m: regs[m.group(1)]=int(m.group(2),0)
        elif i.mnemonic in('mov','movs') and m2: regs[m2.group(1)]=regs.get(m2.group(2))
        elif i.mnemonic.startswith('bl'): regs={}
        else:
            r=ops.split(',')[0].strip()
            if r in('r0','r1','r2','r3') and not i.mnemonic.startswith(('str','cmp','cb','tst')): regs[r]=None
    p=regs.get('r0'); pin=regs.get('r1'); v=regs.get('r2')
    ps=P[p] if isinstance(p,int) and p<11 else '?'
    print(f"{c:#x} -> {t:#x}  P{ps}{pin if pin is not None else '?'}  r2={v}")
