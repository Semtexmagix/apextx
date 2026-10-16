# NB4+ status and roadmap

Last update: 2026-10-16

## At a glance

| Area | State |
|---|---|
| Analysis of stock NB4/NB4+ firmware | Done ([FINDINGS.md](FINDINGS.md)) |
| `NB4_PLUS_HW` build option | Done – compiles, image validated |
| Pin and macro checks of the build | Done |
| External NOR backup tool | Done in emulation (8 MiB byte-identical), **not run on hardware** |
| Test on a real NB4+ | **Not started** |
| Upstream contact | ApexTX issue [#8](https://github.com/GastonGelhorn/apextx/issues/8), EdgeTX discussion [#7912](https://github.com/EdgeTX/edgetx/discussions/7912) |

## Done

- [x] Unpacked and analysed the official NB4+ (1.0.22, four variants) and NB4 (2.0.116) firmware
- [x] Validated the method against the known NB4 RF route
- [x] Compared RF link, power sequence, command set, receiver blocks, keys, ADC, battery, charging, display, touch
- [x] Added `NB4_PLUS_HW` (haptic PB0, LCD fallback ST7796S) to the NB4 target
- [x] Built with GCC 14.2.rel1, validated with `apextx-updater.py --check`
- [x] Macro diff NB4 vs NB4+ and pin comparison with stock
- [x] RAM-only NOR reader, PC script and simulated DFU device; unit, pipeline and fault tests
- [x] Documented method, findings, results and region handling

## Open questions (need hardware or maintainer input)

| Question | Why it matters | How to answer it |
|---|---|---|
| Does the NB4+ RF module answer like the NB4 module? | Core of the whole port | Bind test with the build |
| Which display panel does the NB4+ use? | Fallback driver choice | Boot the build; the detected panel is shown in the hardware info |
| Does the ROM DFU bootloader accept SRAM download/upload, `leave` into SRAM and the jump back? | Needed for the NOR backup tool | First run of `dump_nor.py` on a radio |
| Does FlySky's bootloader accept re-flashing the same firmware version? | Clean return to stock | Inspect the bootloader from a DFU backup of the internal flash |
| Which RF region does a freshly bound receiver use on the NB4+? | Regulatory compliance | Maintainer input / test |
| Does charging behave correctly without PI0? | Battery safety | Charge from empty while watching voltage and temperature |

## Hardware test plan

Each step only continues if the previous one passed. Steps 1–2 are read-only.
The detailed step-by-step guide with commands is [TESTING.md](TESTING.md).

| # | Step | Pass criteria |
|---|---|---|
| 1 | Enter ROM DFU, back up internal flash (2 MiB) with `dfu-util` | `dfu-util -l` shows `0483:df11` with internal flash, option bytes and OTP; upload completes; checksums recorded |
| 2 | Back up the external NOR with `tools/nb4plus-nor-reader/dump_nor.py` (optional) | 8 MiB file, JEDEC ID plausible, all chunk CRCs match |
| 3 | Flash the `NB4_PLUS_HW` build | Readback matches, radio leaves DFU and boots ApexTX |
| 4 | Without receiver: display, touch, keys, trims, wheel, haptic, battery reading, USB, charging | Everything responds; battery voltage plausible against a multimeter |
| 5 | Wheels off the ground: bind, steering/throttle, failsafe, reconnect after power cycle | Bind succeeds; outputs follow; failsafe triggers when the transmitter is switched off; automatic reconnect |
| 6 | Optional: return to stock from the backup | Stock firmware boots; FlySky update and recalibration if needed |

## Possible future work

- **Receiver firmware updates from ApexTX.** ApexTX cannot update FlySky
  receivers; today that needs a temporary return to stock firmware (see
  [UPDATES.md](UPDATES.md)). The stock receiver-update exchange could in
  principle be reverse-engineered the same way the RF link was, but it is a
  large, risky effort and belongs with the RF-stack maintainer.

## How to help

- **NB4+ owners willing to test**: follow the plan above and report results in
  ApexTX issue #8 or EdgeTX discussion #7912. Back up first.
- **ApexTX / EdgeTX developers**: review the `NB4_PLUS_HW` change and the
  region handling; a pull request without the fork-specific README notice can
  be prepared on request.

## History

| Date | Event |
|---|---|
| 2026-10-14 | Analysis, `NB4_PLUS_HW` build, NOR reader; fork published; ApexTX issue #8 and EdgeTX discussion #7912 opened |
| 2026-10-15 | Firmware variants and update flow documented; RF region handling of ApexTX documented |
| 2026-10-16 | Reply from the author of the EdgeTX NB4+ support; call for testers posted |
