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
voice-<set>-personal-<version>.tar, so it is never taken for a release asset.
LICENSE.txt carries the engine's licence in full, the facts first and the long terms last, for a
reader who goes through it line by line: the Kokoro pack names the model (Kokoro-82M by hexgrad,
v1.0), the SHA-256 of the model file and of the voices file, the voice, the credit the model's card
gives and what the project adds (CC0 1.0), then the whole Apache License 2.0; the eSpeak-NG text,
for a pack someone makes themselves, names the engine and the voice, says the same of the
project's part, and ends with the whole GPL-3. The two texts are the files in tools/licences/,
copied from the licences' own wording and never edited. The two checksums are read from the set's
manifest (settings["model_sha256"], the model file's 64 digits and then the voices file's 64, as
voice_build.settings_for records them when the clips were made), not worked out when packing: the
text names the files the clips came from, which the model files on this machine may no longer be.
"""
import argparse
import io
import json
import os
import re
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from voice_build import bucket, clip_order, initial, set_local_dir, set_valid  # noqa: E402

LICENCES_DIR = os.path.join(ROOT, "tools", "licences")

# What the project adds is always CC0 1.0; the engine's terms apply beside it, to the clips that
# come from the engine (decision of 2026-10-11). One line holds each phrase a reader or a check
# looks for, so a wrap never splits it.
CC0 = (
    "What the Sonar project adds to this voice set (the selection of words, the processing, the\n"
    "layout) is released under CC0 1.0 Universal, which dedicates it to the public domain as far\n"
    "as the law allows: https://creativecommons.org/publicdomain/zero/1.0/\n"
    "The licence of the engine or model named above applies beside it, to the clips made with it.\n"
)

# The text of each backend: the short facts first, then the engine's whole licence from
# tools/licences/ (LICENCE_FILES) appended unchanged, so the file ends with the long terms. The
# fields are {voice} and, for Kokoro, {model_sha256} and {voices_sha256}.
LICENCES = {
    "kokoro": (
        "Licence of this voice set\n"
        "\n"
        "This voice set was made with Kokoro, an open text-to-speech model, with the voice {voice}.\n"
        "The clips are derived from the model's output.\n"
        "\n"
        "The model\n"
        "\n"
        "Name: Kokoro-82M, version v1.0, by hexgrad\n"
        "Page: https://huggingface.co/hexgrad/Kokoro-82M\n"
        "Licence: the Apache License 2.0, whose whole text is at the end of this file\n"
        "Files: the ONNX files of the kokoro-onnx project, release model-files-v1.0\n"
        "Files from: https://github.com/thewh1teagle/kokoro-onnx\n"
        "Model file kokoro-v1.0.onnx, SHA-256: {model_sha256}\n"
        "Voices file voices-v1.0.bin, SHA-256: {voices_sha256}\n"
        "Voice: {voice}\n"
        "\n"
        "Credit, as the model's card gives it\n"
        "\n"
        "The card asks for no wording of its own. It credits the StyleTTS 2 architecture to @yl4579\n"
        "(Li et al., arXiv 2306.07691), and it lists the two sets of CC BY audio that were part of the\n"
        "data Kokoro v1.0 was trained on:\n"
        "Koniwa tnc, CC BY 3.0 (https://github.com/koniwa/koniwa)\n"
        "SIWIS, CC BY 4.0 (https://datashare.ed.ac.uk/handle/10283/2353)\n"
        "\n"
        "What the Sonar project adds\n"
        "\n"
        + CC0 +
        "\n"
        "The Apache License 2.0, in full\n"
        "\n"
    ),
    "espeak": (
        "Licence of this voice set\n"
        "\n"
        "This voice set was made with eSpeak-NG, with the voice {voice}. The clips are eSpeak-NG's\n"
        "output, processed for the Flipper's speaker.\n"
        "\n"
        "The engine\n"
        "\n"
        "Name: eSpeak-NG\n"
        "Page: https://github.com/espeak-ng/espeak-ng\n"
        "Licence: the GNU General Public License version 3, whose whole text is at the end of this file\n"
        "Voice: {voice}\n"
        "\n"
        "What the Sonar project adds\n"
        "\n"
        + CC0 +
        "\n"
        "The GNU General Public License version 3, in full\n"
        "\n"
    ),
    "say": (
        "This vocabulary was made with the macOS voice {voice}, which Apple licenses for use\n"
        "on the Mac. It is for the maker's own device and is not redistributed.\n"
    ),
}

# The whole text that follows a backend's facts, in tools/licences/
LICENCE_FILES = {"kokoro": "Apache-2.0.txt", "espeak": "GPL-3.0.txt"}


def licence_file(name):
    """The text of a licence in tools/licences/, as it is on disk."""
    path = os.path.join(LICENCES_DIR, name)
    try:
        with open(path, encoding="utf-8", newline="") as f:
            return f.read()
    except OSError as e:
        sys.exit(f"{path}: the licence text cannot be read ({e.strerror}); it ships with the project")


def kokoro_checksums(settings):
    """The SHA-256 of the model file and of the voices file, from the set's settings: 128 lower case
    hex digits, the model file's 64 and then the voices file's 64 (voice_build.settings_for).
    They are the manifest's record of the files the clips were made with, so they are read, not
    recomputed here; a manifest without them has no licence text to give."""
    joined = settings.get("model_sha256")
    if not isinstance(joined, str) or re.fullmatch(r"[0-9a-f]{128}", joined) is None:
        sys.exit("the set's settings hold no model_sha256 of 128 hex digits (the SHA-256 of the Kokoro model "
                 "file and then of the voices file), which the licence names; make the set with the "
                 "generator, with both model files in voice-models/, so its manifest records them")
    return joined[:64], joined[64:]


def licence_text(settings):
    """The LICENSE.txt of a pack made with these settings (the set's manifest "settings"): the
    engine, the model, the voice and the terms, then the engine's licence in full."""
    backend = settings["backend"]
    if backend not in LICENCES:
        sys.exit(f"no licence text for the backend {backend!r}")
    fields = {"voice": settings["voice"]}
    if backend == "kokoro":
        fields["model_sha256"], fields["voices_sha256"] = kokoro_checksums(settings)
    text = LICENCES[backend].format(**fields)
    if backend in LICENCE_FILES:
        text += licence_file(LICENCE_FILES[backend])
    return text


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
