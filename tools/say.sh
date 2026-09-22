#!/bin/zsh
# Speak text on the Flipper Zero through the patched Text to SAM app.
#
# Usage:
#   tools/say.sh Hello there, this is the Flipper speaking
#   tools/say.sh --voice 64,72,128,128 Hello there
#
# --voice takes pitch,speed,mouth,throat (each 0 to 255).
# Defaults: pitch 64, speed 72, mouth 128, throat 128.
# Speed counts samples per frame: bigger is slower, smaller is faster.
# Text is limited to about 200 characters per call.
set -e
DIR="${0:A:h}"
ROOT="${DIR:h}"
PY="$ROOT/.venv/bin/python"
[ -x "$PY" ] || PY=python3
VOICE=""
if [ "$1" = "--voice" ]; then
  VOICE="!$2 "
  shift 2
fi
TEXT="$*"
if [ -z "$TEXT" ]; then
  echo "usage: tools/say.sh [--voice pitch,speed,mouth,throat] text to speak" >&2
  exit 1
fi
"$PY" "$DIR/flipper_cli.py" --quiet --timeout 60 "loader close" "loader open /ext/apps/Media/text2sam.fap ${VOICE}${TEXT}" | grep -v -E "^(No application is running|Application .* was closed)$" || true
