#!/usr/bin/env python3
"""tools/voice_pack.py: pack(set_dir, set_name, version, out_path) writes a voice set as a release
asset, a plain tar laid out as the card reads it -- sr/voices/<set>/voice.txt,
sr/voices/<set>/LICENSE.txt and the clips in their 64 hashed folders (voice_build.bucket), nothing
else: the local manifest.json and synced.json stay out. A set made with the macOS voices is
refused (Apple licenses them for the Mac only) unless personal=True, and a pack that fails partway
-- a manifest word with no clip on disk -- leaves nothing at out_path, not even a partial file.
licence_text(settings) names the engine, the voice and the terms. Run from the project root:
python3 tests/fbt/test_voice_pack.py"""
import json
import os
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from voice_build import bucket, initial  # noqa: E402
from voice_pack import licence_text, pack  # noqa: E402

failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def make_set(tmp, name, backend="kokoro", voice="af_heart", words=None):
    """A throwaway set directory: manifest.json, voice.txt and one clip per word under its
    <initial>/ folder -- the layout the generator keeps on the Mac (voice_build.initial), not the
    card's hashed one that pack() must translate into."""
    words = {"a": "hash-a", "b": "hash-b"} if words is None else words
    set_dir = os.path.join(tmp, name)
    os.makedirs(set_dir, exist_ok=True)
    manifest = {"set": name, "settings": {"backend": backend, "voice": voice, "rate": 100}, "words": dict(words)}
    with open(os.path.join(set_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f)
    with open(os.path.join(set_dir, "voice.txt"), "w", encoding="utf-8") as f:
        f.write(f"{backend} {voice} rate 100 highpass 500 gain 1.3 soft 16000\n")
    for word in words:
        clip_dir = os.path.join(set_dir, initial(word))
        os.makedirs(clip_dir, exist_ok=True)
        with open(os.path.join(clip_dir, word + ".raw"), "wb") as f:
            f.write(f"clip-{word}".encode() * 4)
    return set_dir


with tempfile.TemporaryDirectory() as tmp:
    # A set's tar: voice.txt, LICENSE.txt, then the clips in sorted-word order, each moved from
    # its local <initial>/ folder to the card's hashed one -- exactly, nothing more.
    set_dir = make_set(tmp, "heart", words={"a": "hash-a", "b": "hash-b"})
    out = os.path.join(tmp, "out.tar")
    count = pack(set_dir, "heart", "0.1.0", out)
    check(count == 2, f"two clips packed: {count}")
    prefix = "sr/voices/heart"
    bucket_a, bucket_b = bucket("a"), bucket("b")
    expected = [f"{prefix}/voice.txt", f"{prefix}/LICENSE.txt", f"{prefix}/{bucket_a}/a.raw", f"{prefix}/{bucket_b}/b.raw"]
    with tarfile.open(out) as tar:
        names = tar.getnames()
        check(names == expected, f"exactly the set's files, in that order, no manifest.json or synced.json: {names}")
        check(tar.extractfile(f"{prefix}/{bucket_a}/a.raw").read() == b"clip-a" * 4, "a's clip bytes are intact")
        check(tar.extractfile(f"{prefix}/{bucket_b}/b.raw").read() == b"clip-b" * 4, "b's clip bytes are intact")
        licence = tar.extractfile(f"{prefix}/LICENSE.txt").read().decode("utf-8")
        check("Kokoro" in licence and "Apache License 2.0" in licence and "af_heart" in licence,
              f"the licence names Kokoro, Apache 2.0 and the voice: {licence!r}")

    # A set made with the macOS voices is for the maker's own device: Apple licenses them for the
    # Mac, not for redistribution, so pack refuses it unless personal=True.
    say_dir = make_set(tmp, "sayset", backend="say", voice="Samantha", words={"a": "hash-a"})
    out2 = os.path.join(tmp, "out2.tar")
    try:
        pack(say_dir, "sayset", "0.1.0", out2)
        check(False, "a say-backend set is refused without --personal")
    except SystemExit as e:
        check("Apple" in str(e), f"the refusal names Apple's licence: {e}")
    check(not os.path.exists(out2), "the refused pack leaves no file behind")
    count2 = pack(say_dir, "sayset", "0.1.0", out2, personal=True)
    check(count2 == 1 and os.path.exists(out2), "--personal packs a say set anyway")

    # licence_text on its own, for a backend that never goes through pack() in these checks
    espeak_licence = licence_text({"backend": "espeak", "voice": "en-us+f3"})
    check("eSpeak-NG" in espeak_licence and "General Public License version 3" in espeak_licence,
          f"the espeak licence names eSpeak-NG and GPL-3: {espeak_licence!r}")

    # A set with no voice.txt has not been built yet
    nov_dir = os.path.join(tmp, "novoice")
    os.makedirs(nov_dir)
    with open(os.path.join(nov_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"set": "novoice", "settings": {"backend": "kokoro", "voice": "af_heart"}, "words": {}}, f)
    try:
        pack(nov_dir, "novoice", "0.1.0", os.path.join(tmp, "out3.tar"))
        check(False, "a missing voice.txt is refused")
    except SystemExit as e:
        check("voice.txt" in str(e), f"the refusal names what's missing: {e}")

    # A manifest word with no clip on disk stops the loop partway through (b's clip was never
    # written): the corrected loop must leave no broken tar, and no stray temp file, at out_path.
    missing_dir = make_set(tmp, "missingclip", words={"a": "hash-a", "z": "hash-z"})
    os.remove(os.path.join(missing_dir, initial("z"), "z.raw"))
    out4 = os.path.join(tmp, "out4.tar")
    try:
        pack(missing_dir, "missingclip", "0.1.0", out4)
        check(False, "a manifest word with no clip on disk is refused")
    except SystemExit as e:
        check("z.raw" in str(e), f"the refusal names the missing clip: {e}")
    check(not os.path.exists(out4) and not os.path.exists(out4 + ".tmp"),
          "a pack that fails partway leaves no broken tar and no stray temp file at out_path")

print(f"voice pack: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
