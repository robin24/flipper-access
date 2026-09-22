#!/bin/zsh
# Compile and run the host unit tests for the screen model with clang.
set -e
ROOT="${0:A:h:h}"
SRC="$ROOT/Momentum-Firmware/applications/services/screen_reader"
OUT="${TMPDIR:-/tmp}/test_screen_model"
clang -std=c11 -Wall -Wextra -Werror -O1 -I "$SRC" -o "$OUT" \
  "$ROOT/tests/host/test_screen_model.c" "$SRC/screen_model.c"
"$OUT"
