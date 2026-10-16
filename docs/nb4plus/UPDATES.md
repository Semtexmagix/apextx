# Regions, RF module and receivers

This page explains which firmware ApexTX replaces, which it does not touch, and
what that means for regions and for updates. It is meant to help NB4+ users in
different countries understand what works and what does not.

## Three separate pieces of firmware

An AFHDS3 setup has three independent parts, each with its own firmware and its
own update path:

| Part | Who owns it | ApexTX |
|---|---|---|
| **Transmitter** (the main STM32 in the radio) | this is what ApexTX replaces | updated with ApexTX's own updater; FlySky's updater restores the stock firmware |
| **RF module** (a separate chip inside the radio) | FlySky | **not touched by ApexTX**; it keeps its own firmware |
| **Receiver** (in the vehicle) | FlySky | **not updated or reflashed by ApexTX** |

## Regions (CE / FCC)

- The region (CE for Europe, FCC for the Americas) is normally a **setting**
  that the transmitter side manages and sends to the RF module, not a separate
  firmware flash.
- On the NB4 path that `NB4_PLUS_HW` is based on, ApexTX does **not** send a
  region setting and does not expose a selector; it keeps whatever region the
  module already has. It does not force CE or FCC. See
  [FINDINGS.md](FINDINGS.md#rf-region-ce--fcc-in-apextx).
- **Operate the radio only in the region that is legal where you use it.** This
  is the user's responsibility, exactly as with the stock firmware.

## Receivers: the important limitation

FlySky receivers are normally updated **through the transmitter**. ApexTX, like
EdgeTX, can bind a receiver, set failsafe and read telemetry, but it **cannot
update or reflash a FlySky receiver**. So while ApexTX is installed, the
in-radio receiver-update path is not available.

If you need to update a receiver's firmware, or change a receiver's region
through the radio, the practical way is:

1. Keep your internal-flash backup (see [TESTING.md](TESTING.md), step 3).
2. Temporarily restore the stock FlySky firmware ([TESTING.md](TESTING.md),
   step 10).
3. Do the receiver update/configuration with FlySky's normal tools.
4. Flash ApexTX back.

**Not confirmed:** FlySky also publishes a standalone "receiver updater"
program. Whether it reaches the receiver only through a transmitter or also
through a direct connection is not established here. If a direct path exists,
the detour via stock firmware may not be needed. This is a good question for
the FlySky community or the ApexTX maintainer.

## Could receiver updates be added to ApexTX?

In principle yes – ApexTX's internal RF support was created by reverse
engineering the stock AFHDS3 protocol, and the receiver-update exchange could
be studied the same way. But it is a **large and risky** piece of work:

- The receiver-update protocol is more involved than normal binding.
- A failed receiver update can brick a receiver, so it needs very careful
  testing.
- It belongs with the person who maintains the RF stack rather than being
  bolted on separately.

It is therefore listed as possible future work in [STATUS.md](STATUS.md), not
as something this fork implements.

## Summary for different countries

- **EU users:** run the radio in CE. ApexTX does not change the region, so a
  radio/module already set to CE stays CE.
- **US users:** run the radio in FCC, which is the legal mode there.
- **Everyone:** receiver firmware updates and receiver region changes still go
  through FlySky's own tools, which currently means temporarily returning to
  the stock transmitter firmware.
