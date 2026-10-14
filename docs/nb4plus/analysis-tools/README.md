# Analysis tools

Scripts used to compare the stock NB4 and NB4+ firmware. They need the official
FlySky updater executables (download them from FlySky yourself; no FlySky files
are part of this repository) and Python 3 with `capstone`, `unicorn` and
`pillow`. Several scripts contain addresses that only apply to NB4+ firmware
1.0.22 and NB4 firmware 2.0.116.

| Script | Purpose |
|---|---|
| `pe_rsrc.py` | Extracts the resources of an updater `.exe`; resource 900 is the application image (loaded at 0x08008000), resource 901 the NOR resource package. |
| `dis.py`, `grepdis.py`, `xref.py`, `findlit.py`, `dumpw.py`, `strs.py`, `lits.py` | Disassembly, cross references, literal and string search, peripheral base-address usage. |
| `calls2.py`, `reqcalls.py` | Lists calls of GPIO helpers / the RF request function with their constant arguments (pins, frame type, command). |
| `tmplsearch.py`, `tmplcmp.py` | Locates and compares the 168-byte receiver configuration blocks with ApexTX's `nb4DefaultReceiver`. |
| `keytab.py` | Decodes the key / encoder / power-key GPIO table. |
| `emu.py` | Runs a stock application image in the Unicorn emulator (scatter-loaded RW data) and logs every peripheral write. |
| `emu2.py` | Same for a complete ApexTX `firmware.bin` (bootloader + application). |
| `pinmap.py` | Rebuilds the final GPIO mode/alternate-function map from an emulator log. |
| `lcdspi.py`, `i2cdec.py` | Decode the bit-banged LCD SPI and touch I2C traffic from an emulator log. |
| `resexport.py` | Exports the images of a NOR resource package as PNG (for local comparison only; do not publish them). |

Results produced with these tools are summarised in [../README.md](../README.md)
and listed in [../verification](../verification).
