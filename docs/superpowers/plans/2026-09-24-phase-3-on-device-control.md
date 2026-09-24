# Phase 3: On-Device Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The blind user controls the screen reader from the device alone: Back chords read the screen, repeat or spell the focus, read the status bar and change the volume; an Accessibility settings screen sets everything else; the lock screen, PIN entry, lock menu and the infrared universal remotes, which draw icons only, get spoken hints; NFC-V emulation is announced before the listener takes the speaker.

**Architecture:** An input filter hook in the input service feeds a pure, host-tested chord state machine inside the screen reader, which posts commands to the reader thread. Icon-only screens describe themselves with a new synthetic-text tap call that the existing screen model treats as a row, so no announcement logic changes. The settings app writes `momentum_settings`, which the reader already reads per frame and now pushes to the speech engine per announcement.

**Tech Stack:** Momentum firmware (fbt, GCC 12, -Wall -Wextra -Werror), C11 host tests with clang and sanitizers, the Flipper console (`input send`, `sr`), the firmware's fap build (`./fbt fap_infrared fap_momentum_app`) and `scripts/storage.py` for copying faps to the card.

**Spec:** docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md, section 17 (binding), with sections 9 and 10 where 17 does not override them. Exploration notes are in the ledger's pre-flight table.

## Global Constraints

- Firmware repo /Users/robin/Downloads/flipper-access/Momentum-Firmware, branch screen-reader (head d5b77c219 at plan time); project repo /Users/robin/Downloads/flipper-access, main (head 5a95714). Commit only your own files with explicit `git add` then `git commit -m "<subject>" -- <the same files>`; never a plain `git commit -a`; do not push; never commit inside the submodule applications/external; never delete or move the repo-root `voice/` directory (the built vocabulary).
- The firmware image must stay under 880,640 bytes: run `tools/flash_headroom.sh` after every firmware build and report the spare bytes (8,592 at plan time). `./fbt` must show only "API version ... is up to date" (87.1 until Task 4 bumps it to 87.2) and the two pre-existing manifest warnings from applications/external; `./fbt lint` must exit 0.
- Host tests: `TMPDIR=<private dir> tools/run_host_tests.sh` must stay green; new tests use the runner's CFLAGS plus `-fsanitize=address,undefined -fno-sanitize-recover=all`.
- Device: /dev/cu.usbmodemflip_R0skie1, console via `.venv/bin/python tools/flipper_cli.py "<command>"`; never `loader close`; after every flash wait for the port and run `sr screen` first; on a crash popup stop and report BLOCKED with the exact output. The user may be using the device between tasks: before a flash, confirm `loader info` says no application and the `announcements` counter of `sr status` is flat over 30 s; leave the device idle on the home screen, reader on, voice on, speech idle.
- Filter callback rules: it runs on the input service thread or the FreeRTOS timer service thread under the pubsub mutex; it must not block, must not publish input events, and must not call into the GUI; it may take the reader's mutex and the speech mutex briefly (both are held for microseconds by every user) and set thread flags.
- Commit messages end with a blank line and the Co-Authored-By line your own attribution guidance gives you.

---

### Task 1: Input filter hook and the chord state machine

**Files:**
- Modify: `Momentum-Firmware/applications/services/input/input.h` (filter API), `input.c` (the four publish sites), `input_cli.c` (`fake_input` goes through the filter too)
- Create: `Momentum-Firmware/applications/services/screen_reader/sr_chords.h`, `sr_chords.c` (pure C)
- Create: `tests/host/test_sr_chords.c`; Modify: `tools/run_host_tests.sh` (append a block)

**Interfaces:**
- Produces (input service): `typedef struct { bool drop; bool emit_long; } InputFilterResult; typedef void (*InputFilterCallback)(const InputEvent* event, InputFilterResult* result, void* context); void input_set_filter(InputFilterCallback callback, void* context);` (NULL removes it). The filter is called before every publish of an `InputEvent`; when `drop` is set the event is not published; when `emit_long` is set an extra event with `type = InputTypeLong` and the same key is published right after the original (or instead of it when both are set).
- Produces (chords): `typedef enum { SrChordNone, SrChordReadAll, SrChordStatus, SrChordRepeat, SrChordSpell, SrChordVolumeDown, SrChordVolumeUp } SrChordCommand; typedef struct { bool back_down; bool chord_used; bool long_pending; uint32_t back_down_ms; int8_t chord_key; bool ok_long_seen; } SrChords; void sr_chords_init(SrChords* s); SrChordCommand sr_chords_feed(SrChords* s, InputKey key, InputType type, uint32_t now_ms, bool* drop, bool* emit_long);` Task 2 wires it into the reader.

- [ ] **Step 1: The filter hook**

`input.h`, after the `InputEvent` typedef:

