#!/usr/bin/env python3
"""tools/voice_build.py's pure helpers: set names, the local and card folders of a set, the
per-backend settings and their line for voice.txt, the resampler's length and level. Also the
settings key, which leaves the model files' paths out; the re-keying of a manifest made before
the sets, with or without the extraction's names; the refusal of a run that names another backend
or voice than the set was made with; the backend and voice a check speaks with; the moves of
--migrate-sets and the refusal of a sync or a pull on a card that still has the first layout; and
the engine check before the pool starts; and the refusal of a Python older than 3.10, first thing.
Importable without pyserial, numpy or the engines (they are imported where they are used). Run
from the project root: python3 tests/fbt/test_voice_build.py"""
import collections
import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import voice_build as vb  # noqa: E402

failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


too_old = vb.python_too_old((3, 9, 6))
check(too_old is not None and "3.10 or newer" in too_old and "Python 3.9" in too_old and "\n" not in too_old,
      f"Python 3.9 is refused in one sentence: {too_old}")
check(vb.python_too_old((3, 10, 0)) is None and vb.python_too_old((3, 13, 1)) is None, "3.10 and newer are taken")
saved_min, saved_argv = vb.PYTHON_MIN, sys.argv
vb.PYTHON_MIN, sys.argv = (99, 0), ["voice_build.py", "--dry"]
try:
    vb.main()
    refused = None
except SystemExit as e:
    refused = str(e.code)
finally:
    vb.PYTHON_MIN, sys.argv = saved_min, saved_argv
check(refused is not None and "99.0 or newer" in refused, f"main() checks the version before anything else: {refused}")

# --jobs below one is refused in one sentence, before anything else is done
saved_argv = sys.argv
sys.argv = ["voice_build.py", "--jobs", "0", "--dry"]
try:
    vb.main()
    refused = None
except SystemExit as e:
    refused = str(e.code)
finally:
    sys.argv = saved_argv
check(refused is not None and "--jobs 0" in refused, f"--jobs 0 is refused: {refused}")

# A run that names no backend or voice takes the set's own, as the README's routine names only the
# set: --set espeak --sync on an espeak set goes on to make and send its clips, instead of counting
# as a say run and being refused. The run ends at stand-ins for the clip pool and the sync, which
# would start worker processes or open a port; the engine's presence is not the question here


class PastTheCheck(Exception):
    pass


def past_the_check(*args, **kwargs):
    raise PastTheCheck()


saved = (sys.argv, vb.set_local_dir, vb.engine_problem, vb.clip_pool, vb.sync)
with tempfile.TemporaryDirectory() as tmp:
    with open(os.path.join(tmp, "manifest.json"), "w") as f:
        json.dump({"words": {}, "settings": vb.settings_for("espeak", {})}, f)
    vb.set_local_dir = lambda name: tmp
    vb.engine_problem = lambda settings: None
    vb.clip_pool = vb.sync = past_the_check
    sys.argv = ["voice_build.py", "--set", "espeak", "--sync"]
    try:
        vb.main()
        stopped = "finished"
    except PastTheCheck:
        stopped = "past the check"
    except SystemExit as e:
        stopped = str(e.code)
    finally:
        sys.argv, vb.set_local_dir, vb.engine_problem, vb.clip_pool, vb.sync = saved
check(stopped == "past the check", f"--set espeak --sync takes the set's backend, not say: {stopped}")

# The order the clips go onto the card (clip_order): the most spoken first, as the list gives
# them, then the rest sorted. The device reads a folder's entries one by one, in the order the
# files were made, so a word made early is found sooner. A listed word the set lacks is left out
order = vb.clip_order({"zulu", "the", "of", "apple", "word"}, ["of", "the", "missing"])
check(order == ["of", "the", "apple", "word", "zulu"], f"the listed words first, then the rest sorted: {order}")
check(vb.clip_order({"b", "a"}, ()) == ["a", "b"], "without a list, sorted")
first = vb.spoken_first({"one", "a", "of"}, collections.Counter({"the": 9, "of": 12, "screen": 3, "word": 9}))
check(first == ["a", "of", "one", "the", "word", "screen"],
      f"the base list first, then the firmware's words by how often its texts use them, ties sorted: {first}")

# The expander's compiler: clang, else cc, else gcc; without any, one sentence
saved_which = vb.shutil.which
try:
    vb.shutil.which = lambda name: "/usr/bin/gcc" if name == "gcc" else None
    check(vb.c_compiler() == "gcc", "gcc when there is no clang or cc")
    vb.shutil.which = lambda name: f"/usr/bin/{name}"
    check(vb.c_compiler() == "clang", "clang first")
    vb.shutil.which = lambda name: None
    check(vb.c_compiler() is None, "none")
    import tempfile as _tempfile
    with _tempfile.TemporaryDirectory() as d:
        try:
            vb.build_expander(d)
            said = None
        except SystemExit as e:
            said = str(e.code)
    check(said is not None and "C compiler" in said, f"--extract without a compiler: one sentence: {said}")
finally:
    vb.shutil.which = saved_which

# A clip written with and without an apostrophe (T7): the device looks both up by the name
# without it, so the clip has one spoken form. The spelling written most often wins, a tie going
# to the apostrophe; a word the firmware's own texts hold is decided by those alone, so an app
# never changes how it sounds. The counts here are the real ones, with every app
words, spellings = vb.expansion_words("Don't stop, dont 'quote' we're I'll")
check(words == {"dont", "stop", "quote", "were", "ill"}
      and spellings == {("dont", "don't"): 1, ("dont", None): 1, ("stop", None): 1, ("quote", None): 1,
                        ("were", "we're"): 1, ("ill", "i'll"): 1},
      f"each token counted with its inner apostrophe, quotes around a word not one: {words}, {spellings}")
C = collections.Counter
own = C({("were", None): 2, ("ill", "i'll"): 2, ("dont", None): 2, ("dont", "don't"): 13, ("its", None): 2, ("its", "it's"): 2,
         ("youre", "you're"): 1})
apps = C({("were", None): 7, ("were", "we're"): 2, ("ill", None): 1, ("its", None): 25, ("its", "it's"): 11,
          ("id", None): 119, ("id", "i'd"): 1, ("cant", None): 5, ("cant", "can't"): 94, ("ab", "a'b"): 1, ("ab", "ab'"): 2})
