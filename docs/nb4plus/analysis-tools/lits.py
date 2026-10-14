# SPDX-License-Identifier: GPL-2.0-only
import sys, struct
d=open(sys.argv[1],'rb').read()
base=0x08008000
periph={'USART1':0x40011000,'USART2':0x40004400,'USART3':0x40004800,'UART4':0x40004C00,'UART5':0x40005000,'USART6':0x40011400,'UART7':0x40007800,'UART8':0x40007C00,
'SPI1':0x40013000,'SPI2':0x40003800,'SPI3':0x40003C00,'SPI4':0x40013400,'SPI5':0x40015000,'SPI6':0x40015400,
'DMA1':0x40026000,'DMA2':0x40026400}
for i in range(10): periph['GPIO'+'ABCDEFGHIJK'[i]]=0x40020000+0x400*i
words=[struct.unpack_from('<I',d,o)[0] for o in range(0,len(d)-3,4)]
for n,a in periph.items():
    hits=[base+o*4 for o,w in enumerate(words) if a<=w<a+0x30]
    print(f"{n:7s} {a:#x} refs={len(hits):3d} ", ' '.join(hex(h) for h in hits[:12]))
v=struct.unpack_from('<II',d,0); print('SP/Reset',hex(v[0]),hex(v[1]))
