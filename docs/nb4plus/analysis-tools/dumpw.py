# SPDX-License-Identifier: GPL-2.0-only
import sys,struct
d=open(sys.argv[1],'rb').read();b=0x08008000
s=int(sys.argv[2],16);e=int(sys.argv[3],16)
for a in range(s,e,4): print(hex(a), hex(struct.unpack_from('<I',d,a-b)[0]))
