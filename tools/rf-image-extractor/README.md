# ApexTX RF Image Extractor (proposal for #23 / #33)

A small Windows tool in the style of the ApexTX Flasher and Theme Editor. It
unpacks the RF-module and receiver firmware images from the user's own FlySky
Noble NB4/NB4+ updater `.exe` and writes them to the radio's USB storage
(`FIRMWARE/`) or to a local folder. The updater is parsed as data and never
executed. No FlySky files are bundled.

This is offered as a reference only. Use whatever parts are helpful.

## How it works

- Reads the PE resource `10/901` (the NOR firmware package) from the updater.
- Finds the `Firmware` section through the package's own section table, not
  through fixed offsets, and lists every embedded image (type, product ID,
  version, size).
- Names receivers via the ApexTX `PN_*` product table and runs a plausibility
  check (Cortex-M stack pointer and reset vector).
- Writes every image found. It does not pin source or image hashes, so it is
  less strict than the catalog in #33.

## Checked against

`Flysky_NoblePlusEU_UpdateFirmware_1031-4FCC.exe` (SHA-256
`5f5475055b7d4e19fc647f4180b30e478e72a68ef0987aefdbfe1d6f9fd6c248`,
the same file pinned as `nb4plus-1.0.31-eu-fcc` in #33). It contains nine
images. The three images pinned in #33 come out byte-identical (same SHA-256).

| Image | Product | Version | Bytes | SHA-256 |
| --- | --- | --- | --- | --- |
| RF module | `0x12340003` | `0x10021` | 38954 | `9f91794947ca8c24b6e3b242d373b9d02c17d794e4b794f2584341231bbe9b25` |
| RF module | `0x12340009` | `0x10004` | 12130 | `76c55274d00f88a00c39a9599fc953309e5791c79d080e636cf79ec60bbff485` |
| FGr4 | `0x12340004` | `0x113` | 51432 | `cbb5021a4a8824d246886d3745b3742ede7f9e0a4bdac89311c699042f753859` |
| FGr4S / FTr4 (shared ID) | `0x12340006` | `0x111` | 50596 | `adaed3edf380bfce83b04342cffb2e12ab8b87311975bb5ea720261421cc6a84` |
| Mini-Z | `0x00010104` | `0x108` | 52056 | `9e9411c68a76be97b0a429c69e5f7d8abb11492530f8fad74bf187d893ef628e` |
| FGr8B | `0x00010107` | `0x117` | 88320 | `f0f25179d309f90d2d33611cbbacae200457c058aee3d2255b558e5eaaa5a37a` |
| FGr12B | `0x00010108` | `0x117` | 88916 | `0e9f277a34fb8a6b1432fa665e2f5616344477867668243c0bd38e0cc83a9ed1` |
| INr4-GYB | `0x0001010b` | `0x109` | 71344 | `74e5ae3b30e24b15078f138fc82b6f7ac96cc2bad1dcc75df4b034a46b2aa5a3` |
| FGr4B | `0x0001010e` | `0x117` | 86780 | `9d5c95fa810e97c424a2898463964cae2e2f9239afeab6c25252d120c58f570d` |

Not supported: the older NB4+ 1.0.22 updater uses a different package format
and is rejected. The original NB4 2.0.116 packages were not tested.

## Run

```sh
python apextx-rf-image-extractor.py                  # local web UI
python apextx-rf-image-extractor.py UPDATER.exe OUT  # command line
```

Build a standalone `.exe`: `pwsh build-windows-rf-image-extractor.ps1`
(Python 3.11+).
