# RF standard / region: where the stock radio sets it (and why ApexTX cannot just copy a command)

This page follows up on [ce-fcc-evidence.md](ce-fcc-evidence.md) and the
"Regions (CE / FCC)" section of [UPDATES.md](UPDATES.md). It records a
**static** trace of the stock FlySky Noble NB4/NB4+ firmware to answer one
question: *which command does the stock radio use to set the regional RF
standard (CE/ETSI vs FCC) in the internal RF module, so ApexTX could offer a
region selector that lets CE receivers bind in Europe and FCC receivers in the
US?*

The goal is a legitimate compliance/portability feature (the correct region per
location). It is **not** about raising transmit power above any local limit.

No FlySky files are in this repository. Everything below is an observation
(addresses, table contents, equal/not-equal) made against the 1.0.22 "Noble+ EU
FCC" application (PE resource 10/900, base `0x08008000`, byte-identical to a
Noble NB4+ internal-flash dump) and its NOR package (resource 10/901). The
method matches [analysis-tools](analysis-tools); updaters must be obtained from
FlySky.

Certainty tags as elsewhere: **High** = read directly / byte-compared,
**Medium** = interpretation, **Open** = needs hardware or more work.

## TL;DR

- The stock menu literally called **"RF Standard" / "RF Std."** (confirmation
  *"This will change RF standard."*) is the **RF protocol selector**
  — AFHDS3 1-Way / AFHDS3 2-Way / Mini-Z(EVO) / Mini-Z(EVO2) / Mini-Z(FHSS) —
  **not** a CE/FCC region switch. **High.**
- The CE/FCC regulatory region (the `FCC` vs `std.` suffix in the version
  string) is **not switched by any runtime menu/command** in the app; in the EU
  FCC build the on-screen choice resolves to FCC. **High/Medium.**
- No dedicated *"set CE/FCC region"* AFHDS3 command was found in the app, nor in
  the readable part of the embedded RF-module firmware. The module's actual
  command handler sits in an **encrypted/obfuscated blob** in the NOR package
  and is not statically recoverable. **High** (that it is not readable),
  **Open** (whether a region command exists inside it).
- Every embedded firmware in the NOR package (RF module + all receivers) is
  **FCC/STD byte-identical**, so no region is compiled in differently. **High.**
- Net: CE/FCC is governed by the **RF module (hardware/runtime)**, consistent
  with [ce-fcc-evidence.md](ce-fcc-evidence.md). A region selector in ApexTX can
  only work **if** the module honours a region/EMI value at runtime — which has
  to be confirmed on hardware.

## 1. The "RF Standard" menu is the protocol selector (not CE/FCC)

- String IDs: `0x308` = `RF Std.`, `0x309` = `RF Standard`.
- Option table at **`0x080952a0`** (3-byte entries `{code, u16 string_id}`):
  `0 -> AFHDS3 1 Way (0x30a)`, `1 -> AFHDS3 2 Way (0x30b)`,
  `2 -> Mini-Z(EVO) (0x30c)`, `3 -> Mini-Z(EVO2) (0x30d)`,
  `4 -> Mini-Z(FHSS) (0x30e)`.
- Current value lives at **`[0x200000c0]+0x1544`** (0..4). The row renderer
  `0x08068030` switches on it to show those five labels.
- The selector `0x08067b08` writes the new value and, on change
  (`0x08067bba`), dispatches RF parameter **pid 0x02** (`0x08067bd0`). The
  *"This will change RF standard."* confirmation belongs to this (switching
  protocol forces a re-bind).

**High** – read directly from the option table and the row/selector handlers.

## 2. `config+0x3a` is the UI language, not the region

An earlier lead held that region lived at `[0x200000bc]+0x3a`. Re-tracing shows
that field is the **UI language** (`English=0 … Deutsch=3`): it is passed as the
second argument to `getText(id, lang)` (e.g. `0x08067900`:
`ldrb r1,[cfg+0x3a]; movw r0,#0x309; bl getText`), and the language selector
`0x0804dc80` writes it from table `0x08095268` (IDs `0x2f0`=English /
`0x2f3`=Deutsch). The tables `0x08095c28`/`0x08095c78` that the earlier lead
named are **telemetry/alarm definitions** (Low Signal Alarm, Sound, Vibration,
RX/TX/BVD voltage, Steering, Throttle …), not region tables. **High.**

## 3. The stock RF parameter-command mechanism

All RF settings go through one dispatcher:

