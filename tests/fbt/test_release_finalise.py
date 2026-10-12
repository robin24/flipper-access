#!/usr/bin/env python3
"""tools/release_finalise.py, which writes SHA256SUMS and release.json from a draft GitHub Release's
assets, the voice pack included, and uploads them (R5, R8). Nothing here calls gh or the network:
the pure functions are checked with temporary files, and the whole run with a stand-in for gh that
keeps what it was asked and what was uploaded, and a throwaway project repository with a
submodule in the place of the fork.

The checks: the SHA-256 values and sizes of files; SHA256SUMS in sha256sum's format, sorted by
name; release.json's keys in their order, the commit at 9 characters, the version without the
name prefix, the voices from the packs' voice.txt lines, the assets sorted; the formats agree with
what install.py's verify reads (with pyserial); the fork's commit from the tag's record of the
submodule, the Momentum base from the tag's tools/momentum-base.txt and the API version from the
table at the fork's commit, each as of the tag and not as of what is checked out now; and the
refusals, each one line: an expected asset missing, a voice pack that is not expected, a file that
is no asset, a pack whose backend is neither kokoro nor espeak, a pack that is no tar or holds no
voice.txt, a tag that is not in the checkout, a release that is published already. A refusal
happens before anything is downloaded when the draft's list already shows it, and before anything
is uploaded always; a dry run uploads nothing.
Run from the project root: python3 tests/fbt/test_release_finalise.py"""
import gzip
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import release_finalise as rf  # noqa: E402

failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def one_sentence(said):
    return bool(said) and "\n" not in said and "Traceback" not in said and said == said.strip()


def refusal(fn, *args, **kwargs):
    """The sentence a call refuses with, or None when it does not refuse."""
    try:
        fn(*args, **kwargs)
    except rf.Refusal as e:
        return str(e)
    return None


TAG = "sonar-0.1.0"
RC = "sonar-0.1.0-rc1"
VOICE_LINE = "kokoro af_heart rate 100 highpass 500 gain 1.3 soft 16000\n"

# Known SHA-256 values (FIPS 180-2's examples and the empty message)
SHA_EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
SHA_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
SHA_HELLO = "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"


def names_for(tag):
    return [f"flipper-z-f7-update-{tag}.tgz", f"install-{tag}.zip", f"{tag}-firmware.elf", f"{tag}-firmware.map",
            f"flipper-z-f7-sdk-{tag}.zip", f"{tag}-source.tar.gz", f"voice-heart-{tag}.tar"]


def make_pack(path, set_name="heart", line=VOICE_LINE, with_voice=True):
    """A voice pack as tools/voice_pack.py lays it out, with a clip: folders first, then voice.txt."""
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as tar:
        for name in ("sr", "sr/voices", f"sr/voices/{set_name}", f"sr/voices/{set_name}/00"):
            info = tarfile.TarInfo(name)
            info.type = tarfile.DIRTYPE
            info.mode = 0o755
            tar.addfile(info)
        files = [(f"sr/voices/{set_name}/LICENSE.txt", b"licence\n"), (f"sr/voices/{set_name}/00/one.raw", b"\x80" * 20)]
        if with_voice:
            files.insert(0, (f"sr/voices/{set_name}/voice.txt", line.encode()))
        for name, data in files:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(data))


def pack_bytes(set_name="heart", line=VOICE_LINE, with_voice=True):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "p.tar")
        make_pack(path, set_name, line, with_voice)
        with open(path, "rb") as f:
            return f.read()


# The three assets of the brief: known bytes, so known digests
THREE = [("b.txt", SHA_ABC, 3), ("a.txt", SHA_EMPTY, 0), ("c.txt", SHA_HELLO, 6)]

# sha256sums: the format of sha256sum, one line each, sorted by name, a final newline
sums = rf.sha256sums(THREE)
check(sums == f"{SHA_EMPTY}  a.txt\n{SHA_ABC}  b.txt\n{SHA_HELLO}  c.txt\n",
      "SHA256SUMS: digest, two spaces, name, sorted by name, newline at the end")
check(all(re.fullmatch(r"[0-9a-f]{64}  \S+", line) for line in sums.splitlines()), "every line is in sha256sum's format")
check(rf.sha256sums([]) == "", "no assets, no lines")
check(rf.sha256sums([("B", SHA_ABC, 3), ("a", SHA_ABC, 3)]).splitlines()[0].endswith(" B"),
      "sorted by code point, as sort in the C locale does")