forms, both = vb.spoken_forms(own, apps)
check("were" not in forms and "id" not in forms, f"were and id are said as written: {forms}")
check(forms.get("ill") == "i'll", f"the firmware's own I'll outweighs an app's ill: {forms}")
check(forms.get("dont") == "don't" and forms.get("cant") == "can't",
      f"a few texts without the apostrophe do not outweigh the many with it: {forms}")
check(forms.get("its") == "it's", f"a tie in the firmware's texts goes to the apostrophe, whatever the apps say: {forms}")
check(forms.get("youre") == "you're" and forms.get("ab") == "ab'", f"otherwise the apostrophe, the most frequent spelling: {forms}")
check(both == {"were": None, "ill": "i'll", "dont": "don't", "its": "it's", "id": None, "cant": "can't"},
      f"each word written both ways is reported with the form chosen: {both}")
check(vb.spoken_forms(own, C({("dont", None): 99}))[0] == vb.spoken_forms(own, C())[0],
      "an app never changes a word of the firmware's own")

# The apps' names and categories as the menus show them (T9): each App's own name, for the kinds
# a menu lists, and each fap_category; not a Lib's name inside an App, a plugin's or a service's,
# nor a commented-out App; a manifest Python cannot read is left out
with tempfile.TemporaryDirectory() as d:
    def manifest(folder, text):
        os.makedirs(os.path.join(d, folder))
        with open(os.path.join(d, folder, "application.fam"), "w") as f:
            f.write(text)
    manifest("core/space", """App(
    appid="space",
    name="Space Playground",
    apptype=FlipperAppType.EXTERNAL,
    fap_category="Games",
    fap_private_libs=[Lib(name="driver")],
)
# App(appid="off", name="Commented Out", apptype=FlipperAppType.EXTERNAL)
App(appid="parser", name="Parser Plugin", apptype=FlipperAppType.PLUGIN)
App(appid="bg", name="Background Service", apptype=FlipperAppType.SERVICE)
App(appid="main", name="Main Thing", apptype=FlipperAppType.MENUEXTERNAL, fap_category="Tools")
App(appid="notes", name="Notifications", apptype=FlipperAppType.SETTINGS)
""")
    manifest("core/broken", 'App(appid="x", name="Never Read"')
    manifest("apps/cooker", 'App(appid="cooker", name="Chief Cooker", apptype=FlipperAppType.EXTERNAL, fap_category="Games")\n')
    with open(os.path.join(d, "apps", "cooker", "cooker.c"), "w") as f:
        f.write('const char* hint = "Stir gently";\n')
    shown = vb.manifest_names([os.path.join(d, "core")])
    check(shown == {"Space Playground", "Games", "Main Thing", "Tools", "Notifications"},
          f"the names a menu shows and the categories, nothing else: {sorted(shown)}")

    # Folded into the extraction: the firmware's own apps always, an extra source's with its strings
    if vb.c_compiler() is None:
        print("skipped the extraction of app names: no C compiler")
    else:
        saved = vb.core_roots, vb.firmware_strings, vb.bubble_texts, vb.log
        vb.core_roots = lambda: [os.path.join(d, "core")]
        vb.firmware_strings = lambda: ["Hello"]
        vb.bubble_texts = lambda: []
        vb.log = lambda msg: None
        os.makedirs(os.path.join(d, "work"))
        try:
            words, _, added, frequency = vb.extract_words(
                os.path.join(d, "work"), [("card-apps", [os.path.join(d, "apps", "cooker")])])
        finally:
            vb.core_roots, vb.firmware_strings, vb.bubble_texts, vb.log = saved
        check({"hello", "space", "playground", "games", "notifications", "chief", "cooker", "stir"} <= words
              and not {"driver", "parser", "background", "never"} & words,
              f"the names come in with the strings, the others not: {sorted(words)}")
        check(added == {"card-apps": 4}, f"an extra source's names count as its own words, chief, cooker, stir, gently: {added}")
        check(frequency["hello"] == 1 and frequency["space"] == 1 and "stir" not in frequency,
              f"the firmware's own words count how often its texts use them, an extra source's not: {dict(frequency)}")

# A clip the engine makes silent is a failure, not 30 ms of silence played for the word (T10)
import wave  # noqa: E402

def fake_say(samples):
    def synth(text, voice, rate, wav_path):
        with wave.open(wav_path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"".join(int(v).to_bytes(2, "little", signed=True) for v in samples))
    return synth

saved_say = vb.synth_say
try:
    with _tempfile.TemporaryDirectory() as d:
        settings = vb.settings_for("say", {})
        out = os.path.join(d, "q", "quiet.raw")
        vb.synth_say = fake_say([0] * 1600)
        word, ok, msg = vb.make_clip(("quiet", "quiet", settings, out))
        check(not ok and "silence" in msg and not os.path.exists(out), f"a silent clip fails and is not written: {ok}, {msg}")
        vb.synth_say = fake_say([int(12000 * math.sin(i / 3)) for i in range(3200)])
        word, ok, msg = vb.make_clip(("tone", "tone", settings, out))
        check(ok and os.path.getsize(out) > 480, f"a clip with sound is written: {ok}, {msg}")
finally:
    vb.synth_say = saved_say

for name in ["samantha", "heart", "espeak", "en-us_f3", "a" * 31]:
    check(vb.set_valid(name), f"valid set name: {name}")
for name in ["", "Heart", "two words", "a/b", ".", "a" * 32, "héart", "auto"]:
    check(not vb.set_valid(name), f"invalid set name: {name!r}")