```c
/** Result of an input filter: drop suppresses the event; emit_long publishes an extra Long
 *  event for the same key right after it (or instead of it when both are set). */
typedef struct {
    bool drop;
    bool emit_long;
} InputFilterResult;

/** Called before every input event is published, on the publishing thread, under the
 *  pubsub mutex: it must not block and must not publish input events itself. */
typedef void (*InputFilterCallback)(const InputEvent* event, InputFilterResult* result, void* context);

/** Install or remove (NULL) the single input filter. Used by the screen reader. */
void input_set_filter(InputFilterCallback callback, void* context);
```

`input.c`: add file scope `static volatile InputFilterCallback input_filter = NULL; static void* volatile input_filter_context = NULL;` and

```c
void input_set_filter(InputFilterCallback callback, void* context) {
    input_filter_context = context;
    input_filter = callback;
}

// Every input event leaves through here so that the filter sees all of them
static void input_publish(FuriPubSub* pubsub, InputEvent* event) {
    InputFilterCallback filter = input_filter;
    InputFilterResult result = {false, false};
    if(filter) filter(event, &result, input_filter_context);
    if(!result.drop) furi_pubsub_publish(pubsub, event);
    if(result.emit_long) {
        InputEvent extra = *event;
        extra.type = InputTypeLong;
        furi_pubsub_publish(pubsub, &extra);
    }
}
```

Replace the four `furi_pubsub_publish(event_pubsub, &event)` calls (the Long and Repeat sites in the timer callback, the Short and the Press/Release sites in the service loop) with `input_publish(event_pubsub, &event)`. The timer callback needs the pubsub pointer: it reaches it through the same file scope variable the service loop uses (check how `event_pubsub` is stored; if it is a local of `input_srv`, move it to file scope). In `input_cli.c`, `fake_input` publishes three events directly: make it call the same path — export `input_publish` as `void input_publish_event(FuriPubSub* pubsub, InputEvent* event)` in input.h (a second public function) and use it in `fake_input`, so console-driven keys pass through the filter exactly like real ones.

Build check: `./fbt` clean, `./fbt lint` exit 0. The filter is not installed by anyone yet; the device behaves as before. Commit: "input: filter hook before every published event".

- [ ] **Step 2: The chord state machine, test first**

Create `tests/host/test_sr_chords.c`:

