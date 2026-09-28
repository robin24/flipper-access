#!/bin/bash
# Build and run the host tests for the screen reader with clang: the screen model, the speech
# helpers, the chords and the throttle; and tests/host/tar_unpack.c, the firmware's tar reader
# unpacking as the device does, for the voice pack check. Then the Python checks: the build's
# exclusion filter, the built-in Sub-GHz app's source list, and the tests of six tools:
# tests/fbt/test_card_prune.py, test_strip_js_symbols.py, test_subghz_manifest.py,
# test_upstream_check.py, test_voice_build.py and test_voice_pack.py. Each Python check prints its
# skip lines, then its summary, so a run shows what it left out, such as the golden checks that
# need upstream/dev, which the continuous build does not have, or the voice generator's resampler
# checks, which need numpy and scipy.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
SRC="$ROOT/Momentum-Firmware/applications/services/screen_reader"
TESTS="$ROOT/tests/host"
OUT="${TMPDIR:-/tmp}/screen_reader_host_tests"
mkdir -p "$OUT"
CFLAGS=(-std=c11 -Wall -Wextra -Werror -O1)

# A Python check's skip lines, then its last line, its summary, unless that was a skip line too.
summary() {
  awk '/^skipped/ { print } { last = $0; skip = /^skipped/ } END { if (!skip) print last }' "$1"
}

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

# The firmware's own tar reader walked as the device unpacks, for test_voice_pack.py. lib/microtar
# is one of the firmware's submodules, which fbt checks out on its first run; without it the
# voice pack check says it skipped the unpack.
MICROTAR="$ROOT/Momentum-Firmware/lib/microtar/src"
TAR_UNPACK=""
if [ -f "$MICROTAR/microtar.c" ]; then
  clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
    -I "$MICROTAR" -o "$OUT/tar_unpack" \
    "$TESTS/tar_unpack.c" "$MICROTAR/microtar.c" "$MICROTAR/microtar-stdio.c"
  TAR_UNPACK="$OUT/tar_unpack"
fi

if ! python3 "$ROOT/tests/fbt/test_exclusions.py" > "$OUT/fbt_exclusions.txt"; then
  cat "$OUT/fbt_exclusions.txt"
  echo "fbt exclusion checks failed"
  exit 1
fi
summary "$OUT/fbt_exclusions.txt"

if ! python3 "$ROOT/tests/fbt/test_subghz_sources.py" > "$OUT/subghz_sources.txt"; then
  cat "$OUT/subghz_sources.txt"
  echo "Sub-GHz source list checks failed"
  exit 1
fi
summary "$OUT/subghz_sources.txt"

if ! python3 "$ROOT/tests/fbt/test_card_prune.py" > "$OUT/card_prune.txt"; then
  cat "$OUT/card_prune.txt"
  echo "card prune checks failed"
  exit 1
fi
summary "$OUT/card_prune.txt"

if ! python3 "$ROOT/tests/fbt/test_strip_js_symbols.py" > "$OUT/strip_js_symbols.txt"; then
  cat "$OUT/strip_js_symbols.txt"
  echo "strip js symbols checks failed"
  exit 1
fi
summary "$OUT/strip_js_symbols.txt"

if ! python3 "$ROOT/tests/fbt/test_subghz_manifest.py" > "$OUT/subghz_manifest.txt"; then
  cat "$OUT/subghz_manifest.txt"
  echo "Sub-GHz manifest checks failed"
  exit 1
fi
summary "$OUT/subghz_manifest.txt"

if ! python3 "$ROOT/tests/fbt/test_upstream_check.py" > "$OUT/upstream_check.txt"; then
  cat "$OUT/upstream_check.txt"
  echo "upstream check checks failed"
  exit 1
fi
summary "$OUT/upstream_check.txt"

if ! python3 "$ROOT/tests/fbt/test_voice_build.py" > "$OUT/voice_build.txt"; then
  cat "$OUT/voice_build.txt"
  echo "voice build checks failed"
  exit 1
fi
summary "$OUT/voice_build.txt"

if ! TAR_UNPACK="$TAR_UNPACK" python3 "$ROOT/tests/fbt/test_voice_pack.py" > "$OUT/voice_pack.txt"; then
  cat "$OUT/voice_pack.txt"
  echo "voice pack checks failed"
  exit 1
fi
summary "$OUT/voice_pack.txt"
