#!/bin/zsh
# Build and run the host tests for the screen reader: the screen model, the SAM port checked
# against the original C++ synthesizer, and the speech helpers. Uses clang from Xcode.
set -e
ROOT="${0:A:h:h}"
SRC="$ROOT/Momentum-Firmware/applications/services/screen_reader"
SAM_ORIG="$ROOT/Momentum-Firmware/applications/external/text2sam"
TESTS="$ROOT/tests/host"
OUT="${TMPDIR:-/tmp}/screen_reader_host_tests"
mkdir -p "$OUT"
CFLAGS=(-std=c11 -Wall -Wextra -Werror -O1)

clang "${CFLAGS[@]}" -I "$SRC" -o "$OUT/test_screen_model" \
  "$TESTS/test_screen_model.c" "$SRC/screen_model.c"
"$OUT/test_screen_model"

clang++ -std=c++17 -O1 -w -I "$TESTS/sam_ref" -I "$SAM_ORIG" -o "$OUT/sam_reference" \
  "$TESTS/sam_ref/sam_reference.cpp" "$SAM_ORIG/stm32_sam.cpp"
clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC/sam" -I "$TESTS" -o "$OUT/test_sam_port" \
  "$TESTS/test_sam_port.c" "$SRC/sam/sam.c" -lm
"$OUT/sam_reference" > "$OUT/sam_reference.txt"
if ! "$OUT/test_sam_port" > "$OUT/sam_port.txt"; then
  cat "$OUT/sam_port.txt"
  echo "SAM port checks failed"
  exit 1
fi
if ! diff <(grep '^case' "$OUT/sam_reference.txt") <(grep '^case' "$OUT/sam_port.txt"); then
  echo "SAM port output differs from the original synthesizer"
  exit 1
fi
grep -v '^case' "$OUT/sam_port.txt"
echo "SAM port matches the original on $(grep -c '^case' "$OUT/sam_reference.txt") cases"
