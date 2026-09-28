#!/usr/bin/env python3
"""Build and sync the screen reader's recorded vocabularies, one voice set at a time.

    tools/voice_build.py [--set NAME] [--backend say|espeak|kokoro] [--voice V] [--rate N]
        [--highpass F] [--gain F] [--soft|--no-soft] [--extract] [--extract-all] [--card-apps]
        [--pull-missing] [--sync] [--migrate-sets] [--mark-synced] [--check] [--dry] [options]

A voice set is a vocabulary made with one engine and one voice. The card holds one folder per
set, /ext/sr/voices/<set>/, with the set's clips, its voice.txt and its own missing.txt; the
reader uses the set chosen in the Accessibility settings or with `sr voice use`, else the first
one it finds. On the Mac the set named samantha is the voice/ directory, where the vocabulary
lived before there were sets, and every other set is voices/<set>/. A set name is 1 to 31 lower
case letters, digits, hyphens and underscores, and auto is reserved. --set names the set a run
works on, samantha by default.

Words come from tools/voice_words.txt and, when it exists, tools/voice_words.local.txt (personal
words such as a device name, not in git), from every string literal in the firmware's core apps
and services and the dolphin's speech bubble texts, run through the real pronunciation layer
(--extract), and from the set's missing.txt on the card (--pull-missing). A clip's name is the
word in lower case without apostrophes ("don't" is dont, spoken as "don't"); a clip listed in
tools/voice_names.txt is spoken as written there, which names the single letters that spell a
word the device has no clip for. Clips land in the set's directory as <initial>/<word>.raw next
to its manifest.json, which remembers the set's name, its settings and the settings each clip
was made with, so a rerun makes only what is missing or changed, and its voice.txt, the settings
line the device shows. --sync uploads new or changed clips to /ext/sr/voices/<set>/<hh>/<word>.raw
on the card, hh being the word's FNV-1a hash modulo 64 as two hex digits, the same folder the
firmware's speech_voice_path computes, and then the set's voice.txt. --pull-missing keeps the
words it pulls in the set's pulled.txt, which every run adds to its words, and leaves the card's
list alone; a sync with nothing failed, made or sent, then removes those words from the card's
list, and the file. --migrate-sets moves the card's first layout, /ext/sr/voice and
/ext/sr/missing.txt, into /ext/sr/voices/samantha, and refuses when the new place is taken;
until then --sync and --pull-missing refuse such a card, since a set folder they started there
would stand in the migration's way. --mark-synced writes the set's synced.json from its manifest
instead of the card, every word's current hash, for a set that reached the card by some other
means than --sync, such as a copy through a card reader (voice_pack.py's tar, unpacked onto the
card with tar -xf); without it the next --sync would not know the set is already there and would
resend everything.

Clip format: raw unsigned 8-bit mono PCM, 16000 Hz, 128 silence, trimmed to 15 ms of silence
at each end, after a high-pass at 500 Hz, a gain of 1.3 and a soft limiter, chosen by ear for
the piezo. The backends, with their default voice and rate:

    kokoro: Kokoro (Apache 2.0), an open neural model, the voice for a release; af_heart, rate
        100 (percent of the model's pace; a voice whose name starts with b speaks British
        English). It runs with the kokoro-onnx package from voice-models/kokoro-v1.0.onnx and
        voices-v1.0.bin, the kokoro-onnx project's model-files-v1.0 release.
    espeak: eSpeak-NG (GPL-3), a small and quick formant synthesizer from the system's package
        manager; en-us+f3, rate 160 (words per minute).
    say: the macOS voices, for personal use only, since Apple's voices may not be redistributed;
        Samantha, rate 175, the settings chosen by ear on 2026-09-24.

--voice, --rate, --highpass, --gain and --soft or --no-soft change the defaults for a run. A
set's manifest records its backend, voice and processing settings and, for kokoro, the SHA-256
of the model and voices files (their paths do not count); a change to any of them makes every
clip of the set again, so a set never mixes settings. Kokoro renders a word the same way every
run with the same --jobs, which sets each worker's share of the cores; another --jobs may move a
sample of a few clips by one step. eSpeak-NG does too, except that its breathy variants such as
+f3 seed their breath noise from the clock. A run that names another backend or voice than the
set was made with is refused, since it would make the whole set again with them.

The routine, per set, with the device connected:

    .venv/bin/python tools/voice_build.py --set samantha --extract --card-apps --pull-missing --sync
    .venv/bin/python tools/voice_build.py --set heart --backend kokoro --extract --card-apps --pull-missing --sync
    .venv/bin/python tools/voice_build.py --set espeak --backend espeak --extract --card-apps --pull-missing --sync

The Python packages are in requirements.txt: pyserial for the firmware's
scripts/flipper/storage.py, which --sync, --pull-missing, --card-apps and --migrate-sets import,
numpy and scipy for the espeak and kokoro backends, kokoro-onnx for kokoro. Run the generator
with the project virtualenv's Python (.venv/bin/python), not the system python3. It needs Python
3.10 or newer, since storage.py does, and says so when it starts on an older one.

--extract-all folds in every app under applications/external (hundreds of them); --card-apps
folds in only the ones actually installed on the card, which is the routine choice, and needs
the device but only to list it, never to write to it. Both need --extract to have an effect.
--check makes ten clips into a temporary directory and verifies them, with the set's own backend
and voice from its manifest unless the command line names them.
--dry builds the word list and prints its counts without making clips, pulling missing.txt,
migrating, marking synced or syncing.
"""
import argparse, glob, hashlib, importlib.util, json, math, multiprocessing, os, re, shutil, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from clip_make import finish, highpass, pad, read_wav, to_u8, trim  # noqa: E402

