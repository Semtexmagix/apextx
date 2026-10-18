# NB4+ ApexTX — ideas and open questions (scratchpad for future work)

A running list so nothing gets lost. Nothing here is implemented unless another
doc says so. Certainty tags: **High** = read/verified, **Medium** =
interpretation, **Open** = needs hardware or more work.

## Two active workstreams
1. **CE/FCC region** — determine whether there is any real region behaviour and,
   if wanted, provide a CE and an FCC build. Static analysis is exhausted (below);
   only measurement (ESP USART6 tap, or RF power) can settle "FCC = more range".
2. **RF module + receiver updater inside ApexTX** — so RF/RX firmware can be
   updated from ApexTX without returning to stock (section below). This is the
   solvable, static-analysable one.

## CE / FCC region — where it stands
- **The FCC-vs-STD app difference is now isolated: it is only the region LABEL
  logic.** In the device-info screen (~`0x0800ae1e`, next to `%sFCC`/`%sstd.`):
  the **FCC build hardcodes `movs r0,#0x50`** → always shows "FCC"; the **STD
  build reads the TX-power value** (`config+0x36`) and shows "FCC" only when it
  equals max (`0x50`=80), else "std". The value only selects the label string.
  **It is NOT a power or duty limiter.** **High.**
- **TX-power clamp is identical** in both builds (max `0x50`=80). The rest of the
  ~76-byte size delta is a separate recompile (different register/stack layout)
  plus relocation — no functional constant. **High.**
- The **NOR package (RF-module + receiver firmware) is byte-identical** FCC vs
  STD (self-verified, not just assumed). **High.**
- **No hardware region strap / option byte**: the GPIOF access is clock/oscillator
  init, the `0x1FFFF800` reference is flash management (RDP) — neither is a region
  selector. Other module GPIO inputs are SX1281 BUSY/DIO + bind button. **High.**
- The menu labelled "RF Standard" is the **protocol** selector (AFHDS3 1/2-way,
  Mini-Z), not a CE/FCC switch; `config+0x3a` is the UI language. **High.**
- Module readable radio driver: **fixed 2.4 GHz channel plan** (base reg
  `0x00b89d8a`), **no `SetTxParams` power command**, **no LBT/CAD**. **High.**
- The RF module's command handler is **obfuscated** (own 256-byte S-box, reached
  by one indirect `blx`, nothing references it as data, no plaintext decryptor).
  It is **byte-identical for FCC and STD**, so even it cannot distinguish region.
  A Unicorn emulation-from-reset attempt (does it self-decrypt into RAM?) is the
  only "make it readable" option — uncertain, since flash cannot self-decrypt
  in place for execution. **Open.**
- **Broader field:** `richardclli/Flysky-ELRS` + ELRS FRM301 branches work on the
  *same* SX128x+STM32F0 module hardware but **replace** it with ELRS, they did not
  decode AFHDS3; EdgeTX states FlySky's AFHDS3 internal API is deliberately
  *proprietary/confidential*; multiple AFHDS3-RE requests (DIY-Multiprotocol
  #231/#314/#1014) were never delivered. The modules are **CE+FCC dual-certified**
  → the hardware is region-agnostic. **High/Medium.**
- **Interpretation:** on this radio CE/FCC is a **label/declaration on
  region-agnostic, dual-certified hardware**; no readable firmware region switch
  exists anywhere. "FCC = more range" (one forum post) is **not backed by any
  readable mechanism** — both builds can emit the same max power and share the
  same module firmware. Only **measurement** could confirm a real difference:
  an ESP USART6 tap comparing stock FCC vs STD on the wire, or an RF
  spectrum/power measurement. Never to exceed a local limit. **Medium/Open.**

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