# describe: the digest and size of real files
with tempfile.TemporaryDirectory() as tmp:
    for name, data in (("b.txt", b"abc"), ("a.txt", b""), ("c.txt", b"hello\n")):
        with open(os.path.join(tmp, name), "wb") as f:
            f.write(data)
    got = rf.describe(tmp, ["c.txt", "a.txt", "b.txt"])
    check(sorted(got) == sorted(THREE), "describe gives (name, SHA-256, size) of each file")
    check([a[0] for a in got] == ["c.txt", "a.txt", "b.txt"], "described in the order of the names given")
    big = os.path.join(tmp, "big.bin")
    with open(big, "wb") as f:
        f.write(b"x" * (3 * (1 << 20) + 5))
    check(rf.describe(tmp, ["big.bin"]) == [("big.bin", hashlib.sha256(b"x" * (3 * (1 << 20) + 5)).hexdigest(), 3 * (1 << 20) + 5)],
          "a file of several chunks is hashed whole")

# release_json: the keys in their order, the values
voices = [{"set": "heart", "backend": "kokoro", "voice": "af_heart", "file": f"voice-heart-{TAG}.tar"}]
FORK = "9149fe493cf0c7ac8f8a8b71020f1f2150ee8312"
BASE = "d3f89dfe2ef6b01839201598e9be1590cba80322"
data = rf.release_json(TAG, FORK, BASE, "87.3", "heart", THREE, voices=voices)
check(list(data) == ["version", "firmware_version", "firmware_commit", "momentum_base", "api_version", "default_voice",
                     "voices", "assets"], "release.json's keys, in order")
check(data["version"] == "0.1.0", "version is the tag without the name prefix")
check(data["firmware_version"] == TAG, "firmware_version is the tag")
check(data["firmware_commit"] == FORK[:9], "firmware_commit is 9 characters")
check(data["momentum_base"] == BASE, "momentum_base is the commit of tools/momentum-base.txt")
check(data["api_version"] == "87.3" and data["default_voice"] == "heart", "api_version and default_voice")
check(data["voices"] == voices, "voices: set, backend, voice and file of each pack")
check(data["assets"] == [{"name": "a.txt", "sha256": SHA_EMPTY, "size": 0}, {"name": "b.txt", "sha256": SHA_ABC, "size": 3},
                         {"name": "c.txt", "sha256": SHA_HELLO, "size": 6}], "assets: name, SHA-256 and size, sorted by name")
check(rf.release_json(RC, FORK, BASE, "87.3", "heart", THREE)["version"] == "0.1.0-rc1", "an rc tag's version keeps its -rc1")
check(rf.release_json(TAG, FORK, BASE, "87.3", "heart", THREE)["voices"] == [], "without packs, voices is empty")
text = rf.release_text(data)
check(json.loads(text) == data and text.endswith("}\n") and "\n  " in text, "the text is the JSON, indented, with a final newline")

# The formats agree with install.py's verify, which needs pyserial
if importlib.util.find_spec("serial") is None:
    print("skipped the check that install.py reads release.json: no pyserial")
else:
    import install

    info = {"firmware.version": TAG, "firmware.commit.hash": FORK[:8], "firmware.api.major": "87", "firmware.api.minor": "3",
            "firmware.commit.dirty": "false", "firmware.origin.fork": "Sonar"}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "release.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        loaded = install._load_release(path)
    check(install.verify(info, loaded) == [], "verify finds no difference between release.json and a device that matches it")
    check(len(install.verify(dict(info, **{"firmware.api.minor": "4"}), loaded)) == 1, "verify notes another API version")
    check(len(install.verify(dict(info, **{"firmware.commit.hash": "0123abcd"}), loaded)) == 1, "verify notes another commit")
    check(len(install.verify(dict(info, **{"firmware.version": RC}), loaded)) == 1, "verify notes another version")

