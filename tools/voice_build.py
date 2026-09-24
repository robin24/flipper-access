#!/usr/bin/env python3
"""Build and sync the screen reader's recorded vocabulary.

    tools/voice_build.py [--extract] [--extract-all] [--card-apps] [--pull-missing] [--sync]
        [--check] [--dry] [options]

Words come from tools/voice_words.txt, from every string literal in the firmware's core apps
and services and the dolphin's speech bubble texts, run through the real pronunciation layer
(--extract), and from the device's /ext/sr/missing.txt (--pull-missing). A clip's name is the
word in lower case without apostrophes ("don't" is dont, spoken as "don't"); a clip listed in
tools/voice_names.txt is spoken as written there, which names the single letters that spell a
word the device has no clip for. Clips land in voice/<initial>/<word>.raw next to
voice/manifest.json, which remembers the settings each clip was made with, so a rerun makes
only what is missing or changed. --sync uploads new or changed clips to
/ext/sr/voice/<hh>/<word>.raw on the card, hh being the word's FNV-1a hash modulo 64
as two hex digits, the same folder the firmware's speech_voice_path computes; --pull-missing
removes the pulled missing list. --remove-legacy clears the first layout's
/ext/sr/voice/<initial>/ folders. Defaults are the settings Robin chose by ear on 2026-09-24.

Clip format: raw unsigned 8-bit mono PCM, 16000 Hz, 128 silence, trimmed to 15 ms of silence
at each end. Backends: say (macOS, personal use: Apple's voices may not be redistributed) and
piper (any platform, a freely licensed model, the right choice for a release).

--sync and --pull-missing import the firmware's scripts/flipper/storage.py, which needs
pyserial: run those with the project virtualenv's Python (.venv/bin/python), not the system
python3.

--extract-all folds in every app under applications/external (hundreds of them); --card-apps
folds in only the ones actually installed on the card, which is the routine choice, and needs
the device but only to list it, never to write to it. Both need --extract to have an effect.
--dry builds the word list and prints its counts without making clips, pulling missing.txt, or
syncing.
"""
import argparse, glob, hashlib, json, math, multiprocessing, os, re, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from clip_make import finish, highpass, pad, read_wav, synth, to_u8, trim  # noqa: E402

FW = os.path.join(ROOT, "Momentum-Firmware")
SRC = os.path.join(FW, "applications", "services", "screen_reader")
DEFAULTS = dict(backend="say", voice="Samantha", rate=175, highpass=500.0, gain=1.3, soft=True, hz=16000, model="")
WORD_RE = re.compile(r"^(?:[a-z]{1,16}|[0-9])$")
STRING_RE = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
PRINTF_RE = re.compile(r"%[-+ 0#]*\d*(?:\.\d+)?(?:hh|h|ll|l|L|q|j|z|t)?[diouxXeEfgGcsp%]")
DIGIT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
FAM_APPID_RE = re.compile(r'appid\s*=\s*"([^"]+)"')
FAM_FILENAME_RE = re.compile(r'fap_file_name\s*=\s*"([^"]+)"')
APP_MANIFEST_DIRS = ("external", "main", "system", "settings", "debug")


def log(msg):
    print(msg, flush=True)


def clip_name(word):
    """The clip name of a token: lower case, apostrophes left out, as the device looks it up."""
    word = word.strip().lower().replace("'", "")
    return word if WORD_RE.match(word) else None


def fnv1a(word):
    """FNV-1a, 32 bit, as speech_voice_hash in the firmware."""
    h = 2166136261
    for b in word.encode():
        h ^= b
        h = (h * 16777619) & 0xffffffff
    return h


def bucket(word):
    """The card folder of a clip: the hash modulo 64 as two lower case hex digits. A directory
    lookup on the card reads the entries one by one, about 0.17 ms each, so the clips are spread
    over 64 folders of a few dozen rather than a few folders of hundreds."""
    return f"{fnv1a(word) % 64:02x}"


