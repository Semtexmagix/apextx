# NB4+ ApexTX — ideas and open questions (scratchpad for future work)

A running list so nothing gets lost. Nothing here is implemented unless another
doc says so. Certainty tags: **High** = read/verified, **Medium** =
interpretation, **Open** = needs hardware or more work.

## CE / FCC region — where it stands
- The stock radio app in **EU FCC** vs **EU STD** builds differs **only by
  relocation/layout** (a ~72-byte size shift and the resulting pointer/branch
  adjustments). An aligned binary diff found **no functional constant
  difference** (no differing TX-power value, region code or config byte); the
  size changes cluster in the **region/version display code** (near the
  `%sFCC` / `%sstd.` format strings). **High.**
- The NOR package (RF-module + receiver firmware) is **byte-identical** between
  FCC and STD. **High.**
- The menu labelled "RF Standard" is the **protocol** selector (AFHDS3 1/2-way,
  Mini-Z), not a CE/FCC switch; `config+0x3a` is the UI language. **High.**
- The RF module's command handler is **obfuscated** (own 256-byte S-box, reached
  by one indirect call, no plaintext decryptor). Not statically recoverable. **High.**
- Interpretation: on this radio the **CE/FCC split looks like a labelling /
  certification matter, not a transmitter behavioural difference** (2.4 GHz ISM
  behaviour can be the same under both regimes). **Medium.**
- Decisive confirmation would need **measurement, not reading**:
  - a USART6 sniff comparing stock **FCC vs STD** on the wire (see ESP tap), or
  - an RF spectrum/power measurement (e.g. TinySA Ultra) of FCC vs STD. **Open.**
- For "two ApexTX builds (CE/FCC)": they would be **cosmetic** (label only)
  unless we impose a real difference ourselves. The only legitimate behavioural
  lever ApexTX already has is **TX power** (a CE build could default/cap lower);
  the stock app has no such constant to copy. Compliance only — never to exceed
  a local limit. **Open.**

## RF module + receiver updater inside ApexTX (wanted feature)
Goal: bundle the newest RF-module and receiver firmware in ApexTX and flash them
from the radio, so no need to return to stock FlySky firmware for RF/RX updates.
- The firmware images live in the **NOR package (updater resource 10/901)**;
  already located/extracted.
- The flashing/update logic is in the **plaintext stock app** + the **module
  bootloader** (the small ~12 KB embedded image with its own SLIP parser) — both
  statically analysable, so the protocol can be reverse-engineered **without
  hardware**. **Medium.**
- EdgeTX/ApexTX do **not** currently flash AFHDS3 RF modules or receivers (it is
  FlySky-proprietary) — this would be new work. **High.**
- Risk: wrongly flashing the module can brick it (module recovery path unknown);
  design/understand first, flash-test very carefully. **Open.**

## Software sniffer / prober in ApexTX (groundwork, no hardware)
ApexTX is the transmitter and owns the USART6 link to the module, so it can log
every TX/RX frame and actively probe the module (send test frames, read
responses).
- Output path: USART6 is busy (the module), so logging must go over the **USB
  VCP**; `TRACE` is compiled out in release, but **`dbgSerialPrintf()`** can be
  called directly and writes to the serial port assigned the **Debug** function.
- Good for the updater work and for actively querying the module; it **cannot**
  see the stock firmware's traffic (closed). **Medium.**

## ESP32-S3 — two uses for the same board
- **Now (region answer):** passive **USART6 tap** on **PC6 (TX) / PC7 (RX)**,
  **1 500 000 baud 8N1**, de-SLIP (START/END 0xC0, ESC 0xDB/DC/DD, CRC =
  sum^0xFF). Uniquely it can sniff the **stock** firmware → the decisive
  **FCC-vs-STD on-the-wire diff**. Needs opening the radio + 3 wires. **Open.**
- **Later (connectivity):** a fixed **WiFi/BT backpack** (ELRS/EdgeTX-backpack
  pattern): OTA / firmware+model+config upload over WiFi, web UI, telemetry/BT.
  Needs a free UART on the NB4 + firmware both sides. Not worthwhile purely as
  "extra storage". **Open.**

## Not pursued
- Flashing the internal module to **ExpressLRS**: hardware is ELRS-class
  (SX1281 + STM32F030), but there is no NB4 target, the F030's 8 KB RAM is tight,
  and ELRS is **dropping STM support**. Dropped.
