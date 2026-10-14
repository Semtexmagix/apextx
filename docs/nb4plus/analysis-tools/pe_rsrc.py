# SPDX-License-Identifier: GPL-2.0-only
import sys, struct, os
d = open(sys.argv[1], 'rb').read(); out = sys.argv[2]
pe = struct.unpack_from('<I', d, 0x3c)[0]
optsz = struct.unpack_from('<H', d, pe+20)[0]; so = pe+24+optsz
nsec = struct.unpack_from('<H', d, pe+6)[0]
secs=[]
for i in range(nsec):
    o=so+i*40; vsz,va,rsz,rptr=struct.unpack_from('<IIII',d,o+8); secs.append((d[o:o+8].rstrip(b'\0'),va,vsz,rptr,rsz))
rs=[s for s in secs if s[0]==b'.rsrc'][0]; base_raw=rs[3]; base_va=rs[1]
def rva2off(r):
    for n,va,vsz,rp,rsz in secs:
        if va<=r<va+max(vsz,rsz): return r-va+rp
def name(off):
    n=struct.unpack_from('<H',d,base_raw+off)[0]
    return d[base_raw+off+2:base_raw+off+2+2*n].decode('utf-16le')
def walk(off, path):
    nn, ni = struct.unpack_from('<HH', d, base_raw+off+12)
    for i in range(nn+ni):
        e = base_raw+off+16+i*8
        nid, ptr = struct.unpack_from('<II', d, e)
        key = name(nid & 0x7fffffff) if nid & 0x80000000 else str(nid)
        if ptr & 0x80000000: walk(ptr & 0x7fffffff, path+[key])
        else:
            r, sz = struct.unpack_from('<II', d, base_raw+ptr)
            o = rva2off(r); blob = d[o:o+sz]
            fn = '_'.join(path+[key]).replace('/','_')
            open(os.path.join(out, fn), 'wb').write(blob)
            print(f"{fn:40s} size={sz:8d} head={blob[:16].hex()}")
walk(0, [])
