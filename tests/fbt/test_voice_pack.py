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
not even a partial file. licence_text(settings) names the engine, the voice and the terms, and
carries the engine's licence in full: the Kokoro pack's LICENSE.txt gives the model's name, URL and
version, the SHA-256 of the model file and of the voices file as the set's manifest holds them (read
from its settings, never worked out when packing), the credit the model's card gives, what the
project adds under CC0 1.0, and then the whole Apache License 2.0 (tools/licences/Apache-2.0.txt);
the eSpeak-NG text names GPL-3 and ends with its whole text (tools/licences/GPL-3.0.txt). Run
from the project root: python3 tests/fbt/test_voice_pack.py"""
import hashlib
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
from voice_pack import licence_text, pack, pack_name  # noqa: E402

LICENCES_DIR = os.path.join(ROOT, "tools", "licences")
# The two checksums a Kokoro set's manifest holds in settings["model_sha256"], one after the other:
# the model file's, then the voices file's. Made up here, so the check does not need the model files.
MODEL_SHA = hashlib.sha256(b"model file").hexdigest()
VOICES_SHA = hashlib.sha256(b"voices file").hexdigest()

failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


check(pack_name("heart", "0.1.0") == "voice-heart-sonar-0.1.0.tar", "a release pack's name")
check(pack_name("samantha", "0.1.0", personal=True) == "voice-samantha-personal-0.1.0.tar",
      "a personal pack is never named as a release asset (R10)")
ignored = open(os.path.join(ROOT, ".gitignore")).read().split("\n")
check("voice-*.tar" in ignored, "and packs in the project root stay out of git")


def make_set(tmp, name, backend="kokoro", voice="af_heart", words=None):
    """A throwaway set directory: manifest.json, voice.txt and one clip per word under its
    <initial>/ folder -- the layout the generator keeps on the Mac (voice_build.initial), not the
    card's hashed one that pack() must translate into."""
    words = {"a": "hash-a", "b": "hash-b"} if words is None else words
    set_dir = os.path.join(tmp, name)
    os.makedirs(set_dir, exist_ok=True)
    settings = {"backend": backend, "voice": voice, "rate": 100}
    if backend == "kokoro":
        settings["model_sha256"] = MODEL_SHA + VOICES_SHA
    manifest = {"set": name, "settings": settings, "words": dict(words)}
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

def read_text(path):
    with open(path, encoding="utf-8", newline="") as f:
        return f.read()


def refused(settings):
    """What licence_text says when it refuses these settings, or None when it writes a text."""
    try:
        licence_text(settings)
    except SystemExit as e:
        return str(e)
    return None


# The licences in full. The two texts are copied, not typed: the Apache License 2.0 is the terms of
# apache.org's LICENSE-2.0.txt, from "Apache License" to "END OF TERMS AND CONDITIONS" (lines 2 to
# 177 of that file, whose own SHA-256 is cfc7749b...523d30), without its appendix on how to apply
# the licence; the GPL-3.0 is gnu.org's gpl-3.0.txt, as Momentum's LICENSE holds it. Their
# checksums are pinned, so a changed word fails here.
apache = read_text(os.path.join(LICENCES_DIR, "Apache-2.0.txt"))
gpl = read_text(os.path.join(LICENCES_DIR, "GPL-3.0.txt"))
check(hashlib.sha256(apache.encode("utf-8")).hexdigest() == "a6cba85bc92e0cff7a450b1d873c0eaa2e9fc96bf472df0247a26bec77bf3ff9",
      "tools/licences/Apache-2.0.txt is the unchanged text of the Apache License 2.0")
check(hashlib.sha256(gpl.encode("utf-8")).hexdigest() == "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986",
      "tools/licences/GPL-3.0.txt is the unchanged text of the GNU GPL version 3")
apache_lines = apache.strip("\n").split("\n")
check(apache_lines[0].strip() == "Apache License" and apache_lines[1].strip() == "Version 2.0, January 2004",
      f"the Apache text opens with its title and version: {apache_lines[:2]}")