FW = os.path.join(ROOT, "Momentum-Firmware")
SRC = os.path.join(FW, "applications", "services", "screen_reader")
WORD_RE = re.compile(r"^(?:[a-z]{1,16}|[0-9])$")
STRING_RE = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
PRINTF_RE = re.compile(r"%[-+ 0#]*\d*(?:\.\d+)?(?:hh|h|ll|l|L|q|j|z|t)?[diouxXeEfgGcsp%]")
DIGIT_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
FAM_APPID_RE = re.compile(r'appid\s*=\s*"([^"]+)"')
FAM_FILENAME_RE = re.compile(r'fap_file_name\s*=\s*"([^"]+)"')
APP_MANIFEST_DIRS = ("external", "main", "system", "settings", "debug")

HZ = 16000
SETS_DIR = "/ext/sr/voices"
# The voice's guard around a transfer: a mute of GUARD_S seconds, renewed every GUARD_RENEW_S as
# the transfer goes, so a tool that dies leaves the reader muted for a minute at most
GUARD_S = 60
GUARD_RENEW_S = 15
# A read that gets no byte for READ_STALL_S raises TimeoutError instead of waiting forever: the
# device answers every command of a transfer within a second or two. The restore at the end of a
# transfer waits RESTORE_STALL_S, since the voice comes back by itself anyway
READ_STALL_S = 30
RESTORE_STALL_S = 5
BACKENDS = {
    "say": dict(voice="Samantha", rate=175, highpass=500.0, gain=1.3, soft=True),
    "espeak": dict(voice="en-us+f3", rate=160, highpass=500.0, gain=1.3, soft=True),
    "kokoro": dict(voice="af_heart", rate=100, highpass=500.0, gain=1.3, soft=True),
}
KOKORO_MODEL = os.path.join(ROOT, "voice-models", "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(ROOT, "voice-models", "voices-v1.0.bin")
# Settings that are recorded but not part of a clip's key: the model files' paths (their checksum is)
UNKEYED = ("model", "voices_file")
# The card's first layout, one vocabulary and its missing list, which --migrate-sets moves
LEGACY_VOICE_DIR = "/ext/sr/voice"
LEGACY_MISSING = "/ext/sr/missing.txt"


def log(msg):
    print(msg, flush=True)


# The firmware's scripts/flipper/storage.py, which the steps on the device import, needs Python
# 3.10 (an annotation str | bytes, evaluated when the module loads); the continuous build runs
# the tools' tests on 3.10
PYTHON_MIN = (3, 10)


def python_too_old(version=None):
    """One sentence for a Python older than PYTHON_MIN, None for one new enough."""
    version = tuple((version or sys.version_info)[:2])
    if version >= PYTHON_MIN:
        return None
    return (f"the voice generator needs Python {PYTHON_MIN[0]}.{PYTHON_MIN[1]} or newer, and this is "
            f"Python {version[0]}.{version[1]}: make the project's .venv with a newer python3, as the "
            "README's Building from source describes")


def set_valid(name):
    """A set name the generator makes: 1 to 31 characters of lower case letters, digits, hyphen
    and underscore; "auto" is reserved for the first set found. The engine, the console's
    sr voice use and the settings app's Voice row take these and any other name of a folder that
    is not hidden and has no slash."""
    return name != "auto" and re.fullmatch(r"[a-z0-9_-]{1,31}", name) is not None


def set_local_dir(name):
    """The Samantha set is the original voice/ directory; every other set lives in voices/."""
    return os.path.join(ROOT, "voice") if name == "samantha" else os.path.join(ROOT, "voices", name)


def set_card_dir(name):
    return f"{SETS_DIR}/{name}"


def settings_for(backend, overrides):
    """The processing settings of a set: the backend's defaults, the overrides given on the
    command line, the fixed clip rate, and for kokoro the checksum of the model and the voices
    file, so a new model regenerates every clip."""
    if backend not in BACKENDS:
        raise ValueError(f"unknown backend {backend!r}; one of {', '.join(sorted(BACKENDS))}")
    settings = dict(backend=backend, **BACKENDS[backend], hz=HZ)
    settings.update({k: v for k, v in overrides.items() if v is not None})
    if backend == "kokoro" and "model_sha256" not in settings:
        settings["model_sha256"] = file_sha256(settings.get("model", KOKORO_MODEL)) + file_sha256(settings.get("voices_file", KOKORO_VOICES))
    return settings


def file_sha256(path):
    h = hashlib.sha256()
    if not os.path.exists(path):
        return "missing"
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def settings_line(s):
    """The first line of a set's voice.txt: what `sr voice status` shows (63 characters)."""
    return f"{s['backend']} {s['voice']} rate {s['rate']} highpass {s['highpass']:g} gain {s['gain']:g} {'soft' if s['soft'] else 'hard'} {s['hz']}"


def resample(x, src_hz, hz):
    """Float samples at src_hz to hz, with scipy's polyphase filter: the same length in
    seconds, the same level."""
    if src_hz == hz:
        return x
    import numpy as np
    from scipy.signal import resample_poly
    g = math.gcd(int(src_hz), int(hz))
    return resample_poly(np.asarray(x, dtype="float32"), hz // g, src_hz // g).astype("float32")


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
    """What the engine speaks for a clip: its line in tools/voice_names.txt (the letters by
    their names, so that a spelled word is heard as "en eff see"), a digit's number word, or the
    word itself."""
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


def settings_hash(settings, text, unkeyed=UNKEYED):
    """A clip's key: its settings and its spoken text, hashed. The paths of kokoro's model files
    take no part, their checksum does, so the same files at another path remake nothing. The
    first generator hashed every key; rekey_legacy checks its manifests with unkeyed=()."""
    key = json.dumps([settings[k] for k in sorted(settings) if k not in unkeyed] + [text])
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def rekey_legacy(manifest, synced, settings, names):
    """Carry a manifest from before the sets over to today's settings, and the sync record with
    it. The first generator's settings held a model path, empty for say, and the settings hash
    covers every key, so without this every clip of the Samantha set would look changed and be
    made and sent again, the same clips. When the recorded settings are today's plus that empty
    path, each word whose hash verifies against them (hashed as the first generator did, every
    key in) takes today's hash, keyed with the text its clip was made with, in the manifest and,
    where it holds the same hash, in synced.json. The text tried first is the spoken text; then
    the word with an apostrophe at each inner position, since dont was made as don't, so the
    carry-over does not depend on this run's --extract and --card-apps. A word that does not
    verify (made with older settings, or spoken differently now) keeps its hash, so it is made
    and sent again as before. Returns the number of words carried over."""
    recorded = manifest.get("settings")
    if recorded != {**settings, "model": ""}:
        return 0
    count = 0
    for word, h in list(manifest["words"].items()):
        texts = [spoken_text(word, names)] + [word[:i] + "'" + word[i:] for i in range(1, len(word))]
        text = next((t for t in texts if settings_hash(recorded, t, unkeyed=()) == h), None)
        if text is None:
            continue
        manifest["words"][word] = settings_hash(settings, text)
        if synced.get(word) == h:
            synced[word] = manifest["words"][word]
        count += 1
    manifest["settings"] = settings
    return count


def set_conflict(recorded, settings):
    """Why a run may not work on a set, as a sentence, or None. A set stands for one backend and
    voice: a run that names others, most likely a forgotten --backend or --voice, would make
    every clip again with them, and --sync would send those over the set on the card. The
    processing settings may change; that makes the set again in the same voice."""
    if not recorded or (recorded.get("backend"), recorded.get("voice")) == (settings["backend"], settings["voice"]):
        return None
    return (f"the set was made with {recorded.get('backend')} {recorded.get('voice')}, not {settings['backend']} "
            f"{settings['voice']}: name them with --backend and --voice, or remove the set's folder to make it anew")


def check_engine(recorded, backend, voice):
    """The backend and voice --check speaks with: those named on the command line, else the
    set's own from its manifest, else say. The set's voice goes only with the set's backend;
    another backend brings its own default voice (None here, settings_for fills it in)."""
    if recorded and recorded.get("backend") in BACKENDS:
        if backend is None:
            backend = recorded["backend"]
        if voice is None and backend == recorded["backend"]:
            voice = recorded.get("voice")
    return backend or "say", voice


def synth_say(text, voice, rate, path):
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", path, "--file-format=WAVE",
                    "--data-format=LEI16@%d" % HZ, text], check=True)


