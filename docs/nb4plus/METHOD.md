# How the NB4+ findings were obtained

This page explains the approach step by step, so that every statement in
[FINDINGS.md](FINDINGS.md) can be traced back and reproduced. The scripts that
were used are in [analysis-tools](analysis-tools).

## 1. Starting point

- Upstream EdgeTX has an `NB4P` target for the Noble NB4+, but lists the
  internal RF module as unsupported. Its internal-module mapping is USART3
  (PB10/PB11) with PI8 as power, driven by the generic AFHDS3 driver.
- ApexTX runs the **original NB4** including its internal RF module. Its author
  recovered the module protocol (a SLIP-framed AFHDS3 dialect without address
  byte, own mode values, configuration pages and receiver block) and found the
  module on USART6 (PC6/PC7).
- Question: is the NB4+ wired and programmed like the NB4, so that the working
  NB4 stack can be reused?

## 2. Source material

Only material that FlySky publishes for everyone was used:

- the official updater executables for the NB4+ (firmware 1.0.22, all four
  variants EU/EN × standard/FCC) and for the original NB4 (2.0.116), downloaded
  from flysky-cn.com.

No radio was opened, connected or modified. None of these files, nor any part
of their code, images or data, is included in this repository.

## 3. Unpacking

Each updater is a small Windows program with the firmware attached as Windows
resources (`pe_rsrc.py`):

- resource 900: the plain application image, linked to start at `0x08008000`
  (the first 32 KiB of internal flash belong to FlySky's bootloader, which is
  not part of the updater);
- resource 901: the resource package (images, fonts) that the application
  loads from the external SPI NOR into SDRAM.

## 4. Static analysis of the application

The application is ordinary Thumb-2 code for the STM32F429. It was
disassembled with Capstone (`dis.py`, `grepdis.py`) and searched in several
complementary ways:

| Technique | Example of what it answered |
|---|---|
| Unique constants | The value 1 500 000 (the AFHDS3 baud rate) occurs exactly once and leads straight to the RF UART initialisation. |
| Peripheral tables | The firmware keeps a table of all UART base addresses with DMA and clock data; the index used by the RF code identifies the UART (`lits.py`, `dumpw.py`). |
| Call sites with constant arguments | Every call of the GPIO write/read helpers and of the RF request function was listed together with its constant arguments: port, pin, level, frame type, command (`calls2.py`, `reqcalls.py`). |
| Cross references | Who calls a function, who reads a variable (`xref.py`, `findlit.py`). |
| String tables | Messages were located in the firmware's string tables and identified by their neighbours, e.g. which update dialog a message belongs to (`strs.py`). |
| Byte patterns | ApexTX's 168-byte default receiver block was searched for in the firmware and compared byte by byte (`tmplsearch.py`, `tmplcmp.py`). |

## 5. Validating the method on the NB4 (known ground truth)

A method is only trustworthy if it gets a known answer right. For the original
NB4 the correct RF route is known from ApexTX, which runs on it. The same
analysis applied to the stock NB4 firmware found **USART6, PC6/PC7, 1.5 Mbaud**
– exactly the route ApexTX uses. The NB4+ results were then obtained with the
identical method.

## 6. Comparing NB4 and NB4+

Every relevant finding was produced for **both** firmwares and compared:
UART selection logic, power sequence, command set, mode values, configuration
operations, receiver blocks, key decoding, battery scaling, start-up pin map.
Where both agree, the NB4 behaviour that ApexTX already handles is very likely
valid for the NB4+ as well. The only differences found are listed in
[FINDINGS.md](FINDINGS.md).

## 7. Emulating the start-up code

Static reading is good for single functions, but some things are easier to
observe. The start-up code of both firmwares was run in the Unicorn CPU
emulator (`emu.py`), with simple stand-ins for status registers the code waits
on (clock ready, SPI/ADC flags, timers). Every write to a peripheral register
was logged, which gave:

- the final GPIO configuration of every pin after start-up (`pinmap.py`);
- the ADC conversion sequence (read directly from the ADC sequence registers);
- the LCD panel-ID probing, decoded from the bit-banged SPI traffic
  (`lcdspi.py`).

The same emulator was later used on the finished ApexTX build (`emu2.py`). It
cannot run the full firmware (no interrupt model, so it stops at the power-key
qualification), therefore the pin check of the build uses the compiler's macro
set instead (step 9).

## 8. Upstream history

The EdgeTX Git history and wiki were read to see what the people who brought
the NB4+ into EdgeTX found on real hardware: the NB4+ bring-up in 2024 adapted
the ST7796S display driver, fixed charging/USB detection without a charger
enable pin, and the NB4+ hardware-mod guide is by the same author.

## 9. Building and checking the variant

- The `NB4_PLUS_HW` option adds only what differs: haptic output and LCD
  fallback. The rest is the unchanged NB4 target.
- The build was compiled with the official ARM toolchain (GCC 14.2.rel1) and
  checked with ApexTX's own image validator.
- With the exact compiler flags of the build, all preprocessor macros of the
  NB4 and the NB4+ configuration were dumped and diffed. Only the haptic
  macros differ. The list of all GPIO pins the build uses was compared with the
  stock NB4+ pin usage.

## 10. External NOR backup tool

Installing ApexTX formats the external NOR, which ROM DFU cannot read. A small
reader that runs from SRAM only was written and tested entirely in emulation,
against a simulated SPI NOR and a simulated ROM DFU device, including a
complete 8 MiB backup and fault injection. Details:
[../../tools/nb4plus-nor-reader](../../tools/nb4plus-nor-reader).

## 11. What was deliberately not done

- No FlySky code, images or data were published.
- No hardware was touched; everything that needs a real radio is listed as open
  in [STATUS.md](STATUS.md).
- The internals of the RF module itself (a separate chip with its own firmware)
  were not analysed; only how the main MCU talks to it.
