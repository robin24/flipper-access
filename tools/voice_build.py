#!/usr/bin/env python3
"""Build and sync the screen reader's recorded vocabulary.

    tools/voice_build.py [--extract] [--pull-missing] [--sync] [--check] [options]

Words come from tools/voice_words.txt, from every string literal in the firmware's core apps and services run
through the real pronunciation layer (--extract), and from the device's /ext/sr/missing.txt
(--pull-missing). Clips land in voice/<initial>/<word>.raw next to voice/manifest.json, which
remembers the settings each clip was made with, so a rerun makes only what is missing or
changed. --sync uploads new or changed files to /ext/sr/voice on the card and removes the
pulled missing list. Defaults are the settings Robin chose by ear on 2026-09-24.

Clip format: raw unsigned 8-bit mono PCM, 16000 Hz, 128 silence, trimmed to 15 ms of silence
at each end. Backends: say (macOS, personal use: Apple's voices may not be redistributed) and
piper (any platform, a freely licensed model, the right choice for a release).

--sync and --pull-missing import the firmware's scripts/flipper/storage.py, which needs
pyserial: run those with the project virtualenv's Python (.venv/bin/python), not the system
python3.
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


def log(msg):
    print(msg, flush=True)


def clip_name(word):
    word = word.strip().lower()
    return word if WORD_RE.match(word) else None


def initial(word):
    c = word[0]
    return c if c.isalnum() else "_"


def load_list(path):
    words = set()
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="replace"):
            n = clip_name(line.split("#", 1)[0])
            if n:
                words.add(n)
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
    if word in names:
        return names[word]
    if len(word) == 1 and word.isdigit():
        return DIGIT_WORDS[int(word)]
    if len(word) == 1:
        return word.upper()
    return word


def build_expander(workdir):
    exe = os.path.join(workdir, "speech_expand")
    src = os.path.join(ROOT, "tests", "host", "speech_expand.c")
    layer = os.path.join(SRC, "speech_text.c")
    newest = max(os.path.getmtime(p) for p in (src, layer, os.path.join(SRC, "speech_text.h")))
    if not os.path.exists(exe) or os.path.getmtime(exe) < newest:
        subprocess.run(["clang", "-std=c11", "-O1", "-I", SRC, "-o", exe, src, layer], check=True)
    return exe


def firmware_strings():
    """Every string literal in the firmware's C sources, unescaped, printf fields removed."""
    seen = set()
    # The core apps and services only: applications/external holds hundreds of community apps
    # whose strings would multiply the vocabulary and the upload time for nothing
    roots = [os.path.join(FW, "applications", d) for d in ("main", "services", "settings", "system")]
    roots.append(os.path.join(FW, "lib", "toolbox"))
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
    return sorted(seen)


def extract_words(workdir):
    exe = build_expander(workdir)
    strings = firmware_strings()
    log(f"extract: {len(strings)} distinct strings from the firmware sources")
    out = subprocess.run([exe], input="\n".join(strings) + "\n", capture_output=True, text=True, check=True).stdout
    words = set()
    for line in out.splitlines():
        for token in line.split():
            n = clip_name(token.strip(".,?!;:"))
            if n:
                words.add(n)
    longest = sorted(words, key=len, reverse=True)[:10]
    log(f"extract: {len(words)} words; longest: {' '.join(longest)}")
    return words


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
    was_on = voice_off(storage)
    words = set()
    try:
        if storage.exist_file("/ext/sr/missing.txt"):
            with tempfile.TemporaryDirectory() as d:
                local = os.path.join(d, "missing.txt")
                storage.receive_file("/ext/sr/missing.txt", local)
                words = load_list(local)
            storage.remove("/ext/sr/missing.txt")
        log(f"pulled {len(words)} missing words from the device")
    finally:
        if was_on:
            voice_on(storage)
        storage.stop()
    return words


def sync(port, out_dir):
    storage, ops = open_storage(port)
    was_on = voice_off(storage)
    try:
        t0 = time.time()
        ops.recursive_send("/ext/sr/voice", out_dir)
        log(f"sync: done in {time.time() - t0:.0f} s")
    finally:
        if was_on:
            voice_on(storage)
        storage.stop()


def check(settings, names, workdir):
    words = ["settings", "sub", "gigahertz", "one", "ay", "b", "7", "okay", "home", "percent"]
    bad = 0
    for word in words:
        path = os.path.join(workdir, initial(word), word + ".raw")
        w, ok, msg = make_clip((word, spoken_text(word, names), settings, path))
        data = open(path, "rb").read() if ok else b""
        seconds = len(data) / settings["hz"]
        pad = int(settings["hz"] * 0.015)
        edges = data[:pad] + data[-pad:]
        quiet = all(abs(v - 128) <= 2 for v in edges)
        loud = max(abs(v - 128) for v in data) >= 100 if data else False
        good = ok and 0.05 <= seconds <= 3.0 and quiet and loud
        bad += 0 if good else 1
        log(f"check {word}: {'ok' if good else 'BAD'} {seconds:.2f} s, quiet edges {quiet}, peak ok {loud} {msg}")
    return bad == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=os.path.join(ROOT, "voice"), help="local vocabulary directory")
    ap.add_argument("--words", action="append", default=[], help="extra word list file (repeatable)")
    ap.add_argument("--extract", action="store_true", help="add the firmware's strings through the pronunciation layer")
    ap.add_argument("--pull-missing", action="store_true", help="add and clear the device's /ext/sr/missing.txt")
    ap.add_argument("--sync", action="store_true", help="upload new or changed clips to the card")
    ap.add_argument("--check", action="store_true", help="make ten clips into a temporary directory and verify them")
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

    words = load_list(os.path.join(HERE, "voice_words.txt"))
    for path in a.words:
        words |= load_list(path)
    if a.extract:
        words |= extract_words(workdir)
    if a.pull_missing:
        words |= pull_missing(a.port)

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
                json.dump(manifest, open(manifest_path, "w"), indent=0, sort_keys=True)
    manifest["settings"] = settings
    json.dump(manifest, open(manifest_path, "w"), indent=0, sort_keys=True)
    with open(os.path.join(a.out, "voice.txt"), "w") as f:
        f.write(settings_line(settings) + "\n")
    log(f"made {made} clips, {failed} failed, {time.time() - t0:.0f} s; vocabulary {len(manifest['words'])} words in {a.out}")
    if a.sync:
        sync(a.port, a.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
