# SPDX-License-Identifier: GPL-2.0-only
import sys,re
d=open(sys.argv[1],'rb').read();b=0x08008000
pat=re.compile(sys.argv[2].encode(),re.I)
for m in re.finditer(rb'[\x20-\x7e]{4,}',d):
    if pat.search(m.group()): print(hex(b+m.start()), m.group()[:100].decode())