def initial(word):
    c = word[0]
    return c if c.isalnum() else "_"


def load_list(path):
    """Load one word per line, '#' starting a comment. A non-blank token that clip_name rejects
    (for example a word that mixes letters and digits, such as "md5") is silently unusable, so
    it is counted and reported rather than just vanishing from the word count."""
    words = set()
    skipped = 0
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="replace"):
            token = line.split("#", 1)[0].strip()
            if not token:
                continue
            n = clip_name(token)
            if n:
                words.add(n)
            else:
                skipped += 1
    if skipped:
        log(f"skipped {skipped} words that cannot be clips")
    return words


def load_names():
    names = {}
    path = os.path.join(HERE, "voice_names.txt")
    if os.path.exists(path):
        for line in open(path, encoding="utf-8"):
            parts = line.rstrip("\n").split("\t")
            if len(parts) == 2 and parts[0]:
                names[parts[0].lower()] = parts[1]
    return names


def spoken_text(word, names):
    """What say speaks for a clip: its line in tools/voice_names.txt (the letters by their
    names, so that a spelled word is heard as "en eff see"), a digit's number word, or the word
    itself."""
    if word in names:
        return names[word]
    if len(word) == 1 and word.isdigit():
        return DIGIT_WORDS[int(word)]
    if len(word) == 1:
        return word  # lower case: say reads an upper case letter as "capital" and the letter
    return word


def build_expander(workdir):
    exe = os.path.join(workdir, "speech_expand")
    src = os.path.join(ROOT, "tests", "host", "speech_expand.c")
    layer = os.path.join(SRC, "speech_text.c")
    newest = max(os.path.getmtime(p) for p in (src, layer, os.path.join(SRC, "speech_text.h")))
    if not os.path.exists(exe) or os.path.getmtime(exe) < newest:
        subprocess.run(["clang", "-std=c11", "-O1", "-I", SRC, "-o", exe, src, layer], check=True)
    return exe


def strings_in(roots):
    """Every string literal in the .c and .h files under the given directories, unescaped,
    printf fields removed -- the same filtering firmware_strings applies to the core roots,
    reused for community app directories by --extract-all and --card-apps."""
    seen = set()
    for root in roots:
        for path in glob.glob(os.path.join(root, "**", "*.[ch]"), recursive=True):
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for m in STRING_RE.finditer(text):
                s = m.group(1)
                s = s.replace("\\n", " ").replace("\\t", " ").replace('\\"', '"').replace("\\\\", "\\")
                s = re.sub(r"\\.", "", s)
                s = PRINTF_RE.sub(" ", s)
                s = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in s).strip()
                if len(s) >= 2:
                    seen.add(s)
    return seen


def firmware_strings():
    """Every string literal in the firmware's core C sources, unescaped, printf fields removed."""
    # The core apps and services only: applications/external holds hundreds of community apps
    # whose strings would multiply the vocabulary and the upload time for nothing, unless asked
    # for with --extract-all or --card-apps.
    roots = [os.path.join(FW, "applications", d) for d in ("main", "services", "settings", "system")]
    roots.append(os.path.join(FW, "lib", "toolbox"))
    return sorted(strings_in(roots))


def external_app_dirs():
    """Every app directory under applications/external: each holds one application.fam. Used by
    --extract-all for the word pipeline, and it is where manifest_index looks too."""
    ext = os.path.join(FW, "applications", "external")
    return sorted(os.path.dirname(p) for p in glob.glob(os.path.join(ext, "*", "application.fam")))


def strip_comment(line):
    """The part of a manifest line before a '#' comment that starts outside a double-quoted
    string. The manifests use plain double-quoted strings (no escapes to worry about), so
    toggling on every '"' is enough to tell a real comment from a '#' that could only appear
    inside one of those strings."""
    in_string = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_string = not in_string
        elif ch == "#" and not in_string:
            return line[:i]
    return line