```c
#include <stdio.h>
#include <string.h>
#include "sr_chords.h"

static int failures = 0;
static int checks = 0;
#define CHECK(cond)                                        \
    do {                                                   \
        checks++;                                          \
        if(!(cond)) {                                      \
            failures++;                                    \
            printf("FAIL line %d: %s\n", __LINE__, #cond); \
        }                                                  \
    } while(0)

static SrChords s;
static bool drop, elong;

static SrChordCommand feed(InputKey key, InputType type, uint32_t ms) {
    drop = elong = true; // must be written by the call
    return sr_chords_feed(&s, key, type, ms, &drop, &elong);
}

static void test_plain_keys_pass(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyUp, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyUp, InputTypeShort, 50) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyUp, InputTypeRelease, 50) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyOk, InputTypeLong, 300) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyOk, InputTypeRepeat, 450) == SrChordNone && !drop && !elong);
}

static void test_back_alone_short(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 1000) == SrChordNone && !drop);
    // input.c publishes Short before Release
    CHECK(feed(InputKeyBack, InputTypeShort, 1100) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeRelease, 1100) == SrChordNone && !drop && !elong);
}

static void test_back_alone_long_on_release(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 1000) == SrChordNone && !drop);
    CHECK(feed(InputKeyBack, InputTypeLong, 1300) == SrChordNone && drop && !elong); // held back
    CHECK(feed(InputKeyBack, InputTypeRepeat, 1450) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeRelease, 1600) == SrChordNone && !drop && elong); // now
    // A fresh press starts clean
    CHECK(feed(InputKeyBack, InputTypePress, 2000) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeShort, 2050) == SrChordNone && !drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 2050) == SrChordNone && !drop && !elong);
}

static void test_chord_up_and_down(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop);
    CHECK(feed(InputKeyUp, InputTypePress, 100) == SrChordReadAll && drop);
    CHECK(feed(InputKeyUp, InputTypeShort, 150) == SrChordNone && drop);
    CHECK(feed(InputKeyUp, InputTypeRelease, 150) == SrChordNone && drop);
    // A second chord in the same hold
    CHECK(feed(InputKeyDown, InputTypePress, 400) == SrChordStatus && drop);
    CHECK(feed(InputKeyDown, InputTypeLong, 700) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeRepeat, 850) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 900) == SrChordNone && drop);
    // Back's own Long and Short are dropped after a chord, Release passes, no Long emitted
    CHECK(feed(InputKeyBack, InputTypeLong, 300) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeShort, 1000) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeRelease, 1000) == SrChordNone && !drop && !elong);
}

static void test_chord_ok_short_and_long(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone);
    CHECK(feed(InputKeyOk, InputTypePress, 100) == SrChordNone && drop); // OK decides later
    CHECK(feed(InputKeyOk, InputTypeShort, 200) == SrChordRepeat && drop);
    CHECK(feed(InputKeyOk, InputTypeRelease, 200) == SrChordNone && drop);
    CHECK(feed(InputKeyOk, InputTypePress, 500) == SrChordNone && drop);
    CHECK(feed(InputKeyOk, InputTypeLong, 800) == SrChordSpell && drop);
    CHECK(feed(InputKeyOk, InputTypeRepeat, 950) == SrChordNone && drop);
    CHECK(feed(InputKeyOk, InputTypeRelease, 1000) == SrChordNone && drop); // no Short after Long
    CHECK(feed(InputKeyBack, InputTypeShort, 1100) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 1100) == SrChordNone && !drop && !elong);
}

static void test_chord_volume(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone);
    CHECK(feed(InputKeyLeft, InputTypePress, 100) == SrChordVolumeDown && drop);
    CHECK(feed(InputKeyLeft, InputTypeRelease, 200) == SrChordNone && drop);
    CHECK(feed(InputKeyRight, InputTypePress, 300) == SrChordVolumeUp && drop);
    CHECK(feed(InputKeyRight, InputTypeShort, 350) == SrChordNone && drop);
    CHECK(feed(InputKeyRight, InputTypeRelease, 350) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 400) == SrChordNone && !drop && !elong);
}

static void test_chord_key_outlives_back(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone);
    CHECK(feed(InputKeyUp, InputTypePress, 100) == SrChordReadAll && drop);
    CHECK(feed(InputKeyBack, InputTypeShort, 200) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 200) == SrChordNone && !drop);
    // Up is still held: its remaining events are still swallowed, then things are normal
    CHECK(feed(InputKeyUp, InputTypeLong, 400) == SrChordNone && drop);
    CHECK(feed(InputKeyUp, InputTypeRelease, 500) == SrChordNone && drop);
    CHECK(feed(InputKeyUp, InputTypePress, 600) == SrChordNone && !drop);
}

static void test_second_key_while_chord_key_held(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone);
    CHECK(feed(InputKeyUp, InputTypePress, 100) == SrChordReadAll && drop);
    // Another key while Up is still held: ignored as a chord, passes through untouched
    CHECK(feed(InputKeyDown, InputTypePress, 150) == SrChordNone && !drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 200) == SrChordNone && !drop);
    CHECK(feed(InputKeyUp, InputTypeRelease, 300) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypePress, 400) == SrChordStatus && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 450) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 500) == SrChordNone && !drop);
}

int main(void) {
    test_plain_keys_pass();
    test_back_alone_short();
    test_back_alone_long_on_release();
    test_chord_up_and_down();
    test_chord_ok_short_and_long();
    test_chord_volume();
    test_chord_key_outlives_back();
    test_second_key_while_chord_key_held();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
```

The test needs `InputKey` and `InputType`: `sr_chords.h` defines them itself when not building for the firmware, so the host test compiles without the firmware headers:

`sr_chords.h`:

```c
/**
 * @file sr_chords.h
 * Back-chord state machine for the screen reader's input filter. Pure C, host tested: it sees
 * every input event before it is published and decides which are swallowed, which Back Long
 * is delivered on release, and which command a chord names. No timing of its own beyond the
 * 300 ms Long threshold, which the input service applies before the Long event arrives.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __has_include
#if __has_include(<input/input.h>)
#include <input/input.h>
#define SR_CHORDS_HAVE_INPUT 1
#endif
#endif
#ifndef SR_CHORDS_HAVE_INPUT
typedef enum { InputKeyUp, InputKeyDown, InputKeyRight, InputKeyLeft, InputKeyOk, InputKeyBack, InputKeyMAX } InputKey;
typedef enum { InputTypePress, InputTypeRelease, InputTypeShort, InputTypeLong, InputTypeRepeat, InputTypeMAX } InputType;
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define SR_CHORD_LONG_MS 300

typedef enum {
    SrChordNone,
    SrChordReadAll, /**< Back + Up: the whole screen */
    SrChordStatus, /**< Back + Down: the status rows */
    SrChordRepeat, /**< Back + OK short: the focus with its position */
    SrChordSpell, /**< Back + OK long: the focus spelled */
    SrChordVolumeDown, /**< Back + Left */
    SrChordVolumeUp, /**< Back + Right */
} SrChordCommand;

typedef struct {
    bool back_down;
    bool chord_used; /**< a chord ran during this Back hold */
    bool long_pending; /**< Back's Long arrived and waits for the release */
    uint32_t back_down_ms;
    int8_t chord_key; /**< key whose events are swallowed until its release, -1 for none */
    bool ok_long_seen; /**< OK Long ran Spell, so its Short must not run Repeat */
} SrChords;

void sr_chords_init(SrChords* s);

/** Feed one event. Returns the command to run (SrChordNone for none) and writes whether the
 *  event is dropped and whether a Long must be emitted for it. */
SrChordCommand sr_chords_feed(
    SrChords* s,
    InputKey key,
    InputType type,
    uint32_t now_ms,
    bool* drop,
    bool* emit_long);

#ifdef __cplusplus
}
#endif
```

