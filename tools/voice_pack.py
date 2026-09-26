#!/usr/bin/env python3
"""Write a voice set as a release asset: voice-<set>-sonar-<version>.tar.

    tools/voice_pack.py --set NAME --version X.Y.Z [--out DIR] [--personal]

The tar holds sr/voices/<set>/voice.txt, sr/voices/<set>/LICENSE.txt and the clips in their
64 hashed folders, nothing else (the manifest and the sync record are the generator's). It is a
plain tar, uncompressed: 8-bit PCM compresses poorly, and the device's tar library can unpack it.
It is built into a temporary file beside out_path and only moved into place once it holds every
clip, so a pack that a missing clip stops partway through never leaves a broken tar at out_path.
A set made with the macOS voices is refused, since Apple licenses them for use on the Mac;
--personal writes it anyway, for a backup of one's own device. The licence text names the
engine, the voice and the terms: Kokoro (Apache 2.0, with attribution to the model), eSpeak-NG
(GPL-3), and CC0 for what the fork adds.
"""
import argparse
import io
import json
import os
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from voice_build import bucket, initial, set_local_dir, set_valid  # noqa: E402

LICENCES = {
    "kokoro": (
        "This vocabulary was made with Kokoro, an open text-to-speech model by hexgrad\n"
        "(https://huggingface.co/hexgrad/Kokoro-82M), licensed under the Apache License 2.0,\n"
        "with the voice {voice}. The clips are derived from the model's output. What the Sonar\n"
        "project adds (the selection of words, the processing, the layout) is dedicated to the\n"
        "public domain under CC0 1.0.\n"
    ),
    "espeak": (
        "This vocabulary was made with eSpeak-NG (https://github.com/espeak-ng/espeak-ng),\n"
        "licensed under the GNU General Public License version 3, with the voice {voice}. The\n"
        "clips are eSpeak-NG's output, processed for the Flipper's speaker. What the Sonar\n"
        "project adds is dedicated to the public domain under CC0 1.0.\n"
    ),
    "say": (
        "This vocabulary was made with the macOS voice {voice}, which Apple licenses for use\n"
        "on the Mac. It is for the maker's own device and is not redistributed.\n"
    ),
}


def licence_text(settings):
    backend = settings["backend"]
    if backend not in LICENCES:
        sys.exit(f"no licence text for the backend {backend!r}")
    return LICENCES[backend].format(voice=settings["voice"])


def pack(set_dir, set_name, version, out_path, personal=False):
    manifest_path = os.path.join(set_dir, "manifest.json")
    voice_txt = os.path.join(set_dir, "voice.txt")
    if not os.path.exists(manifest_path) or not os.path.exists(voice_txt):
        sys.exit(f"{set_dir}: no manifest.json or voice.txt; make the set first")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    settings = manifest["settings"]
    if settings["backend"] == "say" and not personal:
        sys.exit("a set made with the macOS voices is for the maker's device only (Apple's licence); --personal packs it anyway")
    prefix = f"sr/voices/{set_name}"
    words = sorted(manifest["words"])
    count = 0
    # Built next to out_path, not at it: a word whose clip went missing (sys.exit, below) must
    # not leave a half-written tar sitting at the path a release step would otherwise pick up as
    # done. The rename only happens once every clip is in, the same atomic-write shape as
    # voice_build.save_manifest's ".tmp" file for manifest.json and synced.json.
    tmp_path = out_path + ".tmp"
    try:
        with tarfile.open(tmp_path, "w") as tar:
            tar.add(voice_txt, arcname=f"{prefix}/voice.txt")
            info = tarfile.TarInfo(f"{prefix}/LICENSE.txt")
            data = licence_text(settings).encode("utf-8")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
            # On the Mac a set keeps its clips under <initial>/<word>.raw (voice_build.initial);
            # the pack, like the card and the sync, uses the 64 hashed folders the firmware looks
            # in (voice_build.bucket, the same FNV-1a modulo 64), words sorted for a deterministic
            # archive.
            for word in words:
                local = os.path.join(set_dir, initial(word), word + ".raw")
                if not os.path.exists(local):
                    sys.exit(f"{local}: the manifest names a clip that is not on disk; run the generator")
                tar.add(local, arcname=f"{prefix}/{bucket(word)}/{word}.raw")
                count += 1
        os.replace(tmp_path, out_path)
    finally:
        # Reached with tmp_path still there only when the archive was never finished: os.replace
        # above already moved it away on the success path, so this cleans up a failure, not a win.
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
    return count


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True)
    ap.add_argument("--version", required=True, help="the release version, X.Y.Z")
    ap.add_argument("--out", default=ROOT, help="directory for the tar (default: the project root)")
    ap.add_argument("--personal", action="store_true", help="pack a macOS-voice set for one's own device")
    a = ap.parse_args()
    if not set_valid(a.set):
        sys.exit(f"not a set name: {a.set!r}")
    out_path = os.path.join(a.out, f"voice-{a.set}-sonar-{a.version}.tar")
    count = pack(set_local_dir(a.set), a.set, a.version, out_path, a.personal)
    print(f"{out_path}: {count} clips, {os.path.getsize(out_path)} bytes")


if __name__ == "__main__":
    main()
