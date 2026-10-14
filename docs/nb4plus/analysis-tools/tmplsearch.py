# SPDX-License-Identifier: GPL-2.0-only
import sys,re
d=open(sys.argv[1],'rb').read();b=0x08008000
src=open(sys.argv[2],encoding='utf-8').read()
m=re.search(r'nb4DefaultReceiver\[168\] = \{(.*?)\};',src,re.S)
t=bytes(int(x,16) for x in re.findall(r'0x([0-9a-fA-F]{2})',m.group(1)))
print('template len',len(t))
# search nonzero chunks
for start in range(0,len(t)-12,4):
    chunk=t[start:start+12]
    if chunk.count(0)>8: continue
    hits=[m.start() for m in re.finditer(re.escape(chunk),d)]
    if hits: print(f"tmpl[{start:#x}:{start+12:#x}] {chunk.hex()} -> "+' '.join(hex(b+h-start) for h in hits[:5]))