# The facts read from git's records
LS_TREE = f"160000 commit {FORK}\tMomentum-Firmware\n"
check(rf.gitlink_commit(LS_TREE) == FORK, "the submodule's commit from git ls-tree")
check(refusal(rf.gitlink_commit, "") is not None and one_sentence(refusal(rf.gitlink_commit, "")), "no record of the submodule is refused")
check(refusal(rf.gitlink_commit, f"040000 tree {FORK}\tMomentum-Firmware\n") is not None, "a folder in the place of the submodule is refused")
CSV = "entry,status,name,type,params\nVersion,+,87.3,,\nFunction,+,aes_gcm,bool,\"int, int\"\n"
check(rf.parse_api_version(CSV) == "87.3", "the API version from the Version line")
check(refusal(rf.parse_api_version, "entry,status,name,type,params\nFunction,+,x,void,\n") is not None, "a table without a Version line is refused")
check(rf.parse_pin(BASE + "\n") == BASE and rf.parse_pin(f"  {BASE}  \nmore\n") == BASE, "the pin is the file's first line, stripped")
check(refusal(rf.parse_pin, "\n") is not None and refusal(rf.parse_pin, "not a commit\n") is not None, "an empty or odd pin is refused")

# check_assets
NAMES = names_for(TAG)
check(refusal(rf.check_assets, TAG, NAMES) is None, "the seven expected assets pass")
check(refusal(rf.check_assets, TAG, NAMES + ["SHA256SUMS", "release.json"]) is None, "an earlier run's two files are not extras")
for name in NAMES:
    said = refusal(rf.check_assets, TAG, [n for n in NAMES if n != name])
    check(said is not None and one_sentence(said) and name in said, f"missing {name}: one sentence that names it")
said = refusal(rf.check_assets, TAG, NAMES[2:])
check(said is not None and one_sentence(said) and NAMES[0] in said and NAMES[1] in said, "two missing: one sentence names both")
said = refusal(rf.check_assets, TAG, NAMES + [f"voice-espeak-{TAG}.tar"])
check(said is not None and one_sentence(said) and f"voice-espeak-{TAG}.tar" in said and "voice pack" in said,
      "an extra voice pack is refused by name, as a voice pack")
said = refusal(rf.check_assets, TAG, NAMES + ["voice-heart-personal-0.1.0.tar"])
check(said is not None and one_sentence(said) and "voice-heart-personal-0.1.0.tar" in said, "a voice pack with another tag in its name is an extra pack")
said = refusal(rf.check_assets, TAG, NAMES + ["notes.txt"])
check(said is not None and one_sentence(said) and "notes.txt" in said, "a file that is no asset is refused by name")
said = refusal(rf.check_assets, TAG, [n.replace(TAG, "sonar-0.0.9") for n in NAMES])
check(said is not None and one_sentence(said), "the assets of another tag are not these")
check(refusal(rf.check_assets, RC, names_for(RC)) is None, "an rc tag has the same seven, named with it")

# pack_voice: the set, backend and voice from voice.txt inside the pack
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, f"voice-heart-{TAG}.tar")
    make_pack(path)
    check(rf.pack_voice(path, TAG) == voices[0], "the voice from the pack's voice.txt line")

    espeak = os.path.join(tmp, f"voice-espeak-{TAG}.tar")
    make_pack(espeak, "espeak", "espeak en-us+f3 rate 160 highpass 500 gain 1.3 soft 16000\n")
    check(rf.pack_voice(espeak, TAG) == {"set": "espeak", "backend": "espeak", "voice": "en-us+f3", "file": os.path.basename(espeak)},
          "an eSpeak pack is accepted")

    say_pack = os.path.join(tmp, f"voice-samantha-{TAG}.tar")
    make_pack(say_pack, "samantha", "say Samantha rate 175 highpass 500 gain 1.3 soft 16000\n")
    said = refusal(rf.pack_voice, say_pack, TAG)
    check(said is not None and one_sentence(said) and "say" in said and os.path.basename(say_pack) in said,
          "a pack of the macOS voices is refused with its backend and its name")

    odd = os.path.join(tmp, f"voice-odd-{TAG}.tar")
    make_pack(odd, "odd", "festival kal rate 1 highpass 500 gain 1.3 soft 16000\n")
    check(one_sentence(refusal(rf.pack_voice, odd, TAG) or ""), "a backend that is neither kokoro nor espeak is refused")

    blank = os.path.join(tmp, f"voice-blank-{TAG}.tar")
    make_pack(blank, "blank", "\n")
    check(one_sentence(refusal(rf.pack_voice, blank, TAG) or ""), "an empty voice.txt is refused")
    short = os.path.join(tmp, f"voice-short-{TAG}.tar")
    make_pack(short, "short", "kokoro\n")
    check(one_sentence(refusal(rf.pack_voice, short, TAG) or ""), "a voice.txt line without a voice is refused")

    novoice = os.path.join(tmp, f"voice-none-{TAG}.tar")
    make_pack(novoice, "none", with_voice=False)
    said = refusal(rf.pack_voice, novoice, TAG)
    check(said is not None and one_sentence(said) and "voice.txt" in said, "a pack without voice.txt is refused")

    wrongname = os.path.join(tmp, "heart.tar")
    make_pack(wrongname)
    check(one_sentence(refusal(rf.pack_voice, wrongname, TAG) or ""), "a pack not named voice-<set>-<tag>.tar is refused")

    notar = os.path.join(tmp, f"voice-fake-{TAG}.tar")
    with open(notar, "wb") as f:
        f.write(b"this is not a tar file" * 100)
    said = refusal(rf.pack_voice, notar, TAG)
    check(said is not None and one_sentence(said) and "tar" in said, "a file that is no tar is refused")
    zipped = os.path.join(tmp, f"voice-zipped-{TAG}.tar")
    with open(path, "rb") as f:
        raw = f.read()
    with gzip.open(zipped, "wb") as f:
        f.write(raw)
    said = refusal(rf.pack_voice, zipped, TAG)
    check(said is not None and one_sentence(said) and "plain tar" in said, "a compressed tar is refused: the device unpacks a plain tar")
    empty = os.path.join(tmp, f"voice-empty-{TAG}.tar")
    open(empty, "wb").close()
    check(one_sentence(refusal(rf.pack_voice, empty, TAG) or ""), "an empty file is refused")


