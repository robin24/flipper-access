# Publishing, plan B: voice sets, the Kokoro and eSpeak voices, the pack tool

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the reader keep several recorded vocabularies on the card and switch between them, make the generator produce them with Kokoro, eSpeak-NG or the macOS voices, put a Kokoro heart set and an eSpeak set on Robin's card beside Samantha, and turn a set into a release asset.

**Architecture:** The card holds one folder per voice set under `/ext/sr/voices/<set>/`, each with the 64 hashed clip folders, its `voice.txt` settings line and its own `missing.txt`. The speech engine resolves the set to use from a Momentum setting, falling back to the first set on the card; the Accessibility screen and the console change the setting. The generator, `tools/voice_build.py`, gains a set name and two backends beside `say`; a new `tools/voice_pack.py` writes a set as a tar with its licence. Pure logic stays host tested: the path builder in C, the generator's set and settings helpers in Python.

**Tech Stack:** Momentum firmware (C, fbt, `./fbt` in the submodule), the project's Python 3 venv (pyserial, numpy, scipy, kokoro-onnx), eSpeak-NG 1.52 from Homebrew, macOS `say`, the Flipper's USB console through `tools/flipper_cli.py`, the firmware's `scripts/flipper/storage.py` for card transfers.

**Spec:** `docs/superpowers/specs/2026-09-26-github-release-design.md`, section 5 (the engine choice and the voice sets) with sections 3 and 11; the main spec `docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md` for the reader.

## Global Constraints

- The generator keeps the macOS `say` backend as a first-class option, for Robin's own Samantha set and for anyone who wants Apple's voices for personal use; it must never lose the ability to make and sync a `say` set.
- The repository-root `voice/` directory is Robin's Samantha vocabulary: never deleted, moved or committed; it is the local directory of the set named `samantha`. Other sets live under `voices/<set>/`, ignored by git.
- On the card the layout is `/ext/sr/voices/<set>/...`; the firmware reads only that layout. Robin's `/ext/sr/voice` is moved once, by the generator, to `/ext/sr/voices/samantha`, never deleted. Nothing under `/ext/sr/voices` is removed by any task.
- A set name is 1 to 31 characters of lower-case letters, digits, hyphen and underscore (`speech_voice_set_valid`); the Momentum setting `sr_voice_set` is a 32-byte string, empty meaning "the first set found".
- Kokoro and eSpeak render a word identically every run; the generator only makes missing clips or, when a setting or the model changes, all of them, so a set never mixes renditions. Each set's manifest records the backend, the voice, the processing settings and, for Kokoro, the SHA-256 of the model and voices files.
- Firmware: commits on `screen-reader` are pushed to `origin` (the fork) and followed by a pointer commit in the project (`git add Momentum-Firmware`); never `git push upstream`; explicit pathspecs; plain-sentence messages ending with the implementer's own Co-Authored-By line; no `--amend`, no force push; nothing under `applications/external` is touched. Flash limit 880,640 bytes, checked with `tools/flash_headroom.sh`; a release build starts from a wiped `Momentum-Firmware/build`.
- Device: one agent on the device at a time; never `loader close`; never set a PIN; after a flash `sr screen` before any key, then `sysctl debug 1` and `sysctl log_level debug` (a flash clears them), then `tools/card_prune.py`; the UART capture `tools/uart_log.py` keeps running.
- Tests first: every C change to a host-tested module extends `tests/host/`; every Python helper with logic gets a plain-script test under `tests/fbt/`, added to `tools/run_host_tests.sh`; the runner is green before every commit.
- Documentation for a screen reader user: prose and short lists, no tables, commands in code blocks, no em-dashes; the public README names no device and no port.
- The listening session after Task 6 is Robin's: the controller stops the plan there, runs the session, and resumes with Task 7 once Robin has chosen the Kokoro processing settings.

---

### Task 1: The items parked by plan A's last review

**Files:**
- Modify: `tests/fbt/test_upstream_check.py`, `docs/device-notes.md`, `README.md`

- [ ] **Step 1: The test helper also disables tag signing**

In `tests/fbt/test_upstream_check.py`, the `git()` helper passes `-c commit.gpgsign=false`; add `-c tag.gpgSign=false` beside it. Run `python3 tests/fbt/test_upstream_check.py`: still all checks passed.

- [ ] **Step 2: The merge routine keeps the manifest's comment**

In `docs/device-notes.md`, section "Merging Momentum", the step that takes upstream's Sub-GHz manifest and runs `tools/subghz_manifest.py` gets one more sentence: the fork's comment above the source list (why the files are listed one by one) is lost when upstream's file is taken whole, so restore it from `git show HEAD~1:applications/main/subghz/application.fam` after running the script.

- [ ] **Step 3: Four wording fixes**

- `README.md`, the sentence about the tools' port default: `tools/sr_drive.py` takes the port from the `FLIPPER_PORT` environment variable, not from `--port`; say so where `--port` and `FLIPPER_PORT` are explained.
- `README.md`, Building from source: the sentence about `git -C Momentum-Firmware checkout screen-reader` must say that it moves the submodule to the branch's tip, which is the recorded commit only while the project's pointer is current; a source build of exactly the recorded commit keeps the detached HEAD.
- `README.md`, "What changed against Momentum": the stack overflow check "names the thread" only in the debug log; the popup the reader speaks says "StackOverflow". Reword.
- `docs/device-notes.md`: "The update of 2026-09-26" in the settings paragraph becomes "The first update of 2026-09-26, to a0dea0841".

- [ ] **Step 4: Check and commit**

