#!/bin/bash
# Firmware image size against the flash the BLE stack leaves free: the updater refuses any page
# at or above SFSA, the radio stack's first page, which fbt's .free_flash ignores. The limit is the
# radio address that the build wrote into its update package's update.fuf, less the flash base:
# 0x080D7000 for ble_light 1.20.0, 880,640 bytes. So a Momentum merge that brings a new radio
# stack moves the limit with it.
#   tools/flash_headroom.sh [BIN [PACKAGE]]
# BIN: the submodule's build/f7-firmware-C/firmware.bin unless given. PACKAGE: the update package's
# folder, by default dist/f7-C/f7-update-$DIST_SUFFIX when DIST_SUFFIX is set, as in the
# continuous build, else the newest dist/f7-C/f7-update-* folder.
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
FW="$ROOT/Momentum-Firmware"
BIN="${1:-$FW/build/f7-firmware-C/firmware.bin}"
if [ -n "${2:-}" ]; then
  PACKAGE="$2"
elif [ -n "${DIST_SUFFIX:-}" ]; then
  PACKAGE="$FW/dist/f7-C/f7-update-$DIST_SUFFIX"
else
  PACKAGE="$(ls -td "$FW"/dist/f7-C/f7-update-*/ 2>/dev/null | head -n 1)"
fi
FUF="${PACKAGE%/}/update.fuf"
if [ ! -f "$BIN" ]; then echo "no firmware image at $BIN" >&2; exit 1; fi
if [ -z "$PACKAGE" ] || [ ! -f "$FUF" ]; then
  echo "no update package at ${PACKAGE:-$FW/dist/f7-C}: build one with ./fbt updater_package" >&2
  exit 1
fi
# "Radio address: 00 70 0D 08", the bytes little-endian
set -- $(sed -n 's/^Radio address: //p' "$FUF")
if [ $# -ne 4 ] || [ $((0x$4$3$2$1)) -eq 0 ]; then
  echo "no radio address in $FUF" >&2
  exit 1
fi
RADIO=$((0x$4$3$2$1))
LIMIT=$((RADIO - 0x08000000))
SIZE=$(wc -c < "$BIN" | tr -d ' ')
echo "firmware.bin $SIZE bytes, limit $LIMIT (radio stack at $(printf '0x%08X' "$RADIO")), spare $((LIMIT - SIZE)) bytes"
if [ "$SIZE" -gt "$LIMIT" ]; then
  echo "too large by $((SIZE - LIMIT)) bytes"
  exit 1
fi
