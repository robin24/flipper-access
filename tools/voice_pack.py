#!/usr/bin/env python3
"""Write a voice set as a release asset: voice-<set>-sonar-<version>.tar.

    tools/voice_pack.py --set NAME --version X.Y.Z [--out DIR] [--personal]

The tar holds sr/voices/<set>/voice.txt, sr/voices/<set>/LICENSE.txt and the clips in their
64 hashed folders, nothing else (the manifest and the sync record are the generator's). It is a
plain tar, uncompressed: 8-bit PCM compresses poorly, and the device's tar library can unpack it,
with `storage extract <tar> /ext` on the console. That unpacker makes a folder only from a
folder entry and never creates the folders above a file, so the tar opens with entries for sr/,
sr/voices/, the set's folder and each hashed folder it uses, before any file. It is USTAR, as
the firmware's own resources tarball: Python's default, PAX, would put an extra header before
every clip for its fractional time, which the device skips with a warning. Owner, group, mode
and time are fixed (the time from SOURCE_DATE_EPOCH, or 0), so two packs of the same set are
byte for byte the same.
It is built into a temporary file beside out_path and only moved into place once it holds every
clip, so a pack that a missing clip stops partway through never leaves a broken tar at out_path.
A set made with the macOS voices is refused, since Apple licenses them for use on the Mac;
--personal writes it anyway, for a backup of one's own device, and names it
voice-<set>-personal-<version>.tar, so it is never taken for a release asset. The licence text names the
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
from voice_build import bucket, clip_order, initial, set_local_dir, set_valid  # noqa: E402

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


def fixed_time():
    """The time every entry carries: SOURCE_DATE_EPOCH when set, else 0. The device ignores it."""
    return int(os.environ.get("SOURCE_DATE_EPOCH", "0"))


def fixed(info, mtime):
    """Owner, group, mode and time that do not depend on the maker's machine, as the firmware's
    own tar_sanitizer_filter (scripts/flipper/assets/tarball.py) sets them."""
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o755 if info.isdir() else 0o644
    info.mtime = mtime
    return info


def folder(name, mtime):
    info = tarfile.TarInfo(name)
    info.type = tarfile.DIRTYPE
    return fixed(info, mtime)


def pack_name(set_name, version, personal=False):
    """The tar's file name: the release's voice-<set>-sonar-<version>.tar, or for a personal pack
    voice-<set>-personal-<version>.tar."""
    return f"voice-{set_name}-{'personal' if personal else 'sonar'}-{version}.tar"


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
    words = clip_order(manifest["words"], manifest.get("first", ()))
    mtime = fixed_time()
    count = 0
    # Built next to out_path, not at it: a word whose clip went missing (sys.exit, below) must
    # not leave a half-written tar sitting at the path a release step would otherwise pick up as
    # done. The rename only happens once every clip is in, the same atomic-write shape as
    # voice_build.save_manifest's ".tmp" file for manifest.json and synced.json.
    tmp_path = out_path + ".tmp"
    try:
        with tarfile.open(tmp_path, "w", format=tarfile.USTAR_FORMAT) as tar:
            # Every folder before any file, each after its parent: the device's unpacker makes a
            # folder only from its entry, and opens a file only in a folder that exists. The
            # hashed folders are the ones the set's clips use, as a sync makes them.
            for name in ("sr", "sr/voices", prefix):
                tar.addfile(folder(name, mtime))
            for name in sorted({bucket(word) for word in words}):
                tar.addfile(folder(f"{prefix}/{name}", mtime))
            tar.add(voice_txt, arcname=f"{prefix}/voice.txt", filter=lambda info: fixed(info, mtime))
            info = fixed(tarfile.TarInfo(f"{prefix}/LICENSE.txt"), mtime)
            data = licence_text(settings).encode("utf-8")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
            # On the Mac a set keeps its clips under <initial>/<word>.raw (voice_build.initial);
            # the pack, like the card and the sync, uses the 64 hashed folders the firmware looks
            # in (voice_build.bucket, the same FNV-1a modulo 64), words in clip order, the most
            # spoken first, as the device's unpacker then makes them (voice_build.clip_order).
            for word in words:
                local = os.path.join(set_dir, initial(word), word + ".raw")
                if not os.path.exists(local):
                    sys.exit(f"{local}: the manifest names a clip that is not on disk; run the generator")
                tar.add(local, arcname=f"{prefix}/{bucket(word)}/{word}.raw", filter=lambda info: fixed(info, mtime))
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
    out_path = os.path.join(a.out, pack_name(a.set, a.version, a.personal))
    count = pack(set_local_dir(a.set), a.set, a.version, out_path, a.personal)
    print(f"{out_path}: {count} clips, {os.path.getsize(out_path)} bytes")


if __name__ == "__main__":
    main()
