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

clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_screen_model" \
  "$TESTS/test_screen_model.c" "$SRC/screen_model.c"
"$OUT/test_screen_model"

clang++ -std=c++17 -O1 -w -I "$TESTS/sam_ref" -I "$SAM_ORIG" -o "$OUT/sam_reference" \
  "$TESTS/sam_ref/sam_reference.cpp" "$SAM_ORIG/stm32_sam.cpp"
clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC/sam" -I "$TESTS" -o "$OUT/test_sam_port" \
  "$TESTS/test_sam_port.c" "$SRC/sam/sam.c" -lm
# perl's alarm ends a hung run after 120 seconds (macOS has no timeout command)
if ! perl -e 'alarm 120; exec @ARGV' "$OUT/sam_reference" > "$OUT/sam_reference.txt"; then
  echo "SAM reference failed or hung"
  exit 1
fi
if ! perl -e 'alarm 120; exec @ARGV' "$OUT/test_sam_port" > "$OUT/sam_port.txt"; then
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

clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_speech_text" \
  "$TESTS/test_speech_text.c" "$SRC/speech_text.c"
if ! "$OUT/test_speech_text" > "$OUT/speech_text.txt"; then
  cat "$OUT/speech_text.txt"
  echo "speech text checks failed"
  exit 1
fi
echo "speech text: $(tail -n 1 "$OUT/speech_text.txt")"

clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_speech_queue" \
  "$TESTS/test_speech_queue.c" "$SRC/speech_queue.c"
if ! "$OUT/test_speech_queue" > "$OUT/speech_queue.txt"; then
  cat "$OUT/speech_queue.txt"
  echo "speech queue checks failed"
  exit 1
fi
echo "speech queue: $(tail -n 1 "$OUT/speech_queue.txt")"

clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_speech_pcm" \
  "$TESTS/test_speech_pcm.c" "$SRC/speech_pcm.c" -lm
if ! "$OUT/test_speech_pcm" > "$OUT/speech_pcm.txt"; then
  cat "$OUT/speech_pcm.txt"
  echo "speech PCM checks failed"
  exit 1
fi
echo "speech PCM: $(tail -n 1 "$OUT/speech_pcm.txt")"

clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_speech_voice" \
  "$TESTS/test_speech_voice.c" "$SRC/speech_voice.c"
if ! "$OUT/test_speech_voice" > "$OUT/speech_voice.txt"; then
  cat "$OUT/speech_voice.txt"
  echo "speech voice checks failed"
  exit 1
fi
echo "speech voice: $(tail -n 1 "$OUT/speech_voice.txt")"

clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_sr_chords" \
  "$TESTS/test_sr_chords.c" "$SRC/sr_chords.c"
if ! "$OUT/test_sr_chords" > "$OUT/sr_chords.txt"; then
  cat "$OUT/sr_chords.txt"
  echo "chord checks failed"
  exit 1
fi
echo "chords: $(tail -n 1 "$OUT/sr_chords.txt")"

clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_sr_throttle" \
  "$TESTS/test_sr_throttle.c" "$SRC/sr_throttle.c"
if ! "$OUT/test_sr_throttle" > "$OUT/sr_throttle.txt"; then
  cat "$OUT/sr_throttle.txt"
  echo "throttle checks failed"
  exit 1
fi
echo "throttle: $(tail -n 1 "$OUT/sr_throttle.txt")"

if ! python3 "$ROOT/tests/fbt/test_exclusions.py" > "$OUT/fbt_exclusions.txt"; then
  cat "$OUT/fbt_exclusions.txt"
  echo "fbt exclusion checks failed"
  exit 1
fi
echo "fbt exclusions: $(tail -n 1 "$OUT/fbt_exclusions.txt")"
