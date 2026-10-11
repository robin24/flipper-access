#!/usr/bin/env python3
"""Write SHA256SUMS and release.json for a draft GitHub Release, and upload them to it.

    tools/release_finalise.py TAG [--dry]

The release workflow (.github/workflows/release.yml) leaves a draft with six assets. The Mac then
adds the one voice pack, voice-heart-TAG.tar, which tools/voice_pack.py makes and gh release
upload uploads, and this tool finishes the draft: it downloads every asset of the draft, checks
that they are the seven a release has and no others, hashes them, and uploads two more,
SHA256SUMS and release.json, with gh release upload --clobber. It downloads the assets again
rather than reading the local files, so that the checksums are those of the bytes a user will
download. Run from the project root (python3 is enough, it uses the standard library) with the
GitHub command line, gh, signed in:

    tools/release_finalise.py sonar-0.1.0

The seven assets of a release named TAG, such as sonar-0.1.0 or sonar-0.1.0-rc1:
flipper-z-f7-update-TAG.tgz, install-TAG.zip, TAG-firmware.elf, TAG-firmware.map,
flipper-z-f7-sdk-TAG.zip, TAG-source.tar.gz and voice-heart-TAG.tar. Heart is the only voice pack
a release ships, and the default voice. A release holds nothing else, so a second voice pack or a
stray file is refused, as is a pack made with the macOS voices (Apple's licence) or any backend
but kokoro and espeak. Every refusal is one sentence on stderr, exit code 1, before anything is
uploaded; a missing asset is seen in the draft's list before anything is downloaded. A release
that is published already is refused: finalise the draft, then publish it.

SHA256SUMS is in the format of sha256sum, sorted by name, so that
    shasum -a 256 -c SHA256SUMS
checks a download. release.json holds, in this order:
    version           the tag without its name prefix, such as 0.1.0 or 0.1.0-rc1
    firmware_version  the tag, which is what the device's info device reports
    firmware_commit   the fork's commit that the project's tag records for Momentum-Firmware, 9
                      characters (the device prints 8, and install.py compares by prefix)
    momentum_base     the Momentum commit the fork builds on, tools/momentum-base.txt at the tag
    api_version       the firmware API version, such as 87.3, the Version line of
                      targets/f7/api_symbols.csv at the fork's commit (install.py compares it with
                      firmware.api.major and firmware.api.minor joined by a dot)
    default_voice     heart
    voices            for each pack: set, backend and voice from the first line of the pack's own
                      sr/voices/<set>/voice.txt, and file, the asset's name
    assets            for each asset but these two files: name, sha256 and size in bytes, sorted
The commit, the pin and the API version are those of the tag, read from git, whatever is checked
out now; the project's tag must be in this checkout, and the submodule must have the commit it
records. --dry does everything but the upload, and prints the two files.
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FORK_DIR = "Momentum-Firmware"
API_TABLE = "targets/f7/api_symbols.csv"
PIN_FILE = "tools/momentum-base.txt"

TAG_FORM = re.compile(r"sonar-(\d+\.\d+\.\d+(?:-rc\d+)?)")
COMMIT_FORM = re.compile(r"[0-9a-f]{40}")
# The voice packs a release ships; the first is the default (decision of 2026-10-11)
PACKS = ("heart",)
DEFAULT_VOICE = "heart"
# The backends whose clips a release may ship; the macOS voices are for the maker's device only
BACKENDS = ("kokoro", "espeak")
# The two files this tool adds. They are not assets to hash (a file cannot hold its own digest),
# and a draft finalised before holds them already
ENVELOPE = ("SHA256SUMS", "release.json")
CHUNK = 1 << 20


class Refusal(Exception):
    """One sentence to say on stderr; the run stops with exit code 1."""


def join_names(names):
    """'a', 'a and b', 'a, b and c'."""
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def tag_version(tag):
    """The tag without its name prefix; a Refusal for a name that is not sonar-X.Y.Z or
    sonar-X.Y.Z-rcN."""
    m = TAG_FORM.fullmatch(tag)
    if m is None:
        raise Refusal(f"{tag} is not a release tag of the form sonar-X.Y.Z or sonar-X.Y.Z-rcN")
    return m.group(1)


def expected_names(tag):
    """The names of a release's seven assets."""
    return [f"flipper-z-f7-update-{tag}.tgz", f"install-{tag}.zip", f"{tag}-firmware.elf", f"{tag}-firmware.map",
            f"flipper-z-f7-sdk-{tag}.zip", f"{tag}-source.tar.gz"] + [f"voice-{name}-{tag}.tar" for name in PACKS]


def check_assets(tag, names):
    """A Refusal unless names, the draft's files, are the release's seven assets: one is missing,
    a voice pack is not one of PACKS, or a file is none of the seven. SHA256SUMS and release.json
    are ignored, as a draft finalised before holds them."""
    present = [name for name in names if name not in ENVELOPE]
    wanted = expected_names(tag)
    missing = [name for name in wanted if name not in present]
    if missing:
        raise Refusal(f"the draft {tag} lacks {join_names(missing)}; the release workflow builds every asset but the "
                      "voice pack, which tools/voice_pack.py makes")
    extra = sorted(name for name in present if name not in wanted)
    packs = [name for name in extra if name.startswith("voice-") and name.endswith(".tar")]
    if packs:
        raise Refusal(f"the draft {tag} holds {join_names(packs)}, but {join_names(PACKS)} is the only voice pack a "
                      "release ships; delete the extra pack from the draft")
    if extra:
        raise Refusal(f"the draft {tag} holds {join_names(extra)}, which is not one of its assets; delete it from the draft")