def manifest_index(roots):
    """Maps a card .fap's base name to the source directory whose application.fam declares it:
    the appid of one of its App(...) blocks -- a manifest may hold several; applications/main/
    nfc/application.fam alone has over sixty, one per NFC parser plugin -- or, for a manifest
    that names its own build output, its fap_file_name. Comments are stripped line by line
    first, so a commented-out App(...) block -- for example applications/external/subghz_remote/
    application.fam's disabled first block, appid "subghz_remote_ofw" sitting right next to the
    live "subghz_remote", or applications/main/subghz/application.fam's commented "subghz_fap"
    -- is never indexed. A later match wins on a collision, which the firmware's own build
    should not allow in practice."""
    index = {}
    for root in roots:
        for path in glob.glob(os.path.join(root, "**", "application.fam"), recursive=True):
            try:
                raw = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            text = "\n".join(strip_comment(line) for line in raw.splitlines())
            keys = set(FAM_APPID_RE.findall(text)) | set(FAM_FILENAME_RE.findall(text))
            for key in keys:
                index[key] = os.path.dirname(path)
    return index


def bubble_texts():
    """The dolphin's speech bubble texts: the Text: lines of the animation manifests, with the
    \\n line breaks as spaces."""
    seen = set()
    for path in glob.glob(os.path.join(FW, "assets", "dolphin", "**", "*.txt"), recursive=True):
        if os.path.basename(path) not in ("manifest.txt", "meta.txt"):
            continue
        for line in open(path, encoding="utf-8", errors="replace"):
            if line.startswith("Text:"):
                s = line[len("Text:"):].replace("\\n", " ")
                s = "".join(ch if 32 <= ord(ch) < 127 else " " for ch in s).strip()
                if len(s) >= 2:
                    seen.add(s)
    return sorted(seen)


def _expand(exe, lines):
    """Run the pronunciation layer over a set of source strings, returning the clip-name words
    it produces and, for each word an apostrophe was stripped from, the original token to speak
    ("dont" is spoken as "don't")."""
    out = subprocess.run([exe], input="\n".join(sorted(lines)) + "\n", capture_output=True, text=True, check=True).stdout
    words, originals = set(), {}
    for line in out.splitlines():
        for token in line.split():
            token = token.strip(".,?!;:")
            n = clip_name(token)
            if n:
                words.add(n)
                core = token.strip("'").lower()
                if "'" in core:  # inside the word, not quotes around it
                    originals[n] = min(originals.get(n, core), core)
    return words, originals


def extract_words(workdir, extra=()):
    """The words of the firmware's strings and the bubble texts, run through the pronunciation
    layer. extra is a list of (label, directories) pairs -- --extract-all's app directories,
    --card-apps's matched ones -- whose own .c and .h strings are folded into the same pipeline
    on top of the firmware's own, each in turn. The third return value maps each label to how
    many words it alone added on top of everything folded in before it, so the caller can report
    an optional source's worth."""
    exe = build_expander(workdir)
    strings = firmware_strings()
    bubbles = bubble_texts()
    log(f"extract: {len(strings)} distinct strings from the firmware sources, {len(bubbles)} bubble texts")
    lines = set(strings) | set(bubbles)
    words, originals = _expand(exe, lines)
    added = {}
    for label, dirs in extra:
        lines |= strings_in(dirs)
        more_words, more_originals = _expand(exe, lines)
        added[label] = len(more_words - words)
        words, originals = more_words, more_originals
    longest = sorted(words, key=lambda w: (-len(w), w))[:10]
    log(f"extract: {len(words)} words; longest: {' '.join(longest)}")
    log(f"extract: {len(originals)} with an apostrophe: {' '.join(originals[n] for n in sorted(originals))}")
    return words, originals, added