Append to `tools/run_host_tests.sh` after the speech voice block:

```bash
clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$SRC" -o "$OUT/test_sr_chords" \
  "$TESTS/test_sr_chords.c" "$SRC/sr_chords.c"
if ! "$OUT/test_sr_chords" > "$OUT/sr_chords.txt"; then
  cat "$OUT/sr_chords.txt"
  echo "chord checks failed"
  exit 1
fi
echo "chords: $(tail -n 1 "$OUT/sr_chords.txt")"
```

Run the runner: the block must fail to compile (no sr_chords.c).

- [ ] **Step 3: The state machine**

Create `sr_chords.c`:

```c
#include "sr_chords.h"

void sr_chords_init(SrChords* s) {
    s->back_down = false;
    s->chord_used = false;
    s->long_pending = false;
    s->back_down_ms = 0;
    s->chord_key = -1;
    s->ok_long_seen = false;
}

static SrChordCommand command_for(InputKey key) {
    switch(key) {
    case InputKeyUp:
        return SrChordReadAll;
    case InputKeyDown:
        return SrChordStatus;
    case InputKeyLeft:
        return SrChordVolumeDown;
    case InputKeyRight:
        return SrChordVolumeUp;
    default:
        return SrChordNone;
    }
}

SrChordCommand sr_chords_feed(
    SrChords* s,
    InputKey key,
    InputType type,
    uint32_t now_ms,
    bool* drop,
    bool* emit_long) {
    *drop = false;
    *emit_long = false;

    // A chord key is swallowed until it is released, whatever Back does meanwhile
    if(s->chord_key == (int8_t)key) {
        *drop = true;
        if(key == InputKeyOk) {
            if(type == InputTypeShort && !s->ok_long_seen) return SrChordRepeat;
            if(type == InputTypeLong) {
                s->ok_long_seen = true;
                return SrChordSpell;
            }
        }
        if(type == InputTypeRelease) {
            s->chord_key = -1;
            s->ok_long_seen = false;
        }
        return SrChordNone;
    }

    if(key == InputKeyBack) {
        switch(type) {
        case InputTypePress:
            s->back_down = true;
            s->chord_used = false;
            s->long_pending = false;
            s->back_down_ms = now_ms;
            return SrChordNone;
        case InputTypeLong:
            *drop = true; // delivered on release instead
            if(!s->chord_used) s->long_pending = true;
            return SrChordNone;
        case InputTypeRepeat:
            *drop = true;
            return SrChordNone;
        case InputTypeShort:
            *drop = s->chord_used;
            return SrChordNone;
        case InputTypeRelease:
            *emit_long = s->long_pending && !s->chord_used;
            s->back_down = false;
            s->chord_used = false;
            s->long_pending = false;
            return SrChordNone;
        default:
            return SrChordNone;
        }
    }

    // Another key while Back is held and no chord key is active: a chord starts on its Press
    if(s->back_down && s->chord_key < 0 && type == InputTypePress) {
        s->chord_key = (int8_t)key;
        s->chord_used = true;
        s->long_pending = false;
        s->ok_long_seen = false;
        *drop = true;
        return command_for(key); // OK decides on Short or Long, so None here
    }
    return SrChordNone;
}
```

Run the runner: `chords: N checks, 0 failures`. Firmware: `./fbt` compiles the new files (nothing calls them yet), `./fbt lint` exit 0. Commit firmware "screen reader: chord state machine" and project "host tests: chords".

---

