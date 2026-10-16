# Testing the NB4+ build – step by step

> **Nobody has done this on an NB4+ yet.** This guide combines the ApexTX NB4
> installation procedure ([../nb4/FLASH.md](../nb4/FLASH.md)) and the EdgeTX
> NB4+/PL18 flashing guide with the NB4+ specifics found in this fork. Every
> step that writes to the radio comes after a read-only backup step. If a
> backup step fails, **stop** – nothing has been changed at that point.

## Before you start

- **Risk:** flashing replaces FlySky's firmware and almost certainly voids the
  warranty. The STM32 ROM DFU mode cannot be overwritten, so the radio can
  always be re-flashed – but keep the backups from steps 3 and 4.
- **Battery** fully charged. **No receiver and no powered vehicle** connected
  until step 8.
- A **data-capable USB cable** connected directly to the computer (no hub).
- Note down what you see under the radio's system/version info (firmware
  version, `std.` or `FCC`).
- Optional but useful: write down your models and settings – ApexTX starts
  with an empty model list and receivers have to be bound again.

### Tools

| Purpose | Windows | macOS / Linux |
|---|---|---|
| Read/write internal flash via ROM DFU | [STM32CubeProgrammer](https://www.st.com/en/development-tools/stm32cubeprog.html) (free ST account needed; brings its own DFU driver) | `dfu-util` 0.10 or newer |
| Optional external NOR backup | `dfu-util` + WinUSB driver + Python 3 (not tested on Windows) | `dfu-util` + Python 3 |
| Building the NOR reader | ARM GCC (`arm-none-eabi-gcc`) | same |
| Building the firmware | see [README.md](README.md#the-nb4_plus_hw-build-option) | same |

## 1. Get the firmware image

Build it as described in [README.md](README.md#the-nb4_plus_hw-build-option).
The result is `build/nb4plus/firmware.bin` (exactly 2 MiB: ApexTX bootloader +
application). Check it before use:

```sh
python3 tools/apextx-updater.py --check build/nb4plus/firmware.bin
```

Expected: `Valid NB4 firmware image: ... application bytes.`

Never flash an image built for another target (`PCBREV=NB4` without
`NB4_PLUS_HW`, or `NB4P`).

## 2. Enter ROM DFU

The NB4+ has a DFU button and a hard power-off button; their positions are
shown in the EdgeTX NB4+ guide:
[docs/mods/flysky-nb4plus.md](https://github.com/EdgeTX/edgetx/blob/main/docs/mods/flysky-nb4plus.md)
(the procedure itself is the PL18 one:
[flashing-flysky-pl18.md](https://github.com/EdgeTX/edgetx/blob/main/docs/mods/flashing-flysky-pl18.md)).

1. Radio switched off, USB cable connected to the radio only.
2. Hold the **DFU button** and plug the cable into the computer.
3. Check that the computer sees the STM32 bootloader:
   - Windows: STM32CubeProgrammer → USB → *Port* shows `USB1` → **Connect** →
     CPU shows *Cortex-M4*.
   - macOS/Linux: `dfu-util -l` lists `[0483:df11]` with alternate settings
     for *Internal Flash*, *Option Bytes* and *OTP Memory*.

The screen may stay black – that is normal in DFU mode. To leave DFU at any
time: unplug USB and press the **hard power-off button**.

## 3. Back up the internal flash (read-only) – required

This 2 MiB image contains FlySky's bootloader and firmware and is your way
back.

**Windows (STM32CubeProgrammer):** *Memory & File editing* → Address
`0x08000000`, Size `0x200000` → **Read** → *Save As* → e.g.
`nb4plus_internal_flash.bin`. The file must be exactly 2 097 152 bytes.

**macOS/Linux:**

```sh
tools/nb4-backup-mcu.sh ~/nb4plus-backup
```

This saves internal flash, option bytes and OTP with SHA-256 checksums and
verifies them.

Keep the backup private and in two places. It belongs to this one radio.
**If the backup fails or is not exactly 2 MiB: stop here.**

## 4. Back up the external NOR (optional, tool not yet tested on hardware)

The 8 MiB external flash holds FlySky's images, settings, models and probably
the calibration. ApexTX will format it. FlySky's software can restore its
content later (see step 10), so this backup is optional – it makes an exact
return to the current state possible.

```sh
cd tools/nb4plus-nor-reader
sh build.sh                                # builds dumper.bin
python3 dump_nor.py --dry-run              # shows the dfu-util calls
python3 dump_nor.py --out ~/nb4plus-backup/external-nor-8MiB.bin
```

The script only writes two fixed SRAM addresses and reads the result back;
the radio's flash is not written. If it reports an error, nothing is lost –
continue without this backup or stop. Details:
[../../tools/nb4plus-nor-reader](../../tools/nb4plus-nor-reader).

## 5. Flash the NB4+ build

**Windows (STM32CubeProgrammer):** *Erasing & Programming* → File
`firmware.bin`, Start address `0x08000000`, enable **Verify programming** →
**Start Programming**. When it reports success: Disconnect, unplug USB, press
the hard power-off button.

**macOS/Linux:**

```sh
tools/nb4-flash.sh build/nb4plus/firmware.bin
```

The script checks the image, writes it, reads it back, compares byte by byte
and starts the ApexTX bootloader.

## 6. First start of ApexTX

Follow steps 7–9 of [../nb4/FLASH.md](../nb4/FLASH.md):

1. **Settings > System > Storage > Create filesystem** (formats the external
   NOR – this is where FlySky's content is erased). Restart once.
2. Start **USB Storage** mode and copy the contents of the repository's
   `sdcard/` folder (without `SOUNDS/`) onto the radio; optionally one audio
   pack as described in [../nb4/AUDIO.md](../nb4/AUDIO.md). Eject cleanly
   before unplugging.
3. **System > Calibration**: calibrate steering, throttle and auxiliary
   controls over their full travel.

## 7. Bench checks – no receiver

| Check | Pass |
|---|---|
| Display shows a correct picture; note the panel type from the hardware info | ☐ |
| Touch responds in the right place | ☐ |
| Steering wheel and throttle trigger move over their full range | ☐ |
| Enter/exit keys, SW2/SW3, all four trim directions, scroll wheel | ☐ |
| Haptic motor vibrates | ☐ |
| Battery voltage matches a multimeter within about 0.1 V | ☐ |
| USB storage and USB serial connect and exit cleanly | ☐ |
| Charging: voltage rises, radio does not get hot | ☐ |
| Power off and on works reliably | ☐ |

If something here fails, you can still go back (step 10) without having
touched a receiver.

## 8. RF checks – wheels off the ground

| Check | Pass |
|---|---|
| Create a new car model, put the receiver into bind mode, bind | ☐ |
| Steering and throttle outputs follow the controls in the right direction | ☐ |
| Failsafe: switch the transmitter off → the car goes to the failsafe state | ☐ |
| Power-cycle transmitter and receiver → automatic reconnect | ☐ |
| Receiver voltage / link quality telemetry is shown | ☐ |

**If the RF module reports an error or binding never succeeds: stop and report
it** – this is the one point that could not be verified without hardware.

## 9. Report the results

Please post them in [ApexTX issue #8](https://github.com/GastonGelhorn/apextx/issues/8)
or [EdgeTX discussion #7912](https://github.com/EdgeTX/edgetx/discussions/7912):

- NB4+ firmware version before flashing (`std.`/`FCC`)
- which steps passed or failed, with photos/screenshots of error messages
- display panel type and NOR JEDEC ID if shown
- receiver model used for the bind test

Do **not** post your backup files – they contain unit-specific data.

## 10. Going back to FlySky firmware

1. Enter ROM DFU (step 2).
2. Write the backup from step 3 to address `0x08000000`:
   - Windows: STM32CubeProgrammer *Erasing & Programming* with the backup file,
     start address `0x08000000`, Verify programming.
   - macOS/Linux:
     ```sh
     dfu-util -d 0483:df11 -a 0 -s 0x08000000 -D ~/nb4plus-backup/internal-flash-2MiB.bin
     dfu-util -d 0483:df11 -a 0 -s 0x08000000:leave
     ```
3. Unplug USB, press the hard power-off button, switch on.
4. The external NOR was formatted by ApexTX. According to the EdgeTX PL18 guide,
   with FlySky's bootloader restored the **Flysky Assistant** software can
   restore the SPI flash content; alternatively run FlySky's NB4+ firmware
   updater. Then recalibrate and bind your receivers again.

**Never** write option bytes or OTP back – they are only kept for reference.

## Troubleshooting

| Symptom | What to do |
|---|---|
| Computer does not see the radio in DFU | Other cable/port, no hub; hold the DFU button while plugging in; check the button position in the EdgeTX NB4+ guide |
| Screen stays black after flashing | Wait 10 s; hard power-off and switch on again; if still black: DFU and go back (step 10) and report the panel issue |
| Radio does not leave DFU | Unplug USB, press the hard power-off button |
| Radio switches itself off right after start | ApexTX on the NB4 needs the power button held for about two seconds |
| "RF module not responding" / bind never completes | Stop, report in issue #8, go back if needed |
