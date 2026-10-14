# SPDX-License-Identifier: GPL-2.0-only
import sys,struct
d=open(sys.argv[1],'rb').read();b=0x08008000
for v in [int(x,0) for x in sys.argv[2:]]:
    hits=[b+o for o in range(0,len(d)-3,2) if struct.unpack_from('<I',d,o)[0]==v]
    print(hex(v), len(hits), ' '.join(hex(h) for h in hits[:20]))
