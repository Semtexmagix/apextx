# SPDX-License-Identifier: GPL-2.0-only
"""Offline sanity check for an external-NOR backup made with dump_nor.py.

It never touches a radio. It answers "is this dump plausibly a real, correct
FlySky NOR image?" with the evidence available:

1. basic sanity: size, and how much of the image is blank (0xFF) or zero;
2. FlySky resource header: locate the 0x5A5A resource package and verify the
   18-byte header checksum that the stock firmware itself checks;
3. cross-check against the official resource package (resource 901 extracted
   from the FlySky updater with analysis-tools/pe_rsrc.py): if the dump
   contains those exact bytes, that region is proven correct against an
   independent known-good copy;
4. optionally compare two independent full dumps for byte-identity.

What it cannot do: the unit-specific part of the NOR (calibration, models)
has no external reference, so for that part only the dump_nor.py read checks
(each chunk read twice, CRC verified) apply. A backup is only fully proven by
a successful restore, which cannot be rehearsed without writing.

Usage:
  python verify_nor.py dump.bin
  python verify_nor.py dump.bin --resource 10_901_1033
  python verify_nor.py dump.bin --compare dump_second_pass.bin
"""
import argparse
import struct
import sys


def pct(n, total):
    return 100.0 * n / total if total else 0.0


def header_checksum_ok(buf, off):
    """Replicates the stock firmware's resource-header check."""
    if off + 0x14 > len(buf):
        return False
    s = sum(buf[off:off + 0x12]) & 0xFFFF
    stored = struct.unpack_from('<H', buf, off + 0x12)[0]
    return (s ^ 0xFFFF) == stored


def find_resource_headers(buf):
    hits = []
    start = 0
    while True:
        i = buf.find(b'\x5a\x5a', start)
        if i < 0:
            break
        if header_checksum_ok(buf, i):
            hits.append(i)
        start = i + 2
    return hits


def locate(dump, resource):
    """Find where the official resource package sits in the dump.

    Tries several 16 KiB probes (start/quarters) so the package is still
    located even if its first bytes are corrupted; then compares the full
    length at that offset.
    """
    probe_len = min(len(resource), 0x4000)
    for frac in (0.0, 0.25, 0.5, 0.75):
        p = int((len(resource) - probe_len) * frac)
        i = dump.find(resource[p:p + probe_len])
        if i < 0:
            continue
        off = i - p
        if off < 0 or off + len(resource) > len(dump):
            return off, False, 0, 'resource does not fit at the located offset'
        region = dump[off:off + len(resource)]
        diff = sum(1 for a, b in zip(region, resource) if a != b)
        return off, diff == 0, diff, None
    return None


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dump')
    ap.add_argument('--resource', help='official resource package (resource 901)')
    ap.add_argument('--compare', help='a second full dump to compare against')
    args = ap.parse_args()

    dump = open(args.dump, 'rb').read()
    problems = []
    notes = []

    # 1. basic sanity
    ff = dump.count(0xFF)
    zero = dump.count(0x00)
    print(f'size: {len(dump)} bytes ({len(dump) / 1024 / 1024:.2f} MiB)')
    print(f'blank 0xFF: {pct(ff, len(dump)):.1f}%   zero 0x00: {pct(zero, len(dump)):.1f}%')
    if len(dump) == 0 or len(dump) % 0x20000:
        problems.append('size is not a multiple of 128 KiB')
    if pct(ff, len(dump)) > 99 or pct(zero, len(dump)) > 99:
        problems.append('image looks blank/erased')

    # 2. FlySky resource header(s)
    headers = find_resource_headers(dump)
    if headers:
        print(f'FlySky resource header(s) with valid checksum at: '
              + ', '.join(hex(h) for h in headers))
    else:
        notes.append('no 0x5A5A resource header with a valid checksum found '
                     '(the package may be stored differently; use --resource to confirm)')

    # 3. cross-check against the official resource package
    if args.resource:
        resource = open(args.resource, 'rb').read()
        res = locate(dump, resource)
        if res is None:
            problems.append('official resource package not found in the dump')
        else:
            off, identical, diff, err = res
            if err:
                problems.append(err)
            elif identical:
                print(f'VERIFIED: the official resource package ({len(resource)} bytes) '
                      f'is present byte-identical at {off:#x}')
            else:
                problems.append(f'resource package located at {off:#x} but '
                                f'{diff} bytes differ from the official copy')
    else:
        notes.append('no --resource given: content was not cross-checked against a known-good copy')

    # 4. compare two independent dumps
    if args.compare:
        other = open(args.compare, 'rb').read()
        if other == dump:
            print('two independent dumps are byte-identical')
        else:
            n = min(len(dump), len(other))
            first = next((i for i in range(n) if dump[i] != other[i]), n)
            problems.append(f'the two dumps differ (first at {first:#x}; '
                            f'sizes {len(dump)} vs {len(other)})')

    print()
    for s in notes:
        print(f'note: {s}')
    if problems:
        for p in problems:
            print(f'PROBLEM: {p}')
        print('\nResult: NOT OK - do not rely on this backup until resolved.')
        return 1
    print('\nResult: all available checks passed.')
    if not args.resource:
        print('For a content proof, re-run with --resource (see README).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
