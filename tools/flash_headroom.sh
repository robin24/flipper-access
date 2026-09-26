#!/bin/bash
# Firmware image size against the flash the BLE stack leaves free: the updater refuses any page
# at or above SFSA (0xD7 for ble_light 1.20.0, 880,640 bytes); fbt's .free_flash ignores this.
#   tools/flash_headroom.sh [BIN]   (default: the submodule's build/f7-firmware-C/firmware.bin)
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
BIN="${1:-$ROOT/Momentum-Firmware/build/f7-firmware-C/firmware.bin}"
LIMIT=880640
if [ ! -f "$BIN" ]; then echo "no firmware image at $BIN" >&2; exit 1; fi
SIZE=$(wc -c < "$BIN" | tr -d ' ')
echo "firmware.bin $SIZE bytes, limit $LIMIT, spare $((LIMIT - SIZE)) bytes"
if [ "$SIZE" -gt "$LIMIT" ]; then
  echo "too large by $((SIZE - LIMIT)) bytes"
  exit 1
fi