def settings_hash(settings, text):
    key = json.dumps([settings[k] for k in sorted(settings)] + [text])
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def synth_piper(text, model, hz, path):
    wav = path + ".piper.wav"
    subprocess.run(["piper", "--model", model, "--output_file", wav], input=text, text=True, check=True, capture_output=True)
    x, src_hz = read_wav(wav)
    os.remove(wav)
    if src_hz != hz:
        n = int(len(x) * hz / src_hz)
        x = [x[min(len(x) - 1, int(i * src_hz / hz))] for i in range(n)]
    return x


def make_clip(job):
    word, text, settings, out_path = job
    try:
        with tempfile.TemporaryDirectory() as d:
            if settings["backend"] == "piper":
                x = synth_piper(text, settings["model"], settings["hz"], os.path.join(d, "clip"))
            else:
                wav = os.path.join(d, "clip.wav")
                synth(text, settings["voice"], settings["rate"], settings["hz"], wav)
                x, _ = read_wav(wav)
        x = highpass(x, settings["hz"], settings["highpass"])
        x = finish(x, settings["gain"], settings["soft"])
        x = trim(x, settings["hz"])
        x = pad(x, settings["hz"])
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(to_u8(x))
        return word, True, ""
    except Exception as e:  # one bad word must not stop the build
        return word, False, str(e)


def settings_line(settings):
    # The device's status line shows only the first 63 characters of voice.txt, so for piper
    # this prints the model's basename without extension rather than its (possibly long) path.
    s = settings
    voice = os.path.splitext(os.path.basename(s["model"]))[0] if s["backend"] == "piper" else s["voice"]
    return f"{s['backend']} {voice} rate {s['rate']} highpass {s['highpass']:g} gain {s['gain']:g} {'soft' if s['soft'] else 'hard'} {s['hz']}"


def open_storage(port):
    sys.path.insert(0, os.path.join(FW, "scripts"))
    from flipper.storage import FlipperStorage, FlipperStorageOperations  # noqa: E402
    storage = FlipperStorage(port)
    storage.start()
    return storage, FlipperStorageOperations(storage)


def list_card_apps(storage):
    """*.fap base names on the card: the direct contents of /ext/apps, in case a stray file
    sits there, and of each of its category folders one level down. Nothing deeper is visited --
    apps are not nested further than a category folder. storage.walk yields a folder's own
    listing before recursing into its subfolders, so a single shared generator cannot be used
    to step across sibling categories: a category that itself has a subfolder would make the
    next next() descend into it instead of moving to the next category. A fresh walk() per
    category, read only once, always yields that category's own listing first and is simply
    never advanced further, so nothing deeper is ever visited."""
    def faps(names):
        return [os.path.splitext(n)[0] for n in names if n.lower().endswith(".fap")]
    _, categories, root_files = next(storage.walk("/ext/apps"))
    names = faps(root_files)
    for category in categories:
        path = ("/ext/apps/" + category).replace("//", "/")
        _, _, files = next(storage.walk(path))
        names.extend(faps(files))
    return sorted(set(names))


def card_apps(port):
    """The apps installed on the card, mapped to the firmware source directory each came from.
    Read-only, so unlike sync it does not need the voice guard: reuses open_storage directly.
    Returns the .fap names found, the (possibly repeated, one per matching name) directories
    they matched, and the names that matched no manifest."""
    storage, _ = open_storage(port)
    try:
        faps = list_card_apps(storage)
    finally:
        storage.stop()
    index = manifest_index([os.path.join(FW, "applications", d) for d in APP_MANIFEST_DIRS])
    matched, unmatched = [], []
    for fap in faps:
        d = index.get(fap)
        if d:
            matched.append(d)
        else:
            unmatched.append(fap)
    return faps, matched, unmatched


def voice_was_on(storage):
    """True if the device's status reply to `sr voice status` says the recorded voice is on."""
    reply = storage.send_and_wait_prompt("sr voice status\r")
    return b"voice: on" in reply


