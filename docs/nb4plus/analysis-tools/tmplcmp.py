# SPDX-License-Identifier: GPL-2.0-only
import sys,re
d=open(sys.argv[1],'rb').read();b=0x08008000
src=open(sys.argv[2],encoding='utf-8').read()
m=re.search(r'nb4DefaultReceiver\[168\] = \{(.*?)\};',src,re.S)
t=bytearray(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',m.group(1)))
te=bytearray(t); te[0x3a]=0x19; te[0x3d]=1; te[0x40]=1; te[0x8b]=0x30
for name,addr in [(n,int(a,16)) for n,a in zip("AB",sys.argv[3:5])] if len(sys.argv)>4 else (("A",0x8092924),("B",0x80929cc)):
    f=d[addr-b:addr-b+168]
    for tn,tt in (('normal',t),('enhanced',te)):
        diff=[i for i in range(168) if f[i]!=tt[i]]
        print(f"{name}@{addr:#x} vs ApexTX {tn}: {len(diff)} diffs", ' '.join(f"[{i:#x}] fw={f[i]:#04x} apx={tt[i]:#04x}" for i in diff[:12]))
print('gap between tables', 0x80929cc-0x8092924)
print('before A:', d[0x8092924-b-16:0x8092924-b].hex())