def synth_espeak(text, voice, rate, path):
    subprocess.run(["espeak-ng", "-v", voice, "-s", str(rate), "-w", path, text], check=True, capture_output=True)


_kokoro = None


def kokoro_init(model, voices, threads):
    """Pool initializer: one model per worker process (the model is 325 MB; four workers fit),
    each on its share of the cores. onnxruntime's default, a thread per core in every worker,
    makes four workers barely faster than two: 0.29 s a word between them on a 20-core Mac,
    0.15 s with the share, the same clips."""
    global _kokoro
    t0 = time.time()
    try:
        import onnxruntime
        from kokoro_onnx import Kokoro
        options = onnxruntime.SessionOptions()
        options.intra_op_num_threads = threads
        _kokoro = Kokoro.from_session(onnxruntime.InferenceSession(model, options, providers=["CPUExecutionProvider"]), voices)
    except Exception as e:  # raised from here, the pool would start new workers forever
        _kokoro = e
        log(f"kokoro: worker {os.getpid()} could not load the model: {type(e).__name__}: {e}")
        return
    log(f"kokoro: worker {os.getpid()} loaded the model in {time.time() - t0:.1f} s, {threads} threads")


def synth_kokoro(text, voice, rate):
    """Float samples at the model's rate; the voice's first letter picks the accent (a: US, b: British)."""
    if isinstance(_kokoro, Exception):
        raise _kokoro  # the worker could not load the model: every word says why
    lang = "en-gb" if voice.startswith("b") else "en-us"
    samples, hz = _kokoro.create(text, voice=voice, speed=rate / 100.0, lang=lang)
    return samples, hz


