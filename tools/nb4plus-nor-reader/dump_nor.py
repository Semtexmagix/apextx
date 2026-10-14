# SPDX-License-Identifier: GPL-2.0-only
"""Backs up the NB4+ external SPI NOR through the STM32 ROM DFU bootloader.

Per 128 KiB chunk:
  1. download parameter block + reader program into SRAM (0x20007F00)
  2. DfuSe "leave" to 0x20008000 -> the reader runs and returns to ROM DFU
  3. upload the result header + data from SRAM (0x2000FF00)
  4. verify magic, status, range, sequence number and both CRC-32 values

Only two fixed SRAM addresses are ever written or read; every dfu-util call
is checked against them before it runs. Internal flash is never written.

Examples:
  python dump_nor.py --dry-run
  python dump_nor.py --dfu-util "C:/tools/dfu-util.exe" --out nor_backup.bin
  python dump_nor.py --dfu-util "python fake_dfu_util.py" ...   (simulation)
"""
import argparse
import hashlib
import os
import shlex
import struct
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_ADDR = 0x20007F00
LOAD_ADDR = 0x20008000
RESULT_ADDR = 0x2000FF00
RESULT_HDR = 0x100
CHUNK = 0x20000
PARAM_MAGIC = 0x4E4F5251
RESULT_MAGIC = 0x4E4F5244
USB_ID = '0483:df11'
ATTEMPTS = 3


class Abort(Exception):
    pass


def load_image(dumper, start, length, flags):
    """Parameter block at 0x20007F00, reader directly behind it at 0x20008000."""
    block = struct.pack('<IIII', PARAM_MAGIC, start, length, flags)
    return block + bytes(LOAD_ADDR - PARAMS_ADDR - len(block)) + dumper


def check_result(blob, start, length, last_seq):
    if len(blob) < RESULT_HDR + length:
        raise Abort(f'short upload ({len(blob)} bytes)')
    magic, status, jedec, r_start, r_len, crc1, crc2, seq = struct.unpack_from('<8I', blob, 0)
    if magic != RESULT_MAGIC:
        raise Abort('no result from the reader (did it start?)')
    if status != 1:
        raise Abort({2: 'reader rejected the parameters',
                     3: 'no NOR answered (JEDEC ID 000000/FFFFFF)',
                     4: 'two reads of the chunk differed'}.get(status, f'status {status}'))
    if (r_start, r_len) != (start, length):
        raise Abort(f'reader reported range {r_start:#x}+{r_len:#x}')
    if last_seq is not None and seq != last_seq + 1:
        raise Abort(f'sequence {seq} does not follow {last_seq} (stale result)')
    data = blob[RESULT_HDR:RESULT_HDR + length]
    crc = zlib.crc32(data)
    if not crc == crc1 == crc2:
        raise Abort(f'CRC mismatch: upload {crc:#010x}, reader {crc1:#010x}/{crc2:#010x}')
    return jedec, seq, data


