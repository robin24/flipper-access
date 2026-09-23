# Recorded Voice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The screen reader speaks with recorded word clips from the SD card (macOS Samantha by default, any voice through a generator script), falling back to SAM only for words the vocabulary lacks, and logs those words so the vocabulary can grow.

**Architecture:** A pure C module `speech_voice` maps the pronunciation layer's word stream to clip paths and pauses and remembers missing words; the speech worker plays clips through the existing `speech_pcm_push_raw` path word by word and speaks missing words with SAM; a Python generator builds the vocabulary from the firmware's own strings run through the real pronunciation layer, and syncs only new clips to the card.

**Tech Stack:** Momentum firmware (fbt, GCC 12, -Wall -Wextra -Werror), C11 host tests with clang and sanitizers, Python 3 with the project venv (pyserial) and the firmware's `scripts/flipper/storage.py`, macOS `say`, optional Piper.

**Spec:** docs/superpowers/specs/2026-09-24-clip-voice-design.md (binding); the phase 2 engine is described in docs/superpowers/plans/2026-09-23-screen-reader-phase-2-speech.md and its build log.

## Global Constraints

- Firmware repo /Users/robin/Downloads/flipper-access/Momentum-Firmware, branch screen-reader (head 54794522b at plan time); project repo /Users/robin/Downloads/flipper-access, main. Commit only your own files with explicit `git add`; never a plain `git commit -a`; do not push; never commit inside the submodule applications/external.
- The firmware image must stay under 880,640 bytes: run `tools/flash_headroom.sh` after every firmware build and report the spare bytes (10,884 at plan time).
- Host tests: `TMPDIR=<private dir> tools/run_host_tests.sh` must stay green; new tests are built with the runner's CFLAGS plus `-fsanitize=address,undefined -fno-sanitize-recover=all`.
- Device: /dev/cu.usbmodemflip_R0skie1, use `.venv/bin/python tools/flipper_cli.py "<command>"` for console commands and `.venv/bin/python Momentum-Firmware/scripts/storage.py -p /dev/cu.usbmodemflip_R0skie1 send <local> <remote>` for uploads; never send `loader close`; after every flash wait for the port and run `sr screen` first; on a crash popup stop and report BLOCKED with the exact output. Leave the device idle on the home screen, reader on, speech idle.
- Clip format: raw unsigned 8-bit PCM mono at 16,000 samples per second, 128 is silence. Clip path: `/ext/sr/voice/<initial>/<word>.raw`, `<initial>` the first character (a–z, 0–9, else `_`), `<word>` lower case letters and digits, at most 31 characters. Pauses: 40 ms between words, 150 ms after a comma, 300 ms after a period, question or exclamation mark.
- Generator defaults (Robin's choice): backend `say`, voice Samantha, rate 175, high-pass 500 Hz, gain 1.3, tanh limiter on, 16,000 Hz.
- Commit messages end with a blank line and the Co-Authored-By line your own attribution guidance gives you.

---

### Task 1: The voice module (pure C) and its host test

**Files:**
- Create: `Momentum-Firmware/applications/services/screen_reader/speech_voice.h`, `speech_voice.c`
- Create: `tests/host/test_speech_voice.c`
- Modify: `tools/run_host_tests.sh` (append a block after the speech PCM block)

**Interfaces:**
- Consumes: nothing from other tasks.
- Produces: `bool speech_voice_next_word(const char* text, size_t* pos, SpeechVoiceWord* out)`, `size_t speech_voice_path(const char* word, char* out, size_t out_size)`, `SpeechVoiceState` with `speech_voice_state_init`, `bool speech_voice_missing(SpeechVoiceState*, const char* word)`, `size_t speech_voice_log_count(const SpeechVoiceState*)`, `const char* speech_voice_log_word(const SpeechVoiceState*, size_t index)`, `void speech_voice_log_clear(SpeechVoiceState*)`, and the constants below. Task 2 uses all of them.

- [ ] **Step 1: Write the failing test**

Create `tests/host/test_speech_voice.c`:

```c
#include <stdio.h>
#include <string.h>
#include "speech_voice.h"

static int failures = 0;
static int checks = 0;
#define CHECK(cond)                                                     \
    do {                                                                \
        checks++;                                                       \
        if(!(cond)) {                                                   \
            failures++;                                                 \
            printf("FAIL line %d: %s\n", __LINE__, #cond);              \
        }                                                               \
    } while(0)

static void expect_word(const char* text, size_t* pos, const char* word, unsigned pause) {
    SpeechVoiceWord w;
    memset(&w, 0x55, sizeof(w));
    bool got = speech_voice_next_word(text, pos, &w);
    checks++;
    if(!got || strcmp(w.word, word) != 0 || w.pause_ms != pause) {
        failures++;
        printf("FAIL next_word(\"%s\") got %s \"%s\" %u, want \"%s\" %u\n", text,
               got ? "true" : "false", w.word, (unsigned)w.pause_ms, word, pause);
    }
}

static void test_words(void) {
    const char* text = "Sub gigahertz. Apps, one of eleven! U I D, zero four? end";
    size_t pos = 0;
    expect_word(text, &pos, "sub", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "gigahertz", SPEECH_VOICE_STOP_MS);
    expect_word(text, &pos, "apps", SPEECH_VOICE_COMMA_MS);
    expect_word(text, &pos, "one", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "of", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "eleven", SPEECH_VOICE_STOP_MS);
    expect_word(text, &pos, "u", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "i", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "d", SPEECH_VOICE_COMMA_MS);
    expect_word(text, &pos, "zero", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "four", SPEECH_VOICE_STOP_MS);
    expect_word(text, &pos, "end", SPEECH_VOICE_GAP_MS);
    SpeechVoiceWord w;
    CHECK(speech_voice_next_word(text, &pos, &w) == false);
    CHECK(speech_voice_next_word(text, &pos, &w) == false); // stays at the end

    // Punctuation on its own is a pause without a word; leading punctuation is stripped
    pos = 0;
    expect_word(". five", &pos, "", SPEECH_VOICE_STOP_MS);
    expect_word(". five", &pos, "five", SPEECH_VOICE_GAP_MS);
    pos = 0;
    expect_word(",, x", &pos, "", SPEECH_VOICE_COMMA_MS);
    pos = 0;
    expect_word("  spaced   out  ", &pos, "spaced", SPEECH_VOICE_GAP_MS);
    expect_word("  spaced   out  ", &pos, "out", SPEECH_VOICE_GAP_MS);
    CHECK(speech_voice_next_word("  spaced   out  ", &pos, &w) == false);
    pos = 0;
    CHECK(speech_voice_next_word("", &pos, &w) == false);
    pos = 0;
    CHECK(speech_voice_next_word("   ", &pos, &w) == false);

    // Semicolon and colon pause like a comma; a word is cut at 31 characters
    pos = 0;
    expect_word("a; b: c", &pos, "a", SPEECH_VOICE_COMMA_MS);
    expect_word("a; b: c", &pos, "b", SPEECH_VOICE_COMMA_MS);
    expect_word("a; b: c", &pos, "c", SPEECH_VOICE_GAP_MS);
    const char* longword = "abcdefghijklmnopqrstuvwxyzabcdefghij.";
    pos = 0;
    expect_word(longword, &pos, "abcdefghijklmnopqrstuvwxyzabcde", SPEECH_VOICE_STOP_MS);
    CHECK(pos == strlen(longword));
}

static void test_paths(void) {
    char out[SPEECH_VOICE_PATH_MAX];
    CHECK(speech_voice_path("settings", out, sizeof(out)) == strlen("/ext/sr/voice/s/settings.raw"));
    CHECK(strcmp(out, "/ext/sr/voice/s/settings.raw") == 0);
    CHECK(speech_voice_path("7", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voice/7/7.raw") == 0);
    CHECK(speech_voice_path("ay", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voice/a/ay.raw") == 0);
    CHECK(speech_voice_path("'odd", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voice/_/'odd.raw") == 0);
    CHECK(speech_voice_path("", out, sizeof(out)) == 0);
    CHECK(speech_voice_path("settings", out, 20) == 0);
    // The longest word fits the buffer
    const char* longest = "abcdefghijklmnopqrstuvwxyzabcde";
    CHECK(strlen(longest) == SPEECH_VOICE_WORD_MAX - 1);
    CHECK(speech_voice_path(longest, out, sizeof(out)) == strlen(out));
    CHECK(strlen(out) < SPEECH_VOICE_PATH_MAX);
}

static void test_missing(void) {
    SpeechVoiceState s;
    speech_voice_state_init(&s);
    CHECK(speech_voice_log_count(&s) == 0);
    CHECK(speech_voice_missing(&s, "bahncard") == true);
    CHECK(speech_voice_missing(&s, "bahncard") == false); // once per boot
    CHECK(speech_voice_missing(&s, "") == false);
    CHECK(s.missing_words == 1);
    CHECK(speech_voice_log_count(&s) == 1);
    CHECK(strcmp(speech_voice_log_word(&s, 0), "bahncard") == 0);
    speech_voice_log_clear(&s);
    CHECK(speech_voice_log_count(&s) == 0);
    CHECK(speech_voice_missing(&s, "bahncard") == false); // still remembered after the log

    // The log holds SPEECH_VOICE_LOG_MAX words per utterance; more are not recorded at all,
    // so a later utterance logs them
    char word[16];
    for(int i = 0; i < SPEECH_VOICE_LOG_MAX; i++) {
        snprintf(word, sizeof(word), "w%d", i);
        CHECK(speech_voice_missing(&s, word) == true);
    }
    CHECK(speech_voice_missing(&s, "overflow") == false);
    CHECK(speech_voice_log_count(&s) == SPEECH_VOICE_LOG_MAX);
    speech_voice_log_clear(&s);
    CHECK(speech_voice_missing(&s, "overflow") == true);
    speech_voice_log_clear(&s);

    // The set forgets the oldest word after SPEECH_VOICE_MISSING_SET newer ones
    speech_voice_state_init(&s);
    CHECK(speech_voice_missing(&s, "first") == true);
    speech_voice_log_clear(&s);
    for(int i = 0; i < SPEECH_VOICE_MISSING_SET; i++) {
        snprintf(word, sizeof(word), "n%d", i);
        CHECK(speech_voice_missing(&s, word) == true);
        speech_voice_log_clear(&s);
    }
    CHECK(speech_voice_missing(&s, "first") == true);
    CHECK(s.missing_words == SPEECH_VOICE_MISSING_SET + 2);
}

int main(void) {
    test_words();
    test_paths();
    test_missing();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
```

Append to `tools/run_host_tests.sh` after the speech PCM block (keep the file's style):

```bash
clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_speech_voice" \
  "$TESTS/test_speech_voice.c" "$SRC/speech_voice.c"
if ! "$OUT/test_speech_voice" > "$OUT/speech_voice.txt"; then
  cat "$OUT/speech_voice.txt"
  echo "speech voice checks failed"
  exit 1
fi
echo "speech voice: $(tail -n 1 "$OUT/speech_voice.txt")"
```

- [ ] **Step 2: Run the runner to see it fail**

Run: `cd /Users/robin/Downloads/flipper-access && TMPDIR=<private dir> tools/run_host_tests.sh`
Expected: the speech voice block fails to compile (no speech_voice.h).

- [ ] **Step 3: Write the module**

Create `Momentum-Firmware/applications/services/screen_reader/speech_voice.h`:

```c
/**
 * @file speech_voice.h
 * Recorded voice: maps the words of an expanded announcement to clip files on the card and
 * the pauses between them, and remembers which words the vocabulary lacked. Pure C, host
 * tested; the worker in speech.c does the file and sample work.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPEECH_VOICE_DIR         "/ext/sr/voice"
#define SPEECH_VOICE_WORD_MAX    32 /**< clip name with its terminator */
#define SPEECH_VOICE_PATH_MAX    64 /**< "/ext/sr/voice/x/" + name + ".raw" */
#define SPEECH_VOICE_MISSING_SET 64 /**< words remembered as missing, once per boot each */
#define SPEECH_VOICE_LOG_MAX     8 /**< missing words kept for the log per utterance */
#define SPEECH_VOICE_HZ          16000u
#define SPEECH_VOICE_GAP_MS      40
#define SPEECH_VOICE_COMMA_MS    150
#define SPEECH_VOICE_STOP_MS     300

typedef struct {
    char word[SPEECH_VOICE_WORD_MAX]; /**< lower case clip name, punctuation stripped; empty
                                            when the token was punctuation only */
    uint16_t pause_ms; /**< silence after the word */
} SpeechVoiceWord;

/** The next word of `text` from *pos; false at the end. A token is a run of non-space
 *  characters; its last character decides the pause (period, question and exclamation mark:
 *  stop; comma, semicolon, colon: comma; anything else: gap), then punctuation is stripped
 *  from both ends and the rest lower cased and cut at SPEECH_VOICE_WORD_MAX - 1 characters. */
bool speech_voice_next_word(const char* text, size_t* pos, SpeechVoiceWord* out);

/** The clip path of a word: SPEECH_VOICE_DIR "/<initial>/<word>.raw", the initial being the
 *  word's first character when it is a lower case letter or a digit, '_' otherwise. Returns
 *  the length written, 0 for an empty word or a buffer too small. */
size_t speech_voice_path(const char* word, char* out, size_t out_size);

typedef struct {
    uint32_t hashes[SPEECH_VOICE_MISSING_SET]; /**< ring of words already recorded */
    uint8_t next;
    uint8_t count;
    char log[SPEECH_VOICE_LOG_MAX][SPEECH_VOICE_WORD_MAX]; /**< waiting for the log file */
    uint8_t log_count;
    uint32_t clip_words; /**< words spoken from a clip since boot */
    uint32_t fallback_words; /**< words spoken by SAM since boot */
    uint32_t missing_words; /**< distinct words recorded as missing since boot */
} SpeechVoiceState;

void speech_voice_state_init(SpeechVoiceState* state);

/** Record a missing word. True when it is new this boot and there was room in the log buffer
 *  (the caller writes the buffer to the card after the utterance); false when it was recorded
 *  before, is empty, or the buffer is full, in which case it is not remembered either, so a
 *  later utterance records it. */
bool speech_voice_missing(SpeechVoiceState* state, const char* word);

size_t speech_voice_log_count(const SpeechVoiceState* state);
const char* speech_voice_log_word(const SpeechVoiceState* state, size_t index);
void speech_voice_log_clear(SpeechVoiceState* state);

#ifdef __cplusplus
}
#endif
```

Create `speech_voice.c`:

```c
#include "speech_voice.h"

#include <string.h>

static bool sv_is_space(char c) {
    return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}

static bool sv_is_punct(char c) {
    return c == '.' || c == ',' || c == '?' || c == '!' || c == ';' || c == ':';
}

bool speech_voice_next_word(const char* text, size_t* pos, SpeechVoiceWord* out) {
    size_t i = *pos;
    while(text[i] != '\0' && sv_is_space(text[i])) i++;
    if(text[i] == '\0') {
        *pos = i;
        return false;
    }
    size_t start = i;
    while(text[i] != '\0' && !sv_is_space(text[i])) i++;
    size_t end = i;
    *pos = i;

    char last = text[end - 1];
    if(last == '.' || last == '?' || last == '!') {
        out->pause_ms = SPEECH_VOICE_STOP_MS;
    } else if(last == ',' || last == ';' || last == ':') {
        out->pause_ms = SPEECH_VOICE_COMMA_MS;
    } else {
        out->pause_ms = SPEECH_VOICE_GAP_MS;
    }

    while(start < end && sv_is_punct(text[start])) start++;
    while(end > start && sv_is_punct(text[end - 1])) end--;
    size_t n = end - start;
    if(n > SPEECH_VOICE_WORD_MAX - 1) n = SPEECH_VOICE_WORD_MAX - 1;
    for(size_t k = 0; k < n; k++) {
        char c = text[start + k];
        out->word[k] = (c >= 'A' && c <= 'Z') ? (char)(c - 'A' + 'a') : c;
    }
    out->word[n] = '\0';
    return true;
}

size_t speech_voice_path(const char* word, char* out, size_t out_size) {
    size_t n = strlen(word);
    if(n == 0) return 0;
    char c = word[0];
    char initial = ((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9')) ? c : '_';
    size_t dir = strlen(SPEECH_VOICE_DIR);
    size_t need = dir + 3 + n + 4 + 1; // "/x/" name ".raw" NUL
    if(need > out_size) return 0;
    char* p = out;
    memcpy(p, SPEECH_VOICE_DIR, dir);
    p += dir;
    *p++ = '/';
    *p++ = initial;
    *p++ = '/';
    memcpy(p, word, n);
    p += n;
    memcpy(p, ".raw", 4);
    p += 4;
    *p = '\0';
    return (size_t)(p - out);
}

static uint32_t sv_hash(const char* s) {
    uint32_t h = 2166136261u; // FNV-1a
    while(*s != '\0') {
        h ^= (uint8_t)*s++;
        h *= 16777619u;
    }
    return h;
}

void speech_voice_state_init(SpeechVoiceState* state) {
    memset(state, 0, sizeof(*state));
}

bool speech_voice_missing(SpeechVoiceState* state, const char* word) {
    if(word[0] == '\0') return false;
    uint32_t h = sv_hash(word);
    for(size_t i = 0; i < state->count; i++) {
        if(state->hashes[i] == h) return false;
    }
    if(state->log_count >= SPEECH_VOICE_LOG_MAX) return false;
    state->hashes[state->next] = h;
    state->next = (uint8_t)((state->next + 1) % SPEECH_VOICE_MISSING_SET);
    if(state->count < SPEECH_VOICE_MISSING_SET) state->count++;
    strncpy(state->log[state->log_count], word, SPEECH_VOICE_WORD_MAX - 1);
    state->log[state->log_count][SPEECH_VOICE_WORD_MAX - 1] = '\0';
    state->log_count++;
    state->missing_words++;
    return true;
}

size_t speech_voice_log_count(const SpeechVoiceState* state) {
    return state->log_count;
}

const char* speech_voice_log_word(const SpeechVoiceState* state, size_t index) {
    return index < state->log_count ? state->log[index] : "";
}

void speech_voice_log_clear(SpeechVoiceState* state) {
    state->log_count = 0;
}
```

- [ ] **Step 4: Run the runner to see it pass**

Run the runner again. Expected: `speech voice: N checks, 0 failures` and every earlier block green.

- [ ] **Step 5: Firmware compile check and commit**

Run `cd Momentum-Firmware && ./fbt 2>&1 | grep -E "error|warning|API version" | head` (the module is not referenced yet; it must still compile under the firmware's flags: `./fbt` compiles every source in the service directory). Then:

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/speech_voice.h applications/services/screen_reader/speech_voice.c && git commit -m "screen reader: voice module maps words to clips and remembers missing ones"
cd /Users/robin/Downloads/flipper-access && git add tests/host/test_speech_voice.c tools/run_host_tests.sh && git commit -m "host tests: voice module"
```

---

### Task 2: The worker plays clips, the setting and the console command

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/speech.h`, `speech.c`, `screen_reader.c` (start sequence, after `speech_set_voice`), `screen_reader_cli.c` (usage, status, new `voice` command)
- Modify: `Momentum-Firmware/lib/momentum/settings.h` (field `bool sr_voice;` after `sr_verbosity`), `lib/momentum/settings.c` (default `.sr_voice = true,` and `{setting_bool(sr_voice)},` after the `sr_verbosity` line)

**Interfaces:**
- Consumes: Task 1's module. Existing: `speech_pcm_push_raw`, `speech_emit`, `speech_item_begin/end`, `speech_sam_output`, `sam_speak`, the file buffer and storage record already in `Speech`.
- Produces: `void speech_set_voice_clips(Speech* speech, bool enabled);`, `typedef struct { bool enabled; bool vocabulary; uint32_t clip_words; uint32_t fallback_words; uint32_t missing_words; char settings[64]; } SpeechVoiceStats;`, `void speech_get_voice_stats(Speech* speech, SpeechVoiceStats* out);`; console `sr voice on|off|status`; `sr status` line `voice: on|off, vocabulary yes|no, clips N, fallback M, missing K`; card files `/ext/sr/voice/voice.txt` (read, first line) and `/ext/sr/missing.txt` (appended). Task 3 and 4 rely on these paths and the status wording.

- [ ] **Step 1: The engine**

In `speech.h`, after `speech_set_voice`:

```c
typedef struct {
    bool enabled; /**< recorded clips are used when the vocabulary is present */
    bool vocabulary; /**< /ext/sr/voice was found on the card */
    uint32_t clip_words; /**< words spoken from clips since boot */
    uint32_t fallback_words; /**< words spoken by SAM since boot */
    uint32_t missing_words; /**< distinct words recorded in /ext/sr/missing.txt since boot */
    char settings[64]; /**< first line of /ext/sr/voice/voice.txt, empty when absent */
} SpeechVoiceStats;

/** Recorded voice on or off, from the next utterance on; off means SAM speaks everything. */
void speech_set_voice_clips(Speech* speech, bool enabled);

void speech_get_voice_stats(Speech* speech, SpeechVoiceStats* out);
```

In `speech.c`: include `"speech_voice.h"`; add after the other defines

```c
#define SPEECH_VOICE_HOLD_NS       (1000000000u / SPEECH_VOICE_HZ)
#define SPEECH_VOICE_MISSING_PATH  "/ext/sr/missing.txt"
#define SPEECH_VOICE_SETTINGS_PATH SPEECH_VOICE_DIR "/voice.txt"
```

Add to `struct Speech` (document each group as the existing fields are):

```c
    // Set by any thread, read by the worker
    volatile bool voice_enabled;

    // Worker thread only
    bool vocabulary; /* SPEECH_VOICE_DIR was found on the card */
    char voice_settings[64]; /* first line of voice.txt */
    File* voice_file; /* reused for every clip and the missing log */
    SpeechVoiceState voice;
    char path[SPEECH_VOICE_PATH_MAX];
```

Add these worker functions before `speech_speak_item`:

```c
/**
 * The card mounts after the services start, so the vocabulary is looked for when it is
 * first needed and then remembered. Reads the generator's settings line for sr voice status.
 */
static bool speech_voice_ready(Speech* speech) {
    if(speech->vocabulary) return true;
    if(storage_sd_status(speech->storage) != FSE_OK) return false;
    if(!storage_dir_exists(speech->storage, SPEECH_VOICE_DIR)) return false;
    speech->vocabulary = true;
    File* file = speech->voice_file;
    if(storage_file_open(file, SPEECH_VOICE_SETTINGS_PATH, FSAM_READ, FSOM_OPEN_EXISTING)) {
        size_t n = storage_file_read(file, speech->voice_settings, sizeof(speech->voice_settings) - 1);
        speech->voice_settings[n] = '\0';
        char* nl = strpbrk(speech->voice_settings, "\r\n");
        if(nl) *nl = '\0';
    }
    storage_file_close(file);
    return true;
}

/** Silence of `ms` at the clip sample rate, through the same stage as the clips. */
static bool speech_push_silence(Speech* speech, uint32_t ms) {
    memset(speech->file_buffer, SPEECH_SILENCE_VALUE, SPEECH_FILE_CHUNK);
    uint32_t left = ms * (SPEECH_VOICE_HZ / 1000);
    while(left > 0) {
        size_t n = left < SPEECH_FILE_CHUNK ? left : SPEECH_FILE_CHUNK;
        if(!speech_pcm_push_raw(
               &speech->pcm, speech->file_buffer, n, SPEECH_VOICE_HOLD_NS, speech_emit, speech)) {
            return false;
        }
        left -= n;
    }
    return true;
}

/**
 * One clip from the card. False when the file could not be opened: the word is missing. A
 * superseded utterance ends the clip through speech_emit, which sets aborted, and returns true.
 */
static bool speech_play_clip(Speech* speech, const char* path) {
    File* file = speech->voice_file;
    if(!storage_file_open(file, path, FSAM_READ, FSOM_OPEN_EXISTING)) {
        storage_file_close(file);
        return false;
    }
    while(!speech->aborted) {
        size_t n = storage_file_read(file, speech->file_buffer, SPEECH_FILE_CHUNK);
        if(n == 0) break;
        if(!speech_pcm_push_raw(
               &speech->pcm, speech->file_buffer, n, SPEECH_VOICE_HOLD_NS, speech_emit, speech)) {
            break;
        }
    }
    storage_file_close(file);
    return true;
}

/** A word the vocabulary lacks: SAM speaks it, upper cased with a closing period. */
static void speech_sam_word(Speech* speech, const char* word, const SamVoice* voice) {
    size_t len = strlen(word);
    if(len > sizeof(speech->chunk) - 3) len = sizeof(speech->chunk) - 3;
    for(size_t i = 0; i < len; i++) {
        char c = word[i];
        speech->chunk[i] = (c >= 'a' && c <= 'z') ? (char)(c - 'a' + 'A') : c;
    }
    speech->chunk[len] = '.';
    speech->chunk[len + 1] = '\0';
    len++;
    size_t offset = 0;
    while(offset < len && !speech->aborted) {
        size_t consumed = 0;
        sam_speak(speech->chunk + offset, voice, speech_sam_output, speech, &consumed);
        if(consumed == 0) break;
        offset += consumed;
    }
}

/** The expanded text word by word: a clip when the card has it, SAM when not, then the pause. */
static void speech_speak_words(Speech* speech, const SamVoice* voice) {
    size_t pos = 0;
    SpeechVoiceWord word;
    while(!speech->aborted && speech_voice_next_word(speech->expanded, &pos, &word)) {
        if(word.word[0] != '\0') {
            if(speech_voice_path(word.word, speech->path, sizeof(speech->path)) > 0 &&
               speech_play_clip(speech, speech->path)) {
                speech->voice.clip_words++;
            } else {
                speech->voice.fallback_words++;
                speech_voice_missing(&speech->voice, word.word);
                speech_sam_word(speech, word.word, voice);
            }
        }
        if(speech->aborted) break;
        if(!speech_push_silence(speech, word.pause_ms)) break;
    }
}

/** Append the words the last utterance lacked to the missing list on the card. */
static void speech_write_missing(Speech* speech) {
    size_t n = speech_voice_log_count(&speech->voice);
    if(n == 0) return;
    File* file = speech->voice_file;
    if(storage_file_open(file, SPEECH_VOICE_MISSING_PATH, FSAM_WRITE, FSOM_OPEN_APPEND)) {
        for(size_t i = 0; i < n; i++) {
            const char* w = speech_voice_log_word(&speech->voice, i);
            storage_file_write(file, w, strlen(w));
            storage_file_write(file, "\n", 1);
        }
    }
    storage_file_close(file);
    speech_voice_log_clear(&speech->voice);
}
```

In `speech_speak_item`, right after `speech->started = furi_get_tick();`:

```c
    if(speech->voice_enabled && speech_voice_ready(speech)) {
        speech_speak_words(speech, &voice);
        speech_item_end(speech);
        speech_write_missing(speech);
        return;
    }
```

In `speech_alloc`, after `speech->file_buffer = malloc(SPEECH_FILE_CHUNK);`:

```c
    speech->voice_file = storage_file_alloc(speech->storage);
    speech_voice_state_init(&speech->voice);
    speech->voice_enabled = true;
```

Add at the end of the file:

```c
void speech_set_voice_clips(Speech* speech, bool enabled) {
    furi_check(speech);
    speech->voice_enabled = enabled;
}

void speech_get_voice_stats(Speech* speech, SpeechVoiceStats* out) {
    furi_check(speech && out);
    // The worker owns these counters and writes them one word at a time; 32 bit reads are
    // atomic on this core, so the snapshot is consistent enough for a status line
    out->enabled = speech->voice_enabled;
    out->vocabulary = speech->vocabulary;
    out->clip_words = *(volatile uint32_t*)&speech->voice.clip_words;
    out->fallback_words = *(volatile uint32_t*)&speech->voice.fallback_words;
    out->missing_words = *(volatile uint32_t*)&speech->voice.missing_words;
    strncpy(out->settings, speech->voice_settings, sizeof(out->settings) - 1);
    out->settings[sizeof(out->settings) - 1] = '\0';
}
```

- [ ] **Step 2: The setting and the start sequence**

`lib/momentum/settings.h`: add `bool sr_voice;` after `uint32_t sr_verbosity;`. `lib/momentum/settings.c`: add `.sr_voice = true, // recorded voice from the card` after the `.sr_verbosity` default and `{setting_bool(sr_voice)},` after the `sr_verbosity` table entry. In `screen_reader.c`, right after the existing `speech_set_voice(...)` call at start: `speech_set_voice_clips(sr->speech, momentum_settings.sr_voice);`.

- [ ] **Step 3: The console command**

In `screen_reader_cli.c` add, before `sr_cli_status`:

```c
static void sr_cli_print_voice(ScreenReader* sr) {
    SpeechVoiceStats v;
    speech_get_voice_stats(screen_reader_get_speech(sr), &v);
    printf(
        "voice: %s, vocabulary %s%s%s, clips %lu, fallback %lu, missing %lu\r\n",
        v.enabled ? "on" : "off",
        v.vocabulary ? "yes" : "no",
        v.settings[0] ? " " : "",
        v.settings,
        (unsigned long)v.clip_words,
        (unsigned long)v.fallback_words,
        (unsigned long)v.missing_words);
}

static void sr_cli_voice(ScreenReader* sr, FuriString* args) {
    FuriString* sub = furi_string_alloc();
    bool has = args_read_string_and_trim(args, sub);
    if(has && furi_string_cmp_str(sub, "on") == 0) {
        momentum_settings.sr_voice = true;
        momentum_settings_save();
        speech_set_voice_clips(screen_reader_get_speech(sr), true);
        printf("voice on\r\n");
    } else if(has && furi_string_cmp_str(sub, "off") == 0) {
        momentum_settings.sr_voice = false;
        momentum_settings_save();
        speech_set_voice_clips(screen_reader_get_speech(sr), false);
        printf("voice off: SAM speaks everything\r\n");
    } else if(!has || furi_string_cmp_str(sub, "status") == 0) {
        sr_cli_print_voice(sr);
    } else {
        printf("sr voice on|off|status\r\n");
    }
    furi_string_free(sub);
}
```

In `sr_cli_status`, after the "last utterance" line: `sr_cli_print_voice(sr);`. In `sr_cli_execute`: `} else if(furi_string_cmp_str(cmd, "voice") == 0) { sr_cli_voice(sr, args);`. In `sr_cli_usage`: `printf("  voice on|off|status  recorded word clips from the card, SAM for the rest (saved)\r\n");`.

- [ ] **Step 4: Build, headroom, lint, host tests**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt 2>&1 | grep -E "error|warning|API version|free_flash" | head && ./fbt lint 2>&1 | tail -2
cd /Users/robin/Downloads/flipper-access && tools/flash_headroom.sh && TMPDIR=<private dir> tools/run_host_tests.sh 2>&1 | tail -7
```
Expected: no warnings, API 87.1 up to date, lint exit 0, spare bytes above 0 (about 8 KB), runner green.

- [ ] **Step 5: Hand-made clips for the device check**

Make sixteen untrimmed word clips with the existing single-clip tool and upload them (the generator of Task 3 replaces them later):

```bash
cd /Users/robin/Downloads/flipper-access && D=<private dir>/handclips && mkdir -p $D && for w in settings sub gigahertz apps one of eleven home screen read saved back okay office b c; do tools/clip_make.py $D/$w.raw "$w" --highpass 500 --gain 1.3 --soft > /dev/null; done && tools/clip_make.py $D/ay.raw "A" --highpass 500 --gain 1.3 --soft > /dev/null && ls $D | wc -l
printf 'say Samantha rate 175 highpass 500 gain 1.3 soft 16000 (hand made, Task 2)\n' > $D/voice.txt
P=/dev/cu.usbmodemflip_R0skie1; S=".venv/bin/python Momentum-Firmware/scripts/storage.py -p $P"
$S mkdir /ext/sr; $S mkdir /ext/sr/voice; for i in s g a o e h r b c; do $S mkdir /ext/sr/voice/$i; done
for w in settings sub gigahertz apps one of eleven home screen read saved back okay office b c ay; do $S send $D/$w.raw /ext/sr/voice/${w:0:1}/$w.raw > /dev/null; done; $S send $D/voice.txt /ext/sr/voice/voice.txt > /dev/null
.venv/bin/python tools/flipper_cli.py "storage list /ext/sr/voice/s"
```

- [ ] **Step 6: Flash and verify on the device**

`./fbt flash_usb`, wait for the port, `sr screen` (no popup), `info device` shows the new commit. Then record verbatim:

1. `sr voice status`: expect `voice: on, vocabulary yes say Samantha ..., clips 0, fallback 0, missing 0` (the vocabulary is found at the first utterance if not yet; if it says no, run `sr say hello` once and read the status again: it must then say yes).
2. `sr say Settings. Sub-GHz. Apps, 1 of 11.` then after 4 s `sr status` and `sr voice status`: utterances +1, underruns 0, clips +7 (settings, sub, gigahertz, apps, one, of, eleven), fallback +0.
3. `sr say Bahncard office` then `sr voice status`: clips +1, fallback +1, missing 1; `storage read /ext/sr/missing.txt` prints `bahncard`. Repeat the say: missing stays 1 and the file still has one line.
4. `sr say A B C` (spelled: ay, b, c are clips): clips +3, fallback +0.
5. A long say (thirty words of vocabulary and non vocabulary mixed) then `input send back short` after one second: `sr status` aborted +1, speech idle within 0.3 s, no crash; `sr screen` still the home screen (Back on the home screen opens nothing).
6. `sr voice off`, `sr say Settings home`: fallback +2, clips +0; `sr voice on`.
7. `sr status` and `free`: underruns 0 throughout, heap within a few hundred bytes of the start (the shell history costs some).

Leave the device idle on the home screen.

- [ ] **Step 7: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/speech.h applications/services/screen_reader/speech.c applications/services/screen_reader/screen_reader.c applications/services/screen_reader/screen_reader_cli.c lib/momentum/settings.h lib/momentum/settings.c && git commit -m "screen reader: recorded word clips from the card with SAM as the fallback"
```

---

### Task 3: The vocabulary generator

**Files:**
- Create: `tools/voice_build.py`, `tools/voice_words.txt`, `tools/voice_names.txt`, `tests/host/speech_expand.c`
- Modify: `tools/clip_make.py` (shared helpers: trim, finish, to_u8; a `--trim` flag), `.gitignore` (add `voice/`)

**Interfaces:**
- Consumes: the card layout and `voice.txt` from Task 2's constraints; `speech_text.c` for the exact word stream; the firmware's `scripts/flipper/storage.py` (`FlipperStorage`, `FlipperStorageOperations.recursive_send`, `receive_file`, `exist_file`, `remove`).
- Produces: `tools/voice_build.py` with the options below; a local `voice/` directory with `manifest.json`, `voice.txt` and `<initial>/<word>.raw`; Task 4 runs it.

- [ ] **Step 1: The pronunciation layer as a host program**

Create `tests/host/speech_expand.c`:

```c
// Runs the pronunciation layer on every line of standard input and prints the expansion:
// the vocabulary generator uses it so the clips on the card match the words the device asks for.
#include <stdio.h>
#include <string.h>
#include "speech_text.h"

int main(void) {
    static char line[4096];
    static char out[SPEECH_TEXT_MAX];
    while(fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = '\0';
        speech_text_expand(line, out, sizeof(out));
        puts(out);
    }
    return 0;
}
```

Check it by hand: `clang -std=c11 -O1 -I Momentum-Firmware/applications/services/screen_reader -o <private dir>/speech_expand tests/host/speech_expand.c Momentum-Firmware/applications/services/screen_reader/speech_text.c && printf 'Sub-GHz\n125kHz RFID\n' | <private dir>/speech_expand` prints `sub gigahertz` and `one hundred twenty five kilohertz R F I D`.

- [ ] **Step 2: Shared clip helpers**

In `tools/clip_make.py` add these functions after `highpass` and use them in `main` (behaviour of the existing options unchanged; add `--trim`):

```python
def trim(x, hz, threshold=0.02, pad_ms=15):
    """Cut leading and trailing silence, keeping pad_ms of it at each end."""
    first = next((i for i, v in enumerate(x) if abs(v) > threshold), None)
    if first is None:
        return x[: int(hz * pad_ms / 1000)]
    last = next(i for i in range(len(x) - 1, -1, -1) if abs(x[i]) > threshold)
    pad = int(hz * pad_ms / 1000)
    return x[max(0, first - pad) : min(len(x), last + 1 + pad)]


def finish(x, gain=1.0, soft=False):
    """Peak normalise to 0.95, apply the gain and, with soft, the tanh limiter."""
    peak = max((abs(v) for v in x), default=0.0) or 1.0
    x = [v / peak * 0.95 * gain for v in x]
    if soft:
        x = [math.tanh(v * 1.5) / math.tanh(1.5) for v in x]
    return x


def to_u8(x):
    return bytes(max(0, min(255, int(round(v * 127 + 128)))) for v in x)
```

`main` becomes: synth, read, highpass, `if a.trim: x = trim(x, hz)`, `x = finish(x, a.gain, a.soft)`, write `to_u8(x)`.

- [ ] **Step 3: The word lists**

Create `tools/voice_words.txt` (one word per line; the generator lower cases and deduplicates):

```
zero
one
two
three
four
five
six
seven
eight
nine
ten
eleven
twelve
thirteen
fourteen
fifteen
sixteen
seventeen
eighteen
nineteen
twenty
thirty
forty
fifty
sixty
seventy
eighty
ninety
hundred
thousand
point
minus
dash
dot
to
0
1
2
3
4
5
6
7
8
9
a
b
c
d
e
f
g
h
i
j
k
l
m
n
o
p
q
r
s
t
u
v
w
x
y
z
ay
space
comma
underscore
slash
colon
semicolon
exclamation
mark
question
apostrophe
quote
plus
star
equals
percent
and
number
at
open
close
paren
bracket
sub
gigahertz
kilohertz
megahertz
hertz
dee
bee
em
eye
button
okay
pin
why
fye
milliamp
hours
momentum
home
screen
menu
of
selected
locked
unlocked
```

Create `tools/voice_names.txt` (tab separated: clip name, text to synthesize; anything not listed is synthesized as the name, single letters as their upper case letter, digits as their number words):

```
ay	A
fye	fi
```

- [ ] **Step 4: The generator**

Create `tools/voice_build.py`:

```python
#!/usr/bin/env python3
"""Build and sync the screen reader's recorded vocabulary.

    tools/voice_build.py [--extract] [--pull-missing] [--sync] [--check] [options]

Words come from tools/voice_words.txt, from every string literal in the firmware sources run
through the real pronunciation layer (--extract), and from the device's /ext/sr/missing.txt
(--pull-missing). Clips land in voice/<initial>/<word>.raw next to voice/manifest.json, which
remembers the settings each clip was made with, so a rerun makes only what is missing or
changed. --sync uploads new or changed files to /ext/sr/voice on the card and removes the
pulled missing list. Defaults are the settings Robin chose by ear on 2026-09-24.

Clip format: raw unsigned 8-bit mono PCM, 16000 Hz, 128 silence, trimmed to 15 ms of silence
at each end. Backends: say (macOS, personal use: Apple's voices may not be redistributed) and
piper (any platform, a freely licensed model, the right choice for a release).
"""
import argparse, glob, hashlib, json, math, multiprocessing, os, re, subprocess, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from clip_make import finish, highpass, read_wav, synth, to_u8, trim  # noqa: E402

FW = os.path.join(ROOT, "Momentum-Firmware")
SRC = os.path.join(FW, "applications", "services", "screen_reader")
DEFAULTS = dict(backend="say", voice="Samantha", rate=175, highpass=500.0, gain=1.3, soft=True, hz=16000, model="")
WORD_RE = re.compile(r"^[a-z0-9]{1,31}$")
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
    roots = [os.path.join(FW, "applications"), os.path.join(FW, "lib", "toolbox")]
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
        x = trim(x, settings["hz"])
        x = finish(x, settings["gain"], settings["soft"])
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(to_u8(x))
        return word, True, ""
    except Exception as e:  # one bad word must not stop the build
        return word, False, str(e)


def settings_line(settings):
    s = settings
    voice = s["model"] if s["backend"] == "piper" else s["voice"]
    return f"{s['backend']} {voice} rate {s['rate']} highpass {s['highpass']:g} gain {s['gain']:g} {'soft' if s['soft'] else 'hard'} {s['hz']}"


def open_storage(port):
    sys.path.insert(0, os.path.join(FW, "scripts"))
    from flipper.storage import FlipperStorage, FlipperStorageOperations  # noqa: E402
    storage = FlipperStorage(port)
    storage.start()
    return storage, FlipperStorageOperations(storage)


def pull_missing(port):
    storage, _ = open_storage(port)
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
        storage.stop()
    return words


def sync(port, out_dir):
    storage, ops = open_storage(port)
    try:
        t0 = time.time()
        ops.recursive_send("/ext/sr/voice", out_dir)
        log(f"sync: done in {time.time() - t0:.0f} s")
    finally:
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
        quiet = all(abs(v - 128) <= 8 for v in edges)
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
```

Add `voice/` to `.gitignore`. Make the script executable.

- [ ] **Step 5: Verify the generator without the device**

```bash
cd /Users/robin/Downloads/flipper-access && tools/voice_build.py --check
tools/voice_build.py --out <private dir>/trial --limit 25 --extract
ls <private dir>/trial; head -c 300 <private dir>/trial/manifest.json; cat <private dir>/trial/voice.txt
tools/voice_build.py --out <private dir>/trial --limit 25 --extract   # second run: 0 to make
tools/voice_build.py --out <private dir>/trial --limit 5 --extract --gain 1.0   # settings change: remade
```
Expected: `--check` prints ten `ok` lines and exits 0; the trial makes 25 clips in `<initial>/` folders, writes `manifest.json` and `voice.txt` (`say Samantha rate 175 highpass 500 gain 1.3 soft 16000`); the second run makes 0; the gain change remakes 5 (the manifest hash covers the settings). Report the extract counts (strings, words, the ten longest) and the time per clip. If `piper` is installed, also run `--check --backend piper --model <model>`; if not, say so.

- [ ] **Step 6: Commit**

```bash
cd /Users/robin/Downloads/flipper-access && git add tools/voice_build.py tools/voice_words.txt tools/voice_names.txt tools/clip_make.py tests/host/speech_expand.c .gitignore && git commit -m "voice_build: vocabulary generator from the firmware's strings, say or piper, synced to the card"
```

---

### Task 4: The vocabulary on the card, verification, documents

**Files:**
- Modify: `README.md` (a "Recorded voice" section), `docs/superpowers/specs/2026-09-24-clip-voice-design.md` (status line: as built), `docs/roadmap.md` (memory plan item 1 done)
- Create: `docs/measurements/2026-09-24-voice-rollout.txt` (the numbers below)

**Interfaces:**
- Consumes: Tasks 2 and 3 on the device and in the repo.
- Produces: the vocabulary on the card and the numbers that say it works.

- [ ] **Step 1: Build the full vocabulary**

```bash
cd /Users/robin/Downloads/flipper-access && time tools/voice_build.py --extract --pull-missing --jobs 4 2>&1 | tail -25
du -sh voice; find voice -name '*.raw' | wc -l
```
Record the word count, the ten longest words, the failed count (investigate any failure), the total size and the time. Words that are obvious junk from the extraction (format remnants, hex blobs) cost nothing and stay; if the count exceeds 12,000, say so before syncing.

- [ ] **Step 2: Sync and check the card**

```bash
time tools/voice_build.py --sync 2>&1 | tail -3
.venv/bin/python tools/flipper_cli.py "storage list /ext/sr/voice"
.venv/bin/python tools/flipper_cli.py "storage read /ext/sr/voice/voice.txt"
```
Record the upload time. Then `sr voice status` on the device: vocabulary yes with the settings line. The hand-made clips of Task 2 are replaced by the generator's (same names, different bytes: the hash check re-sends them).

- [ ] **Step 3: Verify on the device**

Record verbatim:

1. `sr say Settings. Sub-GHz. Apps, 1 of 11. Read RAW. 433.92 MHz. UID: 04 A2 B3 C4.` then `sr voice status`: fallback +0 (every word is in the vocabulary), clips equal to the word count of the expansion, `sr status` underruns 0.
2. `.venv/bin/python tools/sr_drive.py` both scripted sessions as in phase 2 (see tools/sr_drive.py --help); expect all steps to pass with the voice on; then `sr status` and `sr voice status`: underruns 0, fallback 0 or list the fallback words and check them against the vocabulary (a word that should exist but fell back is a bug: look at `storage list` for its folder).
3. A thirty word announcement: `sr say` with thirty vocabulary words in one sentence; `sr status` underruns 0, played time about the sum of the clips plus pauses.
4. Missing round trip: `sr say Zebrafish moonbeam`, `sr voice status` missing +2, `storage read /ext/sr/missing.txt` lists both; `tools/voice_build.py --pull-missing --sync` makes and uploads the two clips and removes the list; say it again: fallback +0, clips +2.
5. Interrupt and stop: a long say interrupted by another say (aborted +1, the second heard), a long say cut with `input send back short` (aborted +1, idle within 0.3 s).
6. Memory: `free` before and after twenty utterances; the RAM probe is not needed (no new allocations beyond alloc).
7. `sr voice off`, one say, `sr voice on`; the setting survives `power reboot` (read `sr voice status` after the reboot and `sr screen` first).

Write all numbers into `docs/measurements/2026-09-24-voice-rollout.txt`. Leave the device idle on the home screen, reader on, speech idle.

- [ ] **Step 4: Documents**

README: a "Recorded voice" section: what it is, the card layout, `tools/voice_build.py` usage with the defaults and the two backends, the licensing note (Apple voices personal only; Piper for release), the missing-word workflow (`--pull-missing --sync`), `sr voice on|off|status`, and that SAM remains the fallback. Spec: status line "as built 2026-09-24" plus any deviation. Roadmap: memory plan item 1 done.

- [ ] **Step 5: Commit**

```bash
cd /Users/robin/Downloads/flipper-access && git add README.md docs/superpowers/specs/2026-09-24-clip-voice-design.md docs/roadmap.md docs/measurements/2026-09-24-voice-rollout.txt && git commit -m "docs: recorded voice as built, rollout measurements"
```
