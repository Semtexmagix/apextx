# Noble NB4+ support (not yet tested on hardware)

> **Status:** analysis done, build compiles and passes static and emulation
> checks. Nothing here has run on a real NB4+ yet. Do not flash it onto a radio
> you rely on. Current state and next steps: [STATUS.md](STATUS.md).

## What this is about

Upstream EdgeTX supports the FlySky Noble NB4+ only partly: its internal RF
module is listed as unsupported. ApexTX, a car-focused EdgeTX fork, does run
the internal module of the **original NB4**. This work checks whether the NB4+
is close enough to the NB4 to reuse that working code – and adds a build option
for it.

## Result in short

From the MCU's point of view the NB4+ is almost identical to the NB4:

- The RF module sits on the **same UART (USART6, PC6/PC7)**, is powered the
  same way and is driven with the **same protocol dialect, commands and
  receiver blocks** as on the NB4.
- ADC map, key and trim ladders, encoder, power key, display pins, touch,
  battery scaling and charging pins are identical.
- Differences found: the haptic motor output (PB0 instead of PA8) and, very
  likely, the display panel (ST7796S).

The upstream `NB4P` target instead maps the internal module to USART3, which
the stock firmware only uses in one special mode – a likely reason why the
internal RF does not work there.

Every point with its evidence and certainty: [FINDINGS.md](FINDINGS.md).

## The `NB4_PLUS_HW` build option

The option builds the **NB4 target** (including its working internal-RF stack)
with only the two hardware differences changed:

| Item | NB4 target | `NB4_PLUS_HW=ON` |
|---|---|---|
| Haptic motor | PA8, TIM1 CH1 | PB0, TIM1 CH2N (as in the upstream NB4P target) |
| LCD fallback if panel ID detection fails | NT35310 | ST7796S |

```sh
cmake -S . -B build/nb4plus -DPCB=PL18 -DPCBREV=NB4 -DNB4_PLUS_HW=ON \
  -DNB4_RF_PROFILE=RECOVERED_USART6 -DTRANSLATIONS=EN -DDISABLE_COMPANION=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build build/nb4plus --target firmware-size
```

On a machine without a host compiler, configure the ARM build directly by
adding `-DCMAKE_TOOLCHAIN_FILE=cmake/toolchain/arm-none-eabi.cmake
-DEdgeTX_SUPERBUILD=0 -DNATIVE_BUILD=0`.

## RF region (CE / FCC)

On the NB4 path ApexTX shows no region selector and sends no region setting to
the module; the module keeps its existing regional configuration. ApexTX does
not force FCC there. Which region a newly bound receiver uses on an NB4+ is
still open – see [FINDINGS.md](FINDINGS.md#rf-region-ce--fcc-in-apextx).
Operate the radio only in the region that is legal where you use it. How
regions, the RF module and receiver updates fit together is explained in
[UPDATES.md](UPDATES.md).

## Documentation

| Page | Content |
|---|---|
| [TESTING.md](TESTING.md) | Step-by-step guide: backup, flashing, checks, reporting, going back |
| [UPDATES.md](UPDATES.md) | Regions (CE/FCC), RF module and receivers, and what ApexTX does and does not update |
| [STATUS.md](STATUS.md) | What is done, open questions, hardware test plan, how to help, history |
| [METHOD.md](METHOD.md) | How the findings were obtained, step by step |
| [FINDINGS.md](FINDINGS.md) | All findings with evidence and certainty |
| [TEST_RESULTS.md](TEST_RESULTS.md) | Build checks, unit and pipeline tests with logs |
| [verification](verification) | Raw outputs: macro diff, pin lists, build summary |
| [analysis-tools](analysis-tools) | Scripts used for the analysis |
| [../../tools/nb4plus-nor-reader](../../tools/nb4plus-nor-reader) | Backup tool for the external NOR (emulation-tested only) |

No FlySky firmware, code, images or data are part of this repository.
