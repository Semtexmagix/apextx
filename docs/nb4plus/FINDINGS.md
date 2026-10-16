# NB4+ findings with evidence

Every statement below names **how it was established** (see
[METHOD.md](METHOD.md) for the techniques) and **how certain** it is:

- **High** – read directly from the code or registers, cross-checked on both
  NB4 and NB4+, and/or consistent with ApexTX running on the NB4.
- **Medium** – consistent evidence, but an interpretation (e.g. the meaning of
  a pin) rather than a direct observation.
- **Open** – needs a real NB4+.

Firmware versions analysed: NB4+ 1.0.22 (all four variants), NB4 2.0.116.

## RF module

| Finding | How we know | Certainty |
|---|---|---|
| The stock firmware configures **two** UARTs at 1.5 Mbaud for the RF protocol: USART6 (PC6/PC7, AF8) and USART3 (PB10/PB11, AF7). | The only occurrence of the constant 1 500 000 sits in one init function that sets up both UARTs; the GPIO setup next to it gives pins and alternate functions. Same on NB4 and NB4+. | High |
| In normal operation the link uses **USART6**; USART3 is only used when a per-model mode value equals 4. | The send and receive wrappers pick UART index 5 (USART6) unless that mode value is 4; the UART table maps index 5 to USART6. Same logic on NB4 and NB4+. | High |
| The method gives the right answer on the NB4. | Applied to the stock NB4 it finds USART6 – the route ApexTX uses successfully on the NB4. | High |
| The link uses SLIP framing (0xC0 end, 0xDB escape). | The receive parser compares against 0xC0/0xDB/0xDC/0xDD; a shared encoder escapes the same bytes. | High |
| Command set, frame types, mode values 1/2/3 and the configuration sequence (four pages with operation 1 = bind / 2 = update, then an empty apply command) are identical on NB4 and NB4+, and match what ApexTX sends on the NB4. | All calls of the RF request function were listed with their constant frame type and command; mode and operation values read at the call sites. | High |
| The two 168-byte default receiver blocks are byte-identical on NB4 and NB4+ and equal ApexTX's `nb4DefaultReceiver` except for two fields ApexTX sets at runtime. | Byte-pattern search and byte-by-byte comparison. | High |
| Module power: on = PD11 high then PI8 low; off = PD11 low, PI8 high. | GPIO helper calls with constant port/pin/level, executed in the power-key start-up state. Same on NB4 and NB4+. | High (that they are switched), Medium (exact role of each pin) |
| PI8 does not appear critical. | ApexTX keeps PI8 high and works on the NB4, whose stock firmware drives PI8 like the NB4+. | Medium |
| The NB4+ RF module answers like the NB4 module. | Not observable without hardware; the module has its own firmware. | **Open** |

## Board (NB4 vs NB4+)

| Finding | How we know | Certainty |
|---|---|---|
| Identical ADC sequence: channels 2, 3, 12, 7, 11, 10, 6, 14, 15. | ADC sequence registers logged in the start-up emulation of both firmwares; matches the NB4P target's analog order. | High |
| Keys/trims: two 3-state ladders (enter/exit, SW2/SW3) and two 4-state trim ladders with identical thresholds. | Threshold comparisons in the key scan; the scan code is identical between NB4 and NB4+. | High |
| Encoder and power-key table identical (PH10/PH11, PB15/PC13, PI11). | Key table decoded from both firmwares. | High |
| Only start-up pin difference: haptic on PA8 (NB4) vs PB0 (NB4+). | Diff of the emulated start-up pin maps. | High |
| LCD data pins (LTDC) and panel-ID probing are identical; ST7796S is the likely panel. | Pin map from emulation; probe sequence decoded from bit-banged SPI. The ST7796S hint comes from the upstream NB4+ bring-up, which adapted that driver. | High (pins/probing), Medium (panel type) |
| Touch: FocalTech-compatible controller at I2C 0x38; address 0x6A is only the touch chip's firmware-update mode. | I2C address constants at the call sites; the 0x6A handshake matches a touch-controller bootloader entry. | High (addresses), Medium (chip family) |
| Battery: 2.1 divider (EdgeTX `BATTERY_DIVIDER` 2954), capped at 4.20 V, same level tables as the NB4. No LiHV handling. | Scaling constants and level tables found identically in both firmwares. | High |
| Charging: PB13/PB14 read exactly as ApexTX's NB4 code reads them; PI0 toggled by the stock firmware but not needed. | Read-call analysis; upstream EdgeTX charges the NB4+ without driving PI0. | High (pins), Medium (PI0 not needed) |
| PJ7/PJ8/PJ13 are driven by ApexTX but not by the stock firmware; very likely unconnected. | Pin comparison; the upstream NB4P target drives them on NB4+ hardware too. | Medium |

## Stock firmware variants and update flow

| Finding | How we know | Certainty |
|---|---|---|
| The resource package (images, fonts) is identical in all four 1.0.22 variants; only the application differs. | SHA-256 of the extracted resources. | High |
| EU and EN applications differ in data unrelated to the RF link and contain the same language names. | Byte diff and string search. | High |
| The version string shows the variant (`std.` or `FCC`). | Format strings in the firmware. | High |
| "No update is required" belongs to the receiver update dialog, not to updating the transmitter. | Located in the string table between the receiver-update messages. | High |
| The PC updater has no version check. | Its code section contains no such messages; it only talks USB HID. | High |
| Whether FlySky's bootloader accepts re-flashing the same version. | The bootloader is not in the updater; it would be visible after a DFU backup. | **Open** |

## RF region (CE / FCC) in ApexTX

| Finding | How we know | Certainty |
|---|---|---|
| On the NB4 path (`RADIO_NB4`, base of `NB4_PLUS_HW`) ApexTX shows no region selector and sends no region byte to the module; it keeps the module's existing regional data. | ApexTX source (`afhds3_settings.cpp`, `afhds3_nb4.h`). | High |
| The FCC default in `resetAfhds3Options` applies to the generic AFHDS3 path only. | ApexTX source. | High |
| Which region a freshly bound receiver uses on an NB4+. | Decided by the module firmware and receiver block, not the transmitter UI. | **Open** |

## Build checks

| Finding | How we know | Certainty |
|---|---|---|
| The NB4+ build differs from the NB4 build only in the haptic macros. | Preprocessor macro dump with the real compiler flags, diffed. | High |
| Every pin used by the build matches stock NB4+ usage or belongs to features inactive on this target. | Macro pin list compared with the stock pin map. | High |

Logs and raw outputs: [TEST_RESULTS.md](TEST_RESULTS.md) and
[verification](verification).
