#!/usr/bin/env python3
"""tools/voice_build.py's pure helpers: set names, the local and card folders of a set, the
per-backend settings and their line for voice.txt, the resampler's length and level. Also the
re-keying of a manifest made before the sets, the refusal of a run that names another backend or
voice than the set was made with, the moves of --migrate-sets, and the engine check before the
pool starts. Importable without pyserial, numpy or the engines (they are imported where they are
used). Run from the project root: python3 tests/fbt/test_voice_build.py"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import voice_build as vb  # noqa: E402

failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


for name in ["samantha", "heart", "espeak", "en-us_f3", "a" * 31]:
    check(vb.set_valid(name), f"valid set name: {name}")
for name in ["", "Heart", "two words", "a/b", ".", "a" * 32, "héart", "auto"]:
    check(not vb.set_valid(name), f"invalid set name: {name!r}")
check(vb.set_local_dir("samantha") == os.path.join(ROOT, "voice"), "the Samantha set lives in voice/")
check(vb.set_local_dir("heart") == os.path.join(ROOT, "voices", "heart"), "other sets live in voices/<set>/")
check(vb.set_card_dir("heart") == "/ext/sr/voices/heart", "the card folder of a set")
check(sorted(vb.BACKENDS) == ["espeak", "kokoro", "say"], "three backends")
s = vb.settings_for("say", {})
check(s["voice"] == "Samantha" and s["rate"] == 175 and s["highpass"] == 500.0 and s["gain"] == 1.3 and s["soft"] is True and s["hz"] == 16000, f"say defaults: {s}")
check(vb.settings_line(s) == "say Samantha rate 175 highpass 500 gain 1.3 soft 16000", f"the say line: {vb.settings_line(s)}")
s = vb.settings_for("espeak", {"gain": 1.5})
check(s["voice"] == "en-us+f3" and s["rate"] == 160 and s["gain"] == 1.5, f"espeak defaults with an override: {s}")
check(vb.settings_line(s) == "espeak en-us+f3 rate 160 highpass 500 gain 1.5 soft 16000", f"the espeak line: {vb.settings_line(s)}")
s = vb.settings_for("kokoro", {"soft": False})
check(s["voice"] == "af_heart" and s["rate"] == 100 and s["soft"] is False, f"kokoro defaults with an override: {s}")
check(vb.settings_line(s) == "kokoro af_heart rate 100 highpass 500 gain 1.3 hard 16000", f"the kokoro line: {vb.settings_line(s)}")
check(len(vb.settings_line(s)) <= 63, "the line fits the device's status field")
try:
    vb.settings_for("piper", {})
    check(False, "an unknown backend is refused")
except (KeyError, ValueError, SystemExit):
    check(True, "an unknown backend is refused")
check(vb.settings_hash(vb.settings_for("kokoro", {}), "x") != vb.settings_hash(vb.settings_for("kokoro", {"model_sha256": "abc"}), "x"), "the model's checksum is part of the settings hash")

# A manifest from before the sets recorded its settings with the first generator's empty model
# path, and the hash covers every key: the clips are the same, so each hash that verifies against
# the recorded settings is re-keyed, in the manifest and in the sync record, and nothing is made
# or sent again. A hash that does not verify is left, so that clip is made or sent again.
new = vb.settings_for("say", {})
old = {**new, "model": ""}
manifest = {"settings": dict(old), "words": {
    "home": vb.settings_hash(old, "home"),
    "dont": vb.settings_hash(old, "don't"),
    "stale": "0123456789abcdef",
}}
synced = {"home": manifest["words"]["home"], "dont": "fedcba9876543210", "stale": "0123456789abcdef"}
check(vb.rekey_legacy(manifest, synced, new, {"dont": "don't"}) == 2, "the two clips that verify are re-keyed")
check(manifest["words"]["home"] == vb.settings_hash(new, "home"), "a re-keyed word holds the new hash")
check(manifest["words"]["dont"] == vb.settings_hash(new, "don't"), "a word is verified with its spoken text")
check(manifest["words"]["stale"] == "0123456789abcdef", "a hash that does not verify is left")
check(synced["home"] == vb.settings_hash(new, "home"), "the sync record follows the manifest")
check(synced["dont"] == "fedcba9876543210", "a sync record of another rendition is left")
check(manifest["settings"] == new, "the manifest records the new settings")
check(vb.rekey_legacy(manifest, synced, new, {"dont": "don't"}) == 0, "a second pass changes nothing")
gain = {**old, "gain": 1.6}
changed = {"settings": dict(gain), "words": {"home": vb.settings_hash(gain, "home")}}
check(vb.rekey_legacy(changed, {}, new, {}) == 0 and changed["words"]["home"] == vb.settings_hash(gain, "home"),
      "a manifest made with other settings is not re-keyed")
check(vb.rekey_legacy({"words": {}}, {}, new, {}) == 0, "a new set has nothing to re-key")

# A set stands for one backend and voice: a run that names others is refused
kokoro = vb.settings_for("kokoro", {"model_sha256": "x"})
check(vb.set_conflict(None, new) is None, "a new set has nothing to conflict with")
check(vb.set_conflict(old, new) is None, "the same backend and voice")
check(vb.set_conflict({**kokoro, "gain": 1.6}, kokoro) is None, "a changed processing setting is no conflict")
check(vb.set_conflict(kokoro, new) is not None, "a kokoro set refuses a run with the say defaults")
check(vb.set_conflict(kokoro, vb.settings_for("kokoro", {"voice": "bf_emma", "model_sha256": "x"})) is not None,
      "and a run with another voice")


# --migrate-sets: the first layout's folder and missing list move into the samantha set; a
# destination that is there already refuses the whole migration
def migration(*paths):
    return vb.migration_plan(lambda p: p in paths)


check(migration("/ext/sr/voice", "/ext/sr/missing.txt") == ([("/ext/sr/voice", "/ext/sr/voices/samantha"),
      ("/ext/sr/missing.txt", "/ext/sr/voices/samantha/missing.txt")], None), "the folder and the missing list move")
check(migration("/ext/sr/voice") == ([("/ext/sr/voice", "/ext/sr/voices/samantha")], None), "the folder alone")
check(migration("/ext/sr/voices", "/ext/sr/voices/samantha") == ([], None), "nothing left to move")
moves, refusal = migration("/ext/sr/voice", "/ext/sr/voices/samantha")
check(moves == [] and refusal is not None and "/ext/sr/voices/samantha" in refusal, f"an existing set is never moved over: {refusal}")
moves, refusal = migration("/ext/sr/voice", "/ext/sr/missing.txt", "/ext/sr/voices/samantha/missing.txt")
check(moves == [] and refusal is not None, "nor an existing missing list, and then nothing moves")

check(vb.engine_problem(vb.settings_for("kokoro", {"model": "/nonexistent/kokoro.onnx", "model_sha256": "x"})) is not None,
      "a missing model is refused before the pool starts")

try:
    import numpy as np
    import scipy.signal  # noqa: F401  (the resampler's filter)
except ImportError:
    print("skipped the resampler checks: no numpy or scipy")
else:
    t = np.arange(24000) / 24000.0
    x = (0.5 * np.sin(2 * math.pi * 440 * t)).astype(np.float32)
    y = vb.resample(x, 24000, 16000)
    check(abs(len(y) - 16000) <= 2, f"24 kHz to 16 kHz keeps the duration: {len(y)}")
    check(0.45 < float(np.max(np.abs(y))) < 0.55, f"the level is kept: {float(np.max(np.abs(y))):.3f}")
    y = vb.resample(x[:22050], 22050, 16000)
    check(abs(len(y) - 16000) <= 2, f"22.05 kHz to 16 kHz keeps the duration: {len(y)}")
    check(len(vb.resample(x[:1600], 16000, 16000)) == 1600, "same rate: unchanged length")

print(f"voice build: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
