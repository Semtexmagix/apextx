# NB4+ status and roadmap

Last update: 2026-10-17

## At a glance

| Area | State |
|---|---|
| Analysis of stock NB4/NB4+ firmware | Done ([FINDINGS.md](FINDINGS.md)) |
| `NB4_PLUS_HW` build option | Done – compiles, image validated |
| Pin and macro checks of the build | Done |
| External NOR backup tool | Done in emulation (8 MiB byte-identical), not run on hardware |
| **Test on a real NB4+** | **Done – ApexTX runs and the internal RF binds (see below)** |
| Upstream contact | ApexTX issue [#8](https://github.com/GastonGelhorn/apextx/issues/8), EdgeTX discussion [#7912](https://github.com/EdgeTX/edgetx/discussions/7912) |

## Confirmed on a real NB4+ (2026-10-16)

The `NB4_PLUS_HW` build was flashed to a real Noble NB4+ via STM32 ROM DFU
(STM32CubeProgrammer) and the following were verified on hardware:

- **Flashing / recovery:** ROM DFU works (PID 0483:df11), the internal 2 MiB
  flash backs up and the firmware flashes and verifies; the chip is an
  STM32F429 as expected.
- **Boot and UI:** ApexTX boots; display (portrait, correct), touch, keys,
  trims, wheel, haptic and the status LED all work.
- **Storage:** creating the FrFTL/FAT filesystem on the external NOR works and
  persists across reboots. (A first format attempt failed an erase-verify and
  showed a red error; a second attempt succeeded – see Known issues.)
- **Internal RF:** the module answers (not "module not responding"), **binds a
  FlySky FGr8B receiver and drives a servo channel end-to-end.** Binding
  required the **Enhanced** PHY mode; Classic did not bind the FGr8B. The
  **unmodified NB4 RF stack** was used – a separate test with PI8 forced low and
  one with the stock NB4 value (PI8 high) both bound, so **PI8 polarity does not
  matter** and no RF code change is needed for the NB4+.

Not yet verified: failsafe behaviour under load, charging from empty, the
external NOR backup tool on hardware, and whether re-flashing the stock
firmware over DFU accepts the same version.

## Done

- [x] Unpacked and analysed the official NB4+ (1.0.22, four variants) and NB4 (2.0.116) firmware
- [x] Validated the method against the known NB4 RF route
- [x] Compared RF link, power sequence, command set, receiver blocks, keys, ADC, battery, charging, display, touch
- [x] Added `NB4_PLUS_HW` (haptic PB0, LCD fallback ST7796S) to the NB4 target
- [x] Built with GCC 14.2.rel1, validated with `apextx-updater.py --check`
- [x] Macro diff NB4 vs NB4+ and pin comparison with stock
- [x] RAM-only NOR reader, PC script and simulated DFU device; unit, pipeline and fault tests
- [x] Documented method, findings, results and region handling
- [x] **Flashed and tested on a real NB4+: boots, UI works, storage works, internal RF binds a receiver and drives a servo (Enhanced PHY mode)**

## Known issues

- **Fixed: switching the UI language to English powered the radio off**
  (display off, one beep, off - not the orderly shutdown). Confirmed on hardware
  as a UI-task **stack overflow**: the UI-language handler in
  `gui/colorlcd/radio/radio_setup.cpp` (the `ALL_LANGS` block) rebuilt the page
  **reentrantly from inside the Choice value-change callback** (`onCancel()` +
  `QuickMenu::openPage()`), stacking a full page build on top of the running
  LVGL event. On the NB4's tight UI stack that overflowed, faulted and dropped
  the power latch. (The font path was ruled out: English and Spanish share the
  same `en_fontTable`, so no font is reloaded, and both string tables are fully
  populated.) The fix defers the rebuild to the next LVGL cycle with
  `lv_async_call`, so it no longer nests on the event stack. Not NB4+-specific -
  it is in shared ApexTX code. Remaining (cosmetic): on the NB4's own interface
  the new language is shown after the next restart, not live.
- **First filesystem creation can fail an erase-verify** (red error) and then
  succeed on a second attempt. Likely a timing issue during the full-chip
  erase; worth hardening for the NB4+ NOR.

## Open questions (need hardware or maintainer input)

| Question | Why it matters | How to answer it |
|---|---|---|
| Does the stock FlySky bootloader accept re-flashing the same firmware version? | Clean return to stock | Inspect the bootloader from a DFU backup of the internal flash |
| Which RF region does a freshly bound receiver use on the NB4+? | Regulatory compliance | Maintainer input / test |
| Does charging behave correctly without PI0, from empty? | Battery safety | Charge from empty while watching voltage and temperature |
| Does failsafe behave correctly under load? | Safety before driving | Bench test with a servo/ESC, wheels off the ground |
| Does the external NOR backup tool work on real hardware? | Exact return to stock | First run of `dump_nor.py` on a radio |

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
| 2026-10-16 | **First flash on a real NB4+: boots, UI/storage work, internal RF binds an FGr8B and drives a servo (Enhanced PHY mode). Isolation test showed PI8 polarity is irrelevant – the unmodified NB4 RF stack binds; the earlier PI8-low change was reverted. English language switch found to crash.** |
| 2026-10-17 | Static trace of the stock "RF Standard" path: it is the RF **protocol** selector (AFHDS3/Mini-Z), not a CE/FCC switch; the RF module's command handler in the NOR package is a protected blob, so no transmitter-side region command could be recovered. Open hardware question raised. See [rf-standard-command.md](rf-standard-command.md). |
