# SPDX-License-Identifier: GPL-2.0-only
"""Safety and correctness tests for the NOR reader, run entirely in emulation."""
import random
import sys
import time
import zlib

import sim

ALLOWED_WRITE_REGIONS = [
    (0x40023800, 0x40023900),   # RCC
    (0x40013800, 0x40013804),   # SYSCFG_MEMRMP
    (0x40021800, 0x40021C00),   # GPIOG
    (0x40022000, 0x40022400),   # GPIOI
    (0xE000E010, 0xE000E014),   # SysTick CSR
    (0xE000E180, 0xE000E1A0),   # NVIC ICER
    (0xE000E280, 0xE000E2A0),   # NVIC ICPR
    (0xE000ED08, 0xE000ED10),   # VTOR, AIRCR
]
ALLOWED_PINS = {('G', 6), ('G', 12), ('G', 13), ('G', 14), ('I', 14)}


def make_image(size=0x800000):
    rnd = random.Random(1234)
    img = bytearray(rnd.getrandbits(8) for _ in range(size))
    img[0:16] = b'NB4PLUS-SIM-NOR!'
    return bytes(img)


def touched_pins(writes):
    pins = set()
    for addr, value in writes:
        for port, base in (('G', 0x40021800), ('I', 0x40022000)):
            if addr == base + 0x18:
                for pin in range(16):
                    if value & ((1 << pin) | (1 << (pin + 16))):
                        pins.add((port, pin))
            elif addr in (base + 0x00, base + 0x0C):
                pass  # mode/pull registers are checked via the read-modify-write values below
    return pins


def mode_changes(writes, before):
    """Pins whose MODER/PUPDR field changed relative to the previous value."""
    changed = set()
    last = dict(before)
    for addr, value in writes:
        for port, base in (('G', 0x40021800), ('I', 0x40022000)):
            for off in (0x00, 0x0C):
                if addr == base + off:
                    prev = last.get(addr, 0)
                    for pin in range(16):
                        if ((prev ^ value) >> (2 * pin)) & 3:
                            changed.add((port, pin))
                    last[addr] = value
    return changed


def check_common(name, log, nor, expect_end='rom_dfu'):
    problems = []
    if log['end'] != expect_end:
        problems.append(f"end={log['end']} (expected {expect_end})")
    if log['flash_writes']:
        problems.append(f"{log['flash_writes']} writes to internal flash")
    bad = [hex(a) for a, _ in log['writes']
           if not any(lo <= a < hi for lo, hi in ALLOWED_WRITE_REGIONS)]
    if bad:
        problems.append(f'writes outside allowed registers: {sorted(set(bad))[:8]}')
    forbidden = [c for c in nor.commands if c not in (0x9F, 0x03)]
    if forbidden:
        problems.append(f'forbidden NOR commands: {[hex(c) for c in forbidden]}')
    pins = touched_pins(log['writes']) | mode_changes(log['writes'], {})
    if not pins <= ALLOWED_PINS:
        problems.append(f'unexpected pins: {sorted(pins - ALLOWED_PINS)}')
    if log['params_magic_after'] != 0:
        problems.append('parameter block not invalidated')
    print(f"[{'OK ' if not problems else 'FAIL'}] {name}" + ('' if not problems else ': ' + '; '.join(problems)))
    return not problems


def main():
    dumper = open(sys.argv[1] if len(sys.argv) > 1 else 'dumper.bin', 'rb').read()
    image = make_image()
    ok = True

    # 1. small read at the start, speed probe
    nor = sim.NorModel(image)
    t = time.time()
    res, data, log = sim.run(dumper, nor, 0, 4096)
    dt = time.time() - t
    good = res['status'] == 1 and data == image[:4096] and res['crc_first'] == zlib.crc32(image[:4096])
    ok &= check_common('4 KiB at 0x000000', log, nor) and good
    print(f'      status={res["status"]} jedec={res["jedec"]:#08x} data_ok={data == image[:4096]} '
          f'crc_ok={res["crc_first"] == zlib.crc32(image[:4096])} reads={nor.reads} commands={[hex(c) for c in nor.commands]} ({dt:.1f}s)')

    # 2. full 128 KiB chunk at the very end of the 8 MiB chip
    start = 0x800000 - 0x20000
    nor = sim.NorModel(image)
    t = time.time()
    res, data, log = sim.run(dumper, nor, start, 0x20000)
    good = res['status'] == 1 and data == image[start:] and res['crc_first'] == res['crc_second'] == zlib.crc32(image[start:])
    ok &= check_common('128 KiB at 0x7E0000 (last chunk)', log, nor) and good
    print(f'      status={res["status"]} data_ok={data == image[start:]} crc_ok={good} ({time.time() - t:.1f}s)')

    # 3. invalid parameters must not touch the NOR at all
    for desc, args in (('wrong magic', dict(start=0, length=16, magic=0x12345678)),
                       ('length 0', dict(start=0, length=0)),
                       ('length > 128 KiB', dict(start=0, length=0x20001)),
                       ('start beyond 16 MiB', dict(start=0x1000000, length=16)),
                       ('range crosses 16 MiB', dict(start=0xFFFFF0, length=0x20))):
        nor = sim.NorModel(image)
        res, data, log = sim.run(dumper, nor, **args)
        good = res['status'] == 2 and not nor.commands and not any(
            0x40021800 <= a < 0x40022400 for a, _ in log['writes'])
        ok &= check_common(f'rejects {desc}', log, nor) and good
        if not good:
            print(f'      status={res["status"]} commands={nor.commands}')

    # 4. no chip answering (MISO stays high) -> no READ is issued
    nor = sim.NorModel(image, dead=True)
    res, data, log = sim.run(dumper, nor, 0, 64)
    good = res['status'] == 3 and nor.commands == [0x9F]
    ok &= check_common('no flash detected', log, nor) and good
    print(f'      status={res["status"]} jedec={res["jedec"]:#x} commands={[hex(c) for c in nor.commands]}')

    # 5. unstable read is reported, not silently accepted
    nor = sim.NorModel(image, flip_on_second_read=True)
    res, data, log = sim.run(dumper, nor, 0x1000, 256)
    good = res['status'] == 4 and res['crc_first'] != res['crc_second']
    ok &= check_common('detects read mismatch', log, nor) and good
    print(f'      status={res["status"]}')

    # 6. fallback: system reset instead of jumping into ROM DFU
    nor = sim.NorModel(image)
    res, data, log = sim.run(dumper, nor, 0, 64, flags=1)
    good = res['status'] == 1 and data == image[:64]
    ok &= check_common('reset fallback', log, nor, expect_end='system_reset') and good

    print('ALL TESTS PASSED' if ok else 'SOME TESTS FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