1. `0x0805b258(pid, …)` binary-searches a registry at **`0x080ca7cc`**
   (33 entries, 8 bytes: `{pid, precond, u16, fn_ptr}`) and calls the handler.
2. Each handler builds a 42-byte descriptor `{op, count, u16 cmd, u16 val, …}`
   and enqueues it (`0x080750d4`) into a 6-slot queue at **`0x200272ec`**.
3. The RF-TX state machine (`0x08077dc6…`, work buffer `0x20027412`) serialises
   it to the module.

Resolved internal opcodes: pid `0x02 -> 0x5b` (RF protocol = the "RF Standard"
menu), `0x03 -> 0x5c`, `0x04 -> 0x5e` (config), `0x13 -> 0x5d`. **None carries a
CE/FCC region value.** (These are the app-internal UI→RF opcodes; the final
AFHDS3 wire bytes are produced downstream.) **High/Medium.**

## 4. CE/FCC display is build-fixed

The `FCC` / `std.` suffix is built in `0x0800adf0`
(`adr -> "%sFCC" @0x800b113` vs `adr -> "%sstd." @0x800b11c`); in the EU FCC
build the branch resolves to FCC. There is no option string `CE`/`ETSI`/
`Region`/`Country` anywhere, and no dispatcher call switches it. **Medium.**

## 5. The embedded RF-module firmware (NOR resource 10/901)

- The NOR package starts with a `5A5A` header + a TOC, then multiple embedded
  Cortex-M firmwares (RF module + receivers). All plaintext ARM Thumb
  (entropy ~6.6, not whole-image encrypted). **High.**
- The **RF module** firmware is identified by its AFHDS3 UART/SLIP parser at
  `0x08007b3c` (START/END `0xC0`, ESC `0xDB/0xDC/0xDD`, CRC = `sum ^ 0xFF`) —
  exactly the framing in [afhds3_transport.cpp](../../radio/src/pulses/afhds3_transport.cpp).
  Reassembled contiguously (NOR `0x167c..0xde0c`, base `0x08000000`, ~51 KB);
  the reset vector and interrupt handlers resolve to valid code. **High.**
- **But the command handler is not readable.** After a valid CRC the parser
  `blx`-calls a single callback **`0x08009605`** (its only caller:
  `0x080064ee ldr r0,=08009605`). That address lies in a high-entropy blob
  (`0x08009280..0x0800982c`, ~1.4 KB) that disassembles to garbage, is not
  single-byte-XOR code, and is referenced by **nothing else in the image** (no
  code, no data pool). In other words the module's framework/comms layer is
  plaintext, but the actual command-processing code is a protected
  (encrypted/obfuscated, or hardware-flash-decrypted) payload. **High.**
- That blob is **FCC/STD byte-identical** too, so even the protected handler
  carries no region-specific difference. **High.**

→ The module's channel/power/region logic cannot be recovered statically from
the NOR package. **Open.**

## 6. What ApexTX does today, and the open question

EdgeTX/ApexTX already has `eLNK_EMIStandard {LNK_ES_FREE=0, LNK_ES_CE=1,
LNK_ES_FCC=2}` and an `EMIStandard` byte in `sDATA_ConfigV0/V1`
([afhds3_config.h](../../radio/src/pulses/afhds3_config.h)); on external modules
it is sent inside `MODULE_SET_CONFIG (0x04)`. On the **NB4 internal path**,
`afhds3_nb4.h::Nb4RfConfig::page()` does **not** serialise an EMIStandard byte,
and `moduleData->afhds3.emi` is only populated from `MODULE_GET_CONFIG`, which
the NB4 module does not answer. So ApexTX currently sends no region — just like
the stock app on this path.

**Open question (help welcome):** does the NB4 internal RF module honour an
`EMIStandard`/region byte if we include it in `MODULE_SET_CONFIG` (or in any
other command)? If yes, a single worldwide ApexTX build could expose a CE/FCC
selector. If no, the region is fixed by the module hardware/firmware and no
transmitter-side command can change it.

The cheapest decisive test is on hardware: add the `EMIStandard` byte to the NB4
`MODULE_SET_CONFIG` payload and check whether a CE receiver vs an FCC receiver
binds accordingly. A logic-analyzer capture of the stock radio's module UART
while toggling settings would also show any region frame directly.

If anyone has FlySky AFHDS3 module-protocol notes (especially a region/EMI or
channel-plan command), that would shortcut this.
