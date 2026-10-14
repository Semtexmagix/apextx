# SPDX-License-Identifier: GPL-2.0-only
"""End-to-end tests of dump_nor.py against the simulated DFU device.

Runs dump_nor.py exactly as on real hardware, with fake_dfu_util.py standing
in for dfu-util. Usage:
  python test_dump_pipeline.py WORKDIR [--full]
--full additionally backs up the complete 8 MiB (takes ~30 minutes).
"""
import hashlib
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_sim  # noqa: E402


def run_dump(work, name, size, fault=''):
    state = os.path.join(work, 'state_' + name)
    shutil.rmtree(state, ignore_errors=True)
    env = dict(os.environ, FAKE_DFU_STATE=state, FAKE_DFU_NOR=os.path.join(work, 'nor_image.bin'),
               FAKE_DFU_FAULT=fault)
    out = os.path.join(work, name + '.bin')
    if os.path.exists(out):
        os.remove(out)
    fake = f'"{sys.executable}" "{os.path.join(HERE, "fake_dfu_util.py")}"'.replace('\\', '/')
    t = time.time()
    r = subprocess.run([sys.executable, os.path.join(HERE, 'dump_nor.py'), '--dfu-util', fake,
                        '--size', hex(size), '--out', out], env=env, capture_output=True, text=True)
    return r, out, time.time() - t


def main():
    work = os.path.abspath(sys.argv[1])
    full = '--full' in sys.argv
    os.makedirs(work, exist_ok=True)
    image_path = os.path.join(work, 'nor_image.bin')
    if not os.path.exists(image_path):
        open(image_path, 'wb').write(test_sim.make_image())
    image = open(image_path, 'rb').read()
    ok = True

    def report(name, passed, detail):
        nonlocal ok
        ok &= passed
        print(f"[{'OK ' if passed else 'FAIL'}] {name}: {detail}", flush=True)

    r, out, dt = run_dump(work, 'two_chunks', 0x40000)
    good = r.returncode == 0 and open(out, 'rb').read() == image[:0x40000]
    report('2 chunks via simulated DFU', good, f'exit {r.returncode}, data identical={good}, {dt:.0f}s')

    for fault, expect in (('no-start', 'no result from the reader'),
                          ('no-chip', 'no NOR answered'),
                          ('unstable', 'two reads of the chunk differed')):
        r, out, dt = run_dump(work, 'fault_' + fault, 0x20000, fault)
        good = r.returncode == 1 and expect in r.stdout and not os.path.exists(out)
        report(f'fault "{fault}" aborts without a file', good,
               f'exit {r.returncode}, message seen={expect in r.stdout}, file written={os.path.exists(out)}')

    if full:
        r, out, dt = run_dump(work, 'full_8mib', 0x800000)
        data = open(out, 'rb').read() if os.path.exists(out) else b''
        good = r.returncode == 0 and data == image
        report('complete 8 MiB backup', good,
               f'exit {r.returncode}, {len(data)} bytes, identical={good}, '
               f'sha256 {hashlib.sha256(data).hexdigest()}, {dt / 60:.1f} min')
        print(r.stdout[-600:])

    print('ALL PIPELINE TESTS PASSED' if ok else 'SOME PIPELINE TESTS FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
