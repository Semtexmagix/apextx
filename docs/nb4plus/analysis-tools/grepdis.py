# SPDX-License-Identifier: GPL-2.0-only
import sys,capstone,re
d=open(sys.argv[1],'rb').read();b=0x08008000
pat=re.compile(sys.argv[2])
md=capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB|capstone.CS_MODE_MCLASS)
seen=set()
for start in (0,2):
  a=b+start
  while a<b+len(d)-4:
    n=0
    for i in md.disasm(d[a-b:a-b+4096],a):
        s=f"{i.mnemonic} {i.op_str}"
        if pat.search(s) and i.address not in seen:
            seen.add(i.address); print(hex(i.address), s)
        a=i.address+i.size; n+=1
        if a>=b+len(d)-4: break
    if n==0: a+=2