# The throwaway project: tools/momentum-base.txt, a submodule Momentum-Firmware with the API table,
# and the annotated tag sonar-0.1.0 on both; then a later commit in each that changes what the
# tag recorded, which must not reach release.json
def git(repo, *args):
    # protocol.file.allow: git 2.38.1 and newer refuse local submodules without it
    p = subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false",
                        "-c", "tag.gpgSign=false", "-c", "init.defaultBranch=main", "-c", "protocol.file.allow=always",
                        "-C", repo, *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} in {repo}: {p.stderr.strip()}")
    return p.stdout.strip()


def write(repo, name, text):
    path = os.path.join(repo, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)
    git(repo, "add", name)


def api_table(version):
    return f"entry,status,name,type,params\nVersion,+,{version},,\nFunction,+,furi_get_tick,uint32_t,\n"


class FakeGh:
    """gh's stand-in: records every call, answers release view with the draft's list, copies the
    assets into the folder of release download, and keeps the bytes of what release upload is
    given, as the temporary folder they are in goes away with the run."""

    def __init__(self, assets, draft=True):
        self.assets = dict(assets)
        self.draft = draft
        self.calls = []
        self.uploaded = {}

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("release", "view"):
            return json.dumps({"isDraft": self.draft, "assets": [{"name": n, "size": len(d)} for n, d in self.assets.items()]})
        if args[:2] == ("release", "download"):
            folder = args[args.index("--dir") + 1]
            for name, content in self.assets.items():
                with open(os.path.join(folder, name), "wb") as f:
                    f.write(content)
            return ""
        if args[:2] == ("release", "upload"):
            for path in args[3:]:
                if not path.startswith("--"):
                    with open(path, "rb") as f:
                        self.uploaded[os.path.basename(path)] = f.read()
            return ""
        raise AssertionError(f"unexpected gh call: {args}")

    def verbs(self):
        return [call[1] for call in self.calls]


def good_assets(tag=TAG, pack=None):
    assets = {name: f"content of {name}".encode() for name in names_for(tag)}
    assets[f"voice-heart-{tag}.tar"] = pack if pack is not None else pack_bytes()
    return assets


def run_finalise(root, gh, tag=TAG, dry=False):
    said = []
    code = rf.main([tag, "--dry"] if dry else [tag], gh=gh, root=root, say=said.append)
    return code, said