check(vb.set_local_dir("samantha") == os.path.join(ROOT, "voice"), "the Samantha set lives in voice/")
check(vb.set_local_dir("heart") == os.path.join(ROOT, "voices", "heart"), "other sets live in voices/<set>/")
check(vb.set_card_dir("heart") == "/ext/sr/voices/heart", "the card folder of a set")
check(sorted(vb.BACKENDS) == ["espeak", "kokoro", "say"], "three backends")
s = vb.settings_for("say", {})
check(s["voice"] == "Samantha" and s["rate"] == 175 and s["highpass"] == 500.0 and s["gain"] == 1.3 and s["soft"] is True and s["hz"] == 16000, f"say defaults: {s}")
check(vb.settings_line(s) == "say Samantha rate 175 highpass 500 gain 1.3 soft 16000", f"the say line: {vb.settings_line(s)}")
s = vb.settings_for("espeak", {"gain": 1.5})
check(s["voice"] == "en-us+f3" and s["rate"] == 160 and s["gain"] == 1.5, f"espeak defaults with an override: {s}")
check(vb.settings_line(s) == "espeak en-us+f3 rate 160 highpass 500 gain 1.5 soft 16000", f"the espeak line: {vb.settings_line(s)}")
s = vb.settings_for("kokoro", {"soft": False})
check(s["voice"] == "af_heart" and s["rate"] == 100 and s["soft"] is False, f"kokoro defaults with an override: {s}")
check(vb.settings_line(s) == "kokoro af_heart rate 100 highpass 500 gain 1.3 hard 16000", f"the kokoro line: {vb.settings_line(s)}")
check(len(vb.settings_line(s)) <= 63, "the line fits the device's status field")
try:
    vb.settings_for("piper", {})
    check(False, "an unknown backend is refused")
except (KeyError, ValueError, SystemExit):
    check(True, "an unknown backend is refused")
check(vb.settings_hash(vb.settings_for("kokoro", {}), "x") != vb.settings_hash(vb.settings_for("kokoro", {"model_sha256": "abc"}), "x"), "the model's checksum is part of the settings hash")
kokoro = vb.settings_for("kokoro", {"model_sha256": "x"})
check(vb.settings_hash({**kokoro, "model": "/elsewhere/kokoro-v1.0.onnx", "voices_file": "/elsewhere/voices-v1.0.bin"}, "x")
      == vb.settings_hash(kokoro, "x"), "the model files' paths take no part in the key, so the same files elsewhere remake nothing")


def first_hash(settings, text):
    """The first generator's settings hash, every key in it: what voice/manifest.json holds."""
    return hashlib.sha1(json.dumps([settings[k] for k in sorted(settings)] + [text]).encode()).hexdigest()[:16]


# A manifest from before the sets recorded its settings with the first generator's empty model
# path, and that hash covered every key: the clips are the same, so each hash that verifies against
# the recorded settings is re-keyed, in the manifest and in the sync record, and nothing is made
# or sent again. A hash that does not verify is left, so that clip is made or sent again.
new = vb.settings_for("say", {})
old = {**new, "model": ""}
manifest = {"settings": dict(old), "words": {
    "home": first_hash(old, "home"),
    "dont": first_hash(old, "don't"),
    "stale": "0123456789abcdef",
}}
synced = {"home": manifest["words"]["home"], "dont": "fedcba9876543210", "stale": "0123456789abcdef"}
check(vb.rekey_legacy(manifest, synced, new, {"dont": "don't"}) == 2, "the two clips that verify are re-keyed")
check(manifest["words"]["home"] == vb.settings_hash(new, "home"), "a re-keyed word holds the new hash")
check(manifest["words"]["dont"] == vb.settings_hash(new, "don't"), "a word is verified with its spoken text")
check(manifest["words"]["stale"] == "0123456789abcdef", "a hash that does not verify is left")
check(synced["home"] == vb.settings_hash(new, "home"), "the sync record follows the manifest")
check(synced["dont"] == "fedcba9876543210", "a sync record of another rendition is left")
check(manifest["settings"] == new, "the manifest records the new settings")
check(vb.rekey_legacy(manifest, synced, new, {"dont": "don't"}) == 0, "a second pass changes nothing")
gain = {**old, "gain": 1.6}
changed = {"settings": dict(gain), "words": {"home": first_hash(gain, "home")}}
check(vb.rekey_legacy(changed, {}, new, {}) == 0 and changed["words"]["home"] == first_hash(gain, "home"),
      "a manifest made with other settings is not re-keyed")
check(vb.rekey_legacy({"words": {}}, {}, new, {}) == 0, "a new set has nothing to re-key")
# Without the names --extract and --card-apps give (dont spoken as don't), a word is tried with an
# apostrophe at each inner position, so the carry-over does not depend on the first run's flags
spoken = {"dont": "don't", "isnt": "isn't", "youre": "you're", "rubiks": "rubik's", "home": "home"}
manifest = {"settings": dict(old), "words": {w: first_hash(old, t) for w, t in spoken.items()}}
synced = dict(manifest["words"])
check(vb.rekey_legacy(manifest, synced, new, {}) == 5, "every clip carries over without the extraction's names")
check(all(manifest["words"][w] == vb.settings_hash(new, t) for w, t in spoken.items()),
      "each is keyed with the text its clip was made with")
check(synced == manifest["words"], "and the sync record follows")

# A set stands for one backend and voice: a run that names others is refused
check(vb.set_conflict(None, new) is None, "a new set has nothing to conflict with")
check(vb.set_conflict(old, new) is None, "the same backend and voice")
check(vb.set_conflict({**kokoro, "gain": 1.6}, kokoro) is None, "a changed processing setting is no conflict")
check(vb.set_conflict(kokoro, new) is not None, "a kokoro set refuses a run with the say defaults")
check(vb.set_conflict(kokoro, vb.settings_for("kokoro", {"voice": "bf_emma", "model_sha256": "x"})) is not None,
      "and a run with another voice")

# --check speaks with the set's own backend and voice unless the command line names them
heart = {"backend": "kokoro", "voice": "af_heart", "rate": 100}
check(vb.set_engine(None, None, None) == ("say", None), "a check of a new set speaks with say")
check(vb.set_engine(heart, None, None) == ("kokoro", "af_heart"), "a check of a set speaks with its backend and voice")
check(vb.set_engine({**heart, "voice": "bf_emma"}, None, None) == ("kokoro", "bf_emma"), "its own voice, not the default")
check(vb.set_engine(heart, None, "af_bella") == ("kokoro", "af_bella"), "a voice on the command line wins")
check(vb.set_engine(heart, "espeak", None) == ("espeak", None), "a named backend brings its own default voice")
check(vb.set_engine(heart, "kokoro", None) == ("kokoro", "af_heart"), "naming the set's backend keeps its voice")
check(vb.set_engine({"backend": "piper", "voice": "x"}, None, None) == ("say", None), "an unknown recorded backend is not used")


