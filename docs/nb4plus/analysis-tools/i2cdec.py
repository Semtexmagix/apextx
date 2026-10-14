# SPDX-License-Identifier: GPL-2.0-only
import sys,collections
SDA,SCL=7,8
st={SDA:1,SCL:1}; bits=[]; txs=[]; cur=None
for l in open(sys.argv[1]):
    p=l.split()
    if p[0]!='W' or p[2] not in('0x40020418',): continue
    v=int(p[4],16); new=dict(st)
    for k in st:
        if v&(1<<k): new[k]=1
        if v&(1<<(k+16)): new[k]=0
    if st[SCL]==1 and new[SCL]==1 and st[SDA]==1 and new[SDA]==0:  # START
        if cur: txs.append(cur)
        cur=[]; bits=[]
    elif st[SCL]==0 and new[SCL]==1 and cur is not None:
        bits.append(new[SDA])
        if len(bits)==9: cur.append(int(''.join(map(str,bits[:8])),2)); bits=[]
    st=new
if cur: txs.append(cur)
c=collections.Counter(t[0] for t in txs if t)
print('transactions',len(txs),'first bytes',{hex(k):v for k,v in c.items()})
print([ ' '.join(f'{b:02x}' for b in t) for t in txs[:15]])