```bash
grep -c "^|" README.md docs/device-notes.md
tools/run_host_tests.sh
git add tests/fbt/test_upstream_check.py docs/device-notes.md README.md
git commit -m "The items parked by plan A's last review: tag signing off in the test helper, the manifest's comment in the merge routine, four wordings" -- tests/fbt/test_upstream_check.py docs/device-notes.md README.md
git push
```

---

### Task 2: The clip path builder takes a set

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/speech_voice.h`, `speech_voice.c`
- Modify: `tests/host/test_speech_voice.c`

**Interfaces:**
- Produces: `SPEECH_VOICE_SETS_DIR`, `SPEECH_VOICE_SET_MAX`, `SPEECH_VOICE_PATH_MAX` 96, `bool speech_voice_set_valid(const char* name)`, `size_t speech_voice_set_file(const char* set, const char* file, char* out, size_t out_size)`, and `size_t speech_voice_path(const char* set, const char* word, char* out, size_t out_size)` with the new first parameter. Task 3 uses all of them.

- [ ] **Step 1: Extend the host test first**

In `tests/host/test_speech_voice.c`, `expect_path` and `test_paths` change to the new signature and layout, and set names get their own test. Replace `expect_path` with:

```c
static void expect_path(const char* set, const char* word) {
    char out[SPEECH_VOICE_PATH_MAX];
    char want[SPEECH_VOICE_PATH_MAX + 32];
    snprintf(want, sizeof(want), "/ext/sr/voices/%s/%02x/%s.raw", set,
             (unsigned)(ref_hash(word) % SPEECH_VOICE_BUCKETS), word);
    size_t n = speech_voice_path(set, word, out, sizeof(out));
    checks++;
    if(n != strlen(want) || strcmp(out, want) != 0) {
        failures++;
        printf("FAIL path(\"%s\", \"%s\") got %zu \"%s\", want \"%s\"\n", set, word, n, n ? out : "", want);
    }
}
```

In `test_paths`, the pinned checks become (the hash and the folders are unchanged, only the prefix moves):

```c
    CHECK(speech_voice_hash("settings") == 0x68067b08u);
    CHECK(speech_voice_path("samantha", "settings", out, sizeof(out)) == strlen("/ext/sr/voices/samantha/08/settings.raw"));
    CHECK(strcmp(out, "/ext/sr/voices/samantha/08/settings.raw") == 0);
    CHECK(speech_voice_path("heart", "7", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voices/heart/36/7.raw") == 0);
    CHECK(speech_voice_path("heart", "ay", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voices/heart/0f/ay.raw") == 0);
```

and the `don't` check uses `speech_voice_path("samantha", w.word, ...)` expecting `/ext/sr/voices/samantha/0e/dont.raw`; the empty-word and small-buffer checks become `speech_voice_path("samantha", "", ...) == 0` and `speech_voice_path("samantha", "settings", out, 30) == 0`; every `expect_path(words[i])` becomes `expect_path("samantha", words[i])` and the loop over 2000 words uses the set `"heart"`. The longest-word check uses the longest set name too:

```c
    const char* longest_set = "abcdefghijklmnopqrstuvwxyz01234";
    CHECK(strlen(longest_set) == SPEECH_VOICE_SET_MAX - 1);
    CHECK(speech_voice_path(longest_set, longest, out, sizeof(out)) == strlen(out));
    CHECK(strlen(out) < SPEECH_VOICE_PATH_MAX);
    expect_path(longest_set, longest);
```

Add a new test function and call it from `main`:

```c
static void test_sets(void) {
    CHECK(speech_voice_set_valid("samantha"));
    CHECK(speech_voice_set_valid("heart"));
    CHECK(speech_voice_set_valid("en-us_f3"));
    CHECK(speech_voice_set_valid("a"));
    CHECK(speech_voice_set_valid("abcdefghijklmnopqrstuvwxyz01234"));
    CHECK(!speech_voice_set_valid(""));
    CHECK(!speech_voice_set_valid("abcdefghijklmnopqrstuvwxyz012345"));
    CHECK(!speech_voice_set_valid("Heart"));
    CHECK(!speech_voice_set_valid("two words"));
    CHECK(!speech_voice_set_valid("a/b"));
    CHECK(!speech_voice_set_valid("."));
    CHECK(!speech_voice_set_valid(".."));
    CHECK(!speech_voice_set_valid("héart"));
    char out[SPEECH_VOICE_PATH_MAX];
    CHECK(speech_voice_set_file("heart", "voice.txt", out, sizeof(out)) == strlen("/ext/sr/voices/heart/voice.txt"));
    CHECK(strcmp(out, "/ext/sr/voices/heart/voice.txt") == 0);
    CHECK(speech_voice_set_file("heart", "missing.txt", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voices/heart/missing.txt") == 0);
    CHECK(speech_voice_set_file("heart", "", out, sizeof(out)) == strlen("/ext/sr/voices/heart"));
    CHECK(strcmp(out, "/ext/sr/voices/heart") == 0);
    CHECK(speech_voice_set_file("heart", "voice.txt", out, 10) == 0);
    CHECK(speech_voice_set_file("", "voice.txt", out, sizeof(out)) == 0);
}
```

Run the runner's compile line for this test by hand and see it fail to compile (the new symbols do not exist):

```bash
clang -std=c11 -Wall -Wextra -Werror -O1 -fsanitize=address,undefined -fno-sanitize-recover=all -I Momentum-Firmware/applications/services/screen_reader -o /tmp/t_sv tests/host/test_speech_voice.c Momentum-Firmware/applications/services/screen_reader/speech_voice.c
```

- [ ] **Step 2: The header**

In `speech_voice.h` replace the `SPEECH_VOICE_DIR` and `SPEECH_VOICE_PATH_MAX` lines with:

```c
#define SPEECH_VOICE_SETS_DIR "/ext/sr/voices" /**< one folder per voice set */
#define SPEECH_VOICE_SET_MAX  32 /**< set name with its terminator */
#define SPEECH_VOICE_PATH_MAX 96 /**< "/ext/sr/voices/" + set + "/hh/" + name + ".raw" */
```

Replace the comment and declaration of `speech_voice_path` with:

```c
/** True for a set name the card and the settings can hold: 1 to SPEECH_VOICE_SET_MAX - 1
 *  characters, each a lower case letter, a digit, a hyphen or an underscore. */
bool speech_voice_set_valid(const char* name);

/** SPEECH_VOICE_SETS_DIR "/<set>/<file>", or the set's folder itself for an empty file name.
 *  Returns the length written, 0 for an empty set or a buffer too small. The set is not
 *  validated here: the callers pass names that came through speech_voice_set_valid or from
 *  the card's own folder listing. */
size_t speech_voice_set_file(const char* set, const char* file, char* out, size_t out_size);

/** The clip path of a word in a set: SPEECH_VOICE_SETS_DIR "/<set>/<hh>/<word>.raw", where
 *  hh is speech_voice_hash(word) modulo SPEECH_VOICE_BUCKETS as two lower case hex digits. A
 *  directory lookup on the card reads the entries one by one, so a vocabulary is spread over
 *  64 folders of a few dozen clips each. Returns the length written, 0 for an empty set or
 *  word, or a buffer too small. */
size_t speech_voice_path(const char* set, const char* word, char* out, size_t out_size);
```

- [ ] **Step 3: The implementation**

In `speech_voice.c` replace `speech_voice_path` with these three functions:

```c
bool speech_voice_set_valid(const char* name) {
    size_t n = strlen(name);
    if(n == 0 || n > SPEECH_VOICE_SET_MAX - 1) return false;
    for(size_t i = 0; i < n; i++) {
        char c = name[i];
        bool ok = (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-' || c == '_';
        if(!ok) return false;
    }
    return true;
}

size_t speech_voice_set_file(const char* set, const char* file, char* out, size_t out_size) {
    size_t s = strlen(set);
    size_t f = strlen(file);
    if(s == 0) return 0;
    size_t dir = strlen(SPEECH_VOICE_SETS_DIR);
    size_t need = dir + 1 + s + (f ? 1 + f : 0) + 1;
    if(need > out_size) return 0;
    char* p = out;
    memcpy(p, SPEECH_VOICE_SETS_DIR, dir);
    p += dir;
    *p++ = '/';
    memcpy(p, set, s);
    p += s;
    if(f) {
        *p++ = '/';
        memcpy(p, file, f);
        p += f;
    }
    *p = '\0';
    return (size_t)(p - out);
}

size_t speech_voice_path(const char* set, const char* word, char* out, size_t out_size) {
    static const char hex[] = "0123456789abcdef";
    size_t n = strlen(word);
    if(n == 0) return 0;
    size_t dir = speech_voice_set_file(set, "", out, out_size);
    if(dir == 0) return 0;
    size_t need = dir + 4 + n + 4 + 1; // "/hh/" name ".raw" NUL
    if(need > out_size) {
        out[0] = '\0';
        return 0;
    }
    uint32_t bucket = speech_voice_hash(word) % SPEECH_VOICE_BUCKETS;
    char* p = out + dir;
    *p++ = '/';
    *p++ = hex[(bucket >> 4) & 0xf];
    *p++ = hex[bucket & 0xf];
    *p++ = '/';
    memcpy(p, word, n);
    p += n;
    memcpy(p, ".raw", 4);
    p += 4;
    *p = '\0';
    return (size_t)(p - out);
}
```

- [ ] **Step 4: Run the host test, then the whole runner**

The compile line from step 1 must now build and `/tmp/t_sv` print its summary with 0 failures; then `tools/run_host_tests.sh` is green. The firmware does not build yet (`speech.c` still calls the old signature): that is Task 3's first step, so do not run `./fbt` here. Commit in the firmware and the project:

```bash
cd Momentum-Firmware
git commit -m "The clip path builder takes a voice set: one folder per set under /ext/sr/voices" -- applications/services/screen_reader/speech_voice.h applications/services/screen_reader/speech_voice.c
git push origin screen-reader
cd ..
git add Momentum-Firmware tests/host/test_speech_voice.c
git commit -m "Host test of the clip paths with voice sets; firmware pointer" -- Momentum-Firmware tests/host/test_speech_voice.c
git push
```

(The continuous build will fail on this pointer, since the firmware does not link until Task 3; that is expected and Task 3's push turns it green.)

---

### Task 3: The engine resolves a set; the setting, the console, the reader

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/speech.h`, `speech.c`, `screen_reader.c`, `screen_reader_cli.c`
- Modify: `Momentum-Firmware/lib/momentum/settings.h`, `settings.c`

**Interfaces:**
- Consumes: Task 2's builder functions.
- Produces: `void speech_set_voice_set(Speech*, const char* set)`; `SpeechVoiceStats.set[SPEECH_VOICE_SET_MAX]` (the set in use, empty when none) and `SpeechVoiceStats.wanted[SPEECH_VOICE_SET_MAX]` (the saved name, empty for "first found"); `size_t speech_voice_sets(Speech*, void (*fn)(const char* name, void* context), void* context)`; the setting `momentum_settings.sr_voice_set` (`char[SR_VOICE_SET_LEN]`, `SR_VOICE_SET_LEN 32`, default `""`); console commands `sr voice list`, `sr voice use <set>`, and `sr voice status` naming the set. Task 4 uses the setting; Task 6 uses the console commands.

- [ ] **Step 1: The setting**

`lib/momentum/settings.h`: `#define SR_VOICE_SET_LEN 32` near `ASSET_PACKS_NAME_LEN`, and in the struct after `sr_change_ms`: `char sr_voice_set[SR_VOICE_SET_LEN]; // the recorded voice set on the card, empty: the first found`. `settings.c`: the default `.sr_voice_set = "",` beside the other reader defaults, and the entry `{setting_str(sr_voice_set)},` after `sr_change_ms`.

- [ ] **Step 2: The engine**

`speech.h`: in `SpeechVoiceStats` add `char set[32]; /**< the set in use, empty when none was found */` and `char wanted[32]; /**< the set asked for, empty for the first found */` (32 is `SPEECH_VOICE_SET_MAX`; `speech.h` does not include `speech_voice.h`, so write the number with a comment naming the constant, and add `_Static_assert` in `speech.c` that the two agree). Declare:

```c
/** Use the voice set of that name, a folder under /ext/sr/voices, from the next utterance on.
 *  An empty name, or a name whose folder the card lacks, means the first set found in name
 *  order; with no set at all the engine is silent, as without a card. Takes the mutex briefly;
 *  callers are threads. The name is cut at 31 characters. */
void speech_set_voice_set(Speech* speech, const char* set);

/** The sets on the card: fn(name, context) for every folder under /ext/sr/voices, in the
 *  order the card lists them, names cut at 31 characters. Returns the count. Any thread; opens
 *  its own directory handle. */
size_t speech_voice_sets(Speech* speech, void (*fn)(const char* name, void* context), void* context);
```

`speech.c`: replace `SPEECH_VOICE_MISSING_PATH` and `SPEECH_VOICE_SETTINGS_PATH` with per-set paths built by `speech_voice_set_file(set, "missing.txt", ...)` and `(set, "voice.txt", ...)` into `speech->path`. State: `char wanted_set[SPEECH_VOICE_SET_MAX]` (written under the mutex by `speech_set_voice_set`, with a `volatile bool set_changed` flag), and `char set[SPEECH_VOICE_SET_MAX]` (the set in use, worker only). At the start of every item (before `speech_voice_ready`), the worker takes the mutex, and if `set_changed`, copies `wanted_set` into a worker-side `wanted` copy, clears the flag and sets `vocabulary = false` so the set is resolved again. `speech_voice_ready` resolves: with the card mounted, if `wanted` is non-empty and its folder exists, `set` is `wanted`; otherwise `set` is the folder under `SPEECH_VOICE_SETS_DIR` with the smallest name by `strcmp` (open the directory with `storage_dir_open`, read entries with `storage_dir_read`, keep directories whose name does not start with `.`); with no folder at all, `set` is empty, `vocabulary` stays false and the item completes silently as today. When a set is resolved, `voice.txt` of that set is read into `voice_settings` as before. `speech_write_missing` writes to the set's `missing.txt`. The two `speech_voice_path` calls pass `speech->set`. `speech_get_voice_stats` copies `set` and `wanted` (the snapshot rule in the comment there applies: the worker writes them one byte at a time, so a torn read shows at worst a mixed name in a status line). `speech_alloc` starts with both names empty. `speech_voice_sets` opens the directory itself with a directory handle allocated for the call, so the worker's file handle is untouched.

- [ ] **Step 3: The reader pushes the setting**

`screen_reader.c`: beside `sr_push_volume` add `sr_push_voice_set` calling `speech_set_voice_set(sr->speech, momentum_settings.sr_voice_set)`, and call it wherever `sr_push_volume` is called (the engine ignores an unchanged name after a `strcmp`, so this costs a string compare per announcement).

- [ ] **Step 4: The console**

`screen_reader_cli.c`: the `voice` command gains `list` and `use <set>`; the usage line becomes `voice on|off|status|list|use <set>  recorded word clips from the card; off mutes speech until on or a reboot; use picks the set (saved)`. `sr voice list` prints one line per set from `speech_voice_sets`, the set in use marked `(in use)`, then `none found` when the count is 0. `sr voice use <name>`: `auto` clears the setting (empty), otherwise the name must pass `speech_voice_set_valid` and its folder must exist (`storage_dir_exists` through a storage record opened for the call), else print `no such voice set: <name>`; on success `strlcpy` into `momentum_settings.sr_voice_set`, `momentum_settings_save()`, `speech_set_voice_set`, and print `voice set: <name>` (or `voice set: auto, the first found`). `sr_cli_print_voice` prints `set <name>` (or `set none`) right after the vocabulary word, before the settings line, and adds `wanted <name>` after it when the wanted set differs from the one in use.

- [ ] **Step 5: Build, headroom, host tests, commit**

```bash
cd Momentum-Firmware && rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps && ./fbt COMPACT=1 DEBUG=0 2>&1 | tail -3 && cd ..
tools/flash_headroom.sh
tools/run_host_tests.sh
```

Expected: no warning, the image below the limit (record the spare), the runner green. Commit in the firmware with pathspec `-- applications/services/screen_reader/speech.h applications/services/screen_reader/speech.c applications/services/screen_reader/screen_reader.c applications/services/screen_reader/screen_reader_cli.c lib/momentum/settings.h lib/momentum/settings.c`, message "The engine speaks from a chosen voice set, or the first on the card; sr voice list and use; the setting", push `origin screen-reader`, then the pointer commit in the project and `git push`. The continuous build must go green on it.

---

### Task 4: The Voice row in the Accessibility screen

**Files:**
- Modify: `Momentum-Firmware/applications/main/momentum_app/momentum_app.h`, `momentum_app.c`, `scenes/momentum_app_scene_accessibility.c`

**Interfaces:**
- Consumes: `momentum_settings.sr_voice_set`, `SR_VOICE_SET_LEN`.
- Produces: a row "Voice" between "Screen Reader" and "Volume", cycling through the sets found on the card.

- [ ] **Step 1: The list of sets in the app**

`momentum_app.h`: `CharList_t voice_set_names;` and `uint8_t voice_set_index;` beside the asset pack fields. `momentum_app.c`, in `momentum_app_alloc` right after the asset pack scan: the same scan over `/ext/sr/voices` (directories whose name does not start with `.` and is at most 31 characters long, the same names the engine's own listing keeps; the read buffer is 33 bytes so a longer name shows as 32 characters and is skipped), inserted in case-insensitive order, and `voice_set_index` set to the position of `momentum_settings.sr_voice_set` in the list, or 0 when the setting is empty or not found (the first name, which is what the engine's fallback uses). Free the list in `momentum_app_free` like the asset pack names.

- [ ] **Step 2: The row**

In `momentum_app_scene_accessibility.c`: an enum value `VarItemListIndexVoice` after `VarItemListIndexScreenReader`, and the row added right after "Screen Reader":

```c
static void momentum_app_scene_accessibility_voice_changed(VariableItem* item) {
    MomentumApp* app = variable_item_get_context(item);
    if(CharList_size(app->voice_set_names) == 0) return;
    uint8_t index = variable_item_get_current_value_index(item);
    const char* name = *CharList_get(app->voice_set_names, index);
    variable_item_set_current_value_text(item, name);
    strlcpy(momentum_settings.sr_voice_set, name, SR_VOICE_SET_LEN);
    app->voice_set_index = index;
    app->save_settings = true;
}
```

and in `on_enter`:

```c
    size_t voice_sets = CharList_size(app->voice_set_names);
    item = variable_item_list_add(
        var_item_list,
        "Voice",
        voice_sets ? voice_sets : 1,
        momentum_app_scene_accessibility_voice_changed,
        app);
    variable_item_set_current_value_index(item, voice_sets ? app->voice_set_index : 0);
    variable_item_set_current_value_text(
        item, voice_sets ? *CharList_get(app->voice_set_names, app->voice_set_index) : "None");
```

The reader announces the row like any other, and since it pushes the setting before each announcement, the new value is spoken in the new voice.

- [ ] **Step 3: Build, headroom, commit**

Build as in Task 3 step 5, check the headroom and the runner, commit in the firmware with the three paths, message "A Voice row in the Accessibility settings picks the recorded voice set on the card", push, pointer commit, push. The continuous build must go green.

---

### Task 5: The generator: sets, and the Kokoro and eSpeak backends beside `say`

**Files:**
- Modify: `tools/voice_build.py`, `.gitignore` (add `voices/`), `tools/run_host_tests.sh`
- Create: `tests/fbt/test_voice_build.py`, `requirements.txt`

**Interfaces:**
- Produces: `voice_build.set_valid(name)`, `voice_build.set_local_dir(name)`, `voice_build.set_card_dir(name)`, `voice_build.BACKENDS`, `voice_build.settings_for(backend, overrides)`, `voice_build.settings_line(settings)`, `voice_build.resample(x, src_hz, hz)`; the command line `--set NAME --backend say|espeak|kokoro --voice V [--rate N --highpass F --gain F --soft/--no-soft]`, `--migrate-sets`; the routine command per set. Task 6 and 7 run it; Task 8 reads the set's manifest and `voice.txt`.

- [ ] **Step 1: The test first**

Create `tests/fbt/test_voice_build.py`:

```python
#!/usr/bin/env python3
"""tools/voice_build.py's pure helpers: set names, the local and card folders of a set, the
per-backend settings and their line for voice.txt, the resampler's length and level. Importable
without pyserial, numpy or the engines (they are imported where they are used). Run from the
project root: python3 tests/fbt/test_voice_build.py"""
import math
import os
import sys

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

try:
    import numpy as np
except ImportError:
    print("skipped the resampler checks: no numpy")
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
```

Run it: it fails at the first missing helper (`AttributeError`).

- [ ] **Step 2: The generator**

Rework `tools/voice_build.py` as follows; keep everything not named here as it is (word extraction, the pronunciation layer, names, the manifest logic, the sync guard, `--card-apps`, `--check`, `--dry`, `--limit`, `--jobs`).

Module docstring: rewrite the parts that describe the card layout, the backends and the routine to the new design, in the same voice as the current text (the command lines below). Constants and helpers, near the top:

```python
HZ = 16000
SETS_DIR = "/ext/sr/voices"
BACKENDS = {
    "say": dict(voice="Samantha", rate=175, highpass=500.0, gain=1.3, soft=True),
    "espeak": dict(voice="en-us+f3", rate=160, highpass=500.0, gain=1.3, soft=True),
    "kokoro": dict(voice="af_heart", rate=100, highpass=500.0, gain=1.3, soft=True),
}
KOKORO_MODEL = os.path.join(ROOT, "voice-models", "kokoro-v1.0.onnx")
KOKORO_VOICES = os.path.join(ROOT, "voice-models", "voices-v1.0.bin")


def set_valid(name):
    """A set name the card, the settings and the console accept: 1 to 31 characters of lower
    case letters, digits, hyphen and underscore; "auto" is reserved for the first set found."""
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
```

`settings_hash` stays as it is (it hashes every key of the settings, so the checksum takes part). The test's kokoro settings call `file_sha256` on the model files, which exist here; on the continuous build they are missing and hash to `"missing"`, which is fine for the tests.

Backends, replacing `synth_piper`:

```python
def synth_say(text, voice, rate, path):
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", path, "--file-format=WAVE",
                    "--data-format=LEI16@%d" % HZ, text], check=True)


def synth_espeak(text, voice, rate, path):
    subprocess.run(["espeak-ng", "-v", voice, "-s", str(rate), "-w", path, text], check=True, capture_output=True)


_kokoro = None


def kokoro_init(model, voices):
    """Pool initializer: one model per worker process (the model is 325 MB; four workers fit)."""
    global _kokoro
    from kokoro_onnx import Kokoro
    _kokoro = Kokoro(model, voices)


def synth_kokoro(text, voice, rate):
    """Float samples at the model's rate; the voice's first letter picks the accent (a: US, b: British)."""
    lang = "en-gb" if voice.startswith("b") else "en-us"
    samples, hz = _kokoro.create(text, voice=voice, speed=rate / 100.0, lang=lang)
    return samples, hz
```

`make_clip(job)` chooses by `settings["backend"]`: `say` writes a 16 kHz WAV and reads it with `read_wav`; `espeak` writes its WAV, reads it with `read_wav` and resamples to `HZ`; `kokoro` gets the array and resamples; then the processing as today (`highpass`, `finish`, `trim`, `pad`, `to_u8`), converting a numpy array to a list where the helpers need one. The pool is created with `multiprocessing.get_context("spawn").Pool(a.jobs, initializer=kokoro_init, initargs=(model, voices))` for kokoro and plainly otherwise.

Sets on the command line and on the card: `--set NAME` (default `samantha`), validated with `set_valid`; `--out` is removed (the set decides the directory); `--backend`, `--voice`, `--rate`, `--highpass`, `--gain`, `--soft/--no-soft` (defaults `None`, so the backend's defaults apply through `settings_for`); `--model` and `--voices-file` for kokoro. The manifest of a set (`<dir>/manifest.json`) gains `"set"` and `"settings"` beside `"words"`. `voice.txt` in the set's directory holds `settings_line`. `--sync` uploads to `set_card_dir(set)` (its 64 folders, its `voice.txt`), the sync guard unchanged; `--pull-missing` reads and clears `set_card_dir(set) + "/missing.txt"`; `--sync-all` as before. `--remove-legacy` goes (that layout is long gone).

`--migrate-sets`: with the storage open, `storage.mkdir(SETS_DIR)` if missing, then `storage.send_and_wait_prompt('storage rename "/ext/sr/voice" "/ext/sr/voices/samantha"\r')` when `/ext/sr/voice` exists and the new folder does not, then the same for `/ext/sr/missing.txt` to `/ext/sr/voices/samantha/missing.txt` when present; print what was moved; refuse with a sentence when the destination exists. Check the reply with `storage.has_error`.

The routine command in the docstring becomes `.venv/bin/python tools/voice_build.py --set samantha --extract --card-apps --pull-missing --sync` and, for the other sets, `--set heart --backend kokoro ...` and `--set espeak --backend espeak ...`.

`requirements.txt` at the project root:

```
pyserial
numpy
scipy
kokoro-onnx
```

with a comment line that eSpeak-NG comes from the system's package manager and `say` from macOS. `.gitignore` gains `voices/`.

- [ ] **Step 3: Tests, a check of each backend, commit**

```bash
python3 tests/fbt/test_voice_build.py
.venv/bin/python tools/voice_build.py --set samantha --check
.venv/bin/python tools/voice_build.py --set trial-espeak --backend espeak --check
.venv/bin/python tools/voice_build.py --set trial-heart --backend kokoro --check --jobs 2
.venv/bin/python tools/voice_build.py --set samantha --dry
```

Expected: the test green; `--check` makes ten clips with each backend and verifies them (it must report the kokoro workers loading the model once each); `--dry` reports the Samantha set's word count as before (the routine's `--extract --card-apps` needs the device, so `--dry` without them counts the lists only). Add the test's block to `tools/run_host_tests.sh`, run the runner, commit with pathspec `-- tools/voice_build.py tests/fbt/test_voice_build.py tools/run_host_tests.sh requirements.txt .gitignore`, message "The generator makes voice sets with Kokoro, eSpeak-NG or the macOS voices", push.

---

### Task 6: On the device: the firmware with sets, Samantha moved, and the tuning clips

**Files:**
- Create: `docs/measurements/2026-09-26-plan-b.txt` (started here, finished in Task 7)

**Interfaces:**
- Consumes: Tasks 3 to 5.
- Produces: Robin's card in the new layout with the `samantha` set in use; a trial folder `/ext/sr/trial/` with Kokoro heart clips at several settings for the listening session; after this task the controller stops the plan for the session.

- [ ] **Step 1: Flash**

The flash routine: `rm -rf Momentum-Firmware/build`, `./fbt COMPACT=1 DEBUG=0 updater_package` in the submodule, `tools/flash_headroom.sh` (record it), `./fbt COMPACT=1 DEBUG=0 flash_usb_full`, wait for the port (up to ten minutes), then `sr screen` before any key, `info device` (hash equals the firmware HEAD, dirty false, origin Sonar), `sysctl debug 1`, `sysctl log_level debug`, `tools/card_prune.py`.

- [ ] **Step 2: Expect silence, then migrate**

Right after the flash the card still holds the old layout, so `sr voice status` shows `vocabulary no` and `set none`: the engine reads only `/ext/sr/voices`. Then:

```bash
.venv/bin/python tools/voice_build.py --set samantha --migrate-sets
.venv/bin/python tools/flipper_cli.py "storage list /ext/sr" "storage list /ext/sr/voices" "storage list /ext/sr/voices/samantha" "sr voice list" "sr say Home screen" "sr voice status"
```

Expected: `/ext/sr` holds `voices` (and no `voice`); `/ext/sr/voices` holds `samantha`; that folder holds the 64 clip folders and `voice.txt`; `sr voice list` prints `samantha (in use)` after the utterance resolved it (run `sr voice list` again after `sr say` if the first listing came before any utterance); `sr say` is heard in Samantha; the status shows `vocabulary yes set samantha` and the Samantha settings line. Then `sr voice use samantha` (prints `voice set: samantha`, saved), `sr voice use nosuch` (refused), `sr voice use auto`, and `sr voice use samantha` again to leave the setting explicit. Run `tools/sr_drive.py --chords`: no failures.

- [ ] **Step 3: The tuning clips**

Make the same twelve words with the kokoro backend at three processing settings into a trial folder, so the listening session can compare them through the piezo: the words `settings, sub, gigahertz, apps, one, of, eleven, battery, hundred, percent, frequency, analyzer`; the settings A: highpass 500, gain 1.3, soft (today's); B: highpass 300, gain 1.3, soft; C: highpass 500, gain 1.6, soft; D: highpass 800, gain 1.3, soft. For each, run the generator into a throwaway set (`--set trial-a` and so on, with `--words` pointing at a temporary word list of those twelve words and no `--extract`), then concatenate the twelve clips with 150 ms of silence (128) into one raw file `voice-samples/trial/kokoro-heart-<letter>.raw`, and send the four files to `/ext/sr/trial/` on the card with the storage script. Do not play them. Delete the throwaway sets' local folders under `voices/` afterwards.

- [ ] **Step 4: Record, commit, and stop**

Start `docs/measurements/2026-09-26-plan-b.txt` with the headroom line, the `info device` block, the listings of step 2 and the console replies, the trial files' names and settings. Commit it and push. Then report to the controller: the plan pauses here for Robin's listening session; the controller plays `/ext/sr/trial/kokoro-heart-a.raw` to `-d.raw` with `sr play <path> 16000`, names each, and Robin picks the settings for the Kokoro set.

---

### Task 7: The heart and espeak sets on Robin's card

Amended after the listening session: Robin chose the settings A (today's Kokoro defaults), and
asked for the sets to go onto the card through the Mac's card reader instead of the console,
which takes a minute instead of an hour. The controller generates both sets on the Mac (the
two `--extract --card-apps` runs without `--sync`), Task 8's pack tool writes each set in the
card's layout, and the copy happens when Robin puts the card in the reader. What remains for an
implementer is the verification on the device and the record.

**Files:**
- Modify: `docs/measurements/2026-09-26-plan-b.txt`

**Interfaces:**
- Consumes: the sets `heart` and `espeak` on the card (copied from the packs of Task 8), the generator's `--mark-synced` (Task 8), the console commands of Task 3.
- Produces: both sets verified on the device; the trial folder removed; the record.

- [ ] **Step 1: After the copy, mark both sets as synced**

```bash
.venv/bin/python tools/voice_build.py --set heart --mark-synced
.venv/bin/python tools/voice_build.py --set espeak --mark-synced
```

so a later routine run sends only what changes.

- [ ] **Step 2: Each set on the device**

With the card back in the device and the device on its home screen: `sr voice list` shows
`espeak`, `heart`, `samantha (in use)`; then for each of `heart` and `espeak`: `sr voice use
<set>`, `sr say Home screen. Apps, one of eleven. Battery one hundred percent.`, `sr voice
status` (the set, its settings line, `open max`), `sr status` (no underruns), and the chord
routine `tools/sr_drive.py --chords` with the set in use. Then `sr voice use samantha`.

- [ ] **Step 3: The trial folder, the measurements, the commit**

Remove `/ext/sr/trial` and its four files from the card. Append to the measurements file: the
counts and times of each generation (from the controller's log), the pack sizes, the status
lines of each set, `sr voice list`, the free heap, the chord results. Commit the file and push.

### Task 8: `tools/voice_pack.py` and its test

**Files:**
- Create: `tools/voice_pack.py`, `tests/fbt/test_voice_pack.py`
- Modify: `tools/run_host_tests.sh`

**Interfaces:**
- Consumes: a set's local directory with `manifest.json` and `voice.txt` from Task 5.
- Produces: `tools/voice_pack.py --set NAME --version X.Y.Z [--out DIR]` writing `voice-<set>-sonar-X.Y.Z.tar`; `voice_pack.licence_text(settings)`; `voice_pack.pack(set_dir, set_name, version, out_path)`; and in `tools/voice_build.py` the flag `--mark-synced`, which writes the set's `synced.json` from its manifest (every word's current hash), for a set that reached the card by other means than `--sync` (the card reader), with a test in `tests/fbt/test_voice_build.py` through a pure helper.

- [ ] **Step 1: The test first**

Create `tests/fbt/test_voice_pack.py`: it builds a throwaway set directory under a temporary folder with `manifest.json` (`{"set": "heart", "settings": {"backend": "kokoro", "voice": "af_heart", ...}, "words": {"a": "x"}}`), `voice.txt`, and two clip files under two hashed folders (`00/a.raw`, `3f/b.raw`); calls `pack(set_dir, "heart", "0.1.0", out)`; checks with `tarfile` that the archive holds exactly `sr/voices/heart/voice.txt`, `sr/voices/heart/LICENSE.txt`, `sr/voices/heart/00/a.raw`, `sr/voices/heart/3f/b.raw`, in that order sorted, with the clip bytes intact and no `manifest.json` or `synced.json`; that `LICENSE.txt` names Kokoro, Apache 2.0 and the voice; that a set whose backend is `say` is refused by `pack` (raises `SystemExit` with a sentence about Apple's licence) unless `personal=True`; that `licence_text` for espeak names eSpeak-NG and GPL-3; that a missing `voice.txt` is refused. Counts dynamic, the summary line `voice pack: N of N checks passed`. Run it: `ModuleNotFoundError`.

- [ ] **Step 2: The tool**

Create `tools/voice_pack.py`:

```python
#!/usr/bin/env python3
"""Write a voice set as a release asset: voice-<set>-sonar-<version>.tar.

    tools/voice_pack.py --set NAME --version X.Y.Z [--out DIR] [--personal]

The tar holds sr/voices/<set>/voice.txt, sr/voices/<set>/LICENSE.txt and the clips in their
64 hashed folders, nothing else (the manifest and the sync record are the generator's). It is a
plain tar, uncompressed: 8-bit PCM compresses poorly, and the device's tar library can unpack it.
A set made with the macOS voices is refused, since Apple licenses them for use on the Mac;
--personal writes it anyway, for a backup of one's own device. The licence text names the
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
from voice_build import bucket, initial, set_local_dir, set_valid  # noqa: E402

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


def pack(set_dir, set_name, version, out_path, personal=False):
    manifest_path = os.path.join(set_dir, "manifest.json")
    voice_txt = os.path.join(set_dir, "voice.txt")
    if not os.path.exists(manifest_path) or not os.path.exists(voice_txt):
        sys.exit(f"{set_dir}: no manifest.json or voice.txt; make the set first")
    with open(manifest_path, encoding="utf-8") as f:
        settings = json.load(f)["settings"]
    if settings["backend"] == "say" and not personal:
        sys.exit("a set made with the macOS voices is for the maker's device only (Apple's licence); --personal packs it anyway")
    prefix = f"sr/voices/{set_name}"
    with open(manifest_path, encoding="utf-8") as f:
        words = sorted(json.load(f)["words"])
    with tarfile.open(out_path, "w") as tar:
        tar.add(voice_txt, arcname=f"{prefix}/voice.txt")
        info = tarfile.TarInfo(f"{prefix}/LICENSE.txt")
        data = licence_text(settings).encode("utf-8")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
        count = 0
        # On the Mac a set keeps its clips under voice/<initial>/<word>.raw; the card and the
        # pack use the 64 hashed folders the firmware looks in, the same as the sync does
        for word in words:
            local = os.path.join(set_dir, initial(word), word + ".raw")
            if not os.path.exists(local):
                sys.exit(f"{local}: the manifest names a clip that is not on disk; run the generator")
            tar.add(local, arcname=f"{prefix}/{bucket(word)}/{word}.raw")
            count += 1
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
    out_path = os.path.join(a.out, f"voice-{a.set}-sonar-{a.version}.tar")
    count = pack(set_local_dir(a.set), a.set, a.version, out_path, a.personal)
    print(f"{out_path}: {count} clips, {os.path.getsize(out_path)} bytes")


if __name__ == "__main__":
    main()
```

The clips on disk sit in the generator's `<initial>/` folders (`voice/s/settings.raw`), the pack puts them in the card's hashed folders (`voice_build.bucket(word)`, the same FNV-1a modulo 64 as the sync), so the test's throwaway set lays its two clips out as `a/a.raw` and `b/b.raw` on disk and expects `sr/voices/heart/<bucket(a)>/a.raw` and `.../<bucket(b)>/b.raw` in the archive, computing the buckets with `voice_build.bucket`. `initial(word)` and `bucket(word)` exist in `tools/voice_build.py` already.

- [ ] **Step 3: Test, a real pack, commit**

`python3 tests/fbt/test_voice_pack.py` green; then `.venv/bin/python tools/voice_pack.py --set heart --version 0.0.0-trial --out /tmp` and `tar -tf /tmp/voice-heart-sonar-0.0.0-trial.tar | head` (the layout as specified) and `python3 tools/voice_pack.py --set samantha --version 0.0.0-trial --out /tmp` refused. Delete the trial tars. Add the test to the runner, commit with pathspec `-- tools/voice_pack.py tests/fbt/test_voice_pack.py tools/run_host_tests.sh`, message "voice_pack: a voice set as a release asset with its licence", push.

---

### Task 9: The documentation

**Files:**
- Modify: `README.md`, `docs/device-notes.md`, `docs/roadmap.md`, `docs/README.md`

- [ ] **Step 1: The README's voice section**

Rewrite "The voice" for the sets: several vocabularies can live on the card, one folder each under `/ext/sr/voices`; the Voice row in the Accessibility settings switches between them, and so do `sr voice list` and `sr voice use <name>` on the console; the reader uses the first set found when none is chosen. The release ships two sets, heart (Kokoro, the default) and espeak (eSpeak-NG, small and quick); a personal set can be made with the macOS voices for one's own device. The generator's commands, one code block each: the routine for a set, a Kokoro set, an eSpeak set, a `say` set; the requirements (`requirements.txt`, eSpeak-NG from the system's package manager, `say` on macOS); the licensing paragraph (Kokoro Apache 2.0, eSpeak-NG GPL-3, Apple's voices for personal use). Keep the missing-words mechanism, now per set. "What changed against Momentum" gains the voice sets in one sentence.

- [ ] **Step 2: The device notes**

The routine section: the generator's routine per set, the migration done on 2026-09-26, the three sets on Delphi's card and which is in use, the pack command. "Device state": the firmware line for the flashed build, the card layout. `docs/roadmap.md`: the 2026-09-26 status paragraph says plan B is done and names the sets. `docs/README.md`: the new plan and measurements file.

- [ ] **Step 3: Check and commit**

```bash
grep -n -i "r0skie\|delphi\|usbmodem" README.md || echo "public README clean"
grep -c "^|" README.md docs/device-notes.md docs/roadmap.md docs/README.md
tools/run_host_tests.sh
git add README.md docs/device-notes.md docs/roadmap.md docs/README.md
git commit -m "Documentation of the voice sets: the Voice row, the console commands, the generator for Kokoro, eSpeak-NG and the macOS voices" -- README.md docs/device-notes.md docs/roadmap.md docs/README.md
git push
```