# --migrate-sets: the first layout's folder and missing list move into the samantha set; a
# destination that is there already refuses the whole migration
def migration(*paths):
    return vb.migration_plan(lambda p: p in paths)


check(migration("/ext/sr/voice", "/ext/sr/missing.txt") == ([("/ext/sr/voice", "/ext/sr/voices/samantha"),
      ("/ext/sr/missing.txt", "/ext/sr/voices/samantha/missing.txt")], None), "the folder and the missing list move")
check(migration("/ext/sr/voice") == ([("/ext/sr/voice", "/ext/sr/voices/samantha")], None), "the folder alone")
check(migration("/ext/sr/voices", "/ext/sr/voices/samantha") == ([], None), "nothing left to move")
moves, refusal = migration("/ext/sr/voice", "/ext/sr/voices/samantha")
check(moves == [] and refusal is not None and "/ext/sr/voices/samantha" in refusal, f"an existing set is never moved over: {refusal}")
moves, refusal = migration("/ext/sr/voice", "/ext/sr/missing.txt", "/ext/sr/voices/samantha/missing.txt")
check(moves == [] and refusal is not None, "nor an existing missing list, and then nothing moves")
# A sync or a pull on the first layout would start /ext/sr/voices/samantha beside /ext/sr/voice
# and so block the migration: it is refused until the card is migrated
refusal = vb.legacy_refusal(lambda p: p == "/ext/sr/voice")
check(refusal is not None and "--migrate-sets" in refusal, f"the first layout refuses a sync or a pull: {refusal}")
check(vb.legacy_refusal(lambda p: p in ("/ext/sr/voices", "/ext/sr/voices/samantha")) is None, "a migrated card is fine")
check(vb.legacy_refusal(lambda p: False) is None, "and so is a fresh card")

# --mark-synced: a set that reached the card by some other means than --sync (a copy through a
# card reader) still needs a synced.json, so the next --sync does not resend everything; it holds
# exactly the manifest's own hashes, nothing verified against the card, and a code that takes any
# card's (T5)
check(vb.mark_synced({"words": {"a": "x", "b": "y"}}) == {"a": "x", "b": "y", vb.SYNC_ID: vb.ANY_CARD},
      "every word's current hash, taken from the manifest, and any card's code")
check(vb.mark_synced({"words": {}}) == {vb.SYNC_ID: vb.ANY_CARD}, "an empty manifest gives no words")
check(vb.mark_synced({}) == {vb.SYNC_ID: vb.ANY_CARD}, "a manifest with no words key gives none either")

# The voice's guard around a transfer, with a fake console. The mute is timed (sr voice off 60)
# and renewed as the sync goes, so a tool that dies cannot leave the reader muted; the voice is
# restored in the same session after a clean run, and through a fresh one after a failure, since
# a Ctrl-C between a write_chunk and its data leaves the old session waiting for file bytes. A
# second Ctrl-C during the restore, or a port that is gone, is reported, never raised, and the
# session is always closed. A connection that fails stops the sync at once.
class FakeRead:
    stall = None


class FakeConsole:
    """What sync, pull_missing and end_transfer use of flipper.storage.FlipperStorage."""

    def __init__(self, voice="on", fail_send=None, fail_command=None, missing=None, files=None, code=None, fail_code=None):
        self.commands = []
        self.files = files or set()  # the files on the card, for exist_file
        self.code = code  # the set's code on the card; its writes are kept apart from the sends
        self.codes_written = []
        self.fail_code = fail_code  # the exception writing the code raises
        self.looked_up = []
        self.sent = []
        self.stopped = 0
        self.read = FakeRead()
        self.voice = voice
        self.fail_send = fail_send or {}  # the nth send_file (1-based): the exception it raises
        self.fail_command = fail_command  # (command, exception)
        self.missing = missing

    def send_and_wait_prompt(self, line):
        self.commands.append(line)
        if self.fail_command and line == self.fail_command[0]:
            raise self.fail_command[1]
        return f"voice: {self.voice}, vocabulary yes set heart\r\n".encode() if line == "sr voice status\r" else b""

    def exist(self, path):
        return False

    def exist_file(self, path):
        self.looked_up.append(path)
        if path.endswith("/" + vb.SYNC_ID):
            return self.code is not None
        return path in self.files or (self.missing is not None and path.endswith("/missing.txt"))

    def receive_file(self, remote, local):
        if remote.endswith("/" + vb.SYNC_ID):
            with open(local, "w") as f:
                f.write(self.code + "\n")
            return
        if isinstance(self.missing, BaseException):
            raise self.missing
        with open(local, "w") as f:
            f.write(self.missing)

    def remove(self, path):
        self.commands.append(f"remove {path}")

    def send_file(self, local, remote):
        if remote.endswith("/" + vb.SYNC_ID):
            if self.fail_code:
                raise self.fail_code
            self.code = open(local).read().strip()
            self.codes_written.append(self.code)
            return
        self.sent.append(remote)
        error = self.fail_send.get(len(self.sent))
        if error:
            raise error
        self.written = getattr(self, "written", {})
        self.written[remote] = open(local).read() if remote.endswith(".txt") else None

    def stop(self):
        self.stopped += 1


class FakeOps:
    def mkpath(self, path):
        pass


def transfer(consoles, run, renew_s=0):
    """Runs run() with open_storage handing out the consoles in turn (an exception in the list is
    raised instead), GUARD_RENEW_S at renew_s and the log collected. Returns (what run returned
    or raised, the stall each open asked for, the log)."""
    opened, said = [], []
    queue = list(consoles)
    saved = vb.open_storage, vb.log, vb.GUARD_RENEW_S, vb.send_to_card

    def fake_open(port, stall=None):
        opened.append(stall)
        c = queue.pop(0)
        if isinstance(c, BaseException):
            raise c
        return c, FakeOps()

    vb.open_storage, vb.log, vb.GUARD_RENEW_S = fake_open, said.append, renew_s
    vb.send_to_card = lambda storage, local, remote: storage.send_file(local, remote)
    try:
        try:
            outcome = run()
        except BaseException as e:  # noqa: B902 (a Ctrl-C is what these checks are about)
            outcome = e
    finally:
        vb.open_storage, vb.log, vb.GUARD_RENEW_S, vb.send_to_card = saved
    return outcome, opened, said


