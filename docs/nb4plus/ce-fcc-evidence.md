# CE vs FCC: evidence that the two EU packages are the same program

This page records a concrete, reproducible comparison of FlySky's two **Noble+
EU** firmware packages and what it means for regions and for a single worldwide
ApexTX build. It complements [UPDATES.md](UPDATES.md) (the practical summary)
and [FINDINGS.md](FINDINGS.md) (the RF-stack findings).

No FlySky files are part of this repository. Everything below is an observation
(sizes, addresses, equal/not-equal) made with the scripts in
[analysis-tools](analysis-tools); the firmware updaters must be obtained from
FlySky.

Certainty tags as in [FINDINGS.md](FINDINGS.md): **High** = read directly and
byte-compared; **Medium** = interpretation; **Open** = needs more work.

## What was compared

- The user's own internal-flash dump of a Noble NB4+ (application at file
  offset 0x8000, base 0x08008000).
- FlySky's official Noble+ EU updater **1.0.22FCC** (application = PE resource
  `10/900`).
- FlySky's official Noble+ EU updaters **1.0.31-4 "FCC"** and **1.0.31-4**
  (no suffix = the STD / ETSI build), both PE resources `10/900` (app) and
  `10/901` (NOR resource package).

Resources were extracted statically with `pe_rsrc.py` (the updater `.exe` is
read as data, never executed).

## Findings

| Finding | How we know | Certainty |
|---|---|---|
| The user's device runs stock **1.0.22 "Noble+ EU FCC"**. | The flash dump's application region is **byte-identical** to the updater's resource 900 (len 891 634). | High |
| For 1.0.31-4, the **NOR package (resource 901) is byte-identical** between the FCC and the STD build (5 695 344 B). | Byte compare. | High |
| The NOR package embeds **nine real Cortex-M firmware images** (RF module + receiver firmwares). | Strict vector-table scan: nine locations with 44–47 valid handlers, SP in 0x2000xxxx, reset in 0x0800xxxx. | High |
| Those embedded RF/receiver firmwares are therefore **region-neutral** (identical in FCC and STD). | Follows from resource 901 being byte-identical. | High |
| The **application (resource 900) is the same program** in FCC and STD. | STD is only **84 bytes larger** (894 650 vs 894 566). All real strings are identical (5 053 common; the ~30 "only in one" hits are mis-disassembled code fragments, not text). | High |
| The remaining app difference is **relocation plus trivial code-layout**, not a region value. | Pointer/branch-normalised instruction diff: 387 908 vs 387 943 instructions (STD +35). Every large "difference" resolves to relocated `bl`/pointer operands or a different switch/case layout; the referenced **data is identical**. | High |
| The region label (`…FCC` vs `…std`) is produced **at runtime**, not from a build constant. | The region byte lives in the config struct at `[0x200000bc]+0x3a`; it is written from a lookup table (FCC `0x8095c28` / STD `0x8095c78`) indexed by the RF-standard/module index and gated by the RF-module state. The table and the surrounding code are identical in both builds. | High |
| The **default RF/receiver parameter templates** the app copies are byte-identical between FCC and STD. | The copy routine near `0x0805fe84` loads templates from flash (FCC `0x80a0fe8…`, STD `0x80a1038…`, differing only by the +0x50 relocation); the template bytes compare equal. Consistent with FINDINGS.md's "168-byte default receiver blocks". | High |

## Conclusion

- **EU FCC and EU STD are functionally the same firmware.** The flashed
  binaries (RF module + receiver firmware in the NOR package) are identical, and
  the application differs only by relocation and a trivial code-layout change
  with identical data. No region-specific constant, power value or channel table
  could be isolated in the application.
- The **region is a runtime/RF-side matter** (RF-standard and TX-power
  settings), consistent with [UPDATES.md](UPDATES.md): the transmitter manages
  the region and the RF module keeps its own firmware.
- **One ApexTX build serves worldwide.** ApexTX replaces the (region-neutral)
  application; it does not touch the RF module or the receiver firmware. CE vs
  FCC therefore rides on the RF-standard/power settings and the RF module, not
  on a separate ApexTX image.
- Receiver firmware is **carried inside the stock transmitter package** (the
  nine NOR images) and pushed over the air by the RF module – which is why a
  stock receiver update needs no extra download. ApexTX does not implement this
  path (see [UPDATES.md](UPDATES.md)).

**Regulatory note:** operate the radio only in the region that is legal where it
is used. This analysis is about *how* the firmware is structured, not a licence
to exceed local limits.

## Reproduce

From a neutral directory, with the portable Python that has `capstone`
(do not run the scripts from inside `analysis-tools` – a local `dis.py` there
shadows the stdlib module):

1. `pe_rsrc.py <EU_FCC_updater.exe> out_fcc` and `pe_rsrc.py <EU_STD_updater.exe> out_std`.
2. Byte-compare `out_*/10_901_1033` (equal) and `out_*/10_900_1033` (84-byte size
   difference).
3. Compare the real string sets of the two `10_900` blobs (identical).
4. Normalised instruction diff of the two `10_900` blobs (difference is
   relocation + layout only).