def engine_problem(settings):
    """What the backend lacks on this machine, as a sentence, or None. Checked before any clip
    is made or anything is pulled from the card, so such a run stops at once with the reason
    instead of failing word after word."""
    backend = settings["backend"]
    if backend == "say" and not shutil.which("say"):
        return "say is the macOS speech command: on another system use --backend espeak or kokoro"
    if backend == "espeak" and not shutil.which("espeak-ng"):
        return "espeak-ng is not installed: it comes from the system's package manager"
    packages = {"say": [], "espeak": ["numpy", "scipy"], "kokoro": ["numpy", "scipy", "kokoro_onnx"]}[backend]
    missing = [p for p in packages if importlib.util.find_spec(p) is None]
    if missing:
        return (f"the {backend} backend needs the Python packages {', '.join(missing)}: install requirements.txt "
                "into the project's .venv and run the generator with .venv/bin/python")
    if backend == "kokoro":
        for path in (settings.get("model", KOKORO_MODEL), settings.get("voices_file", KOKORO_VOICES)):
            if not os.path.exists(path):
                return (f"{path} is not there: the Kokoro model files kokoro-v1.0.onnx and voices-v1.0.bin come from "
                        "https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0")
    return None


def make_clip(job):
    """One clip: the backend's speech at the clip rate, then the processing chosen by ear (the
    high-pass, the gain and the limiter, the trim to 15 ms of silence at each end), written as
    raw unsigned 8-bit samples. Runs in a pool worker; returns (word, ok, message)."""
    word, text, settings, out_path = job
    try:
        backend = settings["backend"]
        hz = settings["hz"]
        if backend == "kokoro":
            x, src_hz = synth_kokoro(text, settings["voice"], settings["rate"])
        else:
            synth = synth_say if backend == "say" else synth_espeak
            with tempfile.TemporaryDirectory() as d:
                wav = os.path.join(d, "clip.wav")
                synth(text, settings["voice"], settings["rate"], wav)
                x, src_hz = read_wav(wav)
        x = resample(x, src_hz, hz)  # say already speaks at the clip rate: unchanged
        if not isinstance(x, list):
            x = x.tolist()  # numpy's samples: the processing below works on lists of floats
        x = highpass(x, hz, settings["highpass"])
        x = finish(x, settings["gain"], settings["soft"])
        x = trim(x, hz)
        x = pad(x, hz)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(to_u8(x))
        return word, True, ""
    except Exception as e:  # one bad word must not stop the build
        return word, False, str(e)