def voice_off(storage):
    """Silence the recorded voice before a transfer: opening a file the worker has open for
    playback would otherwise block and stall the speaker mid-buffer. Returns whether it was
    on before, so the caller can decide whether to turn it back on."""
    was_on = voice_was_on(storage)
    storage.send_and_wait_prompt("sr voice off\r")
    log("voice: silenced for the transfer")
    return was_on


def voice_on(storage):
    storage.send_and_wait_prompt("sr voice on\r")
    log("voice: restored")


def pull_missing(port):
    storage, _ = open_storage(port)
    words = set()
    was_on = False
    try:
        was_on = voice_off(storage)
        if storage.exist_file("/ext/sr/missing.txt"):
            with tempfile.TemporaryDirectory() as d:
                local = os.path.join(d, "missing.txt")
                storage.receive_file("/ext/sr/missing.txt", local)
                words = load_list(local)
            storage.remove("/ext/sr/missing.txt")
        log(f"pulled {len(words)} missing words from the device")
    finally:
        if was_on:
            try:
                voice_on(storage)
            except Exception as e:
                log(f"failed to restore voice: {e}")
        storage.stop()
    return words


def sync(port, out_dir, manifest, force_all=False):
    """Send voice.txt and the clip files the device actually uses (not .build, not
    manifest.json). voice/synced.json remembers the settings hash uploaded for each word, so a
    rerun only sends what's missing or changed instead of asking the device to md5 every file.
    A word whose local clip is missing or whose send fails is reported and left out of
    synced.json, so the next sync tries it again, and the other words still go. Returns the
    number of such words for main()'s exit code."""
    storage, ops = open_storage(port)
    was_on = False
    try:
        was_on = voice_off(storage)
        t0 = time.time()
        synced_path = os.path.join(out_dir, "synced.json")
        synced = {} if force_all else (json.load(open(synced_path)) if os.path.exists(synced_path) else {})
        made_dirs = set()
        words = manifest.get("words", {})
        sent = skipped = missing = failed = 0
        for i, word in enumerate(sorted(words), 1):
            h = words[word]
            if synced.get(word) == h:
                skipped += 1
                continue
            init = initial(word)
            local_path = os.path.join(out_dir, init, word + ".raw")
            # Checked here, not left to send_file: it removes the card's copy before it opens
            # the local file, so a missing clip would cost the one already on the card
            if not os.path.exists(local_path):
                log(f"sync: missing: {word}: no local clip {init}/{word}.raw, not sent")
                missing += 1
                continue
            folder = bucket(word)
            try:
                if folder not in made_dirs:
                    ops.mkpath(f"/ext/sr/voice/{folder}")
                    made_dirs.add(folder)
                storage.send_file(local_path, f"/ext/sr/voice/{folder}/{word}.raw")
            except Exception as e:  # one bad word must not stop the sync
                log(f"sync: failed: {word}: {type(e).__name__}: {e}")
                failed += 1
                continue
            synced[word] = h
            sent += 1
            if i % 100 == 0:
                log(f"sync: {i} of {len(words)}, {sent} sent, {skipped} skipped, {time.time() - t0:.0f} s")
                save_manifest(synced, synced_path)
        # Saved before voice.txt goes, so a failure there cannot lose the record of what was sent
        save_manifest(synced, synced_path)
        storage.send_file(os.path.join(out_dir, "voice.txt"), "/ext/sr/voice/voice.txt")
        log(f"sync: {sent} sent, {skipped} skipped, {missing} missing, {failed} failed, {time.time() - t0:.0f} s")
        return missing + failed
    finally:
        if was_on:
            try:
                voice_on(storage)
            except Exception as e:
                log(f"failed to restore voice: {e}")
        storage.stop()