if importlib.util.find_spec("serial") is None:
    print("skipped the guard checks: no pyserial")
else:
    import tempfile
    with tempfile.TemporaryDirectory() as out_dir:
        words = {"alpha": "h1", "bravo": "h2", "charlie": "h3"}
        for word in words:
            os.makedirs(os.path.join(out_dir, vb.initial(word)), exist_ok=True)
            open(os.path.join(out_dir, vb.initial(word), word + ".raw"), "wb").close()
        open(os.path.join(out_dir, "voice.txt"), "w").close()
        manifest = {"words": words}

        def sync():
            return vb.sync("port", out_dir, manifest, "heart", force_all=True)

        # A clean sync: the timed mute, renewed before each word here, and the voice back on in
        # the same session, which waits less for it
        c = FakeConsole()
        result, opened, said = transfer([c], sync)
        guard = f"sr voice off {vb.GUARD_S}\r"
        check(result == 0 and len(c.sent) == 4, f"a clean sync sends the three clips and voice.txt: {result}, {c.sent}")
        check(vb.GUARD_S == 60 and c.commands[:2] == ["sr voice status\r", guard],
              f"the voice's mute is timed, a minute: {c.commands[:2]}")
        check(c.commands.count(guard) == 4, f"the mute is renewed as the sync goes: {c.commands}")
        check(c.commands[-1] == "sr voice on\r" and c.read.stall == vb.RESTORE_STALL_S and c.stopped >= 1 and len(opened) == 1,
              f"the voice is restored in the same session, which is closed: {c.commands[-1:]}, {opened}")

        # The clips go in clip order: the manifest's most spoken words first, then the rest sorted
        c = FakeConsole()
        manifest["first"] = ["charlie"]
        result, opened, said = transfer([c], sync)
        del manifest["first"]
        card = vb.set_card_dir("heart")
        clips = [p for p in c.sent if p.endswith(".raw")]
        check(clips == [f"{card}/{vb.bucket(w)}/{w}.raw" for w in ("charlie", "alpha", "bravo")],
              f"the most spoken word goes first: {clips}")

        # Ctrl-C during the second clip: the old session is closed and left alone, and the voice
        # comes back through a fresh one
        c1, c2 = FakeConsole(fail_send={2: KeyboardInterrupt()}), FakeConsole()
        result, opened, said = transfer([c1, c2], sync)
        check(isinstance(result, KeyboardInterrupt), f"the Ctrl-C still ends the run: {result!r}")
        check(c1.stopped >= 1 and "sr voice on\r" not in c1.commands,
              f"the interrupted session gets no more commands, it may be waiting for file bytes: {c1.commands}")
        check(opened == [None, vb.RESTORE_STALL_S] and c2.commands == ["sr voice on\r"] and c2.stopped >= 1,
              f"the voice comes back through a fresh session: {opened}, {c2.commands}")

        # A second Ctrl-C during that restore: reported, never raised, both sessions closed
        c1 = FakeConsole(fail_send={2: KeyboardInterrupt()})
        c2 = FakeConsole(fail_command=("sr voice on\r", KeyboardInterrupt()))
        result, opened, said = transfer([c1, c2], sync)
        check(isinstance(result, KeyboardInterrupt) and c1.stopped >= 1 and c2.stopped >= 1,
              f"a second Ctrl-C leaves both sessions closed: {result!r}, {c1.stopped}, {c2.stopped}")
        check(any("comes back by itself" in line for line in said), f"and says the voice comes back by itself: {said[-1:]}")

        # The port is gone when the voice is to be restored: reported, the first error kept
        c1 = FakeConsole(fail_send={1: KeyboardInterrupt()})
        result, opened, said = transfer([c1, OSError("no such port")], sync)
        check(isinstance(result, KeyboardInterrupt) and any("not restored" in line and "no such port" in line for line in said),
              f"a port that is gone is reported: {result!r}, {said[-1:]}")

        # A connection that stops answering ends the sync at the first clip it fails, not once
        # per word, and the voice is restored through a fresh session
        c1, c2 = FakeConsole(fail_send={2: TimeoutError("the device sent nothing for 30 s")}), FakeConsole()
        result, opened, said = transfer([c1, c2], sync)
        check(isinstance(result, vb.SyncStopped) and isinstance(result.__cause__, TimeoutError) and len(c1.sent) == 2,
              f"a failed connection stops the sync: {result!r}, {c1.sent}")
        check(sum("stopped at word 2 of 3" in line for line in said) == 1 and c2.commands == ["sr voice on\r"],
              f"one line says where, and the voice is restored: {said}, {c2.commands}")

        # A port error of the system's own, not pyserial's, stops it the same way (T4)
        c1, c2 = FakeConsole(fail_send={2: OSError(5, "Input/output error")}), FakeConsole()
        result, opened, said = transfer([c1, c2], sync)
        check(isinstance(result, vb.SyncStopped) and len(c1.sent) == 2 and c2.commands == ["sr voice on\r"],
              f"an OSError stops the sync: {result!r}, {c1.sent}, {c2.commands}")
        check(len([line for line in said if "failed" in line]) == 1, f"with one line, not one per word left: {said}")

        # The card refusing a clip's data, a full card: stopped, as every clip after it would be, and
        # the session ended, since the rest of the chunk reached the console as input (T10)
        c1, c2 = FakeConsole(fail_send={2: vb.CardWriteError("/ext/sr/voices/heart/7c/bravo.raw: Storage error: filesystem full")}), FakeConsole()
        result, opened, said = transfer([c1, c2], sync)
        check(isinstance(result, vb.SyncStopped) and len(c1.sent) == 2 and c1.stopped >= 1 and c2.commands == ["sr voice on\r"],
              f"a refused write stops the sync: {result!r}, {c1.sent}, {c2.commands}")
        check(any("stopped at word 2 of 3" in line and "full" in line for line in said), f"and says so: {said}")

        # One word that fails for itself, not the connection's: counted, and the others still go
        c = FakeConsole(fail_send={2: ValueError("a clip the protocol refused")})
        result, opened, said = transfer([c], sync)
        check(result == 1 and len(c.sent) == 4 and c.commands[-1] == "sr voice on\r",
              f"a failed word is counted and the sync goes on: {result!r}, {c.sent}")

        # synced.json against the card (T5): a card that has the clips it lists gets only voice.txt,
        # after three lookups; a wiped card, or one that lacks any of the three, gets everything, the
        # lookups ending at the first clip missing
        def sync_changed():
            return vb.sync("port", out_dir, manifest, "heart")

        card = vb.set_card_dir("heart")
        on_card = {f"{card}/{vb.bucket(w)}/{w}.raw" for w in words}
        synced_path = os.path.join(out_dir, "synced.json")
        for files, sends, what in ((on_card, 1, "the card has them all"), (set(), 4, "a wiped card"),
                                   (on_card - {f"{card}/{vb.bucket('bravo')}/bravo.raw"}, 4, "the middle one gone")):
            json.dump(words, open(synced_path, "w"))
            c = FakeConsole(files=files)
            result, opened, said = transfer([c], sync_changed)
            lookups = [p for p in c.looked_up if p.endswith(".raw")]
            check(result == 0 and len(c.sent) == sends and c.sent[-1] == f"{card}/voice.txt"
                  and 1 <= len(lookups) <= 3 and (len(lookups) == 3 or sends == 4),
                  f"{what}: {sends} sent after at most three lookups, all three when the clips are there: "
                  f"{result!r}, {c.sent}, {lookups}")
            check(any("wiped" in line for line in said) == (sends == 4), f"{what}: said why only when all is sent: {said}")
        check(not vb.card_lacks_synced(FakeConsole(), card, {"gone": "h9"}, words),
              "words synced.json lists that the manifest no longer has are not looked up")
        check(not vb.card_lacks_synced(FakeConsole(), card, {}, words), "nothing synced, nothing to look up")

        # The card's code (T5): synced.json keeps the code the last sync that changed the card
        # wrote into the set's folder there; a card with another code, a copy from another sync,
        # gets everything, even with the three clips there. A card without one is trusted, as
        # before the codes, and gets one; so is any card after --mark-synced
        for ours, theirs, differs in ((None, None, False), ("a1", None, False), (None, "a1", True), ("a1", "a1", False),
                                      ("a1", "b2", True), (vb.ANY_CARD, "b2", False)):
            check(vb.card_copy_differs(ours, theirs) == differs, f"synced.json's code {ours}, the card's {theirs}: differs {differs}")

        def code_on_file():
            return json.load(open(synced_path)).get(vb.SYNC_ID)

        # A card without a code, its clips there: trusted, only voice.txt sent, and the new code
        # both on the card and in synced.json
        json.dump(words, open(synced_path, "w"))
        c = FakeConsole(files=on_card)
        result, opened, said = transfer([c], sync_changed)
        check(result == 0 and c.sent == [f"{card}/voice.txt"] and len(c.codes_written) == 1
              and c.code == code_on_file() and len(c.code) == 16,
              f"a card without a code keeps its clips and gets the code: {c.sent}, {c.codes_written}, {code_on_file()}")
        check(not any("everything" in line for line in said), f"and nothing says everything is sent: {said}")
        first = c.code

        # The same card again, nothing changed: only voice.txt, and the code stays
        c = FakeConsole(files=on_card, code=first)
        result, opened, said = transfer([c], sync_changed)
        check(result == 0 and c.sent == [f"{card}/voice.txt"] and c.codes_written == [] and code_on_file() == first,
              f"the same card with nothing changed keeps its code: {c.sent}, {c.codes_written}")

        # A word changed: that clip is sent, under a new code, written to synced.json first
        synced_now = json.load(open(synced_path))
        synced_now["bravo"] = "old"
        json.dump(synced_now, open(synced_path, "w"))
        c = FakeConsole(files=on_card, code=first)
        result, opened, said = transfer([c], sync_changed)
        second = code_on_file()
        check(result == 0 and c.sent == [f"{card}/{vb.bucket('bravo')}/bravo.raw", f"{card}/voice.txt"]
              and c.codes_written == [second] and second != first,
              f"a changed clip goes under a new code: {c.sent}, {c.codes_written}, {first}, {second}")

        # Another card with the clips there but the first code, an older copy the last sync
        # overtook: everything is sent, and it gets a new code
        c = FakeConsole(files=on_card, code=first)
        result, opened, said = transfer([c], sync_changed)
        check(result == 0 and len(c.sent) == 4 and len(c.codes_written) == 1 and code_on_file() not in (first, second)
              and c.code == code_on_file(),
              f"an older copy gets everything and a new code: {c.sent}, {c.codes_written}")
        check(any("another sync" in line and "everything" in line for line in said), f"and says why: {said}")
        third = code_on_file()

        # A code from another computer's sync: everything as well
        c = FakeConsole(files=on_card, code="0123456789abcdef")
        result, opened, said = transfer([c], sync_changed)
        check(result == 0 and len(c.sent) == 4 and c.code == code_on_file() != third,
              f"another computer's copy gets everything: {c.sent}")

        # Cut off while the code goes to the card: synced.json has the new code already, so the
        # card, still with its old one, gets everything next time instead of being trusted
        fourth = code_on_file()
        synced_now = json.load(open(synced_path))
        synced_now["bravo"] = "old"
        json.dump(synced_now, open(synced_path, "w"))
        c1, c2 = FakeConsole(files=on_card, code=fourth, fail_code=KeyboardInterrupt()), FakeConsole()
        result, opened, said = transfer([c1, c2], sync_changed)
        check(isinstance(result, KeyboardInterrupt) and c1.sent == [] and code_on_file() not in (None, fourth),
              f"the new code is in synced.json before the card has it: {result!r}, {code_on_file()}, {fourth}")
        c = FakeConsole(files=on_card, code=fourth)
        result, opened, said = transfer([c], sync_changed)
        check(result == 0 and len(c.sent) == 4, f"so that card gets everything next time: {c.sent}")

        # The new code comes before the first clip: a sync cut off at its first clip has renewed it,
        # so another card that still holds the old one gets everything instead of being trusted
        # with clips only the first card got
        fifth = code_on_file()
        synced_now = json.load(open(synced_path))
        synced_now["bravo"] = "old"
        json.dump(synced_now, open(synced_path, "w"))
        c1, c2 = FakeConsole(files=on_card, code=fifth, fail_send={1: KeyboardInterrupt()}), FakeConsole()
        result, opened, said = transfer([c1, c2], sync_changed)
        check(isinstance(result, KeyboardInterrupt) and c1.code == code_on_file() != fifth,
              f"a sync cut off at its first clip has renewed the code: {result!r}, {c1.code}, {fifth}")
        c = FakeConsole(files=on_card, code=fifth)
        result, opened, said = transfer([c], sync_changed)
        check(result == 0 and len(c.sent) == 4, f"so another card with the old code gets everything: {c.sent}")

        # A card that refuses the code, a full one: stopped before the first clip, in one line
        c1, c2 = FakeConsole(files=on_card, fail_code=vb.CardWriteError(f"{card}/.sync-id: Storage error: filesystem full")), FakeConsole()
        result, opened, said = transfer([c1, c2], lambda: vb.sync("port", out_dir, manifest, "heart", force_all=True))
        check(isinstance(result, vb.SyncStopped) and c1.sent == [] and c2.commands == ["sr voice on\r"]
              and sum("before the first clip" in line and "full" in line for line in said) == 1,
              f"a refused code stops the sync with one line: {result!r}, {c1.sent}, {said}")

        # After --mark-synced, whatever code the card holds, its copy is trusted and gets a new code
        json.dump(vb.mark_synced(manifest), open(synced_path, "w"))
        c = FakeConsole(files=on_card, code="0123456789abcdef")
        result, opened, said = transfer([c], sync_changed)
        check(result == 0 and c.sent == [f"{card}/voice.txt"] and c.code == code_on_file() not in (None, vb.ANY_CARD, "0123456789abcdef"),
              f"after --mark-synced the card is trusted and gets a new code: {c.sent}, {c.codes_written}")

        # --sync-all sends everything under a new code, without reading the card's
        c = FakeConsole(files=on_card, code=code_on_file())
        result, opened, said = transfer([c], lambda: vb.sync("port", out_dir, manifest, "heart", force_all=True))
        check(result == 0 and len(c.sent) == 4 and len(c.codes_written) == 1 and c.code == code_on_file()
              and not any(p.endswith(vb.SYNC_ID) for p in c.looked_up),
              f"--sync-all sends everything under a new code: {c.sent}, {c.looked_up}")

        # A sync that sends every clip takes the pulled words off the card's list, and pulled.txt
        # goes; one with a clip failed leaves both for the next (T6)
        pulled_path = os.path.join(out_dir, "pulled.txt")
        for fail, cleared in (({}, True), ({2: ValueError("a clip the protocol refused")}, False)):
            vb.write_list(pulled_path, {"zulu"})
            c = FakeConsole(missing="zulu\n", fail_send=fail)
            result, opened, said = transfer([c], lambda: vb.sync("port", out_dir, manifest, "heart", True, {"zulu"}))
            removed = f"remove {card}/missing.txt" in c.commands
            check(result == (0 if cleared else 1) and removed == cleared and os.path.exists(pulled_path) != cleared,
                  f"pulled words cleared only after a sync without failures ({cleared}): {result!r}, {c.commands}")
        os.remove(pulled_path)

        # Cut off at the second clip: synced.json keeps the first, so the next sync does not send it
        # again (T10)
        if os.path.exists(os.path.join(out_dir, "synced.json")):
            os.remove(os.path.join(out_dir, "synced.json"))
        c1, c2 = FakeConsole(fail_send={2: KeyboardInterrupt()}), FakeConsole()
        result, opened, said = transfer([c1, c2], sync)
        kept = json.load(open(os.path.join(out_dir, "synced.json"))) if os.path.exists(os.path.join(out_dir, "synced.json")) else None
        check(isinstance(result, KeyboardInterrupt) and kept == {"alpha": "h1", vb.SYNC_ID: c1.code},
              f"an interrupted sync keeps its record, with the code the card has, so the next one continues: {kept}, {c1.code}")

        # A voice that was off before the sync stays off, after a failure too: no fresh session
        c1 = FakeConsole(voice="off", fail_send={1: KeyboardInterrupt()})
        result, opened, said = transfer([c1], sync)
        check(len(opened) == 1 and "sr voice on\r" not in c1.commands and c1.stopped >= 1,
              f"a voice that was off is not switched on: {opened}, {c1.commands}")

    # pull_missing cut off by a Ctrl-C while it reads the list: restored through a fresh session
    c1, c2 = FakeConsole(missing=KeyboardInterrupt()), FakeConsole()
    result, opened, said = transfer([c1, c2], lambda: vb.pull_missing("port", "heart"))
    check(isinstance(result, KeyboardInterrupt) and c2.commands == ["sr voice on\r"],
          f"an interrupted pull restores the voice through a fresh session: {result!r}, {c2.commands}")
    c = FakeConsole(missing="zulu\n")
    result, opened, said = transfer([c], lambda: vb.pull_missing("port", "heart"))
    check(result == {"zulu"} and c.commands[-1] == "sr voice on\r" and len(opened) == 1,
          f"a clean pull restores the voice in the same session: {result}, {c.commands}")
    check(not any(cmd.startswith("remove") for cmd in c.commands), f"and leaves the card's list there (T6): {c.commands}")

    # The card's list once the pulled words are synced (T6): gone when it held only those, written
    # back with a word noted since, and left alone when there is none
    missing_path = vb.set_card_dir("heart") + "/missing.txt"
    c = FakeConsole(missing="zulu\n")
    result, opened, said = transfer([c], lambda: vb.clear_pulled(c, vb.set_card_dir("heart"), {"zulu"}))
    check(result == 0 and f"remove {missing_path}" in c.commands and c.sent == [], f"only pulled words: removed: {result}, {c.commands}")
    c = FakeConsole(missing="zulu\nyankee\n")
    result, opened, said = transfer([c], lambda: vb.clear_pulled(c, vb.set_card_dir("heart"), {"zulu"}))
    check(result == 1 and f"remove {missing_path}" in c.commands and c.written.get(missing_path) == "yankee\n",
          f"a word noted since the pull is written back: {result}, {c.commands}, {getattr(c, 'written', {})}")
    c = FakeConsole()
    result, opened, said = transfer([c], lambda: vb.clear_pulled(c, vb.set_card_dir("heart"), {"zulu"}))
    check(result == 0 and c.commands == [] and c.sent == [], "no list on the card: nothing to do")

    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "pulled.txt")
        vb.write_list(path, {"zulu", "alpha"})
        check(open(path).read() == "alpha\nzulu\n" and vb.load_list(path) == {"alpha", "zulu"},
              "pulled.txt: a word a line, sorted, read back as it was written")


