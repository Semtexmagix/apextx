# SPDX-License-Identifier: GPL-2.0-only
# Emulate STM32F429 firmware boot with Unicorn and log peripheral writes.
# usage: emu.py app.bin out.log [max_instructions]
import sys, struct, collections
from unicorn import *
from unicorn.arm_const import *

app = open(sys.argv[1], 'rb').read()
out = open(sys.argv[2], 'w')
MAXI = int(sys.argv[3]) if len(sys.argv) > 3 else 30_000_000
BASE = 0x08008000
ZERO_FN = int(sys.argv[5],16) if len(sys.argv)>5 else 0x8008244
RT_ENTRY = int(sys.argv[6],16) if len(sys.argv)>6 else 0x80082e8

mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
mu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
mu.mem_map(0x08000000, 0x200000)
mu.mem_write(0x08000000, app)
mu.mem_map(0x00000000, 0x200000)
mu.mem_write(0, app)
mu.mem_map(0x10000000, 0x10000)          # CCM
mu.mem_map(0x20000000, 0x40000)          # SRAM
mu.mem_map(0x1FFF0000, 0x10000)          # system memory / OTP / UID
mu.mem_map(0x40000000, 0x80000)          # APB/AHB1 peripherals
mu.mem_map(0x50000000, 0x60000)          # AHB2 (USB OTG)
mu.mem_map(0xA0000000, 0x1000)           # FMC regs
mu.mem_map(0xC0000000, 0x1000000)        # SDRAM bank1
mu.mem_map(0xD0000000, 0x1000000)        # SDRAM bank2
mu.mem_map(0xE0000000, 0x100000)         # system control space

VT = int(sys.argv[4],16)
sp, rst = struct.unpack_from('<II', app, VT-0x08000000)
mu.reg_write(UC_ARM_REG_SP, sp)

def scatterload(table_ptr_addr):
    o1, o2 = struct.unpack_from('<ii', app, table_ptr_addr - BASE)
    s0 = table_ptr_addr + o1; e0 = table_ptr_addr + o2
    for a in range(s0, e0, 16):
        src, dst, ln, fn = struct.unpack_from('<IIII', app, a - BASE)
        if fn == ZERO_FN:
            mu.mem_write(dst, bytes(ln)); continue
        # ARM __decompress1 (LZ-style RW data)
        i = src - BASE; outb = bytearray()
        while len(outb) < ln:
            c = app[i]; i += 1
            n_lit = c & 7
            if n_lit == 0: n_lit = app[i]; i += 1
            n_run = c >> 4
            if n_run == 0: n_run = app[i]; i += 1
            for _ in range(n_lit - 1): outb.append(app[i]); i += 1
            if c & 8:
                back = app[i]; i += 1; n_run += 2
                for _ in range(n_run): outb.append(outb[len(outb) - back])
            else:
                outb.extend(bytes(n_run))
        mu.mem_write(dst, bytes(outb[:ln]))


writes = []
pc_counts = collections.Counter()
loop_reads = collections.deque(maxlen=64)
bumps = collections.Counter()

def periph(a):
    return 0x40000000 <= a < 0x40080000 or 0x50000000 <= a < 0x50060000 or 0xA0000000 <= a < 0xA0001000

def r32(a):
    return struct.unpack('<I', mu.mem_read(a, 4))[0]

def w32(a, v):
    mu.mem_write(a, struct.pack('<I', v & 0xffffffff))

since_write=[0]
pi_reads=[0]
first_pi=[None]
def hook_write(uc, access, addr, size, value, user):
    if periph(addr): since_write[0]=0
    if periph(addr) or 0xE000E000 <= addr < 0xE000F000:
        pc = uc.reg_read(UC_ARM_REG_PC)
        out.write(f"W {pc:#010x} {addr:#010x} {size} {value & ((1 << (8*size))-1):#x}\n")

