# SPDX-License-Identifier: GPL-2.0-only
"""Emulates the RAM-only NOR reader against a simulated SPI NOR chip.

The emulated STM32 provides only what the reader uses: SRAM, the GPIO/RCC/
SYSCFG registers, the system control block and a stub ROM bootloader at
0x1FFF0000 whose entry ends the run. Every peripheral write and every SPI
command is recorded so the tests can check the reader's behaviour.
"""
import struct
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS, UcError
from unicorn import UC_HOOK_MEM_WRITE, UC_HOOK_MEM_READ, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_SP, UC_ARM_REG_PC, UC_CPU_ARM_CORTEX_M4

LOAD = 0x20008000
PARAMS = 0x20007F00
RESULT = 0x2000FF00
BUFFER = 0x20010000
ROM_STUB = 0x1FFF0100
GPIOG = 0x40021800
GPIOI = 0x40022000
PIN_CS, PIN_MISO, PIN_SCK, PIN_MOSI = 6, 12, 13, 14


class NorModel:
    """SPI mode-0 NOR: answers 0x9F and 0x03, records every command byte."""

    def __init__(self, image, jedec=0xEF4017, dead=False, flip_on_second_read=False):
        self.image = image
        self.jedec = jedec
        self.dead = dead
        self.flip = flip_on_second_read
        self.commands = []
        self.reads = 0
        self.selected = False

    def select(self):
        self.selected = True
        self.rx_bits = 0
        self.rx = 0
        self.cmd = None
        self.addr = 0
        self.edges = 0

    def deselect(self):
        self.selected = False

    def rising_edge(self, mosi):
        if not self.selected:
            return
        self.edges += 1
        self.rx = ((self.rx << 1) | mosi) & 0xFF
        self.rx_bits += 1
        if self.rx_bits == 8:
            self.rx_bits = 0
            if self.cmd is None:
                self.cmd = self.rx
                self.commands.append(self.rx)
                if self.cmd == 0x03:
                    self.reads += 1
            elif self.cmd == 0x03 and self.edges <= 32:
                self.addr = (self.addr << 8) | self.rx

    def miso(self):
        """Bit presented while SCK is high after the current rising edge."""
        if self.dead or not self.selected or self.cmd is None:
            return 1
        if self.cmd == 0x9F:
            k = self.edges - 8 - 1
            if k < 0 or k >= 24:
                return 1
            return (self.jedec >> (23 - k)) & 1
        if self.cmd == 0x03:
            k = self.edges - 32 - 1
            if k < 0:
                return 1
            byte_index = self.addr + k // 8
            b = self.image[byte_index % len(self.image)]
            if self.flip and self.reads == 2 and byte_index == self.addr + 5:
                b ^= 0x10
            return (b >> (7 - k % 8)) & 1
        return 1


SRAM_SIZE = 0x30000


def run(dumper_bin, nor, start=0, length=0, flags=0, magic=0x4E4F5251, sram=None):
    mu = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    mu.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M4)
    mu.mem_map(0x08000000, 0x200000)       # internal flash (must never be written)
    mu.mem_map(0x1FFF0000, 0x10000)        # ROM bootloader stub
    mu.mem_map(0x20000000, 0x30000)        # SRAM1..3
    mu.mem_map(0x40000000, 0x80000)        # peripherals
    mu.mem_map(0xE0000000, 0x100000)       # system control space

    mu.mem_write(0x1FFF0000, struct.pack('<II', 0x20002000, ROM_STUB | 1))
    mu.mem_write(ROM_STUB, b'\xfe\xe7')    # b .
    if sram is not None:
        # Device-style run: SRAM already holds parameters and program.
        mu.mem_write(0x20000000, sram)
        dumper_bin = bytes(mu.mem_read(LOAD, 8))
    else:
        mu.mem_write(LOAD, dumper_bin)
        mu.mem_write(PARAMS, struct.pack('<IIII', magic, start, length, flags))
    mu.mem_write(0x40023808, struct.pack('<I', 0x0000000A))  # CFGR: running on PLL

    st = {'cs': 1, 'sck': 0, 'mosi': 0}
    log = {'writes': [], 'end': None, 'flash_writes': 0}

    def r32(a):
        return struct.unpack('<I', mu.mem_read(a, 4))[0]

    def apply_pin(pin, val):
        if pin == PIN_CS:
            if st['cs'] == 1 and val == 0:
                nor.select()
            elif st['cs'] == 0 and val == 1:
                nor.deselect()
            st['cs'] = val
        elif pin == PIN_SCK:
            if st['sck'] == 0 and val == 1:
                nor.rising_edge(st['mosi'])
            st['sck'] = val
        elif pin == PIN_MOSI:
            st['mosi'] = val

    def on_write(uc, access, addr, size, value, user):
        if 0x08000000 <= addr < 0x08200000:
            log['flash_writes'] += 1
            return
        log['writes'].append((addr, value))
        if addr == GPIOG + 0x18:
            for pin in (PIN_CS, PIN_SCK, PIN_MOSI):
                if value & (1 << (pin + 16)):
                    apply_pin(pin, 0)
                if value & (1 << pin):
                    apply_pin(pin, 1)
        elif addr == 0xE000ED0C and (value & 0xFFFF0004) == 0x05FA0004:
            log['end'] = 'system_reset'
            uc.emu_stop()

    def on_read(uc, access, addr, size, value, user):
        a = addr & ~3
        if a == GPIOG + 0x10:
            v = r32(a) & ~(1 << PIN_MISO)
            mu.mem_write(a, struct.pack('<I', v | (nor.miso() << PIN_MISO)))
        elif a == 0x40023800:
            mu.mem_write(a, struct.pack('<I', r32(a) | 2))           # HSIRDY
        elif a == 0x40023808:
            v = r32(a)
            mu.mem_write(a, struct.pack('<I', (v & ~0xC) | ((v & 3) << 2)))

    def on_rom(uc, addr, size, user):
        log['end'] = 'rom_dfu'
        log['rom_sp'] = uc.reg_read(UC_ARM_REG_SP)
        uc.emu_stop()

    mu.hook_add(UC_HOOK_MEM_WRITE, on_write, begin=0x08000000, end=0x081FFFFF)
    mu.hook_add(UC_HOOK_MEM_WRITE, on_write, begin=0x40000000, end=0x4007FFFF)
    mu.hook_add(UC_HOOK_MEM_WRITE, on_write, begin=0xE0000000, end=0xE00FFFFF)
    mu.hook_add(UC_HOOK_MEM_READ, on_read, begin=0x40000000, end=0x4007FFFF)
    mu.hook_add(UC_HOOK_CODE, on_rom, begin=ROM_STUB, end=ROM_STUB + 1)

    sp, pc = struct.unpack('<II', dumper_bin[:8])
    mu.reg_write(UC_ARM_REG_SP, sp)
    try:
        mu.emu_start(pc, 0xFFFFFFFF, count=0)
    except UcError as e:
        log['end'] = f'crash: {e} pc={mu.reg_read(UC_ARM_REG_PC):#x}'

    hdr = struct.unpack('<8I', mu.mem_read(RESULT, 32))
    result = dict(zip(('magic', 'status', 'jedec', 'start', 'length',
                       'crc_first', 'crc_second', 'seq'), hdr))
    data = bytes(mu.mem_read(BUFFER, length)) if 0 < length <= 0x20000 else b''
    log['params_magic_after'] = struct.unpack('<I', mu.mem_read(PARAMS, 4))[0]
    log['pins'] = st
    log['sram'] = bytes(mu.mem_read(0x20000000, SRAM_SIZE))
    return result, data, log
