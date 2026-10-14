# NB4+ work: tests and results

All results below come from builds, static analysis and CPU emulation.
**Nothing has been run on a real NB4+ yet.**

## 1. Firmware build (`NB4_PLUS_HW=ON`)

| Check | Result | Evidence |
|---|---|---|
| Builds with arm-none-eabi-gcc 14.2.rel1 (Release) | OK, flash 1725.91 KiB (84.27 %) | [verification/build_summary.txt](verification/build_summary.txt) |
| ApexTX image manifest check (`tools/apextx-updater.py --check`) | `Valid NB4 firmware image` | [verification/build_summary.txt](verification/build_summary.txt) |
| Preprocessor macros, NB4 build vs NB4+ build | only the haptic macros differ | [verification/macro_diff_nb4_vs_nb4plus.txt](verification/macro_diff_nb4_vs_nb4plus.txt) |
| GPIO pins used by the NB4+ build | listed; all match stock NB4+ usage or belong to features inactive on the NB4 target | [verification/gpio_pins_nb4plus_build.txt](verification/gpio_pins_nb4plus_build.txt) |
| Stock start-up pin configuration NB4 vs NB4+ (emulated) | identical except haptic (PA8 vs PB0) | [verification/stock_boot_pins_nb4.txt](verification/stock_boot_pins_nb4.txt), [verification/stock_boot_pins_nb4plus.txt](verification/stock_boot_pins_nb4plus.txt) |

The firmware itself could not be fully booted in the emulator (no interrupt
model, so it stops at the power-button qualification); the pin check therefore
uses the compiler's macro set instead.

## 2. NOR reader – unit tests (`tools/nb4plus-nor-reader/test_sim.py`)

Reader binary sha256 `e66d541bdd94ed70158abb62625717593c01e220ad65bbd9e6f3f734c08dd38d`
(built with `build.sh`, `-O0`, no IT blocks).

| Test | Result |
|---|---|
| 4 KiB at 0x000000: data and CRC | OK |
| 128 KiB at 0x7E0000 (last chunk of 8 MiB): data and both CRCs | OK |
| rejects wrong magic / length 0 / length > 128 KiB / start ≥ 16 MiB / range crossing 16 MiB, without touching the NOR | OK (5 tests) |
| no chip (MISO high, JEDEC FFFFFF): status 3, no READ issued | OK |
| unstable second read: status 4 | OK |
| reset fallback instead of jump to ROM DFU | OK |
| every test: no internal-flash write, only allowed registers and pins, only NOR commands 0x9F/0x03 | OK |

Log: [../../tools/nb4plus-nor-reader/results/test_sim.log](../../tools/nb4plus-nor-reader/results/test_sim.log)

## 3. NOR reader – end-to-end pipeline (`test_dump_pipeline.py`)

`dump_nor.py` was run exactly as it would be on hardware, with
`fake_dfu_util.py` standing in for `dfu-util` (simulated ROM DFU device whose
"leave" runs the reader in the emulator against a simulated 8 MiB SPI NOR,
JEDEC ID EF4017).

| Test | Result |
|---|---|
| 2 chunks (256 KiB) | OK, byte-identical |
| fault: reader never starts | aborts with "no result from the reader", no output file |
| fault: no NOR answers | aborts with "no NOR answered", no output file |
| fault: unstable read | aborts with "two reads of the chunk differed", no output file |
| **complete 8 MiB backup** (64 chunks) | **OK, 8 388 608 bytes, byte-identical**, 16.5 min in emulation |

Backup sha256 `25bb6459f9c0442fb819246ad423252985562e2abe1ae97d36f4a1a252a63382`
equals the sha256 of the simulated NOR image
([results/simulated_nor_image.sha256](../../tools/nb4plus-nor-reader/results/simulated_nor_image.sha256)).

Logs: [pipeline_tests.log](../../tools/nb4plus-nor-reader/results/pipeline_tests.log),
[dry_run.log](../../tools/nb4plus-nor-reader/results/dry_run.log) (the exact
`dfu-util` calls per chunk).

## 4. Not covered by any test yet

- Behaviour of the real NB4+ ROM DFU bootloader with SRAM downloads/uploads,
  `leave` into SRAM and the jump back into the bootloader.
- The real NB4+ RF module, display panel, charging and haptic output with the
  `NB4_PLUS_HW` firmware.