def describe(directory, names):
    """(name, SHA-256, size in bytes) of each file of names in directory, in that order."""
    found = []
    for name in names:
        digest = hashlib.sha256()
        size = 0
        with open(os.path.join(directory, name), "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK), b""):
                digest.update(chunk)
                size += len(chunk)
        found.append((name, digest.hexdigest(), size))
    return found


def sha256sums(assets):
    """SHA256SUMS: one line per asset in the format of sha256sum, the digest, two spaces and the
    name, sorted by name, each line ended by a newline. assets: (name, SHA-256, size) tuples."""
    return "".join(f"{digest}  {name}\n" for name, digest, _size in sorted(assets))


def pack_voice(path, tag):
    """The voice of the pack at path, named voice-<set>-<tag>.tar: {"set", "backend", "voice",
    "file"}, from the first line of its sr/voices/<set>/voice.txt, which the generator writes as
    "<backend> <voice> rate ..." (voice_build.settings_line). A Refusal for a name of another form,
    a file that is no plain tar or holds no voice.txt, or a backend that is neither kokoro nor
    espeak."""
    file = os.path.basename(path)
    named = re.fullmatch(rf"voice-(.+)-{re.escape(tag)}\.tar", file)
    if named is None:
        raise Refusal(f"{file} is not named voice-<set>-{tag}.tar")
    set_name = named.group(1)
    member = f"sr/voices/{set_name}/voice.txt"
    line = None
    try:
        # "r:" is a plain tar, which is what the device unpacks; a compressed one is refused
        with tarfile.open(path, "r:") as tar:
            for entry in tar:
                if entry.name == member and entry.isfile():
                    line = tar.extractfile(entry).read(4096).decode("utf-8", "replace")
                    break
    except (tarfile.TarError, OSError) as e:
        raise Refusal(f"the pack {file} cannot be read as a plain tar file ({e})") from None
    if line is None:
        raise Refusal(f"the pack {file} holds no {member}; make it again with tools/voice_pack.py")
    fields = line.split("\n", 1)[0].split()
    if len(fields) < 2:
        raise Refusal(f"the first line of {member} in the pack {file} names no backend and voice")
    backend, voice = fields[0], fields[1]
    if backend not in BACKENDS:
        raise Refusal(f"the pack {file} was made with the backend {backend}, and a release ships only "
                      f"{join_names(BACKENDS)} voices")
    return {"set": set_name, "backend": backend, "voice": voice, "file": file}


def release_json(tag, fork_commit, momentum_base, api_version, default_voice, assets, voices=()):
    """release.json's fields, in order. fork_commit: the fork's commit, cut to 9 characters as
    install.py compares by prefix with the 8 the device prints; momentum_base is kept whole.
    assets: (name, SHA-256, size) tuples, listed sorted by name; voices: the packs' pack_voice
    dicts."""
    return {
        "version": tag_version(tag),
        "firmware_version": tag,
        "firmware_commit": fork_commit[:9],
        "momentum_base": momentum_base,
        "api_version": api_version,
        "default_voice": default_voice,
        "voices": list(voices),
        "assets": [{"name": name, "sha256": digest, "size": size} for name, digest, size in sorted(assets)],
    }


def release_text(data):
    """release.json's text: indented JSON with a final newline."""
    return json.dumps(data, indent=2) + "\n"


# What the tag records, read from git so that it is the tag's and not what is checked out now


def git(root, *args):
    try:
        return subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise Refusal("git is not installed or not on the PATH") from None


def gitlink_commit(ls_tree):
    """The commit of the submodule in git ls-tree's output: the line of mode 160000."""
    for line in ls_tree.splitlines():
        m = re.fullmatch(rf"160000 commit ({COMMIT_FORM.pattern})\t{re.escape(FORK_DIR)}", line)
        if m:
            return m.group(1)
    raise Refusal(f"the project's tag records no commit of the submodule {FORK_DIR}")


def parse_api_version(table):
    """The Version line of the API table, such as "Version,+,87.3,,": 87.3."""
    m = re.search(r"^Version,\+,(\d+\.\d+),,\s*$", table, re.MULTILINE)
    if m is None:
        raise Refusal(f"{API_TABLE} has no Version line")
    return m.group(1)


def parse_pin(text):
    """The Momentum commit in tools/momentum-base.txt: its first line, 40 hex digits."""
    first = (text.splitlines() or [""])[0].strip()
    if COMMIT_FORM.fullmatch(first) is None:
        raise Refusal(f"{PIN_FILE} does not start with a commit of 40 hex digits")
    return first


def fork_commit(root, tag):
    """The fork's commit that the project's tag records for the submodule."""
    p = git(root, "ls-tree", f"refs/tags/{tag}", FORK_DIR)
    if p.returncode != 0:
        raise Refusal(f"the tag {tag} is not in this checkout; fetch it with git fetch origin tag {tag}")
    return gitlink_commit(p.stdout)


def momentum_base(root, tag):
    """The Momentum commit the fork builds on, tools/momentum-base.txt as the tag has it."""
    p = git(root, "show", f"refs/tags/{tag}:{PIN_FILE}")
    if p.returncode != 0:
        raise Refusal(f"the tag {tag} has no {PIN_FILE}")
    return parse_pin(p.stdout)


def api_version(root, commit):
    """The firmware API version in the fork's table at commit, from the submodule's own history."""
    p = git(os.path.join(root, FORK_DIR), "show", f"{commit}:{API_TABLE}")
    if p.returncode != 0:
        raise Refusal(f"{API_TABLE} cannot be read at the commit {commit[:9]} of {FORK_DIR}; update the submodule "
                      "with git submodule update --init")
    return parse_api_version(p.stdout)


# GitHub, through the gh command line only


def run_gh(*args, cmd=("gh",)):
    """gh's output for gh *args, run in the project (which tells gh the repository), never asking
    anything; a Refusal with gh's last line of complaint when it cannot run or fails."""
    try:
        p = subprocess.run([*cmd, *args], capture_output=True, text=True, stdin=subprocess.DEVNULL, cwd=ROOT)
    except FileNotFoundError:
        raise Refusal("gh is not installed or not on the PATH; install it with brew install gh and sign in with "
                      "gh auth login") from None
    except OSError as e:
        raise Refusal(f"gh cannot be run ({e.strerror or e})") from None
    if p.returncode != 0:
        said = [line.strip() for line in p.stderr.splitlines() if line.strip()]
        raise Refusal(f"gh {' '.join(args[:2])} failed: {said[-1] if said else 'exit code ' + str(p.returncode)}")
    return p.stdout


def finalise(tag, root=ROOT, gh=run_gh, dry=False, say=print):
    """Write SHA256SUMS and release.json for the draft of tag and upload them, or with dry only
    say them. gh(*args) runs the gh command line and returns its output."""
    tag_version(tag)
    commit = fork_commit(root, tag)
    base = momentum_base(root, tag)
    api = api_version(root, commit)
    say(f"The tag {tag} records the fork's commit {commit[:9]}, on the Momentum base {base[:9]}, with API version {api}.")

    try:
        listing = json.loads(gh("release", "view", tag, "--json", "isDraft,assets"))
        draft = listing["isDraft"]
        listed = [asset["name"] for asset in listing["assets"]]
    except (ValueError, KeyError, TypeError):
        raise Refusal(f"gh release view {tag} gave an answer without isDraft and assets") from None
    if not draft:
        raise Refusal(f"the release {tag} is published already; finalise the draft before publishing it")
    check_assets(tag, listed)

    with tempfile.TemporaryDirectory() as tmp:
        downloads = os.path.join(tmp, "assets")
        uploads = os.path.join(tmp, "upload")
        os.mkdir(downloads)
        os.mkdir(uploads)
        say(f"Downloading the {len(listed)} files of the draft {tag}; the voice pack and the source bundle are large, "
            "so this takes a few minutes.")
        gh("release", "download", tag, "--dir", downloads)
        names = sorted(os.listdir(downloads))
        check_assets(tag, names)
        names = [name for name in names if name not in ENVELOPE]
        assets = describe(downloads, names)
        say(f"Hashed {len(assets)} assets, {sum(size for _n, _d, size in assets):,} bytes in all.")
        voices = [pack_voice(os.path.join(downloads, f"voice-{name}-{tag}.tar"), tag) for name in PACKS]
        for voice in voices:
            say(f"The voice pack {voice['file']} holds the {voice['backend']} voice {voice['voice']}.")

        sums = sha256sums(assets)
        text = release_text(release_json(tag, commit, base, api, DEFAULT_VOICE, assets, voices))
        if dry:
            say("SHA256SUMS:")
            say(sums.rstrip("\n"))
            say("release.json:")
            say(text.rstrip("\n"))
            say("This was a dry run, so nothing was uploaded.")
            return
        paths = []
        for name, content in (("SHA256SUMS", sums), ("release.json", text)):
            paths.append(os.path.join(uploads, name))
            with open(paths[-1], "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
        say(f"Uploading SHA256SUMS and release.json to the draft {tag}.")
        gh("release", "upload", tag, *paths, "--clobber")
    say(f"Done. The draft {tag} has its SHA256SUMS and release.json; look it over on GitHub, then publish it by hand.")


def main(argv=None, gh=run_gh, root=ROOT, say=print):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("tag", help="the release's tag, sonar-X.Y.Z or sonar-X.Y.Z-rcN")
    ap.add_argument("--dry", action="store_true", help="download and check, print the two files, upload nothing")
    args = ap.parse_args(argv)
    try:
        finalise(args.tag, root, gh, args.dry, say)
    except Refusal as e:
        print(e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
