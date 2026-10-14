# SPDX-License-Identifier: GPL-2.0-only
import sys
SCK,CS,MOSI=2,4,6
state={SCK:0,CS:1,MOSI:0}
bits=[];frames=[];pcs=set()
for l in open(sys.argv[1]):
    p=l.split()
    if p[0]!='W' or p[2] not in('0x40021018','0x40021014'): continue
    v=int(p[4],16)
    if p[2]=='0x40021014':
        new={k:(v>>k)&1 for k in state}
    else:
        new=dict(state)
        for k in state:
            if v&(1<<k): new[k]=1
            if v&(1<<(k+16)): new[k]=0
    if state[CS]==0 and new[CS]==1 and bits:
        frames.append(bits); bits=[]
    if new[CS]==0 and state[SCK]==0 and new[SCK]==1:
        bits.append(new[MOSI])
    state=new
if bits: frames.append(bits)
print('frames',len(frames),'lens',sorted(set(len(f) for f in frames)))
out=[]
for f in frames:
    for i in range(0,len(f)-8,9):
        w=f[i:i+9]; dc=w[0]; val=int(''.join(map(str,w[1:])),2)
        out.append(('D' if dc else 'C')+f'{val:02X}')
s=' '.join(out)
print(s.replace(' C','\nC')[:4000])
