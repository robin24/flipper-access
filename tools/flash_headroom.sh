#!/bin/zsh
# Firmware image size against the flash the BLE stack leaves free: the updater refuses any page
# at or above SFSA (0xD7 for ble_light 1.20.0, 880,640 bytes); fbt's .free_flash ignores this.
BIN="${0:A:h:h}/Momentum-Firmware/build/f7-firmware-C/firmware.bin"; LIMIT=880640; SIZE=$(stat -f %z "$BIN")
echo "firmware.bin $SIZE bytes, limit $LIMIT, spare $((LIMIT - SIZE)) bytes"; [ "$SIZE" -le "$LIMIT" ]
