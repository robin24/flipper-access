# Text screens and WiFi Marauder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Text boxes and widget scrolling text move and speak one printed line at a time in whole words, consoles speak new output as paced changes on the same screen, and every word WiFi Marauder shows is pronounced recognisably, with the app's flows unchanged.

**Architecture:** A new pure C unit, `text_stops`, holds the wrapping, the stops and the place-keeping, and is tested on the computer. The text box and the widget scrolling text are thin adapters over it that draw and give the reader hints. The reader gets one new hint, the reading kind, and treats reading screens by its rules. The speech rules and the one app label change are independent of all that.

**Tech Stack:** C for the Flipper firmware (fbt, arm-none-eabi), clang with sanitizers for host tests, Python for the device tools.

**Spec:** `docs/superpowers/specs/2026-11-05-text-screens-and-marauder-design.md`

## Global Constraints

- The app's flows don't change. A flow problem is reported to Robin, not fixed.
- With the reader off, behaviour is today's.
- No new functions are exported in the SDK, and `targets/f7/api_symbols.csv` must not change. New hints go in `canvas_i.h`.
- Every network name and address in a committed file is made up: `Example-Net`, `Other-Net`, `a0:1b:2c:3d:4e:5f`. Nothing from Robin's environment goes in the repo, and no session or device records either.
- Check the image with `tools/flash_headroom.sh` before every flash. The limit is 880,640 bytes, and 8,428 are spare today. If it doesn't fit, stop and tell Robin.
- After a flash, run `sr screen` before any key. Never send loader exit signals to apps, use Back. One agent on the device at a time.
- While Robin is at the device, use short commands and hand back, with no long blocking waits.
- Run nothing that transmits or changes the board's state: Attack, Targeted Attacks, Evil Portal, Sniff, Beacon Spam, Join WiFi. Scan all, List, Select and Info are fine.
- `Momentum-Firmware/AGENTS.md` is the upstream project's policy for contributions to upstream. This is Robin's own GPL fork, worked on at Robin's request, and nothing is opened against Next-Flip. Pull requests go to `robin24/Momentum-Firmware` and `robin24/flipper-access`.
- Two repositories are involved. Firmware files commit in `Momentum-Firmware` on branch `claude/marauder-speech-2026-11-05`, which Task 1 creates from `screen-reader`. Tests, tools and docs commit in the project on the branch of the same name, which already exists.
- Commit messages say what is now true in a sentence and end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Format changed firmware C files with `Momentum-Firmware/toolchain/current/bin/clang-format -i` before each commit.

## Review Focus

1. Console text with `\r\n` line endings, control bytes and non-ASCII names, because the board prints `\r\n`: a line reads clean, and a line of only such bytes isn't a silent stop. Pinned in Task 2.
2. A glyph wider than the row, or of zero width: wrapping always advances and never hangs. Pinned in Task 2.
3. Text that shrinks or is cleared while the current place is past its end, because Marauder halves its store and resets it for a new command: the first stop or "Empty", never a read past the end. Pinned in Task 3 under the address sanitizer.
4. A key held down, or more steps queued than there are stops: movement stops at the first and last stops. Pinned in Task 3.
5. The reader switched off and on with a console or scrolling text open: no crash, scrolling works in both states. Pinned by device steps in Tasks 5 and 6.

---

### Task 1: Pronunciation

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/speech_text.c` (rule list at the top, `terms[]` at line 180, `stop_words[]` at line 201, `speech_text_expand` at line 509)
- Modify: `tools/voice_words.txt`
- Test: `tests/host/test_speech_text.c`

**Interfaces:**
- Consumes: nothing.
- Produces: no new functions. `speech_text_expand` gives the new output.

- [ ] **Step 1: Create the firmware branch**

```bash
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware checkout -b claude/marauder-speech-2026-11-05 screen-reader
```

- [ ] **Step 2: Write the failing tests**

Add `test_marauder_words` to `tests/host/test_speech_text.c`, call it from `main`, and change the two existing lines in `test_rule11_minus` to `expect("Ch-3", "C H three")` and `expect("a -b", "a dash b")`.

```c
static void test_marauder_words(void) {
    // MAC addresses, pair by pair
    expect("a0:1b:2c:3d:4e:5f", "ay zero, one B, two C, three D, four E, five F");
    expect("A0:1B:2C:3D:4E:60", "ay zero, one B, two C, three D, four E, six zero");
    expect("BSSID: a0:1b:2c:3d:4e:5f", "B S S I D, ay zero, one B, two C, three D, four E, five F");
    expect(
        "-84 Ch: 2 a0:1b:2c:3d:4e:5f ESSID: Example-Net 31 14",
        "minus eighty four C H, two ay zero, one B, two C, three D, four E, five F "
        "E S S I D, Example Net thirty one fourteen");
    expect("12:34", "twelve thirty four");
    expect("12:34:56", "twelve thirty four fifty six");
    // Stop words
    expect("[+] ADD ITEM", "plus ADD ITEM");
    expect("ITEMS", "ITEMS");
    expect("STAGE", "STAGE");
    expect("TRUE", "TRUE");
    expect("FALSE", "FALSE");
    expect("WRITE", "WRITE");
    expect("BEGIN", "BEGIN");
    expect("CLOSE", "CLOSE");
    // Abbreviations
    expect("list -a", "list dash a");
    expect("ap", "ay P");
    expect("ssid", "S S I D");
    expect("sta", "S T ay");
    expect("rssi", "R S S I");
    expect("Ch: 6", "C H, six");
    expect("pmkid", "P M K I D");
    expect("bt", "B T");
    expect("sd", "S D");
    expect("dns", "D N S");
    expect("ssh", "S S H");
    expect("http", "H T T P");
    expect("https", "H T T P S");
    expect("smtp", "S M T P");
    expect("rdp", "R D P");
    expect("csa", "C S ay");
    expect("sae", "S ay E");
    // Joined words
    expect("stopscan", "stop scan");
    expect("scanall", "scan all");
    expect("pcaps", "pea caps");
    expect("ForcePMKID", "Force P M K I D");
    expect("ForceProbe", "Force Probe");
    expect("SavePCAP", "Save pea cap");
    expect("EnableLED", "Enable L E D");
    expect("EPDeauth", "E P dee auth");
    // Dash and hash
    expect("select -a 4", "select dash a four");
    expect("-40", "minus forty");
    expect("- 90", "ninety");
    expect("#list", "hash list");
    expect("#1", "number one");
    expect("#", "number");
    // The index first in a list row
    expect("[4][CH:1] Example-Net -40", "four C H, one Example Net minus forty");
}
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `tools/run_host_tests.sh`
Expected: FAIL lines from `test_marauder_words`, ending in "speech text checks failed".

