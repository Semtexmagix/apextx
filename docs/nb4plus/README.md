# Noble NB4+ support notes (not yet tested on hardware)

> **Status:** compiles and passes static/emulation checks. Nothing here has run
> on a real NB4+ yet. Do not flash it onto a radio you rely on.

## Summary

The NB4+ appears to be electrically almost identical to the original NB4 as
seen from the MCU. The proposed `NB4_PLUS_HW` option therefore builds the
**NB4 target** (including its working AFHDS3 internal-RF stack) with two
changes, instead of using the `NB4P` target:

| Item | NB4 target | `NB4_PLUS_HW=ON` |
|---|---|---|
| Haptic motor | PA8, TIM1 CH1 | PB0, TIM1 CH2N (as in the upstream NB4P target) |
| LCD fallback if panel ID detection fails | NT35310 | ST7796S |

Everything else (RF route, keys, trims, ADC map, touch, charging, battery
scaling, power latch) stays exactly as in the NB4 target.

```sh
cmake -S . -B build/nb4plus -DPCB=PL18 -DPCBREV=NB4 -DNB4_PLUS_HW=ON \
  -DNB4_RF_PROFILE=RECOVERED_USART6 -DTRANSLATIONS=EN -DDISABLE_COMPANION=ON \
  -DCMAKE_BUILD_TYPE=Release
```

## Why not the NB4P target

The NB4P target inherits the upstream EdgeTX mapping, which puts the internal
module on USART3 (PB10/PB11) with PI8 as power, and uses the generic AFHDS3
driver. Upstream EdgeTX lists the NB4+ internal RF as unsupported. The NB4P
target also scales the battery with a 1:2 divider and only decodes two of the
four positions on each trim ladder.

## How the findings were obtained

The official FlySky updaters for the NB4+ (firmware 1.0.22) and for the
original NB4 (2.0.116) were unpacked; each contains a plain application image
and a resource package. The application code was analysed statically and the
start-up code was additionally run in a CPU emulator to log every peripheral
register write. No FlySky code, images or data are included in this
repository; the points below are the conclusions only.

## Findings

### RF module

- Both stock firmwares configure **two** UARTs at 1.5 Mbaud with the same
  AFHDS3 (SLIP-framed) protocol handler: USART6 on PC6/PC7 and USART3 on
  PB10/PB11.
- In normal operation the RF link uses **USART6** - the same route ApexTX
  recovered for the NB4. USART3 is only selected for one special per-model
  mode.
- The command set sent to the module is identical on NB4 and NB4+ (ready,
  state, mode 1/2/3, four configuration pages with operation 1 = bind /
  2 = update, apply-config, channels/failsafe, version and a few extras).
- The default receiver configuration block (two 168-byte variants) is
  byte-identical between NB4 and NB4+, and matches ApexTX's
  `nb4DefaultReceiver` except for the two fields ApexTX overwrites at runtime.
- RF power: both stock firmwares drive PD11 high and PI8 low when switching on,
  and PD11 low / PI8 high when switching off. ApexTX's NB4 profile keeps PI8
  high and works on the NB4, so PI8 does not appear to be critical.

### Rest of the board (stock NB4 vs NB4+)

- Identical ADC regular sequence: channels 2, 3, 12, 7, 11, 10, 6, 14, 15
  (steering, throttle, two aux, key ladder, switch ladder, two trim ladders,
  battery).
- Identical key/trim ladder decoding thresholds, identical rotary-encoder and
  power-key table (PH10/PH11, PB15/PC13, PI11), identical LTDC pins, identical
  LCD panel-ID probing over the bidirectional PE6 line.
- The only difference in the start-up pin configuration: haptic PA8 (TIM1 CH1)
  on the NB4, PB0 (TIM3 CH3) on the NB4+.
- Touch: FocalTech-compatible controller at I2C address 0x38 in normal
  operation (address 0x6A is only used for the touch controller's firmware
  update mode).
- Battery: both firmwares use a 2.1 divider (EdgeTX `BATTERY_DIVIDER` 2954)
  and the same level tables, capped at 4.20 V. No LiHV handling was found.
- Charging: PB13/PB14 are read exactly as ApexTX's NB4 code reads them. The
  stock firmware also toggles PI0 depending on its power state; neither ApexTX
  nor the upstream NB4P target drives PI0, and upstream reports working
  charging on the NB4+ without it.
- Display: the upstream NB4+ bring-up adjusted the ST7796S driver, which is
  why it is used as the fallback here.

### Pin check of this build

All GPIO macros of the `NB4_PLUS_HW` build were dumped with the real compiler
flags and compared with the stock NB4+ pin usage. Apart from the intended
haptic change they match the NB4 build. PJ7/PJ8/PJ13 (telemetry inverter pins
of the PL18 family) are driven by ApexTX but not by the stock firmware; the
upstream NB4P target drives them on NB4+ hardware as well.

## Remaining risk

- The NB4+ RF module itself has not been exercised. The MCU side matches the
  NB4 exactly, but the module firmware could differ.
- Display panel, charging and haptic behaviour need confirmation on a device.

## Proposed hardware test order

1. Enter ROM DFU and back up the internal flash (read-only).
2. Back up the external NOR (see `tools/nb4plus-nor-reader`, still untested).
3. Flash; check display, touch, keys, trims, battery reading, USB, charging -
   without a receiver.
4. Wheels off the ground: bind, steering/throttle, failsafe, reconnect.