with tempfile.TemporaryDirectory() as tmp:
    fw = os.path.join(tmp, "fw")
    proj = os.path.join(tmp, "proj")
    for repo in (fw, proj):
        git(tmp, "init", "-q", repo)
    write(fw, "targets/f7/api_symbols.csv", api_table("87.3"))
    git(fw, "commit", "-q", "-m", "the fork at the tag")
    fork_at_tag = git(fw, "rev-parse", "HEAD")
    write(proj, "tools/momentum-base.txt", BASE + "\n")
    git(proj, "commit", "-q", "-m", "the project")
    git(proj, "submodule", "add", "-q", fw, "Momentum-Firmware")
    git(proj, "commit", "-q", "-m", "the submodule")
    git(proj, "tag", "-a", "-m", TAG, TAG)

    # After the tag: a newer pin in the project, a newer table checked out in the submodule
    write(proj, "tools/momentum-base.txt", "f" * 40 + "\n")
    git(proj, "commit", "-q", "-m", "a later pin")
    sub = os.path.join(proj, "Momentum-Firmware")
    write(sub, "targets/f7/api_symbols.csv", api_table("88.0"))
    git(sub, "commit", "-q", "-m", "a later table")

    check(rf.fork_commit(proj, TAG) == fork_at_tag, "the fork's commit is the one the tag records, not the one checked out")
    check(rf.momentum_base(proj, TAG) == BASE, "the Momentum base is tools/momentum-base.txt at the tag, not today's")
    check(rf.api_version(proj, fork_at_tag) == "87.3", "the API version is the table's at the fork's commit, not today's")
    said = refusal(rf.fork_commit, proj, "sonar-9.9.9")
    check(said is not None and one_sentence(said) and "sonar-9.9.9" in said, "a tag that is not in the checkout is refused")
    said = refusal(rf.api_version, proj, "0" * 40)
    check(said is not None and one_sentence(said), "a commit the submodule does not have is refused")
    said = refusal(rf.momentum_base, proj, "sonar-9.9.9")
    check(said is not None and one_sentence(said), "no tools/momentum-base.txt at an unknown tag is refused")

    # The whole run, with the assets of a good draft
    gh = FakeGh(good_assets())
    code, said = run_finalise(proj, gh)
    check(code == 0, "a good draft is finalised with exit code 0")
    check(gh.verbs() == ["view", "download", "upload"], "gh is asked to view the draft, download it and upload, in that order")
    upload = gh.calls[-1]
    check(upload[:3] == ("release", "upload", TAG) and upload[-1] == "--clobber"
          and sorted(os.path.basename(p) for p in upload[3:-1]) == ["SHA256SUMS", "release.json"],
          "the upload names the tag, SHA256SUMS and release.json, and --clobber")
    check(sorted(gh.uploaded) == ["SHA256SUMS", "release.json"], "only those two files were uploaded")
    uploaded = json.loads(gh.uploaded["release.json"])
    check(uploaded["firmware_version"] == TAG and uploaded["version"] == "0.1.0", "release.json names the tag")
    check(uploaded["firmware_commit"] == fork_at_tag[:9], "release.json carries the fork's commit at the tag, 9 characters")
    check(uploaded["momentum_base"] == BASE and uploaded["api_version"] == "87.3", "the Momentum base and the API version as of the tag")
    check(uploaded["default_voice"] == "heart" and uploaded["voices"] == [
        {"set": "heart", "backend": "kokoro", "voice": "af_heart", "file": f"voice-heart-{TAG}.tar"}],
        "heart is the default voice and the only one, read from the pack")
    check([a["name"] for a in uploaded["assets"]] == sorted(names_for(TAG)), "release.json lists the seven assets")
    check(all(a["sha256"] == hashlib.sha256(gh.assets[a["name"]]).hexdigest() and a["size"] == len(gh.assets[a["name"]])
              for a in uploaded["assets"]), "each asset's SHA-256 and size are those of its bytes")
    check(gh.uploaded["SHA256SUMS"].decode() == "".join(
        f"{hashlib.sha256(gh.assets[n]).hexdigest()}  {n}\n" for n in sorted(names_for(TAG))),
        "SHA256SUMS lists the same seven")
    check(all(isinstance(line, str) and "\n" not in line for line in said) and any(TAG in line for line in said), "the run says its steps in lines")

    # A second run over a draft that has the two files already: they are replaced, not listed
    again = good_assets()
    again["SHA256SUMS"] = b"old\n"
    again["release.json"] = b"{}\n"
    gh = FakeGh(again)
    code, _ = run_finalise(proj, gh)
    check(code == 0 and json.loads(gh.uploaded["release.json"])["assets"] == uploaded["assets"], "a rerun lists the seven again, not its own files")

    # An rc tag needs a tag of its own in the project
    git(proj, "tag", "-a", "-m", RC, RC, TAG)
    gh = FakeGh(good_assets(RC))
    code, _ = run_finalise(proj, gh, RC)
    check(code == 0 and json.loads(gh.uploaded["release.json"])["version"] == "0.1.0-rc1", "an rc tag is finalised with its version")

    # A dry run uploads nothing and says what it would
    gh = FakeGh(good_assets())
    code, said = run_finalise(proj, gh, dry=True)
    check(code == 0 and gh.verbs() == ["view", "download"] and not gh.uploaded, "a dry run views and downloads, and uploads nothing")
    check(any('"firmware_commit"' in line for line in " ".join(said).splitlines()), "a dry run shows release.json")

    # Refusals: one sentence on stderr, exit code 1, nothing uploaded
    def stderr_of(gh, tag=TAG):
        err = io.StringIO()
        old = sys.stderr
        sys.stderr = err
        try:
            code = rf.main([tag], gh=gh, root=proj, say=lambda line: None)
        finally:
            sys.stderr = old
        return code, err.getvalue()

    missing = good_assets()
    del missing[f"voice-heart-{TAG}.tar"]
    gh = FakeGh(missing)
    code, err = stderr_of(gh)
    check(code == 1 and one_sentence(err.rstrip("\n")) and f"voice-heart-{TAG}.tar" in err, "a missing pack: exit 1, one sentence on stderr that names it")
    check(gh.verbs() == ["view"], "the missing pack is seen in the draft's list: nothing is downloaded or uploaded")

    extra = good_assets()
    extra[f"voice-espeak-{TAG}.tar"] = pack_bytes("espeak", "espeak en-us+f3 rate 160 highpass 500 gain 1.3 soft 16000\n")
    gh = FakeGh(extra)
    code, err = stderr_of(gh)
    check(code == 1 and one_sentence(err.rstrip("\n")) and "voice-espeak" in err and "upload" not in gh.verbs(),
          "an extra voice pack: exit 1, one sentence, no upload")

    wrong = good_assets(pack=pack_bytes("heart", "say Samantha rate 175 highpass 500 gain 1.3 soft 16000\n"))
    gh = FakeGh(wrong)
    code, err = stderr_of(gh)
    check(code == 1 and one_sentence(err.rstrip("\n")) and "say" in err and "upload" not in gh.verbs(),
          "a pack of macOS voices: exit 1, one sentence, no upload")

    gh = FakeGh(good_assets(), draft=False)
    code, err = stderr_of(gh)
    check(code == 1 and one_sentence(err.rstrip("\n")) and "published" in err and gh.verbs() == ["view"],
          "a published release is refused before anything is downloaded")

    gh = FakeGh(good_assets())
    code, err = stderr_of(gh, "sonar-9.9.9")
    check(code == 1 and one_sentence(err.rstrip("\n")) and "sonar-9.9.9" in err and gh.calls == [],
          "a tag that is not in the checkout is refused before gh is asked anything")

    def failing(*args):
        raise rf.Refusal("gh release view failed: HTTP 404: Not Found")

    code, err = stderr_of(failing)
    check(code == 1 and err.strip() == "gh release view failed: HTTP 404: Not Found", "a failure of gh is told in its own sentence")