class Dfu:
    def __init__(self, command, serial, dry_run):
        self.base = shlex.split(command)
        self.serial = serial
        self.dry_run = dry_run

    def run(self, *args, check=True):
        cmd = self.base + ['-d', USB_ID] + (['-S', self.serial] if self.serial else []) + list(args)
        if self.dry_run:
            print('    $', ' '.join(cmd))
            return ''
        r = subprocess.run(cmd, capture_output=True, text=True)
        if check and r.returncode != 0:
            raise Abort(f'dfu-util failed: {(r.stderr or r.stdout).strip()[-300:]}')
        return r.stdout

    def wait_rom_dfu(self, timeout):
        if self.dry_run:
            return
        end = time.time() + timeout
        while time.time() < end:
            out = subprocess.run(self.base + ['-l'], capture_output=True, text=True).stdout
            if USB_ID in out and '@Internal Flash' in out:
                return
            time.sleep(0.5)
        raise Abort('radio is not (back) in STM32 ROM DFU')

    def download(self, addr, path):
        if addr != PARAMS_ADDR:
            raise Abort(f'refusing to write {addr:#x}')
        self.run('-a', '0', '-s', f'{addr:#010x}:force', '-D', path)

    def leave(self, addr):
        if addr != LOAD_ADDR:
            raise Abort(f'refusing to start {addr:#x}')
        # The device disconnects while the reader runs; dfu-util may report that.
        self.run('-a', '0', '-s', f'{addr:#010x}:leave', check=False)

    def upload(self, addr, size, path):
        if addr != RESULT_ADDR or size > RESULT_HDR + CHUNK:
            raise Abort(f'refusing to read {addr:#x}+{size:#x}')
        if os.path.exists(path):
            os.remove(path)
        self.run('-a', '0', '-s', f'{addr:#010x}:{size}:force', '-U', path)
        return b'' if self.dry_run else open(path, 'rb').read()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', default='nor_backup.bin')
    ap.add_argument('--size', type=lambda s: int(s, 0), default=0x800000)
    ap.add_argument('--dumper', default=os.path.join(HERE, 'dumper.bin'))
    ap.add_argument('--dfu-util', default='dfu-util')
    ap.add_argument('--serial')
    ap.add_argument('--reset-fallback', action='store_true',
                    help='reader resets instead of jumping into ROM DFU (keep the DFU button held)')
    ap.add_argument('--dry-run', action='store_true', help='print the commands for the first chunk only')
    args = ap.parse_args()

    if args.size <= 0 or args.size % CHUNK or args.size > 0x1000000:
        sys.exit('size must be a multiple of 128 KiB and at most 16 MiB')
    dumper = open(args.dumper, 'rb').read()
    flags = 1 if args.reset_fallback else 0
    dfu = Dfu(args.dfu_util, args.serial, args.dry_run)
    work = os.path.dirname(os.path.abspath(args.out)) or '.'
    load_path = os.path.join(work, '_nor_load.bin')
    result_path = os.path.join(work, '_nor_result.bin')

    out = bytearray()
    seq = None
    jedec_seen = None
    t0 = time.time()
    try:
        for start in range(0, args.size, CHUNK):
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    with open(load_path, 'wb') as f:
                        f.write(load_image(dumper, start, CHUNK, flags))
                    dfu.wait_rom_dfu(timeout=20)
                    dfu.download(PARAMS_ADDR, load_path)
                    dfu.leave(LOAD_ADDR)
                    dfu.wait_rom_dfu(timeout=60)
                    blob = dfu.upload(RESULT_ADDR, RESULT_HDR + CHUNK, result_path)
                    if args.dry_run:
                        print('dry run: the same three calls repeat for every chunk')
                        return 0
                    jedec, seq, data = check_result(blob, start, CHUNK, seq)
                    if jedec_seen is None:
                        jedec_seen = jedec
                        size_code = jedec & 0xFF
                        cap = 1 << size_code if 0x10 <= size_code <= 0x20 else 0
                        print(f'NOR JEDEC ID {jedec:06x}' + (f', {cap >> 20} MiB' if cap else ''))
                        if cap and cap != args.size:
                            print(f'note: chip reports {cap:#x} bytes, reading {args.size:#x}')
                    elif jedec != jedec_seen:
                        raise Abort(f'JEDEC ID changed to {jedec:06x}')
                    out += data
                    break
                except Abort as e:
                    print(f'  chunk {start:#08x}, attempt {attempt}: {e}', flush=True)
                    seq = None          # a failed attempt may have advanced the reader's counter
                    if attempt == ATTEMPTS:
                        print('aborted: nothing was written to the radio; partial data discarded')
                        return 1
            print(f'  {(start + CHUNK) >> 10:5d} / {args.size >> 10} KiB  ({time.time() - t0:.0f}s)', flush=True)
    finally:
        for p in (load_path, result_path):
            if os.path.exists(p):
                os.remove(p)

    with open(args.out, 'wb') as f:
        f.write(out)
    digest = hashlib.sha256(out).hexdigest()
    with open(args.out + '.sha256', 'w') as f:
        f.write(f'{digest}  {os.path.basename(args.out)}\n')
    print(f'saved {args.out} ({len(out)} bytes), sha256 {digest}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