- [ ] **Step 4: Implement the rules in `speech_text.c`**

Add the eight stop words and the terms. In `speech_text_expand`, before the token scan at each position, check for a MAC address: exactly six pairs of hex digits joined by colons, with no alphanumeric or colon just before or after it. Spell each digit with `ones[]` and each letter as `single_character` does, with a comma after every pair but the last. In the between-tokens branch, a `-` with a letter next gives `out_word(&o, "dash")`, and a `#` with a letter next gives `out_word(&o, "hash")`. Add these as rules 15, 16 and 17 in the comment at the top of the file.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `tools/run_host_tests.sh`
Expected: every check passes, including the voice parity check.

- [ ] **Step 6: Add the board's words to the vocabulary list**

Add `hash`, `targets`, `tran` and `ssids` to `tools/voice_words.txt`. Add nothing from `tools/voice_words.local.txt` or the device's `missing.txt` without checking it's a generic word and not a network name.

- [ ] **Step 7: Commit in both repositories**

```bash
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware add applications/services/screen_reader/speech_text.c
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware commit -m "MAC addresses are spelled pair by pair, a dash starting a word and a hash before a letter are spoken, and Marauder's abbreviations, joined words and capitalised words are read recognisably"
git -C /Users/robin/Downloads/flipper-access add tests/host/test_speech_text.c tools/voice_words.txt
git -C /Users/robin/Downloads/flipper-access commit -m "The speech tests hold the rules for MAC addresses and Marauder's words, and the vocabulary list has the words only the board prints"
```

Both commit messages end with the attribution line.

### Task 2: Rows and stops