# send_to_card over the storage protocol: write_chunk, "Ready", the data, the prompt; no line of its
# own, where storage.send_file prints one per file; an error before the data raises the protocol's
# exception, one after it CardWriteError
if importlib.util.find_spec("serial") is not None:
    import contextlib
    import io
    import tempfile

    class ProtocolRead:
        def __init__(self, answers):
            self.answers = list(answers)

        def until(self, eol):
            return bytearray(self.answers.pop(0))

    class ProtocolPort:
        def __init__(self):
            self.data = b""

        def write(self, data):
            self.data += data

    class ProtocolConsole:
        CLI_EOL = "\r\n"
        CLI_PROMPT = ">: "
        chunk_size = 4

        def __init__(self, answers, exists=False):
            self.read = ProtocolRead(answers)
            self.port = ProtocolPort()
            self.exists = exists
            self.commands = []

        def exist_file(self, path):
            return self.exists

        def remove(self, path):
            self.commands.append(f"remove {path}")

        def send_and_wait_eol(self, line):
            self.commands.append(line)

        def has_error(self, data):
            return data.find(b"Storage error:") != -1

        def get_error(self, data):
            from flipper.storage import StorageErrorCode
            return StorageErrorCode.from_value(data.decode("ascii").split(": ")[1].strip())

    sys.path.insert(0, os.path.join(vb.FW, "scripts"))
    with tempfile.TemporaryDirectory() as d:
        clip = os.path.join(d, "clip.raw")
        open(clip, "wb").write(b"0123456789")
        c = ProtocolConsole([b"Ready", b"", b"Ready", b"", b"Ready", b""], exists=True)
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            vb.send_to_card(c, clip, "/ext/x.raw")
        check(c.port.data == b"0123456789" and c.commands[0] == "remove /ext/x.raw"
              and c.commands[1:] == ['storage write_chunk "/ext/x.raw" 4\r'] * 2 + ['storage write_chunk "/ext/x.raw" 2\r'],
              f"a file goes in chunks after the old one is removed: {c.commands}, {c.port.data!r}")
        check(printed.getvalue() == "", f"and prints nothing: {printed.getvalue()!r}")
        # Answers for all three chunks, so that a send ignoring the error would run to the end
        c = ProtocolConsole([b"Ready", b"Storage error: filesystem full\r\n", b"Ready", b"", b"Ready", b""])
        try:
            vb.send_to_card(c, clip, "/ext/x.raw")
            raised = None
        except vb.CardWriteError as e:
            raised = str(e)
        check(raised is not None and "filesystem full" in raised and len(c.port.data) == 4,
              f"an error after the data is read, not taken for success: {raised}")
        from flipper.storage import FlipperStorageException
        c = ProtocolConsole([b"Storage error: file/dir not exist", b""])
        try:
            vb.send_to_card(c, clip, "/ext/x.raw")
            raised = None
        except FlipperStorageException as e:
            raised = e
        check(raised is not None and c.port.data == b"", f"an error before the data sends none of it: {raised!r}")