def remove_legacy(port, out_dir):
    """Remove the first layout from the card: /ext/sr/voice/<initial>/<word>.raw for every word
    voice/synced.json records, then each single character folder that is left empty (a folder
    that still holds anything refuses the remove, which is ignored). synced.json is cleared
    afterwards, so the next --sync sends everything into the hashed folders."""
    synced_path = os.path.join(out_dir, "synced.json")
    synced = json.load(open(synced_path)) if os.path.exists(synced_path) else {}
    storage, _ = open_storage(port)
    from flipper.storage import FlipperStorageException  # noqa: E402  (open_storage set the path)
    was_on = False
    try:
        was_on = voice_off(storage)
        t0 = time.time()
        removed = absent = emptied = 0
        folders = set()
        for i, word in enumerate(sorted(synced), 1):
            init = initial(word)
            folders.add(init)
            try:
                storage.remove(f"/ext/sr/voice/{init}/{word}.raw")
                removed += 1
            except FlipperStorageException:
                absent += 1
            if i % 500 == 0:
                log(f"remove-legacy: {i} of {len(synced)}, {time.time() - t0:.0f} s")
        for init in sorted(folders):
            if len(init) != 1:
                continue
            try:
                storage.remove(f"/ext/sr/voice/{init}")
                emptied += 1
            except FlipperStorageException:
                pass
        save_manifest({}, synced_path)
        log(f"remove-legacy: {removed} clips removed, {absent} not found, {emptied} of {len(folders)} folders removed, "
            f"synced.json cleared, {time.time() - t0:.0f} s")
    finally:
        if was_on:
            try:
                voice_on(storage)
            except Exception as e:
                log(f"failed to restore voice: {e}")
        storage.stop()


def check(settings, names, workdir):
    words = ["settings", "sub", "gigahertz", "one", "ay", "b", "7", "okay", "home", "percent"]
    bad = 0
    for word in words:
        path = os.path.join(workdir, initial(word), word + ".raw")
        w, ok, msg = make_clip((word, spoken_text(word, names), settings, path))
        data = open(path, "rb").read() if ok else b""
        seconds = len(data) / settings["hz"]
        edge = int(settings["hz"] * 0.015)
        edges = data[:edge] + data[-edge:]
        quiet = all(abs(v - 128) <= 2 for v in edges)
        loud = max(abs(v - 128) for v in data) >= 100 if data else False
        good = ok and 0.05 <= seconds <= 3.0 and quiet and loud
        bad += 0 if good else 1
        log(f"check {word}: {'ok' if good else 'BAD'} {seconds:.2f} s, quiet edges {quiet}, peak ok {loud} {msg}")
    return bad == 0