check(apache_lines[-1].strip() == "END OF TERMS AND CONDITIONS",
      f"the Apache text ends with its terms, no appendix of a package's copyright holder: {apache_lines[-1]!r}")
check("[name of copyright owner]" not in apache and "[yyyy]" not in apache, "and no notice with a holder's name to fill in")
gpl_lines = gpl.strip("\n").split("\n")
check(gpl_lines[0].strip() == "GNU GENERAL PUBLIC LICENSE" and gpl_lines[1].strip() == "Version 3, 29 June 2007",
      f"the GPL text opens with its title and version: {gpl_lines[:2]}")

with tempfile.TemporaryDirectory() as tmp:
    # The heart pack's LICENSE.txt, read from the tar as a user of the pack would find it
    set_dir = make_set(tmp, "heart")
    out = os.path.join(tmp, "heart.tar")
    pack(set_dir, "heart", "0.1.0", out)
    with tarfile.open(out) as tar:
        text = tar.extractfile("sr/voices/heart/LICENSE.txt").read().decode("utf-8")
    manifest = json.load(open(os.path.join(set_dir, "manifest.json"), encoding="utf-8"))
    check(text == licence_text(manifest["settings"]), "the pack's LICENSE.txt is licence_text of the set's settings")
    lines = text.split("\n")

    # The Apache License 2.0 in full, last: the short facts come first, for a reader who goes
    # through the file line by line, and the long terms after them
    check(text.endswith(apache), "the heart licence ends with the whole Apache License 2.0, word for word")
    check(0 <= text.find("af_heart") < text.find(apache),
          "the facts come before the full terms")
    check("GNU GENERAL PUBLIC LICENSE" not in text and "eSpeak" not in text, "and nothing of the other engine's licence")

    # The model: its name, URL, version and the two files, each with its own SHA-256
    for want in ("Kokoro-82M", "hexgrad", "https://huggingface.co/hexgrad/Kokoro-82M", "v1.0", "af_heart",
                 "kokoro-onnx", "model-files-v1.0"):
        check(want in text, f"the heart licence names {want}")
    model_line = [line for line in lines if "kokoro-v1.0.onnx" in line]
    voices_line = [line for line in lines if "voices-v1.0.bin" in line]
    check(len(model_line) == 1 and MODEL_SHA in model_line[0] and VOICES_SHA not in model_line[0],
          f"the model file's SHA-256 is on the line that names the file: {model_line}")
    check(len(voices_line) == 1 and VOICES_SHA in voices_line[0] and MODEL_SHA not in voices_line[0],
          f"the voices file's SHA-256 is on the line that names that file: {voices_line}")
    check(text.count(MODEL_SHA) == 1 and text.count(VOICES_SHA) == 1 and (MODEL_SHA + VOICES_SHA) not in text,
          "each checksum once, the manifest's joined 128 digits nowhere")

    # What the model's card gives as credit: the StyleTTS 2 architecture, and the two CC BY sets of
    # audio in the training data of Kokoro v1.0
    for want in ("StyleTTS 2", "yl4579", "Koniwa", "CC BY 3.0", "SIWIS", "CC BY 4.0"):
        check(want in text, f"the heart licence gives the model card's credit: {want}")

    # What the project adds: CC0 1.0, beside the engine's terms
    check("CC0 1.0 Universal" in text and "https://creativecommons.org/publicdomain/zero/1.0/" in text,
          "the heart licence puts what the project adds under CC0 1.0 and gives its URL")
    for want in ("selection of words", "processing", "layout"):
        check(want in text, f"and says what that is: {want}")
    check(text.isascii() and "\r" not in text and text.endswith("\n"), "plain ASCII, newline-ended, no carriage returns")

    # The checksums come from the manifest's settings: other settings, other checksums in the text
    other = dict(manifest["settings"], model_sha256="a" * 64 + "b" * 64)
    other_text = licence_text(other)
    check("a" * 64 in other_text and "b" * 64 in other_text and MODEL_SHA not in other_text,
          "the checksums are the settings', not worked out from any model file at pack time")
    check(0 <= other_text.find("a" * 64) < other_text.find("b" * 64), "the model file's first, then the voices file's")

    # A Kokoro set whose manifest has no usable checksum pair gets no licence at all, and so no pack
    for bad in (None, "", "a" * 64, "missing" + "b" * 64, "g" * 128, "A" * 128, "a" * 129):
        settings = {k: v for k, v in manifest["settings"].items() if k != "model_sha256"}
        if bad is not None:
            settings["model_sha256"] = bad
        why = refused(settings)
        check(why is not None and "model_sha256" in why, f"settings with model_sha256 {bad!r} are refused: {why}")
    bad_dir = make_set(tmp, "nosum")
    bad_manifest_path = os.path.join(bad_dir, "manifest.json")
    bad_manifest = json.load(open(bad_manifest_path, encoding="utf-8"))
    del bad_manifest["settings"]["model_sha256"]
    with open(bad_manifest_path, "w", encoding="utf-8") as f:
        json.dump(bad_manifest, f)
    nosum_out = os.path.join(tmp, "nosum.tar")
    try:
        pack(bad_dir, "nosum", "0.1.0", nosum_out)
        check(False, "a Kokoro set with no checksums in its manifest is refused")
    except SystemExit as e:
        check("model_sha256" in str(e), f"the refusal names the missing checksums: {e}")
    check(not os.path.exists(nosum_out) and not os.path.exists(nosum_out + ".tmp"), "and leaves no tar behind")

    # The eSpeak-NG text, for the packs people make themselves: the engine, GPL-3 in full, CC0 1.0
    espeak = licence_text({"backend": "espeak", "voice": "en-us+f3"})
    check("eSpeak-NG" in espeak and "https://github.com/espeak-ng/espeak-ng" in espeak and "en-us+f3" in espeak,
          f"the espeak licence names eSpeak-NG, its page and the voice: {espeak[:300]!r}")
    check("General Public License version 3" in espeak, "and the GPL version 3")
    check(espeak.endswith(gpl), "and ends with the whole GNU GPL version 3, word for word")
    check(0 <= espeak.find("en-us+f3") < espeak.find(gpl), "the facts come before the full terms")
    check("CC0 1.0 Universal" in espeak and "https://creativecommons.org/publicdomain/zero/1.0/" in espeak,
          "the espeak licence puts what the project adds under CC0 1.0 and gives its URL")
    check("Apache" not in espeak and "Kokoro" not in espeak and espeak.isascii() and "\r" not in espeak,
          "and nothing of Kokoro's terms; plain ASCII")
    # eSpeak needs no model checksums: a pack made with it has none to name
    check(refused({"backend": "espeak", "voice": "en-us+f3", "model_sha256": "x"}) is None, "an espeak set's settings need no checksums")

    # Any other backend has no licence text, so no pack; the macOS voices' pack is refused above
    # without --personal and keeps its short text
    why = refused({"backend": "piper", "voice": "x"})
    check(why is not None and "piper" in why, f"a backend with no licence text is refused: {why}")
    say = licence_text({"backend": "say", "voice": "Samantha"})
    check("Apple" in say and "Samantha" in say and "CC0" not in say and "not redistributed" in say,
          f"the macOS voices' text is unchanged: {say!r}")


# The clips go into the pack in clip order, the most spoken first, as a sync writes them: the
# device's unpacker makes the files in the archive's order, and the folders keep it
with tempfile.TemporaryDirectory() as tmp:
    ordered_dir = make_set(tmp, "ordered", words={"zulu": "h1", "the": "h2", "apple": "h3"})
    manifest_path = os.path.join(ordered_dir, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        ordered = json.load(f)
    ordered["first"] = ["the"]
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(ordered, f)
    out5 = os.path.join(tmp, "out5.tar")
    pack(ordered_dir, "ordered", "0.1.0", out5)
    with tarfile.open(out5) as tar:
        clips = [os.path.basename(m.name) for m in tar.getmembers() if m.name.endswith(".raw")]
    check(clips == ["the.raw", "apple.raw", "zulu.raw"], f"the pack's clips in clip order: {clips}")

print(f"voice pack: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