**Files:**
- Create: `Momentum-Firmware/applications/services/gui/modules/text_stops.h`
- Create: `Momentum-Firmware/applications/services/gui/modules/text_stops.c`
- Create: `tests/host/test_text_stops.c`
- Modify: `tools/run_host_tests.sh` (a build-and-run block after the throttle's, and the header comment)

The gui service has no `sources` list, so fbt compiles the new file by itself. The file needs only `<stdbool.h>`, `<stddef.h>`, `<stdint.h>` and `<string.h>`, and it isn't added to `sdk_headers`.

**Interfaces:**
- Consumes: nothing.
- Produces, in `text_stops.h`:

```c
#define TEXT_STOPS_ROW_CHARS     47 /* the most one tapped string holds */
#define TEXT_STOPS_STOP_CHARS    60
#define TEXT_STOPS_OPENING_CHARS 100
#define TEXT_STOPS_ANCHOR_BYTES  16

typedef uint8_t (*TextStopsGlyphWidth)(char c, void* context);

typedef struct {
    TextStopsGlyphWidth glyph_width;
    void* context;
    uint16_t row_width; /* pixels */
    uint8_t rows_max; /* rows the display holds, at least 1 */
} TextStopsLayout;

typedef enum {
    TextStopsBreakLine, /* a newline ended the row */
    TextStopsBreakSpace, /* broken at a space, which isn't drawn */
    TextStopsBreakWord, /* broken inside a word */
    TextStopsBreakEnd, /* the text ended */
} TextStopsBreak;

typedef struct {
    size_t start; /* the row's first byte */
    size_t length; /* bytes to draw: no newline, no carriage return before it, no space at a break */
    size_t next; /* where the next row starts */
    TextStopsBreak ends;
} TextStopsRow;

typedef struct {
    size_t start; /* the first row's first byte */
    size_t end; /* just after the last drawn byte */
    size_t next; /* where to look for the next stop */
    uint8_t rows;
    bool line_start; /* begins its printed line */
    bool complete; /* its printed line ends in a newline */
} TextStop;

typedef struct {
    size_t chars;
    uint8_t rows;
} TextStopsGroup;

void text_stops_row(const char* text, size_t start, const TextStopsLayout* layout, TextStopsRow* row);
bool text_stops_line_is_silent(const char* line, size_t length);
/** Add a row of `chars` bytes. True when it begins a new stop; a row at a line's start always does. */
bool text_stops_group_row(TextStopsGroup* group, size_t chars, bool line_start, const TextStopsLayout* layout);
/** The first stop at or after `from`, which is a row's start. False when there's none. */
bool text_stops_next(const char* text, size_t from, const TextStopsLayout* layout, TextStop* stop);
/** The last stop starting before `before`. False when there's none. */
bool text_stops_prev(const char* text, size_t before, const TextStopsLayout* layout, TextStop* stop);
```

- [ ] **Step 1: Write the failing tests in `tests/host/test_text_stops.c`**

Use the same `CHECK` macro and pass-count ending as `test_sr_throttle.c`. The stand-in layout has every glyph 6 pixels wide, `row_width` 120, so 20 characters to a row, and `rows_max` 5. Each `rows` and `end` value below is exact.

```c
static void test_row_breaks_at_space(void) {
    // "With compatible marauder firmware", 33 characters
    // Row at 0: length 15, next 16, ends Space
    // Row at 16: length 17, next 33, ends End
}
static void test_row_exact_fit(void) {
    // 20 'a' then " bbb": length 20, next 21, ends Space
    // 20 'a' then "\nb": length 20, next 21, ends Line
}
static void test_row_long_word(void) {
    // 25 'x': length 20, next 20, ends Word; then length 5, next 25, ends End
}
static void test_row_carriage_return(void) {
    // "one\r\ntwo\r\n": length 3, next 5, ends Line; length 3, next 10, ends Line;
    // at 10: length 0, next 10, ends End
}
static void test_row_char_limit(void) {
    // A 2 pixel glyph, 60 'i': length 47, next 47, ends Word
}
static void test_row_always_advances(void) {
    // A zero width glyph, 60 'x': length 47, ends Word
    // A 200 pixel glyph, "xy": length 1, next 1, ends Word; then length 1, next 2, ends End
}
static void test_silent_lines(void) {
    // Silent: "", "   ", "-----", " - - ", "|||", "\r", "\xE2\x9C\x93"
    // Not silent: "a", "> ", "=====", "[1]"
}
static void test_stops_of_a_list(void) {
    // "[1][CH:1] Example-Net -40\n[2][CH:6] Other-Net -71\n3 selected\n> "
    // Four stops. The first three are complete, the fourth, ">", isn't.
    // The first has rows 2, because it's 25 characters.
}
static void test_long_line_splits_at_rows(void) {
    // Twelve words of 9 'a' joined by spaces, 119 characters, then "\n". Rows are 19 long.
    // Stop 1: start 0, end 59, next 60, rows 3, line_start true, complete true.
    // Stop 2: start 60, end 119, rows 3, line_start false, complete true.
    // No third stop.
}
static void test_rows_max_limits_a_stop(void) {
    // The same text with rows_max 2: stop 1 has rows 2, end 39.
}
static void test_silent_lines_are_skipped(void) {
    // "one\n\n---\n   \ntwo\n": next from 0 is at 0; next from its next field is at 13.
    // prev before 13 is at 0. prev before 0 is false.
}
static void test_prev_within_a_long_line(void) {
    // The twelve words: prev before 60 is at 0, rows 3.
}
static void test_group_row(void) {
    // Four rows of 19 characters, rows_max 5, only the first at a line start:
    // true, false, false, true. The space between rows counts, so the third reaches 59
    // and the fourth would reach 79.
}
```

Write these as real calls with `CHECK`s. The comments here give the inputs and every expected value.

- [ ] **Step 2: Add the block to `tools/run_host_tests.sh`, and run it to verify it fails**

```bash
clang "${CFLAGS[@]}" -fsanitize=address,undefined -fno-sanitize-recover=all \
  -I "$ROOT/Momentum-Firmware/applications/services/gui/modules" -o "$OUT/test_text_stops" \
  "$TESTS/test_text_stops.c" "$ROOT/Momentum-Firmware/applications/services/gui/modules/text_stops.c"
if ! "$OUT/test_text_stops" > "$OUT/text_stops.txt"; then
  cat "$OUT/text_stops.txt"
  echo "text stops checks failed"
  exit 1
fi
echo "text stops: $(tail -n 1 "$OUT/text_stops.txt")"
```

Run: `tools/run_host_tests.sh`
Expected: FAIL, because `text_stops.c` doesn't exist.

- [ ] **Step 3: Implement the functions in `text_stops.c`**

`text_stops_row` keeps the position of the last space while it adds glyph widths. It stops at a newline, at the text's end, at `TEXT_STOPS_ROW_CHARS`, or when the next glyph would pass `row_width`. It always takes at least one character. When a row breaks at the width with the next character a space, that's `TextStopsBreakSpace`. A silent character is a dash, `|`, a byte up to space, or a byte above 0x7E, which mirrors `sr_normalize`. `text_stops_next` and `text_stops_prev` skip silent lines. `text_stops_prev` scans back by bytes to a line start, without measuring, and walks forward from there.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `tools/run_host_tests.sh`
Expected: "text stops:" with no failures, and the rest of the run still passing.

- [ ] **Step 5: Commit in both repositories**

```bash
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware add applications/services/gui/modules/text_stops.h applications/services/gui/modules/text_stops.c
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware commit -m "A new text_stops unit wraps text at spaces and groups rows into stops of at most 60 characters, without the canvas, so the computer can test it"
git -C /Users/robin/Downloads/flipper-access add tests/host/test_text_stops.c tools/run_host_tests.sh
git -C /Users/robin/Downloads/flipper-access commit -m "The host tests cover wrapping and stops"
```

Both commit messages end with the attribution line.

### Task 3: Keeping the place

**Files:**
- Modify: `Momentum-Firmware/applications/services/gui/modules/text_stops.h`, `text_stops.c`
- Test: `tests/host/test_text_stops.c`

**Interfaces:**
- Consumes: `text_stops_next`, `text_stops_prev` and `TextStopsLayout` from Task 2.
- Produces:

```c
typedef struct {
    size_t offset; /* the current stop's first byte */
    uint16_t index; /* 1-based, 0 when the text has no stops */
    uint16_t count;
    bool following; /* on or after the newest complete line, or no line is complete */
    bool live; /* a change of this stop without a key is news */
    size_t newest_offset; /* the newest complete line's first stop */
    uint16_t newest_index; /* 0 when no line is complete */
    char anchor[TEXT_STOPS_ANCHOR_BYTES];
    uint8_t anchor_length;
    bool anchor_complete;
} TextStopsCursor;

/** at_end is the box's TextBoxFocusEnd. */
void text_stops_cursor_open(TextStopsCursor* cursor, const char* text, const TextStopsLayout* layout, bool at_end);
void text_stops_cursor_refresh(TextStopsCursor* cursor, const char* text, const TextStopsLayout* layout, bool at_end);
void text_stops_cursor_step(TextStopsCursor* cursor, const char* text, const TextStopsLayout* layout, bool at_end, int16_t steps);

bool text_stops_opening_takes(uint16_t taken, size_t used_chars, size_t stop_chars);
void text_stops_opening_step(bool* opening, uint16_t* current, uint16_t taken, uint16_t total, int8_t step);
```

- [ ] **Step 1: Write the failing tests**

`T` is `"one\ntwo\nthree\n> "`, which has the stops one, two, three and an unfinished `>`.

```c
static void test_cursor_open(void) {
    // not at_end: index 1, count 4, offset 0, following false, live true
    // at_end: index 3 ("three"), count 4, following true, live true
    // "" either way: index 0, count 0
    // Twelve words of 9 'a' then "\n", at_end: index 1 of 2, its first stop
}
static void test_cursor_step_and_following(void) {
    // at_end, from index 3: step +1 gives index 4, following true, live false (unfinished)
    // step -2 gives index 2, following false, live false
    // step +1 gives index 3, following true, live true
}
static void test_cursor_step_clamps(void) {
    // step +100 gives the last stop; step -100 gives index 1; on "" both leave index 0
}
static void test_cursor_follows_new_lines(void) {
    // at_end on T, refresh with "one\ntwo\nthree\nfour\n> ": index 4 ("four"), count 5, live true
}
static void test_cursor_stays_while_reading_back(void) {
    // at_end on "two": refresh with more lines appended: same offset, index 2, live false
}
static void test_cursor_after_trimming(void) {
    // at_end on "one\ntwo\nthree\nfour\n", step -1 to "three": refresh with "three\nfour\n":
    // offset 0, index 1, following false
    // The same text, step -2 to "two": refresh with "wo\nthree\nfour\n":
    // index 1, offset 0, following false, live false
}
static void test_cursor_matches_exactly(void) {
    // On the complete "a" in "x\na\nabc\n": refresh with "x\nabc\n": index 1, offset 0
    // On the second "same" of "same\nsame\nsame\n": refresh with one more "same\n": offset 5, index 2
    // On the unfinished "Sca" of "one\nSca", not at_end: refresh with "one\nScanning\n": offset 4, index 2
}
static void test_cursor_replaced_text(void) {
    // Not at_end, on index 2 of T: refresh with "new text": index 1, offset 0, live true
}
static void test_cursor_shrinks_past_the_end(void) {
    // On the last stop of a 200 byte text: refresh with "": index 0, count 0
    // Refresh with "one\n": index 1, offset 0. The address sanitizer proves no read past the end.
}
static void test_cursor_no_complete_line(void) {
    // at_end on "Sca": index 1, following true, live false
    // refresh with "Scan": the same
    // refresh with "Scan\n": index 1, following true, live true
}
static void test_opening_takes_save_prompt(void) {
    // Lines of 24, 27, 28, 21 and 30 characters: takes(0, 0, 24) true, takes(1, 24, 27) true,
    // takes(2, 51, 28) true, takes(3, 79, 21) true, takes(4, 100, 30) false
    // The first stop is always taken: takes(0, 0, 150) true
}
static void test_opening_step(void) {
    // Opening, taken 4, total 7: Down gives opening false, current 5
    // Opening, taken 4, total 7: Up gives opening false, current 4
    // Opening, taken 1, total 1: Down stays opening; Up gives opening false, current 1
    // Not opening, current 5: Up gives 4. Current 1: Up stays 1. Current 7 of 7: Down stays 7.
}
```

Write these as real calls and `CHECK`s.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `tools/run_host_tests.sh`
Expected: a compile error, because the functions aren't defined.

- [ ] **Step 3: Implement in `text_stops.c`**

`text_stops_cursor_refresh` walks every stop once to get the count, the last stop, the newest complete line's first stop and the place. A complete anchor shorter than 16 bytes must match the candidate's whole length. An unfinished anchor is a prefix. Among matches, the nearest at or before the old offset wins, and with no match the place is the first stop. `live` is true when not `at_end`, and otherwise when following on a complete stop. After a step, `following` compares the offset with `newest_offset`, and steps walk with next and prev so no full pass is needed. The anchor is copied after every move.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `tools/run_host_tests.sh`
Expected: "text stops:" with no failures and no sanitizer report.

- [ ] **Step 5: Commit in both repositories**

```bash
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware add applications/services/gui/modules/text_stops.h applications/services/gui/modules/text_stops.c
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware commit -m "text_stops keeps the place in text that grows or is trimmed, follows the newest complete line, and decides what a scrolling text's opening reads"
git -C /Users/robin/Downloads/flipper-access add tests/host/test_text_stops.c
git -C /Users/robin/Downloads/flipper-access commit -m "The host tests cover keeping the place, following and the opening of scrolling text"
```

Both commit messages end with the attribution line.

### Task 4: The reader

**Files:**
- Modify: `Momentum-Firmware/applications/services/gui/canvas_i.h`, `canvas.c`
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_model.h`, `screen_model.c`, `screen_reader.c:129-150`, `screen_reader_cli.c:128-142`
- Test: `tests/host/test_screen_model.c`

**Interfaces:**
- Consumes: nothing.
- Produces, in `canvas_i.h` (the values match `SrReading` and `SrJoin`, as `CANVAS_TAP_JOIN_*` already do):

```c
#define CANVAS_TAP_JOIN_SPACE 3 /* one space between them: a line wrapped at a space */
#define CANVAS_TAP_READING_STOP     1 /* a stop that keys move */
#define CANVAS_TAP_READING_LIVE     2 /* a stop whose change without a key is news */
#define CANVAS_TAP_READING_OPEN     3 /* a scrolling text's opening */
#define CANVAS_TAP_READING_POSITION 4 /* the opening's "4 of 7" */

/** The next string or canvas_tap_note is reading text of this kind. */
void canvas_tap_hint_reading(Canvas* canvas, uint8_t kind);
```

- Produces, in `screen_model.h`: `SrJoinSpace = 3`; `SrReadingNone`, `SrReadingStop`, `SrReadingLive`, `SrReadingOpen`, `SrReadingPosition` as 0 to 4; `uint8_t reading` in `SrRecord` and `SrRow`; `uint8_t reading` in `SrScreen`, the kind of the first reading record, with a position note counting as opening.

- [ ] **Step 1: Write the failing tests**

Add a helper `add_reading(f, y, reading, focus, index, count, text)`, which adds a secondary font record on `SrLayerWindow`. Call each test from `main`. Unless the test says otherwise, the model has verbosity 1.

```c
static void test_join_with_space(void) {
    // "With compatible" focus 1 of 3, then "marauder firmware" with SrJoinSpace:
    // one focus row, "With compatible marauder firmware", index 1, count 3
}
static void test_reading_opens_with_position(void) {
    // Verbosity 0, 1 and 2: a live stop "one" 1 of 3 first: SrAnnScreen "one, 1 of 3"
}
static void test_live_line_is_a_change(void) {
    // Live "one" 1 of 3, then live "two" 2 of 3, no key:
    // one SrAnnChange "two", not interrupting. No SrAnnScreen.
    // Then live "five" 5 of 5, no key, as after a burst of lines: SrAnnChange "five".
}
static void test_key_moves_are_focus(void) {
    // Stop "one" 1 of 3, then stop "two" 2 of 3 with a key: SrAnnFocus "two", interrupting
    // At verbosity 2: "two, 2 of 3"
}
static void test_quiet_while_reading_back(void) {
    // Stop "one" 1 of 3, then stop "two" 1 of 3, no key: no announcement
}
static void test_repeated_line(void) {
    // Stop "same" 1 of 3, then stop "same" 2 of 3 with a key: SrAnnFocus "same"
    // Live "same" 3 of 3, then live "same" 4 of 4, no key: no announcement
    // At the first stop, stop "same" 1 of 3 again with a key: no announcement
}
static void test_reading_is_not_a_keyboard(void) {
    // A focus stop in SrFontKeyboard: on_keyboard false, has_keyboard false
}
static void test_reading_is_not_the_title(void) {
    // An opening row in SrFontPrimary at y 10: title_row -1
}
static void test_bare_prompt_stays(void) {
    // A stop ">" 2 of 2 keeps its row, and as the first frame SrAnnScreen says ">, 2 of 2"
    // A plain ">" with no reading kind is still dropped
}
static void test_opening_announcement(void) {
    // Title "Save pcaps?" (primary, y 10), opening rows "With compatible marauder" and
    // "firmware, you can choose to", position "4 of 7" at y 80, buttons left "No" and right "Yes":
    // "Save pcaps?. With compatible marauder. firmware, you can choose to. 4 of 7. buttons: left No, right Yes"
}
static void test_position_keeps_its_room(void) {
    // Opening rows long enough to overflow SR_ANN_TEXT_MAX: the text is cut,
    // and the announcement still ends "4 of 7. buttons: left No, right Yes"
}
static void test_opening_is_a_new_screen(void) {
    // Stop "one" 5 of 7, then opening rows with the same buttons: SrAnnScreen
    // Opening rows, then a stop with a key: SrAnnFocus with only the stop
}
static void test_text_below_the_display(void) {
    // Row at y 40, button at y 62, a record at y 75 joined with SrJoinSpace:
    // the joined text is on the row at y 40, and the button's text is unchanged
}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `tools/run_host_tests.sh`
Expected: a compile error on `SrJoinSpace` and `SrReadingStop`.

- [ ] **Step 3: Implement the canvas hint in `canvas.c`**

Add `uint8_t tap_hint_reading` to `Canvas` and `uint8_t reading` to `CanvasTapRecord`. `canvas_tap_fill` copies and clears it. Clear it everywhere `tap_hint_join` is cleared: the two no-callback branches, `canvas_tap_set_callback` and `canvas_tap_set_layer`. Add it to the `continues` condition in `canvas_tap_glyph`. Copy `reading` in `sr_text` in `screen_reader.c`, and print it in `screen_reader_cli.c` as ` reading=%u` when it isn't zero.

- [ ] **Step 4: Implement the rules in `screen_model.c`**

- In the sort in `sr_screen_build`, a button goes after every record that isn't a button, ahead of the existing rule.
- A reading string is exempt from `sr_is_arrow_token`.
- `SrJoinSpace` appends a space and the text.
- Rows take `reading` from their first record.
- Fill `screen->reading`. When it isn't none, `has_keyboard` and `on_keyboard` stay false and no reading row is the title.
- In `sr_screen_changed`, after the title check: `if(cur->reading == SrReadingOpen && prev->reading != SrReadingOpen) return true;` then `if(prev->reading && cur->reading && cur->reading != SrReadingOpen) return false;`.
- In `sr_screen_announcement`, append the focus position when `s->reading` too. A `SrReadingPosition` row isn't read with the rows. It's built before the text, like the buttons, counted in `keep`, and appended before them.
- In `sr_model_process`, on a reading screen after a reading screen with a focus row:

```c
bool text_same = strcmp(focus_now, focus_was) == 0;
bool index_same = sr_focus_index(cur) == sr_focus_index(&model->prev);
if(key_recent && (!text_same || !index_same)) {
    /* the existing focus announcement, position at verbosity >= 2 */
} else if(!key_recent && cur->reading == SrReadingLive && !text_same) {
    sr_emit(out, out_max, &n, SrAnnChange, false, focus_now);
}
/* otherwise the focus row says nothing; the other rows keep today's path */
```

`sr_focus_index` is a new static function returning the first focus row's index.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `tools/run_host_tests.sh`
Expected: every check passes, and no existing test changed.

- [ ] **Step 6: Confirm the firmware compiles and the API is unchanged**

Run: `(cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt firmware_all)`, in the background, then `git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware status --short targets/`
Expected: the build succeeds, and `targets/` shows no change.

- [ ] **Step 7: Commit in both repositories**

```bash
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware add applications/services/gui/canvas_i.h applications/services/gui/canvas.c applications/services/screen_reader/screen_model.h applications/services/screen_reader/screen_model.c applications/services/screen_reader/screen_reader.c applications/services/screen_reader/screen_reader_cli.c
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware commit -m "The reader knows reading text: a live stop's new line is a paced change on the same screen, a key move is a focus even onto an identical line, position is said on opening at any verbosity, and a scrolling text's opening keeps room for its position"
git -C /Users/robin/Downloads/flipper-access add tests/host/test_screen_model.c
git -C /Users/robin/Downloads/flipper-access commit -m "The host tests cover how the reader treats reading text"
```

Both commit messages end with the attribution line.

### Task 5: The text box

**Files:**
- Modify: `Momentum-Firmware/applications/services/gui/modules/text_box.c`

**Interfaces:**
- Consumes: `TextStopsLayout`, `TextStopsRow`, `TextStop`, `TextStopsCursor`, `text_stops_row`, `text_stops_next` and the cursor functions from Tasks 2 and 3; `canvas_tap_hint_reading`, `canvas_tap_hint_focus`, `canvas_tap_hint_join`, `canvas_tap_hint_full_text` and `canvas_tap_note` from `gui/canvas_i.h`.
- Produces: no API change. The public functions of `text_box.h` are the same.

- [ ] **Step 1: Add the reader-on path to `text_box.c`**

- `TextBoxModel` gains `bool reading`, `bool opened`, `int16_t pending` and `TextStopsCursor cursor`. Add `_Static_assert(TEXT_STOPS_ROW_CHARS < CANVAS_TAP_TEXT_MAX, ...)`.
- In the draw callback, after the font is set: `bool reader = canvas->tap_callback != NULL;`. If that differs from `model->reading`, set `reading`, clear `opened` and `pending`, and clear `formatted`.
- With `reader` false, the rest of the callback is today's code.
- With `reader` true, the layout has `row_width` `TEXT_BOX_TEXT_WIDTH`, `rows_max` `TEXT_BOX_TEXT_HEIGHT / canvas_current_font_height(canvas)`, and a glyph width function calling `canvas_glyph_width`. When `!model->formatted`, call `open` if not `opened`, otherwise `refresh`, and set both flags. Then apply `pending` with `step` and clear it. The refresh comes before the step, so a move lands on current text. `at_end` is `model->focus == TextBoxFocusEnd`.
- Draw `elements_slightly_rounded_frame`, then `elements_scrollbar(canvas, index - 1, count)` when `count > 1`, then rows from `cursor.offset` at `x` 3, starting at `y` 11 and adding the font height while `y < 64`, using `text_stops_row` and `furi_string_set_strn` into `text_line`, then `canvas_draw_str`.
- Hints before each row are:
  - the stop's first row: `canvas_tap_hint_focus(canvas, index, count)` and `canvas_tap_hint_reading(canvas, live ? CANVAS_TAP_READING_LIVE : CANVAS_TAP_READING_STOP)`;
  - the stop's other rows: `canvas_tap_hint_join` with `CANVAS_TAP_JOIN_SPACE` after a space break or `CANVAS_TAP_JOIN_DIRECT` after a word break, and the same reading hint;
  - every other row: `canvas_tap_hint_full_text(canvas, "", false)`.
- With no stops, draw nothing and report `canvas_tap_hint_reading(canvas, CANVAS_TAP_READING_STOP); canvas_tap_note(canvas, 3, 11, "Empty");`.
- In `text_box_process_down` and `text_box_process_up`, when `model->reading`, change `pending` by one whatever `lines` is, including 0.
- `text_box_reset` clears `opened`, `pending` and `reading`.

- [ ] **Step 2: Build and check the size**

Run: `(cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt updater_package)` in the background, then `tools/flash_headroom.sh`.
Expected: the build succeeds and the image is under 880,640 bytes. Note the bytes spare for the task's report.

- [ ] **Step 3: Flash and read the screen**

Run: `(cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt flash_usb)` in the background. When the port is back: `.venv/bin/python tools/flipper_cli.py "sr screen"`.
Expected: no crash popup, and the reader is running.

- [ ] **Step 4: Check the console on the device**

Use `tools/sr_drive.py --interactive`, or the session's driver script if it's still there. Open `[ESP32] WiFi Marauder`, then Scan for a short time, then List ap. Check each of these:

- Opening a console says one stop and a count, at verbosity 1.
- Up moves one line at a time, with no broken words, and a network's index is heard first.
- An identical adjacent line is still spoken.
- New output during a short Scan all comes as paced changes, and Up goes quiet.
- Down to the newest line starts following again.
- With the console open, `sr off`, then Up and Down, then `sr on`, then Up and Down: no crash, and scrolling works both ways.
- "Empty" on opening a console, against any noise when a command starts. If it adds noise, remove the note and tell Robin.

- [ ] **Step 5: Commit**

```bash
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware add applications/services/gui/modules/text_box.c
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware commit -m "With the reader on, the text box wraps at spaces, moves one printed line at a time, keeps the place when text arrives, and follows the newest complete line when it opens at the end"
```

The commit message ends with the attribution line.

### Task 6: Scrolling text in widgets

**Files:**
- Modify: `Momentum-Firmware/applications/services/gui/modules/widget_elements/widget_element_text_scroll.c`

**Interfaces:**
- Consumes: `TextStopsLayout`, `TextStopsRow`, `TextStopsGroup`, `text_stops_row`, `text_stops_group_row`, `text_stops_line_is_silent`, `text_stops_opening_takes`, `text_stops_opening_step`; the hints as in Task 5.
- Produces: no API change.

- [ ] **Step 1: Add the reader-on path**

- `TextScrollLineArray` gains `uint16_t stop` (1-based, 0 for a silent line) and `uint8_t join` (`CANVAS_TAP_JOIN_*` onto the row before). The model gains `bool reader`, `bool opening`, `uint16_t stop_current`, `uint16_t stops_total` and `uint16_t opening_taken`.
- In the first draw, set `reader` from `canvas->tap_callback`. It then stays as it is for the element's life, because formatting consumes the text.
- With `reader` false, `fill_lines`, the draw loop and the input code are today's.
- With `reader` true, the fill handles control symbols at each printed line's start as today, then walks rows with `text_stops_row` until the line ends, using `canvas_glyph_width` in the line's font. `row_width` is `model->width`, and `rows_max` is the larger of 1 and `model->height / canvas_get_font_params(canvas, FontSecondary)->leading_default`. Rows of a silent line get `stop` 0. Other rows go through `text_stops_group_row` to number the stops. `opening_taken` grows through `text_stops_opening_takes` while it says yes, and once it says no it never takes again. `opening` starts true.
- In the opening, the display starts at the first row. Rows of stops up to `opening_taken` carry `canvas_tap_hint_reading(canvas, CANVAS_TAP_READING_OPEN)` and their join. Other visible rows are hidden with `canvas_tap_hint_full_text(canvas, "", false)`. Rows of taken stops past the display are reported with `canvas_tap_note` at the next `y`, without being drawn. If `opening_taken < stops_total`, report `canvas_tap_hint_reading(canvas, CANVAS_TAP_READING_POSITION)` and `canvas_tap_note` with the text from `snprintf("%u of %u", opening_taken, stops_total)`, at `y` past all the rows.
- After the opening, the display starts at the first row of `stop_current`. That stop's first row carries `canvas_tap_hint_focus(canvas, stop_current, stops_total)` and `CANVAS_TAP_READING_STOP`, and its other rows the join and `CANVAS_TAP_READING_STOP`. Other rows are hidden.
- The scrollbar shows position `opening ? 0 : stop_current - 1` of `stops_total`, when `stops_total > 1`.
- In input with `reader` true, Up and Down call `text_stops_opening_step` with step -1 or +1 and consume the key.

- [ ] **Step 2: Build, check the size, flash**

Run: `(cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt updater_package)` in the background, then `tools/flash_headroom.sh`, then `(cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt flash_usb)` in the background, then `.venv/bin/python tools/flipper_cli.py "sr screen"`.
Expected: fits, flashes, no crash popup.

- [ ] **Step 3: Check on the device**

- **Save prompts:** copy `/ext/apps_data/marauder/save_pcaps_here.setting` and `save_logs_here.setting` to the computer, or rename them, then remove them and open Marauder. Expect "Save pcaps? With compatible marauder. firmware, you can choose to. save captures (pcaps) to the. flipper sd card here: 4 of 7. buttons: left No, right Yes." Down reads the folder path as one stop, then "You can change this setting in the app at any time. Would", then the last line. Up from the opening reads "flipper sd card here:" alone. Put the files back afterwards.
- **An existing info screen:** one NFC or Sub-GHz screen that uses scrolling text. A short one sounds the same as it did, in whole words. Scrolling still works.
- **Reader toggle:** with a scrolling text open, `sr off`, then Up and Down, then `sr on`, then Up and Down: no crash.

- [ ] **Step 4: Commit**

```bash
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware add applications/services/gui/modules/widget_elements/widget_element_text_scroll.c
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware commit -m "With the reader on, widget scrolling text wraps at spaces, opens with as many whole stops as fit and its position, and then moves one printed line at a time"
```

The commit message ends with the attribution line.

### Task 7: Unnamed buttons and the whole run

Marauder's source is in `applications/external`, a pin of upstream's Momentum-Apps, so by Robin's decision of 2026-11-05 the app stays as it is and the reader names an unnamed button.

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_model.c`
- Test: `tests/host/test_screen_model.c`

**Interfaces:**
- Consumes: the firmware from Tasks 1 to 6.
- Produces: no API change.

- [ ] **Step 1: Name an unnamed button, test first**

`test_unnamed_button`: "Some text" with buttons left "", center "" and right "2/3" describes as "Some text. buttons: left button, center button, right 2/3", and empty text without a button hint gives no row. In `sr_screen_build`, a record with a button hint and empty text gets the text "button".

- [ ] **Step 2: Build everything, check the size, flash the firmware with its resources**

Remove the old resources first, as the routine in `docs/developer-notes.md` says. Run:

```bash
rm -rf /Users/robin/Downloads/flipper-access/Momentum-Firmware/build/f7-firmware-C/resources /Users/robin/Downloads/flipper-access/Momentum-Firmware/build/f7-firmware-C/.extapps
```

```bash
(cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt updater_package)
```

```bash
tools/flash_headroom.sh
```

```bash
(cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt flash_usb_full)
```

Run the builds and the flash in the background. The update takes about six minutes. Then run `.venv/bin/python tools/flipper_cli.py "sr screen"`, and `"sysctl debug 1" "sysctl log_level debug"` as the routine says. Expected: fits, flashes, no crash popup.

- [ ] **Step 3: Update the card's clips**

Run: `.venv/bin/python tools/voice_build.py --set heart --backend kokoro --extract --card-apps --pull-missing --sync`, in the background.
Expected: it finishes without errors, and the new words have clips.

- [ ] **Step 4: Check the whole of Marauder on the device**

- Scan all for a short time, List ap, Select with a typed index, and hearing the reply.
- AP Info on a selected network.
- View Log from start and from end, and reading back during output.
- The log viewer on a log of at least three pages, on every page: the buttons are named, and turning a page reads the new page's opening.
- The script menus, moving through them without running anything.
- The lowest free heap, the minimum in `.venv/bin/python tools/flipper_cli.py "top 0"`, compared with 28,920 bytes.
- `text_box_view_test`, if `(cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt fap_text_box_view_test)` builds it, sent to the card and run for both ways of opening. If not, View Log from start and from end cover both, and say so in the report.

- [ ] **Step 5: Check with Robin in short turns**

Hand back after each short batch and wait for Robin's answer:

- Play the phrases in small batches with `.venv/bin/python tools/flipper_cli.py "sr say <phrase>"`, using the made-up strings from Task 1's test, and fix what Robin says sounds wrong. Each fix to a rule gets its test first.
- Robin unplugs the board once, and opens a console, to hear a console with no reply.

- [ ] **Step 6: Commit**

```bash
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware add applications/services/screen_reader/screen_model.c
git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware commit -m "The reader says button for a button drawn with no label"
git -C /Users/robin/Downloads/flipper-access add tests/host/test_screen_model.c docs/superpowers/specs/2026-11-05-text-screens-and-marauder-design.md docs/superpowers/plans/2026-11-05-text-screens-and-marauder.md
git -C /Users/robin/Downloads/flipper-access commit -m "The host tests cover an unnamed button, and the spec and plan say the app stays as upstream ships it"
```

Both commit messages end with the attribution line.

### Task 8: Docs and delivery

**Files:**
- Modify: `README.md` ("What changed against Momentum" at line 32, and new sections after "Sub-GHz Read RAW", before "The file browser's menus", at line 738)
- Modify: `docs/README.md` (the plans list)

**Interfaces:**
- Consumes: everything above.
- Produces: the merged work.

- [ ] **Step 1: Write the README sections**

Add `### Text boxes and scrolling text`, saying how opening, Up and Down, position and following work, and what's in Known limits. Add `### WiFi Marauder`, saying what the console says for List, Select and Scan all, how to read back, and that indexes are typed as before. Add a line to "What changed against Momentum". Use `Example-Net` in examples. Keep the README's plain, linear style, without tables. Add the plan to the list in `docs/README.md`.

- [ ] **Step 2: Run all the host tests**

Run: `tools/run_host_tests.sh`
Expected: every check passes.

- [ ] **Step 3: Open the fork's pull request and switch on Auto-fix**

Push `claude/marauder-speech-2026-11-05` in `Momentum-Firmware`, and open a pull request into `screen-reader` on `robin24/Momentum-Firmware`, with a description ending in the attribution line. Then bind it with `mcp__ccd_pr__bind_pr` if `get_status` doesn't report it, and call `mcp__ccd_pr__set_monitor` with Auto-fix and address comments on.

- [ ] **Step 4: Merge the fork's pull request after a green build**

Use `gh pr merge <n> --repo robin24/Momentum-Firmware --merge --admin`, as the project's ruleset routine says. If Robin hasn't asked for that, give the command in a `bash` block instead.

- [ ] **Step 5: Point the project at the merge and open its pull request**

In `Momentum-Firmware`, check out `screen-reader` and pull, then commit the new submodule pointer in the project, saying which merge it points at. Push the branch, and open a pull request into `main` on `robin24/flipper-access`, with a description ending in the attribution line. Bind it and switch on Auto-fix as in Step 3.

- [ ] **Step 6: Merge the project's pull request after a green build, as in Step 4, and confirm**

Run: `git -C /Users/robin/Downloads/flipper-access log -1 --format='%h %s' origin/main`
Expected: the merge of the pull request.