def clip_pool(settings, jobs, count):
    """The worker pool that makes count clips: --jobs workers, fewer when there are fewer clips.
    For kokoro each worker loads the model once, in a spawned process (onnxruntime must not be
    forked), and runs on the share of the cores that --jobs gives it, whatever the pool's size,
    so a run of three words and a run of thousands render a word alike; say and espeak need
    nothing loaded."""
    size = min(jobs, count)
    if settings["backend"] == "kokoro":
        model = settings.get("model", KOKORO_MODEL)
        voices = settings.get("voices_file", KOKORO_VOICES)
        threads = max(1, (os.cpu_count() or 1) // jobs)
        return multiprocessing.get_context("spawn").Pool(size, initializer=kokoro_init, initargs=(model, voices, threads))
    return multiprocessing.Pool(size)


class StalledRead:
    """What scripts/flipper/storage.py's BufferedRead does, with a deadline: until() raises
    TimeoutError once the device has sent nothing for `stall` seconds, where BufferedRead reads
    forever (a device waiting for the data of a write_chunk that a Ctrl-C cut off never sends the
    prompt). The port's own timeout, 2 s, bounds each read."""

    def __init__(self, stream, stall):
        self.buffer = bytearray()
        self.stream = stream
        self.stall = stall

    def until(self, eol="\n", cut_eol=True):
        eol = eol.encode("ascii")
        last = time.monotonic()
        while True:
            i = self.buffer.find(eol)
            if i >= 0:
                read = self.buffer[:i] if cut_eol else self.buffer[: i + len(eol)]
                self.buffer = self.buffer[i + len(eol):]
                return read
            data = self.stream.read(max(1, self.stream.in_waiting))
            if data:
                self.buffer.extend(data)
                last = time.monotonic()
            elif time.monotonic() - last >= self.stall:
                raise TimeoutError(f"the device sent nothing for {self.stall:g} s")


def open_storage(port, stall=None):
    """A console session through the firmware's storage protocol, whose reads give up after
    READ_STALL_S seconds without a byte (or `stall`)."""
    sys.path.insert(0, os.path.join(FW, "scripts"))
    from flipper.storage import FlipperStorage, FlipperStorageOperations  # noqa: E402
    storage = FlipperStorage(port)
    storage.read = StalledRead(storage.port, READ_STALL_S if stall is None else stall)
    storage.start()
    return storage, FlipperStorageOperations(storage)


class CardWriteError(Exception):
    """The card answered a file's data with an error, a full card for one."""


class SyncStopped(Exception):
    """A sync that cannot go on: its connection failed, or the card refused a file's data, which
    every file after it would meet as well. The sync has said where, in one line."""


def send_to_card(storage, local_path, card_path):
    """storage.send_file without its progress line, which a screen reader would read once per
    clip, ten thousand times in a full sync, and with the device's answer to the data read too:
    write_chunk stops reading at a write that fails, so an error there, a full card for one,
    raises CardWriteError instead of the file counting as sent (and the rest of the chunk has
    reached the console as input, so the session must end). An error before the data, a file the
    card cannot open, raises the storage protocol's own exception."""
    from flipper.storage import FlipperStorageException  # noqa: E402  (open_storage put it on the path)
    if storage.exist_file(card_path):
        storage.remove(card_path)
    with open(local_path, "rb") as f:
        while True:
            data = f.read(storage.chunk_size)
            if not data:
                return
            storage.send_and_wait_eol(f'storage write_chunk "{card_path}" {len(data)}\r')
            answer = storage.read.until(storage.CLI_EOL)
            if storage.has_error(answer):
                error = storage.get_error(answer)
                storage.read.until(storage.CLI_PROMPT)
                raise FlipperStorageException.from_error_code(card_path, error)
            storage.port.write(data)
            answer = storage.read.until(storage.CLI_PROMPT)
            if storage.has_error(answer):
                said = bytes(answer).decode("ascii", "replace").strip()
                raise CardWriteError(f"{card_path}: {said}")


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
    playback would otherwise block and stall the speaker mid-buffer. The mute is timed, GUARD_S
    seconds, and the transfer renews it (voice_guard), so when this tool dies the voice comes back
    by itself. Returns whether it was on before, so the caller can decide whether to turn it back
    on."""
    was_on = voice_was_on(storage)
    voice_guard(storage)
    log(f"voice: silenced for the transfer; should the transfer die, it comes back by itself within {GUARD_S} s")
    return was_on


def voice_guard(storage):
    """The timed mute, set or renewed. A voice already off without an end stays so, and a
    firmware from before the timed mute takes it as a plain off, until sr voice on."""
    storage.send_and_wait_prompt(f"sr voice off {GUARD_S}\r")


def voice_on(storage):
    storage.send_and_wait_prompt("sr voice on\r")
    log("voice: restored")


def end_transfer(storage, port, was_on, clean):
    """Close a transfer's console session, switching the voice back on first if it was on
    before. After a failure the session may be in the middle of a command -- a Ctrl-C between a
    write_chunk and its data leaves the device waiting for file bytes, and it would take the next
    command as data -- so the voice is then restored through a fresh session; closing the old one
    ends the stuck command on the device. Never raises, not even for a second Ctrl-C: when the
    voice cannot be restored, it says so, and the timed mute lifts itself."""
    try:
        if not clean:
            storage.stop()
        if was_on:
            if clean:
                storage.read.stall = RESTORE_STALL_S
            else:
                storage, _ = open_storage(port, RESTORE_STALL_S)
            voice_on(storage)
    except BaseException as e:
        log(f"voice: not restored ({type(e).__name__}: {e}); it comes back by itself within {GUARD_S} s, or with sr voice on")
    finally:
        try:
            storage.stop()
        except BaseException:
            pass


def write_list(path, words):
    """One word per line, sorted, as load_list reads them; atomically, as save_manifest writes."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write("".join(f"{w}\n" for w in sorted(words)))
    os.replace(tmp, path)


def pull_missing(port, set_name):
    """The words the device found no clip for in the set: its missing.txt on the card, read and
    left there; main() keeps them in the set's pulled.txt, and a sync that sends every clip takes
    them off the card's list (clear_pulled). Refused, before anything else, on a card that still
    has the first layout."""
    path = set_card_dir(set_name) + "/missing.txt"
    storage, _ = open_storage(port)
    words = set()
    was_on = False
    clean = True
    try:
        refusal = legacy_refusal(storage.exist)
        if refusal:
            sys.exit(refusal)
        was_on = voice_off(storage)
        if storage.exist_file(path):
            with tempfile.TemporaryDirectory() as d:
                local = os.path.join(d, "missing.txt")
                storage.receive_file(path, local)
                words = load_list(local)
        log(f"pulled {len(words)} missing words from {path}, which stays on the card until they are synced")
    except BaseException:
        clean = False
        raise
    finally:
        end_transfer(storage, port, was_on, clean)
    return words


def clear_pulled(storage, card, pulled):
    """The card's missing.txt without the words pulled from it, now that their clips are on the
    card: removed when it holds no others, else written back with the ones the device noted since
    the pull. Runs in the sync's session, with the voice muted, so the device notes none
    meanwhile. Returns how many words stay on the list."""
    path = f"{card}/missing.txt"
    if not storage.exist_file(path):
        return 0
    with tempfile.TemporaryDirectory() as d:
        local = os.path.join(d, "missing.txt")
        storage.receive_file(path, local)
        left = load_list(local) - set(pulled)
        storage.remove(path)
        if left:
            write_list(local, left)
            send_to_card(storage, local, path)
    return len(left)


def card_lacks_synced(storage, card, synced, words):
    """True when clips that synced.json says are on the card are not: a wiped card, or another
    one, which would otherwise get nothing. The first, middle and last of those words still in
    the manifest are looked up, three round trips. A card with an older copy of the set, from
    another sync, is not told apart."""
    sent = sorted(w for w in synced if w in words)
    if not sent:
        return False
    return any(not storage.exist_file(f"{card}/{bucket(w)}/{w}.raw") for w in {sent[0], sent[len(sent) // 2], sent[-1]})


def sync(port, out_dir, manifest, set_name, force_all=False, pulled=None):
    """Send the set's voice.txt and the clip files the device actually uses (not .build, not
    manifest.json) to the set's folder on the card, /ext/sr/voices/<set>. The set's synced.json
    remembers the settings hash uploaded for each word, so a rerun only sends what's missing or
    changed instead of asking the device to md5 every file; when a few of the clips it names are
    not on the card, everything is sent, as --sync-all does (card_lacks_synced). A word whose
    local clip is missing or whose send fails is reported and left out of synced.json, so the
    next sync tries it again, and the other words still go. Returns the number of such words for
    main()'s exit code. With pulled, the words --pull-missing took from the card's missing.txt,
    and nothing missing or failed, those words then leave the card's list, and the set's
    pulled.txt goes. Refused, before anything is sent, on a card that still has the first
    layout."""
    card = set_card_dir(set_name)
    storage, ops = open_storage(port)
    import serial  # pyserial, which open_storage has loaded: its errors are the connection's
    was_on = False
    clean = True
    try:
        refusal = legacy_refusal(storage.exist)
        if refusal:
            sys.exit(refusal)
        was_on = voice_off(storage)
        renewed = time.monotonic()
        t0 = time.time()
        synced_path = os.path.join(out_dir, "synced.json")
        synced = {} if force_all else (json.load(open(synced_path)) if os.path.exists(synced_path) else {})
        words = manifest.get("words", {})
        if card_lacks_synced(storage, card, synced, words):
            log("sync: clips that synced.json lists are not on the card, a wiped card or another one, so everything is sent, as --sync-all does")
            synced = {}
        made_dirs = set()
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
            if time.monotonic() - renewed >= GUARD_RENEW_S:
                voice_guard(storage)
                renewed = time.monotonic()
            try:
                if folder not in made_dirs:
                    ops.mkpath(f"{card}/{folder}")
                    made_dirs.add(folder)
                send_to_card(storage, local_path, f"{card}/{folder}/{word}.raw")
            except CardWriteError as e:
                log(f"sync: stopped at word {i} of {len(words)}, {word}: the card did not take the data, is it full? {e}")
                raise SyncStopped(str(e)) from e
            except (serial.SerialException, TimeoutError, OSError) as e:
                # The connection, not the word: every word after it would fail the same way
                log(f"sync: stopped at word {i} of {len(words)}, {word}: the connection failed: {e}")
                raise SyncStopped(str(e)) from e
            except Exception as e:  # one bad word must not stop the sync
                log(f"sync: failed: {word}: {type(e).__name__}: {e}")
                failed += 1
                continue
            synced[word] = h
            sent += 1
            if i % 100 == 0:
                log(f"sync: {i} of {len(words)}, {sent} sent, {skipped} skipped, {time.time() - t0:.0f} s")
                save_manifest(synced, synced_path)
        # Saved before voice.txt goes, so a failure there cannot lose the record of what was sent;
        # the set's folder made first, which a card without a single clip of the set lacks
        save_manifest(synced, synced_path)
        ops.mkpath(card)
        send_to_card(storage, os.path.join(out_dir, "voice.txt"), f"{card}/voice.txt")
        log(f"sync: {sent} sent, {skipped} skipped, {missing} missing, {failed} failed, {time.time() - t0:.0f} s")
        if pulled and not (missing or failed):
            left = clear_pulled(storage, card, pulled)
            pulled_path = os.path.join(out_dir, "pulled.txt")
            if os.path.exists(pulled_path):
                os.remove(pulled_path)
            log(f"sync: the {len(pulled)} pulled words are off the card's missing list"
                + (f"; {left} noted since stay on it" if left else ""))
        return missing + failed
    except BaseException:
        clean = False
        raise
    finally:
        end_transfer(storage, port, was_on, clean)


def migration_plan(exists):
    """The moves of --migrate-sets, given exists(path) on the card: the first layout's clip
    folder and missing list, each that is there, into the samantha set, the set of the local
    voice/ directory whose clips they are. When a destination is there already the migration is
    refused with a sentence, and nothing moves. Returns (moves, refusal)."""
    dest = set_card_dir("samantha")
    moves = [(old, new) for old, new in ((LEGACY_VOICE_DIR, dest), (LEGACY_MISSING, dest + "/missing.txt")) if exists(old)]
    for old, new in moves:
        if exists(new):
            return [], f"{new} is on the card already, so {old} stays where it is and nothing was moved"
    return moves, None


def legacy_refusal(exists):
    """A sentence when the card still has the first layout, given exists(path) on the card, else
    None. A sync or a pull there would start /ext/sr/voices/samantha beside /ext/sr/voice, and
    --migrate-sets never moves the old folder onto an existing one: the migration comes first."""
    if exists(LEGACY_VOICE_DIR):
        return f"the card still has the first layout, {LEGACY_VOICE_DIR}: run --migrate-sets first"
    return None


def migrate_sets(port):
    """Move the card's first layout into the samantha set, once: /ext/sr/voice, its clip folders
    and voice.txt, to /ext/sr/voices/samantha, and /ext/sr/missing.txt into it. The storage's
    rename moves in place; nothing is copied or removed. Returns whether it succeeded."""
    storage, _ = open_storage(port)
    was_on = False
    clean = True
    try:
        was_on = voice_off(storage)
        moves, refusal = migration_plan(storage.exist)
        if refusal:
            log(f"migrate: {refusal}")
            return False
        if not storage.exist_dir(SETS_DIR):
            storage.mkdir(SETS_DIR)
            log(f"migrate: made {SETS_DIR}")
        for old, new in moves:
            reply = storage.send_and_wait_prompt(f'storage rename "{old}" "{new}"\r')
            if storage.has_error(reply):
                error = next((line.strip() for line in reply.decode("ascii", "replace").splitlines() if "Storage error:" in line), "")
                log(f"migrate: {old} was not moved: {error}")
                return False
            log(f"migrate: moved {old} to {new}")
        if not moves:
            log(f"migrate: nothing to move, the card has no {LEGACY_VOICE_DIR} or {LEGACY_MISSING}")
        return True
    except BaseException:
        clean = False
        raise
    finally:
        end_transfer(storage, port, was_on, clean)


def check(settings, names, workdir, jobs):
    """Make ten clips with the given settings through the same pool as a build, and verify each:
    between 0.05 and 3 s long, quiet at the edges, a peak near full scale."""
    words = ["settings", "sub", "gigahertz", "one", "ay", "b", "7", "okay", "home", "percent"]
    todo = [(word, spoken_text(word, names), settings, os.path.join(workdir, initial(word), word + ".raw")) for word in words]
    log(f"check: {len(todo)} clips with {settings_line(settings)}")
    t0 = time.time()
    with clip_pool(settings, jobs, len(todo)) as pool:
        results = pool.map(make_clip, todo)
    bad = 0
    for (word, _, _, path), (_, ok, msg) in zip(todo, results):
        data = open(path, "rb").read() if ok else b""
        seconds = len(data) / settings["hz"]
        edge = int(settings["hz"] * 0.015)
        edges = data[:edge] + data[-edge:]
        quiet = all(abs(v - 128) <= 2 for v in edges)
        loud = max(abs(v - 128) for v in data) >= 100 if data else False
        good = ok and 0.05 <= seconds <= 3.0 and quiet and loud
        bad += 0 if good else 1
        log(f"check {word}: {'ok' if good else 'BAD'} {seconds:.2f} s, quiet edges {quiet}, peak ok {loud} {msg}")
    log(f"check: {len(todo) - bad} of {len(todo)} good, {time.time() - t0:.1f} s")
    return bad == 0


def mark_synced(manifest):
    """The synced.json for a set that reached the card by some other means than --sync, such as a
    copy through a card reader (voice_pack.py's tar, unpacked with tar -xf onto the card): every
    word's current hash, taken from the manifest, with nothing to verify it against since the
    words were never actually sent by this tool. Without this the next --sync would see an empty
    or stale synced.json and resend the whole set."""
    return dict(manifest.get("words", {}))


def save_manifest(manifest, manifest_path):
    """Write the manifest atomically, so a crash or interruption mid-write can never leave a
    truncated/corrupt manifest.json behind."""
    tmp = manifest_path + ".tmp"
    json.dump(manifest, open(tmp, "w"), indent=0, sort_keys=True)
    os.replace(tmp, manifest_path)


def main():
    too_old = python_too_old()
    if too_old:
        sys.exit(too_old)
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default="samantha", help="the voice set to work on (default samantha, the voice/ directory)")
    ap.add_argument("--backend", choices=sorted(BACKENDS), help="the speech engine (default say; --check takes the set's own)")
    ap.add_argument("--voice", help="the engine's voice (defaults: say Samantha, espeak en-us+f3, kokoro af_heart)")
    ap.add_argument("--rate", type=int, help="words per minute for say and espeak, percent of the model's pace for kokoro")
    ap.add_argument("--highpass", type=float, help="high-pass cutoff in Hz (default 500)")
    ap.add_argument("--gain", type=float, help="gain after peak normalising to 0.95 (default 1.3)")
    ap.add_argument("--soft", action=argparse.BooleanOptionalAction, help="the tanh limiter (default on)")
    ap.add_argument("--model", help="kokoro: the model file (default voice-models/kokoro-v1.0.onnx)")
    ap.add_argument("--voices-file", help="kokoro: the voices file (default voice-models/voices-v1.0.bin)")
    ap.add_argument("--words", action="append", default=[], help="extra word list file (repeatable)")
    ap.add_argument("--extract", action="store_true", help="add the firmware's strings through the pronunciation layer")
    ap.add_argument("--extract-all", action="store_true", help="with --extract: also add every app under applications/external, not just the ones on the card")
    ap.add_argument("--card-apps", action="store_true", help="with --extract: also add the apps actually installed on the card (needs the device, read-only)")
    ap.add_argument("--pull-missing", action="store_true", help="add the words of the set's missing.txt on the card, kept in its pulled.txt until a sync with nothing failed takes them off the card's list")
    ap.add_argument("--sync", action="store_true", help="upload new or changed clips to the set's folder on the card")
    ap.add_argument("--sync-all", action="store_true", help="with --sync: ignore the set's synced.json and resend everything (for a wiped card)")
    ap.add_argument("--migrate-sets", action="store_true", help="move the card's /ext/sr/voice and /ext/sr/missing.txt into /ext/sr/voices/samantha, once")
    ap.add_argument("--mark-synced", action="store_true", help="write the set's synced.json from its manifest (every word's current hash), for a set that reached the card by some other means than --sync, such as a card reader")
    ap.add_argument("--check", action="store_true", help="make ten clips into a temporary directory and verify them, with the set's own backend and voice unless named")
    ap.add_argument("--dry", action="store_true", help="build the word list and print the counts, without making clips, pulling missing.txt, migrating or syncing")
    ap.add_argument("--port", default=(sorted(glob.glob("/dev/cu.usbmodemflip_*")) + [None])[0],
                    help="serial port, default: the first /dev/cu.usbmodemflip_* (the device's name is part of it)")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help="stop after this many new clips (for trials)")
    a = ap.parse_args()
    if not set_valid(a.set):
        sys.exit(f"{a.set!r} is not a set name: 1 to 31 lower case letters, digits, hyphens and underscores, and not auto")
    out_dir = set_local_dir(a.set)
    workdir = os.path.join(out_dir, ".build")
    manifest_path = os.path.join(out_dir, "manifest.json")
    manifest = json.load(open(manifest_path)) if os.path.exists(manifest_path) else {"words": {}}
    if a.check:
        backend, voice = check_engine(manifest.get("settings"), a.backend, a.voice)
    else:
        backend, voice = a.backend or "say", a.voice
    if backend != "kokoro" and (a.model or a.voices_file):
        sys.exit("--model and --voices-file are for --backend kokoro")
    settings = settings_for(backend, dict(voice=voice, rate=a.rate, highpass=a.highpass, gain=a.gain, soft=a.soft,
                                          model=a.model, voices_file=a.voices_file))
    names = load_names()
    migrate_only = a.migrate_sets and not (a.extract or a.pull_missing or a.sync or a.words)
    mark_synced_only = a.mark_synced and not (a.extract or a.pull_missing or a.sync or a.words)
    building = not (a.check or a.dry or migrate_only or mark_synced_only)
    # Refused before anything is pulled from the card or made: an engine this machine lacks, or
    # a run naming another backend or voice than the set was made with
    if a.check or building:
        problem = engine_problem(settings)
        if problem:
            sys.exit(problem)
    if building:
        conflict = set_conflict(manifest.get("settings"), settings)
        if conflict:
            sys.exit(f"{a.set}: {conflict}")

    if a.check:
        with tempfile.TemporaryDirectory() as d:
            sys.exit(0 if check(settings, names, d, a.jobs) else 1)
    if a.migrate_sets:
        if a.dry:
            log("dry run: the card's layout not migrated")
        elif not migrate_sets(a.port):
            return 1
        if migrate_only:
            return 0
    if a.mark_synced:
        if a.dry:
            log("dry run: synced.json not written")
        else:
            synced_path = os.path.join(out_dir, "synced.json")
            synced = mark_synced(manifest)
            save_manifest(synced, synced_path)
            log(f"mark-synced: {len(synced)} words written to {synced_path}")
        if mark_synced_only:
            return 0

    words = load_list(os.path.join(HERE, "voice_words.txt"))
    words |= load_list(os.path.join(HERE, "voice_words.local.txt"))
    for path in a.words:
        words |= load_list(path)
    if a.extract:
        os.makedirs(workdir, exist_ok=True)
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
    # Words pulled before and not yet synced, from a run that failed or stopped: kept in the set's
    # pulled.txt, since the card keeps its list until they are synced
    pulled_path = os.path.join(out_dir, "pulled.txt")
    pulled = load_list(pulled_path)
    if a.pull_missing:
        if a.dry:
            log("dry run: missing.txt not pulled")
        else:
            pulled |= pull_missing(a.port, a.set)
            os.makedirs(out_dir, exist_ok=True)
            write_list(pulled_path, pulled)
    words |= pulled

    if a.dry:
        log(f"dry run: {len(words)} words total, no clips made")
        return 0

    os.makedirs(out_dir, exist_ok=True)
    synced_path = os.path.join(out_dir, "synced.json")
    synced = json.load(open(synced_path)) if os.path.exists(synced_path) else {}
    carried = rekey_legacy(manifest, synced, settings, names)
    if carried:
        # The sync record first: interrupted before the manifest, a rerun carries it over again
        if os.path.exists(synced_path):
            save_manifest(synced, synced_path)
        save_manifest(manifest, manifest_path)
        log(f"manifest: {carried} clips carried over from the settings before the sets, not made or sent again")
    jobs = []
    for word in sorted(words):
        text = spoken_text(word, names)
        h = settings_hash(settings, text)
        path = os.path.join(out_dir, initial(word), word + ".raw")
        if manifest["words"].get(word) == h and os.path.exists(path):
            continue
        jobs.append((word, text, settings, path))
    if a.limit:
        jobs = jobs[: a.limit]
    log(f"set {a.set}: {len(words)} words, {len(jobs)} to make with {settings_line(settings)}")
    t0 = time.time()
    made = failed = 0
    if jobs:
        with clip_pool(settings, a.jobs, len(jobs)) as pool:
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
    manifest["set"] = a.set
    manifest["settings"] = settings
    save_manifest(manifest, manifest_path)
    with open(os.path.join(out_dir, "voice.txt"), "w") as f:
        f.write(settings_line(settings) + "\n")
    log(f"made {made} clips, {failed} failed, {time.time() - t0:.0f} s; vocabulary {len(manifest['words'])} words in {out_dir}")
    if a.sync:
        # The pulled words leave the card's list only when every clip was made
        failed += sync(a.port, out_dir, manifest, a.set, a.sync_all, pulled if not failed else None)
    if failed:
        log(f"{failed} clip(s) failed to build or sync")
    return 1 if failed else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("stopped")
        sys.exit(130)
    except SyncStopped:
        sys.exit(1)  # the sync has said where and why, in one line
    except (OSError, TimeoutError) as e:
        # The device's connection, or a file: one line, not a traceback for a screen reader
        log(f"stopped: {type(e).__name__}: {e}")
        sys.exit(1)
