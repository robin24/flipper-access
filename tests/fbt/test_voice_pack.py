#!/usr/bin/env python3
"""tools/voice_pack.py: pack(set_dir, set_name, version, out_path) writes a voice set as a release
asset, a plain tar laid out as the card reads it -- sr/voices/<set>/voice.txt,
sr/voices/<set>/LICENSE.txt and the clips in their 64 hashed folders (voice_build.bucket), nothing
else: the local manifest.json and synced.json stay out. The device's unpacker (`storage extract`,
lib/toolbox/tar/tar_archive.c) makes a folder only from a folder entry and opens each file in a
folder that must already exist, so the tar starts with an entry for every folder, each after its
parent; unpack() below follows those two rules. The tar is USTAR with no PAX headers, and owner,
group, mode and time are fixed, so two packs of one set are byte for byte the same. A set made
with the macOS voices is refused (Apple licenses them for the Mac only) unless personal=True, and
a pack that fails partway -- a manifest word with no clip on disk -- leaves nothing at out_path,
not even a partial file. licence_text(settings) names the engine, the voice and the terms. Run
from the project root: python3 tests/fbt/test_voice_pack.py"""
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time

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


def unpack(path):
    """The device's two rules, as tar_archive_unpack_to follows them: a folder entry makes its
    folder, whose parent must exist (a mkdir on the card makes one level); a file is opened with
    create-always in a folder that must exist, since nothing makes the folders above a file.
    Returns the problems, one sentence each; the destination itself is there from the start."""
    made = {""}
    problems = []
    with tarfile.open(path) as tar:
        for m in tar.getmembers():
            name = m.name.rstrip("/")
            parent = os.path.dirname(name)
            if parent not in made:
                problems.append(f"{m.name}: its folder {parent or '/'} does not exist yet")
            if m.isdir():
                made.add(name)
            elif not m.isfile():
                problems.append(f"{m.name}: neither a file nor a folder, type {m.type!r}")
    return problems


def headers(path):
    """Each raw 512-byte header of the tar: (name, type flag, magic), PAX and GNU entries included,
    which tarfile's own reader folds into the member that follows."""
    with open(path, "rb") as f:
        data = f.read()
    found = []
    offset = 0
    while offset + 512 <= len(data) and data[offset:offset + 512].strip(b"\0"):
        block = data[offset:offset + 512]
        size = int(block[124:136].strip(b"\0 ") or b"0", 8)
        found.append((block[0:100].rstrip(b"\0").decode(), block[156:157], block[257:265]))
        offset += 512 + (size + 511) // 512 * 512
    return found


# The checks of the times below assume no SOURCE_DATE_EPOCH from the caller's environment
os.environ.pop("SOURCE_DATE_EPOCH", None)