### Task 2: Chords in the reader, commands, spelling, console

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_reader.c` (install the filter, run commands), `screen_reader_cli.c` (`sr chord ...`, help text), `speech.h`, `speech.c` (`speech_say_spelled`), `speech_queue.h`, `speech_queue.c` (a `spell` flag on items)

**Interfaces:**
- Consumes: Task 1's `input_set_filter`, `sr_chords_feed`; the model's `sr_screen_describe(screen, out, size)` and `sr_screen_focus_text(screen, out, size)`; `SrScreen.rows[]` with `kind == SrRowStatus`, `SrScreen.focus.index/count` (read screen_model.h for the exact field names); `speech_set_voice`, `momentum_settings.sr_volume`, `momentum_settings_save`.
- Produces: `void speech_say_spelled(Speech* speech, const char* text);` (interrupting, non-replaceable, every word spelled with the letter and digit clips, 60 ms between letters, 150 ms between words); `SpeechItem.spell`; reader commands reachable from `sr chord up|down|ok|okhold|left|right`; the filter installed while the reader is enabled and removed when disabled.

- [ ] **Step 1: Spelled items**

`speech_queue.h`: add `bool spell;` to `SpeechItem` after `file`, and `void speech_queue_push_spelled(SpeechQueue* queue, const char* text);` (like an interrupting non-replaceable push with `spell` true). `speech_queue.c`: implement; `speech_queue_push` and `push_file` leave `spell` false. Host test in tests/host/test_speech_queue.c: one push_spelled after a text leaves one item with spell true and the text.

`speech.c`: in `speech_speak_words`, when the item is spelled, every non-empty word goes through `speech_spell_word` (count it as a clip word, not a fallback, and do not record it as missing) and the pause after a word is at least 150 ms; pass the item's `spell` flag into `speech_speak_words` (signature `speech_speak_words(Speech* speech, const SamVoice* voice, bool spell)`). When the voice is off, a spelled item falls to the SAM path with the text spaced out letter by letter ("A B C") built in the chunk buffer. `speech.h`/`speech.c`: `speech_say_spelled` pushes with `speech_queue_push_spelled` and wakes the worker like `speech_say`.

- [ ] **Step 2: The reader runs commands**

In `screen_reader.c`: add to the `ScreenReader` struct `SrChords chords;` and `volatile uint8_t pending_command;` and the flag `SR_FLAG_COMMAND`. The filter callback:

```c
// Input filter: runs on the input service or timer thread, under the pubsub mutex
static void sr_input_filter(const InputEvent* event, InputFilterResult* result, void* context) {
    ScreenReader* sr = context;
    bool drop = false, emit_long = false;
    SrChordCommand command =
        sr_chords_feed(&sr->chords, event->key, event->type, furi_get_tick(), &drop, &emit_long);
    result->drop = drop;
    result->emit_long = emit_long;
    if(command != SrChordNone) {
        sr->pending_command = (uint8_t)command;
        furi_thread_flags_set(sr->thread_id, SR_FLAG_COMMAND);
    }
}
```

The existing input subscription callback keeps stopping speech on every Press it still sees (dropped chord presses never reach it, which is right: the command's own speech must not be stopped). Install the filter in `screen_reader_set_enabled(sr, true)` and at start when enabled (`input_set_filter(sr_input_filter, sr)` after `sr_chords_init`), remove it (`input_set_filter(NULL, NULL)`) when disabled. In the service loop, handle `SR_FLAG_COMMAND` by calling `sr_run_command(sr, command)`:

```c
static void sr_run_command(ScreenReader* sr, SrChordCommand command) {
    char* text = malloc(SR_ANN_TEXT_MAX);
    SrScreen* screen = malloc(sizeof(SrScreen));
    screen_reader_get_screen(sr, screen);
    switch(command) {
    case SrChordReadAll:
        sr_screen_describe(screen, text, SR_ANN_TEXT_MAX);
        if(text[0] == '\0') strlcpy(text, "Nothing on screen", SR_ANN_TEXT_MAX);
        speech_say(sr->speech, text, true, false);
        break;
    case SrChordStatus:
        sr_status_text(screen, text, SR_ANN_TEXT_MAX); // rows with kind SrRowStatus joined by ", "
        if(text[0] == '\0') strlcpy(text, "No status bar", SR_ANN_TEXT_MAX);
        speech_say(sr->speech, text, true, false);
        break;
    case SrChordRepeat:
        sr_focus_with_position(screen, text, SR_ANN_TEXT_MAX); // focus text, then "N of M" when known
        if(text[0] == '\0') strlcpy(text, "No focus", SR_ANN_TEXT_MAX);
        speech_say(sr->speech, text, true, false);
        break;
    case SrChordSpell:
        sr_screen_focus_text(screen, text, SR_ANN_TEXT_MAX);
        if(text[0] == '\0') strlcpy(text, "No focus", SR_ANN_TEXT_MAX);
        speech_say_spelled(sr->speech, text);
        break;
    case SrChordVolumeDown:
    case SrChordVolumeUp: {
        int v = (int)momentum_settings.sr_volume + (command == SrChordVolumeUp ? 10 : -10);
        if(v < 0) v = 0;
        if(v > 100) v = 100;
        momentum_settings.sr_volume = (uint32_t)v;
        momentum_settings_save();
        speech_set_voice(sr->speech, (uint8_t)momentum_settings.sr_rate, (uint8_t)v);
        snprintf(text, SR_ANN_TEXT_MAX, "Volume %d", v);
        speech_say(sr->speech, text, true, false);
        break;
    }
    default:
        break;
    }
    free(screen);
    free(text);
}
```

`sr_status_text` and `sr_focus_with_position` are small helpers in screen_model.c (pure, host tested in test_screen_model.c with one check each: a screen with two status rows gives "14:05, 100"; a focus with index 3 of 11 gives "Apps, 3 of 11"; without a known position just the focus text). Use the existing row and focus fields; read screen_model.h and the phase 1 test for the builders that make screens in tests.

Live settings: in `sr_process`, before the `speech_say` of an announcement, push `speech_set_voice(sr->speech, (uint8_t)momentum_settings.sr_rate, (uint8_t)momentum_settings.sr_volume)` and `speech_set_voice_clips(sr->speech, momentum_settings.sr_voice)` (both are cheap stores), so the settings app's changes apply live in Task 3.

- [ ] **Step 3: Console**

`screen_reader_cli.c`: `sr chord up|down|ok|okhold|left|right` maps to the six commands and calls a new `void screen_reader_run_command(ScreenReader* sr, SrChordCommand command)` (public in screen_reader.h) that sets `pending_command` and the flag exactly like the filter does. Help text: add the line and change "SAM for the rest" on the voice line to "recorded word clips from the card, spelled letters for the rest (saved)".

- [ ] **Step 4: Build, flash, verify**

`./fbt` clean, `./fbt lint` exit 0, `tools/flash_headroom.sh`, host runner green. Flash; `sr screen` first. Then record verbatim:
1. `sr chord up` from the home screen: speaks the description (`sr status` utterances +1). `sr chord down`: the status rows. `sr chord ok`: the focus or "No focus". `sr chord okhold`: spelled. `sr chord right` twice: "Volume 100" (already max) — then `sr chord left`: "Volume 90", `sr status` rate line shows volume 90; `sr chord right`: back to 100.
2. Real chords through the console's `input send`, which now passes the filter: `input send back press`, `input send up press`, `input send up release`, `input send back release` → the whole screen is spoken, the menu did NOT open (`sr screen` still the desktop), `sr status` utterances +1. Then `input send back press`, `input send ok press`, `input send ok short`, `input send ok release`, `input send back release` → the focus repeated, nothing opened. Then `input send back press`, `input send ok press`, `input send ok long`, `input send ok release`, `input send back release` → spelled.
3. Back alone still works: open the main menu (`input send ok short`), `sr screen` shows the menu, `input send back short` → home screen announced. Back Long on release: `input send back press`, wait 0.5 s, `input send back release` → the power-off dialog opens (the desktop's Back Long), `sr screen` shows it, then `input send back short` to leave it.
4. Chords inside an app: open Settings (`loader open Settings` or through the menu), `input send back press`, `input send up press`, `input send up release`, `input send back release` → the settings screen is read and the app stays open; `input send back short` leaves it.
5. Reader off and on: `sr off` then `input send back press`, `input send up press`, `input send up release`, `input send back release` → the menu opens (no filter: Up went through), `input send back short`; `sr on`.
Leave the device idle on the home screen.

- [ ] **Step 5: Commit**

Firmware: "screen reader: Back chords read, repeat, spell, status and volume; live settings". Project: "host tests: spelled items, status and focus helpers".

---

### Task 3: Accessibility settings scene

**Files:**
- Modify: `Momentum-Firmware/applications/main/momentum_app/scenes/momentum_app_scene_config.h` (add `ADD_SCENE(momentum_app, accessibility, Accessibility)`), `momentum_app_scene_start.c` (a fourth root item "Accessibility" after Misc, index `VarItemListIndexAccessibility`, entering the new scene like the others)
- Create: `Momentum-Firmware/applications/main/momentum_app/scenes/momentum_app_scene_accessibility.c`

**Interfaces:**
- Consumes: `momentum_settings.screen_reader`, `.sr_voice`, `.sr_rate`, `.sr_volume`, `.sr_verbosity`; the app's `app->save_settings` deferred save; the reader's live reads (Task 2).
- Produces: the scene, reachable by speech: Momentum settings, Accessibility.

- [ ] **Step 1: The scene**

Model it on `momentum_app_scene_misc_screen.c`: a `VariableItemList` with five items. Screen reader: values "OFF", "ON" (2 values) writing `momentum_settings.screen_reader` (the reader reads it per frame, so it takes effect at once; turning it off silences the device from the next frame — announce nothing special). Voice: "SAM", "Recorded" (2 values, `sr_voice`). Rate: 21 values from 40 to 120 in steps of 4, text the number, `sr_rate`. Volume: 11 values 0 to 100 in steps of 10, text the number, `sr_volume`. Verbosity: "Terse", "Normal", "Verbose", `sr_verbosity`. Each change callback sets `app->save_settings = true` and updates the value text. The reader announces the list as any variable item list (label and value), so the user hears each change.

- [ ] **Step 2: Build the fap, copy, verify**

`./fbt fap_momentum_app` (the app is external; the firmware image does not change), copy `build/f7-firmware-C/.extapps/momentum_app.fap` to the card at its existing path (find it with `storage list /ext/apps` folders, the assets category the manifest names) with `scripts/storage.py send`. On the device: `loader open` the Momentum settings app (its app id from the manifest), navigate by `input send down short` to Accessibility, `input send ok short`; `sr screen` shows the five rows with values; change Volume with `input send left short` and read `sr status` (volume line changed live after the next announcement); `input send right short` restores; change Rate the same way and restore; leave with `input send back short` repeatedly until the home screen; then `sr status` shows the saved values persisted (the app saves on exit); `power reboot` is not needed. Record outputs.

- [ ] **Step 3: Commit**

Firmware: "momentum settings: Accessibility scene for the screen reader".

---

### Task 4: Hints for icon-only screens: tap notes, desktop, button panel, universal remotes

**Files:**
- Modify: `Momentum-Firmware/applications/services/gui/canvas_i.h`, `canvas.c` (`canvas_tap_hint_note`), `applications/services/gui/canvas.h` (public declaration for external apps), `applications/services/screen_reader/screen_reader.c` (the tap callback records notes), `screen_model.c/.h` (note records become rows), `applications/services/gui/modules/button_panel.h/.c` (`button_panel_item_set_name`, hint on draw), `applications/services/desktop/views/desktop_view_lock_menu.c`, `desktop_view_pin_input.c`, `desktop_view_locked.c` (hints), `applications/services/screen_reader/screen_reader.c` (desktop status pubsub: "Locked"/"Unlocked"), `applications/main/infrared/scenes/infrared_scene_universal_*.c` (names), `targets/f7/api_symbols.csv` (two new functions, version 87.2), `lib/signal_reader/signal_reader.c` (400 ms first-start grace)
- Modify: `tests/host/test_screen_model.c` (note rows)

**Interfaces:**
- Produces: `void canvas_tap_hint_note(Canvas* canvas, const char* text, bool focus);` — records a synthetic text record on the current layer with the note flag; the screen model treats it as a normal row, or as the focus row when `focus` is true, and never as a title. `void button_panel_item_set_name(ButtonPanel* button_panel, uint32_t index, const char* name);` — the module calls `canvas_tap_hint_note(canvas, name, true)` for the selected item in its draw callback when a name is set (the string must outlive the panel: the infrared scenes pass literals). Both exported (API 87.2).

- [ ] **Step 1: The note record**

Read `canvas_i.h` (CanvasTapRecord, the tap struct) and `screen_reader.c`'s `sr_text` callback, then `screen_model.h`'s `SrTextRecord`/frame fields. Add a `bool note` flag to the tap record and to the frame's text record; `canvas_tap_hint_note` fills a record with the text, the current layer, x = 0, y = 0 (notes have no position), font secondary, colour normal, `note = true`, `focus = focus`, and passes it through the same path as drawn text. In `screen_model.c`, a note record becomes a row of kind `SrRowFocus` when focus is set, else `SrRowNormal`; notes never become the title and are excluded from the "no text drawn" home-screen detection. Host test: a frame with one drawn title and one focus note describes as "Title, note text" with the note as the focus.

- [ ] **Step 2: Desktop hints**

`desktop_view_lock_menu.c` draw callback: after drawing, `canvas_tap_hint_note(canvas, <name of the selected tile>, true)` where the names are "Left handed", "Settings", "Dark mode", "Lock", "Bluetooth", "Momentum", and for the sliders "Brightness N" and "Volume N" formatted into a small buffer in the model (read how the selection index and slider values are stored). `desktop_view_pin_input.c` draw: `canvas_tap_hint_note(canvas, "N digits entered", false)` with N the current length (never the digits), plus the existing strings stay. `desktop_view_locked.c` lockscreen draw: `canvas_tap_hint_note(canvas, pin_locked ? "Locked with PIN, press Up to enter it" : "Locked, press Back three times to unlock", false)`. Unlock: in `screen_reader.c`, subscribe to `desktop_api_get_status_pubsub(furi_record_open(RECORD_DESKTOP))` at start (after the desktop record exists; if the record is not yet available at service start, subscribe lazily from the service loop on the first frame) and announce "Unlocked" when `locked` goes from true to false (the lock itself is announced by the lockscreen note).

- [ ] **Step 3: Button panel names and the universal remotes**

`button_panel.h/.c`: `ButtonItem` gains `const char* name;` (NULL by default); `button_panel_item_set_name` sets it for the item with that index; the draw callback calls `canvas_tap_hint_note(canvas, item->name, true)` for the selected item when its name is non-NULL, after drawing the icons (so the label text is still the title). In each `infrared_scene_universal_<type>.c`, after every `button_panel_add_item(...)` for index N, add `button_panel_item_set_name(panel, N, "<name>");` using these spoken names for the record names: Power → "Power", Mute → "Mute", Vol_up → "Volume up", Vol_dn → "Volume down", Ch_next → "Channel up", Ch_prev → "Channel down", Off → "Off", Dh → "Dry", Cool_hi → "Cool high", Cool_lo → "Cool low", Heat_hi → "Heat high", Heat_lo → "Heat low", Play → "Play", Pause → "Pause", Next → "Next", Prev → "Previous", Input/Source → "Input", Menu → "Menu", Brightness_up → "Brightness up", Brightness_dn → "Brightness down", Speed_up → "Speed up", Speed_dn → "Speed down", Rotate → "Rotate", Timer → "Timer", Mode → "Mode", Eject → "Eject", Subtitle → "Subtitle", Setup → "Setup", Ok → "OK", Up/Down/Left/Right → "Up"/"Down"/"Left"/"Right", Sleep → "Sleep", Fan_speed → "Fan speed", Swing → "Swing" (any other record name: the name with underscores replaced by spaces).

- [ ] **Step 4: API export and NFC-V grace**

Add to `targets/f7/api_symbols.csv` the two functions in the file's format (`Function,+,canvas_tap_hint_note,void,"Canvas*, const char*, bool"` and `Function,+,button_panel_item_set_name,void,"ButtonPanel*, uint32_t, const char*"`, in alphabetical position) and bump the version line to `Version,+,87.2,,`; declare `canvas_tap_hint_note` in the public `canvas.h` so the fap sees it. `./fbt` then reports "API version 87.2 is up to date" (if it reports a mismatch, run `./fbt api_sync` and commit its result). `signal_reader.c`: the instance gets `bool first_start_done;` (false at alloc); in `signal_reader_start`, before the speaker acquire, `if(!instance->first_start_done) { instance->first_start_done = true; furi_delay_ms(400); }` with a comment that the screen reader's emulation announcement takes the speaker in that window and the acquire then waits for it to finish.

- [ ] **Step 5: Build, flash, faps, verify**

`./fbt` (API 87.2 up to date), `./fbt lint`, `tools/flash_headroom.sh`, host runner green. `./fbt fap_infrared fap_momentum_app`; flash the firmware; copy `infrared.fap` and `momentum_app.fap` to their card paths (`storage list /ext/apps/Infrared` etc.; overwrite). `sr screen` first. Verify, verbatim:
1. Infrared, Universal Remotes, TVs: open by `loader open Infrared` and navigation (`sr screen` to see the rows, `input send` to reach "Universal Remotes" then "TVs"); `sr screen` shows the title "TVs" and the focus note "Power"; `input send right short` → the reader announces the new focus ("Mute" or whichever is next); `input send down short` → another; record the announcements from `sr status` counters and `sr screen`.
2. Lock: `loader open` nothing; from the home screen trigger the lock menu through its keybind (read the desktop keybind settings in `sr screen` or the Momentum settings; if no keybind opens it, skip the lock menu check and say so) → the selected tile is announced; move with `input send right short`; leave with Back.
3. Auto-lock text: lock the device from the lock menu with the Lock tile (keypad lock) → "Locked, press Back three times to unlock" is spoken; `input send back short` three times → "Unlocked" then "Home screen".
4. NFC-V: `sr say` a long sentence, then `loader open NFC /ext/nfc/sr_nfcv_test.nfc` as in phase 2: the "Emulating" screen is spoken before the listener takes the speaker (utterances +1, dropped +0 for it), then Back leaves.
5. PIN: not exercised (setting a PIN unattended risks locking the user out); say so.
Leave the device idle on the home screen.

- [ ] **Step 6: Commit**

Firmware: "gui: tap notes for icon-only screens; button panel names; desktop lock hints; infrared remote names; API 87.2". Project: "host tests: note rows".

---

### Task 5: Documents and a chord session for sr_drive

**Files:**
- Modify: `README.md` (a "Using it on the device" section: the chord table as prose, the settings screen, what the lock screen and remotes say), `docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md` (section 17 status: as built, deviations), `docs/roadmap.md` (phase 3 done; next: the memory plan), `tools/sr_drive.py` (a third scripted session "chords" that runs the Task 2 step 2 sequences and checks the counters)
- Create: `docs/measurements/2026-09-24-phase-3.txt` (the device outputs of Tasks 2 to 4 in plain lines)

- [ ] **Step 1: sr_drive chords session**

Read tools/sr_drive.py's session structure and add a session that sends the chord sequences with `input send` through tools/flipper_cli.py's connection, waits for speech to go idle (`sr status` polling), and checks that the utterance counter rose and that `sr screen` still shows the same screen (the chord did not navigate). Run it; expect 0 failures.

- [ ] **Step 2: Documents and commit**

Write the README section in plain prose for a blind reader (no tables), the spec status, the roadmap, the measurements file. Commit: "docs: phase 3 as built; sr_drive chord session".