# StalledRead: the reply up to the prompt, or TimeoutError once the device has sent nothing for
# the stall, where scripts/flipper/storage.py's BufferedRead would read forever
class FakePort:
    def __init__(self, data):
        self.data = bytearray(data)
        self.in_waiting = len(self.data)

    def read(self, n):
        chunk, self.data = bytes(self.data[:n]), self.data[n:]
        self.in_waiting = len(self.data)
        return chunk


r = vb.StalledRead(FakePort(b"voice on\r\n>: "), 0.05)
check(r.until(">: ") == b"voice on\r\n", "the reply up to the prompt")
r = vb.StalledRead(FakePort(b"Ready\r\n"), 0.05)
try:
    r.until(">: ")
    check(False, "a device that sends nothing more gives a TimeoutError")
except TimeoutError as e:
    check("nothing for 0.05 s" in str(e), f"a device that sends nothing more gives a TimeoutError: {e}")

if all(importlib.util.find_spec(p) for p in ("numpy", "scipy", "kokoro_onnx")):
    problem = vb.engine_problem(vb.settings_for("kokoro", {"model": "/nonexistent/kokoro.onnx", "model_sha256": "x"}))
    check(problem is not None and "/nonexistent/kokoro.onnx" in problem, f"a missing model is named before the pool starts: {problem}")
else:
    print("skipped the missing-model check: no numpy, scipy or kokoro-onnx")

try:
    import numpy as np
    import scipy.signal  # noqa: F401  (the resampler's filter)
except ImportError:
    print("skipped the resampler checks: no numpy or scipy")
else:
    t = np.arange(24000) / 24000.0
    x = (0.5 * np.sin(2 * math.pi * 440 * t)).astype(np.float32)
    y = vb.resample(x, 24000, 16000)
    check(abs(len(y) - 16000) <= 2, f"24 kHz to 16 kHz keeps the duration: {len(y)}")
    check(0.45 < float(np.max(np.abs(y))) < 0.55, f"the level is kept: {float(np.max(np.abs(y))):.3f}")
    y = vb.resample(x[:22050], 22050, 16000)
    check(abs(len(y) - 16000) <= 2, f"22.05 kHz to 16 kHz keeps the duration: {len(y)}")
    check(len(vb.resample(x[:1600], 16000, 16000)) == 1600, "same rate: unchanged length")

print(f"voice build: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
