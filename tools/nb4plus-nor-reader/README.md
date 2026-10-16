# NB4+ external NOR reader (untested on hardware)

> **Status: simulation only.** This reader has never run on a real radio. It is
> published for review. Do not rely on it until it has been verified on an NB4+.

ApexTX formats the 8 MiB external SPI NOR on first installation. STM32 ROM DFU
can back up the internal flash, but it cannot read that NOR, and the NOR holds
the unit-specific FlySky data needed for an exact return to stock. This tool
aims to make that backup possible without an SPI programmer.

## How it works

1. A ~1.5 KiB program is downloaded through ROM DFU into SRAM only
   (parameters at `0x20007F00`, code at `0x20008000`) and started with a DfuSe
   *leave* request. Internal flash is never written.
2. It bit-bangs the NOR on the stock pins (PG6 CS, PG12 MISO, PG13 SCK,
   PG14 MOSI), reads the JEDEC ID and then one chunk of up to 128 KiB with the
   plain `0x03` READ command - **twice** - and stores the data plus both CRC-32
   values at `0x2000FF00`/`0x20010000`.
3. It restores the clock tree, resets USB OTG FS and jumps back into the ROM
   bootloader (optional fallback: system reset while the DFU button is held;
   SRAM survives a reset).
4. The PC uploads the result from SRAM and checks magic, status, range,
   sequence number and both CRCs, then requests the next chunk.

The reader only ever sends `0x9F` and `0x03` to the NOR. It never issues
write-enable, program or erase commands.

## Simulation tests

`sim.py` runs the reader in the Unicorn CPU emulator against a simulated SPI
NOR; `test_sim.py` checks:

- byte-exact data and matching CRCs at the start and at the last chunk of 8 MiB
- rejection of invalid parameters without touching the NOR
- detection of a missing chip (JEDEC ID `FFFFFF`) without issuing a READ
- detection of an unstable read (CRC mismatch between the two passes)
- the reset fallback
- no write to internal flash, only RCC/SYSCFG/GPIOG/GPIOI/SCB/NVIC/SysTick
  registers written, only the five expected pins driven, only commands
  `0x9F`/`0x03` sent

```sh
pip install unicorn
./build.sh
python test_sim.py dumper.bin
```

## PC side and end-to-end test

`dump_nor.py` drives `dfu-util` chunk by chunk (only the two fixed SRAM
addresses are ever written or read; `--dry-run` prints the exact calls).
`test_dump_pipeline.py` runs it against `fake_dfu_util.py`, a simulated ROM
DFU device, including fault injection and (with `--full`) a complete 8 MiB
backup. Results: [../../docs/nb4plus/TEST_RESULTS.md](../../docs/nb4plus/TEST_RESULTS.md).

```sh
python dump_nor.py --dry-run
python test_dump_pipeline.py /tmp/norsim --full
```

## Verifying a backup (`verify_nor.py`)

A dump is read twice with matching CRCs, but that only proves the read was
stable and the transfer intact – not that the content is a valid FlySky image.
`verify_nor.py` checks the content offline (it never touches a radio):

- size and blank/erased detection;
- the FlySky `0x5A5A` resource header and its 18-byte checksum, the same check
  the stock firmware does;
- a byte-for-byte cross-check against the official resource package. Extract it
  yourself from the FlySky updater you downloaded, using
  `../../docs/nb4plus/analysis-tools/pe_rsrc.py`; the package is the
  `10_901_1033` output file (no FlySky file is shipped here);
- optionally, a comparison of two independent full dumps.

```sh
python verify_nor.py dump.bin --resource 10_901_1033
python verify_nor.py dump.bin --compare second_pass.bin
```

**What it proves:** the shared part (FlySky images/fonts) is byte-identical to
an independent known-good copy. **What it cannot prove:** the unit-specific
part (calibration, models) has no external reference, so there only the
read-twice CRC check applies; and a backup is only fully proven by a successful
restore, which cannot be rehearsed without writing.

## Open questions for real hardware

- Whether the NB4+ ROM DFU accepts writes to and uploads from SRAM
  (`dfu-util` needs the `:force` modifier for addresses outside the flash
  layout).
- Whether DfuSe *leave* to `0x20008000` starts the program from SRAM.
- Whether the jump back into the ROM bootloader re-enumerates cleanly.
- The SRAM range used by the ROM bootloader (the reader assumes it stays below
  `0x20004000`).