# run_gh: the real wrapper, with a stand-in command in the place of gh
said = refusal(rf.run_gh, "release", "view", TAG, cmd=("/nonexistent/gh",))
check(said is not None and one_sentence(said) and "gh" in said, "a gh that is not installed is told in one sentence")
fake = (sys.executable, "-c", "import sys; sys.stderr.write('HTTP 404: Not Found\\nsecond line\\n'); sys.exit(1)")
said = refusal(rf.run_gh, "release", "view", TAG, cmd=fake)
check(said is not None and one_sentence(said) and "release view" in said and "second line" in said,
      "a gh that fails is told with its last line of complaint")
ok = (sys.executable, "-c", "import sys; print(' '.join(sys.argv[1:]))")
check(rf.run_gh("release", "view", TAG, cmd=ok).strip() == f"release view {TAG}", "the arguments reach gh, and its output comes back")

# The command line: a tag of the wrong form is refused before gh is asked anything
for bad in ("main", "sonar-1.2", "v1.2.3", "sonar-1.2.3-beta"):
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "release_finalise.py"), bad], capture_output=True, text=True)
    check(p.returncode == 1 and one_sentence(p.stderr.rstrip("\n")) and bad in p.stderr and p.stdout == "",
          f"the tag {bad!r} is refused in one sentence, exit 1")
p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "release_finalise.py")], capture_output=True, text=True)
check(p.returncode != 0 and "usage" in p.stderr.lower(), "without a tag the usage is shown")

print(f"release finalise: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
