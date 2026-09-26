#!/bin/zsh
# Build and run the host tests for the screen reader: the screen model, the speech helpers, the
# chords, the throttle, the build's exclusion filter and the built-in Sub-GHz app's source list.
# Uses clang from Xcode.
set -e
ROOT="${0:A:h:h}"
SRC="$ROOT/Momentum-Firmware/applications/services/screen_reader"
TESTS="$ROOT/tests/host"
OUT="${TMPDIR:-/tmp}/screen_reader_host_tests"
mkdir -p "$OUT"
CFLAGS=(-std=c11 -Wall -Wextra -Werror -O1)

clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_screen_model" \
  "$TESTS/test_screen_model.c" "$SRC/screen_model.c"
"$OUT/test_screen_model"

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
echo "$(tail -n 1 "$OUT/fbt_exclusions.txt")"

if ! python3 "$ROOT/tests/fbt/test_subghz_sources.py" > "$OUT/subghz_sources.txt"; then
  cat "$OUT/subghz_sources.txt"
  echo "Sub-GHz source list checks failed"
  exit 1
fi
echo "$(tail -n 1 "$OUT/subghz_sources.txt")"

if ! python3 "$ROOT/tests/fbt/test_card_prune.py" > "$OUT/card_prune.txt"; then
  cat "$OUT/card_prune.txt"
  echo "card prune checks failed"
  exit 1
fi
echo "$(tail -n 1 "$OUT/card_prune.txt")"