def hook_read(uc, access, addr, size, value, user):
    loop_reads.append(addr)
    a = addr & ~3
    # status registers that the firmware polls
    if a == 0x40023800:   # RCC_CR: all RDY bits
        w32(a, r32(a) | 0x2A0A0002)
    elif a == 0x40023808: # RCC_CFGR: SWS mirrors SW
        v = r32(a); w32(a, (v & ~0xC) | ((v & 3) << 2))
    elif a == 0x40023874: # RCC_BDCR LSERDY
        w32(a, r32(a) | 2)
    elif a == 0x40023870 or a == 0x40023874:
        pass
    elif a == 0x40007004: # PWR_CSR VOSRDY/ODRDY/ODSWRDY
        w32(a, r32(a) | (1 << 14) | (1 << 16) | (1 << 17))
    elif 0x40011000 <= a < 0x40011800 or 0x40004400 <= a < 0x40005400 or 0x40007800 <= a < 0x40008000:
        if (a & 0x3ff) == 0: w32(a, r32(a) | 0xC0)  # USART SR TXE|TC
    elif a in (0x40013008, 0x40003808, 0x40003C08, 0x40013408, 0x40015008, 0x40015408):
        w32(a, (r32(a) | 3) & ~0x80)                # SPI SR TXE|RXNE, !BSY
    elif a in (0x40012000, 0x40012100, 0x40012200):
        w32(a, r32(a) | 0x12)                       # ADC SR EOC|STRT
    elif a == 0xA0000158:
        w32(a, r32(a) & ~0x20)                      # FMC SDSR !BUSY
    elif a == 0xE000E018:
        w32(a, (r32(a) - 5000) & 0xFFFFFF)          # SysTick VAL counts down
    elif a in (0x40005414, 0x40005814, 0x40005C14):
        w32(a, r32(a) | 0xC7)                       # I2C SR1 SB|ADDR|BTF|RXNE|TXE
    elif a in (0x40005418, 0x40005818, 0x40005C18):
        w32(a, r32(a) & ~2)                         # I2C SR2 !BUSY
    elif a == 0x40022010:
        pi_reads[0]+=1; v=r32(a)
        if TICKS and first_pi[0] is None: first_pi[0] = r32(TICKS[0])
        pressed = (r32(TICKS[0]) - first_pi[0] < 2600) if TICKS else (pi_reads[0] < 4000)
        w32(a, (v & ~(1<<11)) if pressed else (v | (1<<11)))
    elif a == 0xE0001004:
        w32(a, (r32(a) + 20000) & 0xFFFFFFFF)       # DWT CYCCNT
    elif a == 0xE000E010:
        w32(a, r32(a) | 0x10000)                    # SysTick COUNTFLAG
    elif a == 0x40023C0C:
        w32(a, r32(a) & ~0x10000)                   # FLASH_SR !BSY

import os
TICKS = [int(x,16) for x in os.environ.get('EMU_TICKS','').split(',') if x]
total=[0]
def hook_code(uc, addr, size, user):
    total[0]+=1
    if TICKS and total[0] % 20000 == 0:
        w32(TICKS[0], r32(TICKS[0]) + 1)
        if len(TICKS)>1 and total[0] % 200000 == 0: w32(TICKS[1], r32(TICKS[1]) + 1)
    if total[0] >= MAXI:
        out.write('MAXI reached\n'); uc.emu_stop(); return
    pc_counts[addr] += 1
    n = pc_counts[addr]
    since_write[0]+=1
    if since_write[0] > 3000000 and since_write[0] % 1000000 == 0:
        # stuck loop: bump every RAM word read recently, flip peripheral regs
        seen = set(loop_reads)
        msg = []
        for a in seen:
            a4 = a & ~3
            sp = uc.reg_read(UC_ARM_REG_SP)
            if abs(a4 - sp) < 0x400: continue
            if 0x20000000 <= a4 < 0x20040000 or 0x10000000 <= a4 < 0x10010000:
                w32(a4, r32(a4) + 5000); msg.append(f"ram {a4:#x}")
            elif periph(a4):
                k = bumps[a4]; bumps[a4] += 1
                w32(a4, 0xFFFFFFFF if k % 2 == 0 else 0); msg.append(f"per {a4:#x}->{'ff' if k%2==0 else '0'}")
        out.write(f"STUCK {addr:#010x} n={n} bump: {', '.join(sorted(msg))}\n")
        if since_write[0] >= 12000000:
            out.write(f"GIVEUP {addr:#010x}\n"); uc.emu_stop()

def hook_unmapped(uc, access, addr, size, value, user):
    out.write(f"UNMAPPED acc={access} addr={addr:#x} pc={uc.reg_read(UC_ARM_REG_PC):#x}\n")
    return False
mu.hook_add(UC_HOOK_MEM_UNMAPPED, hook_unmapped)
mu.hook_add(UC_HOOK_MEM_WRITE, hook_write)
mu.hook_add(UC_HOOK_MEM_READ, hook_read)
mu.hook_add(UC_HOOK_CODE, hook_code)
try:
    # find __scatterload table: reset handler jumps to __main; __main+8 is 'adr r0,#imm'
    main_addr = struct.unpack_from('<I', app, (rst & ~1) - BASE + 0x2c)[0] & ~1 if False else None
    mu.mem_write(0xE000ED88, struct.pack('<I', 0xF00000))
    mu.mem_write(0xE000ED08, struct.pack('<I', VT))
    mu.mem_write(0, app[VT-0x08000000:])
    mu.emu_start(rst, 0xFFFFFFFF)
except UcError as e:
    out.write(f"ERROR {e} pc={mu.reg_read(UC_ARM_REG_PC):#x} lr={mu.reg_read(UC_ARM_REG_LR):#x}\n")
out.write(f"END lr={mu.reg_read(UC_ARM_REG_LR):#x} pi_reads={pi_reads[0]} pc={mu.reg_read(UC_ARM_REG_PC):#x} executed_unique={len(pc_counts)}\n")
out.close()
