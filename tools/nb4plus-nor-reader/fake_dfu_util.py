# SPDX-License-Identifier: GPL-2.0-only
"""Stand-in for dfu-util that behaves like an NB4+ in STM32 ROM DFU.

It understands only the calls dump_nor.py makes (-l, -D, -U, -s ...:force,
-s ...:leave) and keeps the device SRAM in a state file between calls. A
"leave" runs the reader program from that SRAM in the emulator against a
simulated SPI NOR. Like the real ROM bootloader assumption, writes below
0x20004000 (bootloader RAM) and anywhere outside SRAM are refused.

Environment: FAKE_DFU_STATE (directory), FAKE_DFU_NOR (NOR image file),
optional FAKE_DFU_FAULT = no-start | no-chip | unstable for fault injection.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sim  # noqa: E402

SRAM_BASE = 0x20000000
BOOT_RAM_END = 0x20004000


def fail(msg):
    print(f'dfu-util (fake): {msg}', file=sys.stderr)
    sys.exit(74)


def main():
    args = sys.argv[1:]
    state = os.environ['FAKE_DFU_STATE']
    ram_file = os.path.join(state, 'sram.bin')
    os.makedirs(state, exist_ok=True)
    ram = bytearray(open(ram_file, 'rb').read()) if os.path.exists(ram_file) else bytearray(sim.SRAM_SIZE)

    if '-l' in args:
        print('Found DFU: [0483:df11] ver=2200, devnum=1, cfg=1, intf=0, path="1-1", alt=0, '
              'name="@Internal Flash  /0x08000000/04*016Kg,01*064Kg,07*128Kg", serial="SIMULATED"')
        return 0

    spec = args[args.index('-s') + 1] if '-s' in args else None
    if spec is None:
        fail('missing -s')
    parts = spec.split(':')
    addr = int(parts[0], 16)
    mods = parts[1:]

    if '-D' in args:
        if 'force' not in mods:
            fail(f'Page at {addr:#x} can not be written (no :force)')
        data = open(args[args.index('-D') + 1], 'rb').read()
        if not (BOOT_RAM_END <= addr and addr + len(data) <= SRAM_BASE + sim.SRAM_SIZE):
            fail(f'refusing download to {addr:#x}+{len(data):#x}')
        off = addr - SRAM_BASE
        ram[off:off + len(data)] = data
    elif '-U' in args:
        size = int(mods[0], 0)
        if not (SRAM_BASE <= addr and addr + size <= SRAM_BASE + sim.SRAM_SIZE):
            fail(f'refusing upload from {addr:#x}')
        off = addr - SRAM_BASE
        open(args[args.index('-U') + 1], 'wb').write(ram[off:off + size])
    elif mods == ['leave']:
        if addr != 0x20008000:
            fail(f'unexpected leave address {addr:#x}')
        fault = os.environ.get('FAKE_DFU_FAULT', '')
        if fault == 'no-start':
            return 0                      # program never runs, SRAM unchanged
        nor = sim.NorModel(open(os.environ['FAKE_DFU_NOR'], 'rb').read(),
                           dead=(fault == 'no-chip'),
                           flip_on_second_read=(fault == 'unstable'))
        _res, _data, log = sim.run(None, nor, sram=bytes(ram))
        bad = [c for c in nor.commands if c not in (0x9F, 0x03)]
        if bad or log['flash_writes']:
            fail(f'UNSAFE: NOR commands {bad}, flash writes {log["flash_writes"]}')
        if log['end'] not in ('rom_dfu', 'system_reset'):
            fail(f'reader did not return to DFU: {log["end"]}')
        ram = bytearray(log['sram'])
    else:
        fail(f'unsupported call: {args}')

    open(ram_file, 'wb').write(ram)
    return 0


if __name__ == '__main__':
    sys.exit(main())
