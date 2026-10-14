#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Builds the RAM-only NOR reader. -O0 is deliberate: the Unicorn emulator used
# by the tests mishandles Thumb IT blocks, and -O0 emits none, so the tested
# binary is exactly the one that would run on the radio.
set -e
cd "$(dirname "$0")"
CC=${CROSS_COMPILE:-arm-none-eabi-}
"${CC}gcc" -mcpu=cortex-m4 -mthumb -O0 -ffreestanding -nostdlib -fno-builtin \
  -Wall -Wextra -T link.ld -Wl,--gc-sections -o dumper.elf dumper.c
"${CC}objcopy" -O binary dumper.elf dumper.bin
if "${CC}objdump" -d dumper.elf | grep -qE '\sit[te]*\s'; then
  echo "error: IT blocks present" >&2
  exit 1
fi
sha256sum dumper.bin