with tempfile.TemporaryDirectory() as tmp:
    # A set's tar: the folders sr/, sr/voices/, the set's and the hashed folders its clips use,
    # then voice.txt, LICENSE.txt and the clips in sorted-word order, each moved from its local
    # <initial>/ folder to the card's hashed one -- exactly, nothing more.
    set_dir = make_set(tmp, "heart", words={"a": "hash-a", "b": "hash-b"})
    out = os.path.join(tmp, "out.tar")
    count = pack(set_dir, "heart", "0.1.0", out)
    check(count == 2, f"two clips packed: {count}")
    prefix = "sr/voices/heart"
    bucket_a, bucket_b = bucket("a"), bucket("b")
    folders = ["sr", "sr/voices", prefix] + [f"{prefix}/{b}" for b in sorted({bucket_a, bucket_b})]
    expected = folders + [f"{prefix}/voice.txt", f"{prefix}/LICENSE.txt", f"{prefix}/{bucket_a}/a.raw", f"{prefix}/{bucket_b}/b.raw"]
    with tarfile.open(out) as tar:
        names = tar.getnames()
        check(names == expected, f"the folders, then exactly the set's files, in that order, no manifest.json or synced.json: {names}")
        check(all(n in names and tar.getmember(n).isdir() for n in folders), "the folder entries are folders")
        check(tar.extractfile(f"{prefix}/{bucket_a}/a.raw").read() == b"clip-a" * 4, "a's clip bytes are intact")
        check(tar.extractfile(f"{prefix}/{bucket_b}/b.raw").read() == b"clip-b" * 4, "b's clip bytes are intact")
        licence = tar.extractfile(f"{prefix}/LICENSE.txt").read().decode("utf-8")
        check("Kokoro" in licence and "Apache License 2.0" in licence and "af_heart" in licence,
              f"the licence names Kokoro, Apache 2.0 and the voice: {licence!r}")
        owners = {(m.uid, m.gid, m.uname, m.gname) for m in tar.getmembers()}
        check(owners == {(0, 0, "", "")}, f"no owner or group of the maker's machine: {owners}")
        modes = {(m.isdir(), m.mode) for m in tar.getmembers()}
        check(modes == {(True, 0o755), (False, 0o644)}, f"folders 755 and files 644: {modes}")
        times = {m.mtime for m in tar.getmembers()}
        check(times == {0}, f"every entry at time 0 without SOURCE_DATE_EPOCH: {times}")

    # Unpacked with the device's rules, every folder exists before anything goes into it
    problems = unpack(out)
    check(not problems, f"the device's unpacker would make every folder and open every file: {problems}")

    # The same with the firmware's own tar reader (tests/host/tar_unpack.c, which
    # tools/run_host_tests.sh builds from lib/microtar): the whole pack unpacks, nothing skipped,
    # the clips intact; and a pack with no folder entries, as this tool wrote them before, stops at
    # its first file, as `storage extract` did on the device
    tar_unpack = os.environ.get("TAR_UNPACK")
    if tar_unpack:
        card = os.path.join(tmp, "card")
        os.makedirs(card)
        p = subprocess.run([tar_unpack, out, card], capture_output=True, text=True)
        check(p.returncode == 0, f"the firmware's tar reader unpacks the whole pack: {p.stdout.strip()}")
        clip = os.path.join(card, prefix, bucket_b, "b.raw")
        check(os.path.exists(clip) and open(clip, "rb").read() == b"clip-b" * 4,
              "the clip unpacked by the firmware's tar reader is intact")
        flat = os.path.join(tmp, "flat.tar")
        with tarfile.open(flat, "w") as tar:
            tar.add(os.path.join(set_dir, "voice.txt"), arcname=f"{prefix}/voice.txt")
        card2 = os.path.join(tmp, "card2")
        os.makedirs(card2)
        p = subprocess.run([tar_unpack, flat, card2], capture_output=True, text=True)
        check(p.returncode != 0 and f"{prefix}/voice.txt" in p.stdout,
              f"a pack without folder entries stops at its first file: {p.stdout.strip()}")
    else:
        print("skipped the unpack with the firmware's tar reader: no TAR_UNPACK, which "
              "tools/run_host_tests.sh builds once the firmware's lib/microtar is checked out")

    # USTAR throughout: no PAX or GNU header before any entry, which the device would skip with a
    # warning, and only files and folders
    raw = headers(out)
    check(len(raw) == len(expected), f"one header per entry, nothing extra: {len(raw)} for {len(expected)}")
    check(all(magic == b"ustar\x0000" for _, _, magic in raw), f"every header is USTAR: {set(m for _, _, m in raw)}")
    check(all(flag in (b"0", b"5") for _, flag, _ in raw), f"only file and folder headers: {set(f for _, f, _ in raw)}")

    # The same set packed again, with the clips' times changed in between: the same bytes
    os.utime(os.path.join(set_dir, initial("a"), "a.raw"), (time.time() + 1000.5, time.time() + 1000.5))
    again = os.path.join(tmp, "again.tar")
    pack(set_dir, "heart", "0.1.0", again)
    with open(out, "rb") as f1, open(again, "rb") as f2:
        check(f1.read() == f2.read(), "two packs of the same set are byte for byte the same")

    # SOURCE_DATE_EPOCH sets the time of every entry
    os.environ["SOURCE_DATE_EPOCH"] = "1790000000"
    try:
        dated = os.path.join(tmp, "dated.tar")
        pack(set_dir, "heart", "0.1.0", dated)
        with tarfile.open(dated) as tar:
            times = {m.mtime for m in tar.getmembers()}
        check(times == {1790000000}, f"every entry at SOURCE_DATE_EPOCH: {times}")
    finally:
        del os.environ["SOURCE_DATE_EPOCH"]

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