def save_manifest(manifest, manifest_path):
    """Write the manifest atomically, so a crash or interruption mid-write can never leave a
    truncated/corrupt manifest.json behind."""
    tmp = manifest_path + ".tmp"
    json.dump(manifest, open(tmp, "w"), indent=0, sort_keys=True)
    os.replace(tmp, manifest_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "voice"), help="local vocabulary directory")
    ap.add_argument("--words", action="append", default=[], help="extra word list file (repeatable)")
    ap.add_argument("--extract", action="store_true", help="add the firmware's strings through the pronunciation layer")
    ap.add_argument("--extract-all", action="store_true", help="with --extract: also add every app under applications/external, not just the ones on the card")
    ap.add_argument("--card-apps", action="store_true", help="with --extract: also add the apps actually installed on the card (needs the device, read-only)")
    ap.add_argument("--pull-missing", action="store_true", help="add and clear the device's /ext/sr/missing.txt")
    ap.add_argument("--sync", action="store_true", help="upload new or changed clips to the card")
    ap.add_argument("--sync-all", action="store_true", help="with --sync: ignore voice/synced.json and resend everything (for a wiped card)")
    ap.add_argument("--remove-legacy", action="store_true", help="remove the first layout's /ext/sr/voice/<initial>/ clips from the card and clear voice/synced.json")
    ap.add_argument("--check", action="store_true", help="make ten clips into a temporary directory and verify them")
    ap.add_argument("--dry", action="store_true", help="build the word list and print the counts, without making clips, pulling missing.txt, or syncing")
    ap.add_argument("--port", default="/dev/cu.usbmodemflip_R0skie1")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="stop after this many new clips (for trials)")
    for key, value in DEFAULTS.items():
        if key == "soft":
            ap.add_argument("--soft", dest="soft", action="store_true", default=True)
            ap.add_argument("--no-soft", dest="soft", action="store_false")
        else:
            ap.add_argument("--" + key, type=type(value), default=value)
    a = ap.parse_args()
    settings = {k: getattr(a, k) for k in DEFAULTS}
    if settings["backend"] == "piper" and not settings["model"]:
        sys.exit("--backend piper needs --model <voice.onnx>")
    names = load_names()
    workdir = os.path.join(a.out, ".build")
    os.makedirs(workdir, exist_ok=True)

    if a.check:
        with tempfile.TemporaryDirectory() as d:
            sys.exit(0 if check(settings, names, d) else 1)
    if a.remove_legacy:
        remove_legacy(a.port, a.out)
        if not (a.extract or a.pull_missing or a.sync or a.words):
            return 0

    words = load_list(os.path.join(HERE, "voice_words.txt"))
    for path in a.words:
        words |= load_list(path)
    if a.extract:
        extra = []
        if a.extract_all:
            ext_dirs = external_app_dirs()
            extra.append(("extract-all", ext_dirs))
        if a.card_apps:
            card_faps, card_matched, card_unmatched = card_apps(a.port)
            extra.append(("card-apps", sorted(set(card_matched))))
        extracted, originals, added = extract_words(workdir, extra)
        words |= extracted
        names = {**originals, **names}  # an entry in tools/voice_names.txt still wins
        if a.extract_all:
            log(f"extract-all: {len(ext_dirs)} apps under applications/external, "
                f"{added.get('extract-all', 0)} words added")
        if a.card_apps:
            skipped = ", ".join(card_unmatched) if card_unmatched else "(none)"
            log(f"card apps: {len(card_faps)} faps, {len(card_matched)} matched, "
                f"{added.get('card-apps', 0)} words added; unmatched: {skipped}")
    elif a.extract_all or a.card_apps:
        log("--extract-all and --card-apps only add to the word pipeline together with --extract; ignored")
    if a.pull_missing:
        if a.dry:
            log("dry run: missing.txt not pulled")
        else:
            words |= pull_missing(a.port)

    if a.dry:
        log(f"dry run: {len(words)} words total, no clips made")
        return 0

    manifest_path = os.path.join(a.out, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {"words": {}}
    jobs = []
    for word in sorted(words):
        text = spoken_text(word, names)
        h = settings_hash(settings, text)
        path = os.path.join(a.out, initial(word), word + ".raw")
        if manifest["words"].get(word) == h and os.path.exists(path):
            continue
        jobs.append((word, text, settings, path))
    if a.limit:
        jobs = jobs[: a.limit]
    log(f"{len(words)} words, {len(jobs)} to make with {settings_line(settings)}")
    t0 = time.time()
    made = failed = 0
    with multiprocessing.Pool(a.jobs) as pool:
        for i, (word, ok, msg) in enumerate(pool.imap_unordered(make_clip, jobs), 1):
            if ok:
                made += 1
                manifest["words"][word] = settings_hash(settings, spoken_text(word, names))
            else:
                failed += 1
                log(f"failed: {word}: {msg}")
            if i % 100 == 0:
                log(f"{i} of {len(jobs)} clips, {time.time() - t0:.0f} s")
                save_manifest(manifest, manifest_path)
    manifest["settings"] = settings
    save_manifest(manifest, manifest_path)
    with open(os.path.join(a.out, "voice.txt"), "w") as f:
        f.write(settings_line(settings) + "\n")
    log(f"made {made} clips, {failed} failed, {time.time() - t0:.0f} s; vocabulary {len(manifest['words'])} words in {a.out}")
    if a.sync:
        failed += sync(a.port, a.out, manifest, a.sync_all)
    if failed:
        log(f"{failed} clip(s) failed to build or sync")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
