# Screen Reader Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture every string the Flipper draws, model focus and screen changes, and mirror announcements to the USB console, so Robin can drive and read the device from one terminal window. No audio yet.

**Architecture:** A text tap inside the GUI service records drawn strings per frame and hands the frame to a new screen reader service thread. A pure C screen model (host tested) turns frames into announcements. A console command `sr` prints the captured screen, streams announcements, and forwards arrow keys as button presses.

**Tech Stack:** Momentum firmware (C, FreeRTOS, fbt build tool), Flipper CLI pipe API, clang on macOS for host tests, pyserial tools in the project folder.

**Spec:** `/Users/robin/Downloads/flipper-access/docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md`

## Global Constraints

- Firmware repo: `/Users/robin/Downloads/flipper-access/Momentum-Firmware`, work on branch `screen-reader` created from `dev` (commit d3f89dfe2). Do not touch the `applications/external` submodule beyond the existing Text to SAM patch.
- Project repo (tests, tools, docs): `/Users/robin/Downloads/flipper-access`. Commit there too.
- Build: `cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt` (full build, under 3 minutes). Warnings are errors (`-Werror`); COMPACT=1 is the default.
- Flash: `./fbt flash_usb` uploads and installs the firmware only (no resources), the device reboots through its updater and the serial port `/dev/cu.usbmodemflip_R0skie1` disappears for one to two minutes. Wait for it with the loop given in Task 6.
- Console helper: `/Users/robin/Downloads/flipper-access/.venv/bin/python /Users/robin/Downloads/flipper-access/tools/flipper_cli.py "<command>"`. Only one command runs at a time on the console; streaming commands hold it until Ctrl-C.
- Never close apps with `loader close` from scripts; it crashes the NFC app in read mode. Use `input send back short` presses. `power reboot` works while an app is open.
- Memory budget for the whole reader (all phases): about 19 KB heap. Phase 1 allocates everything once at service start, nothing per frame. No heap allocation on the GUI thread.
- All new public-looking functions stay in the internal headers `canvas_i.h` and `gui_i.h` so `targets/f7/api_symbols.csv` and the SDK API version 87.1 stay unchanged. If the build prints an API mismatch, something leaked into a public header; fix that instead of running `api_sync`.
- Sizes: `CANVAS_TAP_TEXT_MAX`, `SR_TEXT_MAX` are both 48; `SR_MAX_RECORDS` is 32; `SR_MAX_ROWS` is 16; `SR_ANN_TEXT_MAX` is 160.
- Text in announcements is plain ASCII. Non printable bytes are dropped by normalisation.
- Robin reads through a screen reader: keep console output line oriented, no box drawing, no colour codes.

---

## File structure

Firmware repo:

- `lib/momentum/settings.h`, `lib/momentum/settings.c`: four new settings (Task 1).
- `applications/services/gui/canvas_i.h`, `canvas.c`: the text tap, hints, glyph runs, font tracking (Task 5).
- `applications/services/gui/gui_i.h`, `gui.c`: frame begin and end, layer tags, `gui_tap_set` (Task 5).
- `applications/services/gui/elements.c`: full text hints in the ellipsis and marquee helpers (Task 8).
- `applications/services/gui/modules/submenu.c`, `variable_item_list.c`, `menu.c`, `file_browser.c`, `button_menu.c`, `text_input.c`: focus hints (Task 8).
- `applications/services/screen_reader/application.fam`: service manifest (Task 6).
- `applications/services/screen_reader/screen_model.h`, `screen_model.c`: pure C model, no furi includes (Tasks 2 to 4).
- `applications/services/screen_reader/screen_reader.h`, `screen_reader.c`: the service (Task 6).
- `applications/services/screen_reader/screen_reader_cli.h`, `screen_reader_cli.c`: the `sr` command (Tasks 6 and 7).
- `applications/services/application.fam`: add `screen_reader` to the metapackage (Task 6).

Project repo:

- `tests/host/test_screen_model.c`, `tools/run_host_tests.sh`: host unit tests (Task 2).
- `tools/sr_drive.py`: scripted device walk through (Task 9).
- `README.md`: usage notes (Task 9).

---

### Task 1: Branch and settings fields

**Files:**
- Modify: `Momentum-Firmware/lib/momentum/settings.h` (struct `MomentumSettings`, after the field `ScreenFrameColor rpc_color_bg;`)
- Modify: `Momentum-Firmware/lib/momentum/settings.c` (defaults after `.rpc_color_bg = ...`, table after `{setting_uint(rpc_color_bg, 0x000000, 0xFFFFFF)},`)

**Interfaces:**
- Produces: `momentum_settings.screen_reader` (bool), `momentum_settings.sr_rate` (uint32_t 40..120), `momentum_settings.sr_volume` (uint32_t 0..100), `momentum_settings.sr_verbosity` (uint32_t 0..2). Keys in the settings file are the field names.

- [ ] **Step 1: Create the branch**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git checkout -b screen-reader && git status --short | head
```

Expected: on branch `screen-reader`; the only dirty entry is the submodule `applications/external` (the Text to SAM patch). Leave it.

- [ ] **Step 2: Add the fields to the struct**

In `lib/momentum/settings.h`, inside `typedef struct { ... } MomentumSettings;`, after the line `ScreenFrameColor rpc_color_bg;` add:

```c
    bool screen_reader;
    uint32_t sr_rate;
    uint32_t sr_volume;
    uint32_t sr_verbosity;
```

- [ ] **Step 3: Add defaults and table rows**

In `lib/momentum/settings.c`, in the initializer `MomentumSettings momentum_settings = { ... };`, after the line ending `// Default Orange` add:

```c
    .screen_reader = false, // OFF
    .sr_rate = 72, // SAM speed, bigger is slower
    .sr_volume = 100, // %
    .sr_verbosity = 1, // Normal
```

In the table `momentum_settings_entries[]`, after `{setting_uint(rpc_color_bg, 0x000000, 0xFFFFFF)},` add:

```c
    {setting_bool(screen_reader)},
    {setting_uint(sr_rate, 40, 120)},
    {setting_uint(sr_volume, 0, 100)},
    {setting_uint(sr_verbosity, 0, 2)},
```

- [ ] **Step 4: Build**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt 2>&1 | tail -8
```

Expected: ends with `Firmware binaries can be found at: dist/f7-C`, no errors, `.free_flash` still about 210000.

- [ ] **Step 5: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add lib/momentum/settings.h lib/momentum/settings.c && git commit -m "momentum settings: screen reader fields"
```

---

### Task 2: Screen model types, normalisation, and row building (host tested)

**Files:**
- Create: `Momentum-Firmware/applications/services/screen_reader/screen_model.h`
- Create: `Momentum-Firmware/applications/services/screen_reader/screen_model.c`
- Create: `tests/host/test_screen_model.c` (project repo)
- Create: `tools/run_host_tests.sh` (project repo)

**Interfaces:**
- Produces: everything in `screen_model.h` below. Later tasks use `sr_normalize`, `sr_screen_build`, `sr_screen_focus_text`, `sr_screen_describe`, `sr_model_init`, `sr_model_process`, and the types `SrRecord`, `SrFrame`, `SrRow`, `SrScreen`, `SrAnnouncement`, `SrModel`.

- [ ] **Step 1: Write the header**

Create `Momentum-Firmware/applications/services/screen_reader/screen_model.h`:

```c
/**
 * @file screen_model.h
 * Screen reader: pure C model of what is on the display. No firmware dependencies,
 * so it compiles on the host for unit tests.
 */
#pragma once

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SR_TEXT_MAX          48
#define SR_MAX_RECORDS       32
#define SR_MAX_ROWS          16
#define SR_ROW_TEXT_MAX      64
#define SR_ANN_TEXT_MAX      160
#define SR_MAX_ANNOUNCEMENTS 4

/** Same numbering as GuiLayer in gui.h; duplicated so this header has no gui dependency. */
enum {
    SrLayerDesktop = 0,
    SrLayerWindow = 1,
    SrLayerStatusLeft = 2,
    SrLayerStatusRight = 3,
    SrLayerFullscreen = 4,
    SrLayerUnknown = 255,
};

/** Same numbering as Font in canvas.h. */
enum {
    SrFontPrimary = 0,
    SrFontSecondary = 1,
    SrFontKeyboard = 2,
    SrFontBigNumbers = 3,
    SrFontBatteryPercent = 4,
    SrFontCustom = 255,
};

/** One drawn string as captured by the GUI text tap. */
typedef struct {
    int16_t x;
    int16_t y;
    uint8_t layer;
    uint8_t font;
    bool inverted; /**< drawn in white, i.e. on a filled box */
    bool focus; /**< a module marked this string as the focused item */
    uint16_t index; /**< 1-based position from the module, 0 if unknown */
    uint16_t count; /**< item count from the module, 0 if unknown */
    char text[SR_TEXT_MAX];
} SrRecord;

/** Everything captured during one frame. */
typedef struct {
    SrRecord records[SR_MAX_RECORDS];
    uint8_t count;
    bool overflow; /**< more strings were drawn than fit */
    uint8_t content_layer; /**< layer that drew the main content, SrLayerUnknown if none */
} SrFrame;

typedef enum {
    SrRowNormal,
    SrRowFocus,
    SrRowButton,
    SrRowStatus,
} SrRowKind;

/** Strings on one baseline, joined in reading order. */
typedef struct {
    char text[SR_ROW_TEXT_MAX];
    int16_t x;
    int16_t y;
    uint8_t font;
    SrRowKind kind;
    uint16_t index;
    uint16_t count;
} SrRow;

/** A frame after modelling. */
typedef struct {
    SrRow rows[SR_MAX_ROWS];
    uint8_t row_count;
    int8_t title_row; /**< index into rows, or -1 */
    uint8_t content_layer;
    bool has_content; /**< at least one record outside the status bar */
    bool has_keyboard; /**< at least one record in the keyboard font */
    bool overflow;
} SrScreen;

typedef enum {
    SrAnnFocus, /**< the focused item changed */
    SrAnnScreen, /**< a different screen appeared */
    SrAnnChange, /**< some text on the same screen changed */
    SrAnnTyped, /**< a character was typed into a text field */
    SrAnnHome, /**< the home screen with no text appeared */
} SrAnnKind;

typedef struct {
    SrAnnKind kind;
    bool interrupt; /**< speech should stop what it is saying */
    char text[SR_ANN_TEXT_MAX];
} SrAnnouncement;

typedef struct {
    SrScreen prev;
    SrScreen current;
    bool have_prev;
    uint32_t last_spontaneous_ms;
    uint8_t verbosity; /**< 0 terse, 1 normal, 2 verbose */
} SrModel;

/** Trim, collapse spaces, drop the text cursor bar and non printable bytes. */
void sr_normalize(const char* in, char* out, size_t out_size);

/** Turn a frame into rows, focus, title, buttons. */
void sr_screen_build(const SrFrame* frame, SrScreen* screen);

/** All focus rows joined with ", ". Returns the length written. */
size_t sr_screen_focus_text(const SrScreen* screen, char* out, size_t out_size);

/** Title, rows, focus with position, buttons, as one readable text. */
size_t sr_screen_describe(const SrScreen* screen, char* out, size_t out_size);

void sr_model_init(SrModel* model, uint8_t verbosity);

/** Compare the frame with the previous one and write announcements. Returns how many. */
size_t sr_model_process(
    SrModel* model,
    const SrFrame* frame,
    uint32_t now_ms,
    bool key_recent,
    SrAnnouncement* out,
    size_t out_max);

#ifdef __cplusplus
}
#endif
```

- [ ] **Step 2: Write the failing tests for normalisation and rows**

Create `tests/host/test_screen_model.c` in the project repo:

```c
#include <stdio.h>
#include <string.h>
#include "screen_model.h"

static int failures = 0;
static int checks = 0;

#define CHECK(cond)                                                            \
    do {                                                                       \
        checks++;                                                              \
        if(!(cond)) {                                                          \
            failures++;                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);            \
        }                                                                      \
    } while(0)

#define CHECK_STR(actual, expected)                                            \
    do {                                                                       \
        checks++;                                                              \
        if(strcmp((actual), (expected)) != 0) {                                \
            failures++;                                                        \
            printf("FAIL %s:%d: got \"%s\" expected \"%s\"\n", __FILE__,       \
                   __LINE__, (actual), (expected));                            \
        }                                                                      \
    } while(0)

static void add(
    SrFrame* f,
    int x,
    int y,
    uint8_t layer,
    uint8_t font,
    bool inverted,
    bool focus,
    unsigned index,
    unsigned count,
    const char* text) {
    SrRecord* r = &f->records[f->count++];
    memset(r, 0, sizeof(*r));
    r->x = (int16_t)x;
    r->y = (int16_t)y;
    r->layer = layer;
    r->font = font;
    r->inverted = inverted;
    r->focus = focus;
    r->index = (uint16_t)index;
    r->count = (uint16_t)count;
    strncpy(r->text, text, SR_TEXT_MAX - 1);
}

static void frame_init(SrFrame* f, uint8_t content_layer) {
    memset(f, 0, sizeof(*f));
    f->content_layer = content_layer;
}

static void test_normalize(void) {
    char out[SR_TEXT_MAX];
    sr_normalize("  Hello   World ", out, sizeof(out));
    CHECK_STR(out, "Hello World");
    sr_normalize("hel|lo", out, sizeof(out));
    CHECK_STR(out, "hello");
    sr_normalize("a\tb\x01" "c", out, sizeof(out));
    CHECK_STR(out, "a b c");
    sr_normalize("", out, sizeof(out));
    CHECK_STR(out, "");
    sr_normalize("   ", out, sizeof(out));
    CHECK_STR(out, "");
}

static void test_rows_join_and_sort(void) {
    SrFrame f;
    frame_init(&f, SrLayerWindow);
    add(&f, 6, 40, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "Second");
    add(&f, 115, 24, SrLayerWindow, SrFontSecondary, true, false, 0, 0, ">");
    add(&f, 6, 24, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "Brightness");
    add(&f, 73, 24, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "<");
    add(&f, 90, 25, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "50%");
    SrScreen s;
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 2);
    CHECK_STR(s.rows[0].text, "Brightness 50%");
    CHECK(s.rows[0].y == 24);
    CHECK_STR(s.rows[1].text, "Second");
    CHECK(s.has_content);
    CHECK(!s.has_keyboard);
    CHECK(s.content_layer == SrLayerWindow);
}

static void test_status_rows_kept_apart(void) {
    SrFrame f;
    frame_init(&f, SrLayerDesktop);
    add(&f, 100, 8, SrLayerStatusRight, SrFontPrimary, false, false, 0, 0, "12:34");
    SrScreen s;
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK(s.rows[0].kind == SrRowStatus);
    CHECK(!s.has_content);
}

int main(void) {
    test_normalize();
    test_rows_join_and_sort();
    test_status_rows_kept_apart();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
```

Create `tools/run_host_tests.sh` in the project repo:

```bash
#!/bin/zsh
# Compile and run the host unit tests for the screen model with clang.
set -e
ROOT="${0:A:h:h}"
SRC="$ROOT/Momentum-Firmware/applications/services/screen_reader"
OUT="${TMPDIR:-/tmp}/test_screen_model"
clang -std=c11 -Wall -Wextra -Werror -O1 -I "$SRC" -o "$OUT" \
  "$ROOT/tests/host/test_screen_model.c" "$SRC/screen_model.c"
"$OUT"
```

```bash
chmod +x /Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

- [ ] **Step 3: Run the tests to see them fail**

```bash
/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

Expected: clang fails because `screen_model.c` does not exist yet.

- [ ] **Step 4: Implement normalisation and row building**

Create `Momentum-Firmware/applications/services/screen_reader/screen_model.c`:

```c
#include "screen_model.h"
#include <string.h>
#include <stdio.h>

#define SR_ROW_Y_TOLERANCE 2
#define SR_BUTTON_ROW_Y    54
#define SR_TITLE_MAX_Y     26
#define SR_SPONTANEOUS_MS  1500
#define SR_SPONTANEOUS_MAX 80

static void sr_copy(char* out, size_t out_size, const char* in) {
    if(out_size == 0) return;
    size_t i = 0;
    while(i + 1 < out_size && in[i] != '\0') {
        out[i] = in[i];
        i++;
    }
    out[i] = '\0';
}

static void sr_append(char* out, size_t out_size, const char* in) {
    size_t len = strlen(out);
    if(len + 1 >= out_size) return;
    sr_copy(out + len, out_size - len, in);
}

void sr_normalize(const char* in, char* out, size_t out_size) {
    if(out_size == 0) return;
    size_t o = 0;
    bool pending_space = false;
    for(const char* p = in; *p; p++) {
        unsigned char c = (unsigned char)*p;
        if(c == '|') continue;
        if(c <= ' ' || c > 0x7E) {
            if(o > 0) pending_space = true;
            continue;
        }
        if(pending_space) {
            if(o + 1 < out_size) out[o++] = ' ';
            pending_space = false;
        }
        if(o + 1 < out_size) out[o++] = (char)c;
    }
    out[o] = '\0';
}

static bool sr_record_is_status(const SrRecord* r) {
    return r->layer == SrLayerStatusLeft || r->layer == SrLayerStatusRight;
}

static bool sr_record_is_button(const SrRecord* r) {
    return r->inverted && !r->focus && r->y >= SR_BUTTON_ROW_Y &&
           r->font == SrFontSecondary && !sr_record_is_status(r);
}

static bool sr_is_arrow_token(const char* text) {
    return strcmp(text, "<") == 0 || strcmp(text, ">") == 0;
}

void sr_screen_build(const SrFrame* frame, SrScreen* screen) {
    memset(screen, 0, sizeof(*screen));
    screen->title_row = -1;
    screen->content_layer = frame->content_layer;
    screen->overflow = frame->overflow;

    // Reading order: by baseline, then by x. Insertion sort on indices.
    uint8_t order[SR_MAX_RECORDS];
    uint8_t n = frame->count > SR_MAX_RECORDS ? SR_MAX_RECORDS : frame->count;
    for(uint8_t i = 0; i < n; i++) {
        uint8_t j = i;
        while(j > 0) {
            const SrRecord* a = &frame->records[order[j - 1]];
            const SrRecord* b = &frame->records[i];
            bool after = (a->y > b->y) || (a->y == b->y && a->x > b->x);
            if(!after) break;
            order[j] = order[j - 1];
            j--;
        }
        order[j] = i;
    }

    bool any_focus_hint = false;
    for(uint8_t i = 0; i < n; i++) {
        const SrRecord* r = &frame->records[i];
        if(r->focus) any_focus_hint = true;
        if(!sr_record_is_status(r)) screen->has_content = true;
        if(r->font == SrFontKeyboard && !sr_record_is_status(r)) screen->has_keyboard = true;
    }

    SrRow* row = NULL;
    for(uint8_t k = 0; k < n; k++) {
        const SrRecord* r = &frame->records[order[k]];
        char text[SR_TEXT_MAX];
        sr_normalize(r->text, text, sizeof(text));
        if(text[0] == '\0' || sr_is_arrow_token(text)) continue;

        bool status = sr_record_is_status(r);
        bool button = sr_record_is_button(r);
        bool same_row = row && !button && row->kind != SrRowButton &&
                        (status ? row->kind == SrRowStatus : row->kind != SrRowStatus) &&
                        (r->y - row->y) <= SR_ROW_Y_TOLERANCE &&
                        (row->y - r->y) <= SR_ROW_Y_TOLERANCE;
        if(!same_row) {
            if(screen->row_count >= SR_MAX_ROWS) {
                screen->overflow = true;
                break;
            }
            row = &screen->rows[screen->row_count++];
            memset(row, 0, sizeof(*row));
            row->x = r->x;
            row->y = r->y;
            row->font = r->font;
            row->kind = status ? SrRowStatus : (button ? SrRowButton : SrRowNormal);
        }
        if(row->text[0] != '\0') sr_append(row->text, sizeof(row->text), " ");
        sr_append(row->text, sizeof(row->text), text);

        bool focus = r->focus || (!any_focus_hint && r->inverted && !button && !status);
        if(focus && row->kind == SrRowNormal) row->kind = SrRowFocus;
        if(r->count && !row->count) {
            row->index = r->index;
            row->count = r->count;
        }
    }

    for(uint8_t i = 0; i < screen->row_count; i++) {
        const SrRow* c = &screen->rows[i];
        if(c->kind == SrRowNormal && c->font == SrFontPrimary && c->y <= SR_TITLE_MAX_Y) {
            screen->title_row = (int8_t)i;
            break;
        }
    }
}
```

The remaining functions of the header are added in Task 3 and Task 4. To make this file compile now, append temporary stubs at the end of `screen_model.c`; Task 3 replaces them:

```c
size_t sr_screen_focus_text(const SrScreen* screen, char* out, size_t out_size) {
    (void)screen;
    if(out_size) out[0] = '\0';
    return 0;
}

size_t sr_screen_describe(const SrScreen* screen, char* out, size_t out_size) {
    (void)screen;
    if(out_size) out[0] = '\0';
    return 0;
}

void sr_model_init(SrModel* model, uint8_t verbosity) {
    memset(model, 0, sizeof(*model));
    model->verbosity = verbosity;
}

size_t sr_model_process(
    SrModel* model,
    const SrFrame* frame,
    uint32_t now_ms,
    bool key_recent,
    SrAnnouncement* out,
    size_t out_max) {
    (void)model;
    (void)frame;
    (void)now_ms;
    (void)key_recent;
    (void)out;
    (void)out_max;
    return 0;
}
```

- [ ] **Step 5: Run the tests to see them pass**

```bash
/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

Expected: `N checks, 0 failures` (N is 14).

- [ ] **Step 6: Commit both repos**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/screen_model.h applications/services/screen_reader/screen_model.c && git commit -m "screen reader: screen model types, normalisation, rows"
cd /Users/robin/Downloads/flipper-access && git add tests/host/test_screen_model.c tools/run_host_tests.sh && git commit -m "host tests for the screen model"
```

---

### Task 3: Focus text, title, buttons, and the screen description

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_model.c` (replace the stubs `sr_screen_focus_text`, `sr_screen_describe`)
- Modify: `tests/host/test_screen_model.c`

**Interfaces:**
- Consumes: `sr_screen_build`, `SrScreen`, `SrRow` from Task 2.
- Produces: `size_t sr_screen_focus_text(const SrScreen*, char* out, size_t out_size)`; `size_t sr_screen_describe(const SrScreen*, char* out, size_t out_size)`. Description format: `"<title>. <row>. <row>. <focus>, 3 of 12. buttons: left Cancel, right OK"` with parts omitted when absent.

- [ ] **Step 1: Write the failing tests**

Add to `tests/host/test_screen_model.c` before `main`:

```c
static void test_focus_by_hint_and_position(void) {
    SrFrame f;
    frame_init(&f, SrLayerWindow);
    add(&f, 4, 24, SrLayerWindow, SrFontPrimary, false, false, 0, 0, "Settings");
    add(&f, 6, 40, SrLayerWindow, SrFontSecondary, true, true, 3, 12, "Bluetooth");
    add(&f, 6, 56, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "Storage");
    SrScreen s;
    sr_screen_build(&f, &s);
    CHECK(s.title_row == 0);
    CHECK(s.rows[1].kind == SrRowFocus);
    CHECK(s.rows[1].index == 3 && s.rows[1].count == 12);
    char focus[SR_ANN_TEXT_MAX];
    sr_screen_focus_text(&s, focus, sizeof(focus));
    CHECK_STR(focus, "Bluetooth");
    char text[SR_ANN_TEXT_MAX];
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Settings. Storage. Bluetooth, 3 of 12");
}

static void test_focus_by_inversion_and_buttons(void) {
    SrFrame f;
    frame_init(&f, SrLayerWindow);
    add(&f, 6, 30, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "Read");
    add(&f, 6, 46, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "Saved");
    add(&f, 10, 62, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "Cancel");
    add(&f, 100, 62, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "OK");
    SrScreen s;
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 4);
    CHECK(s.rows[0].kind == SrRowFocus);
    CHECK(s.rows[2].kind == SrRowButton);
    CHECK(s.rows[3].kind == SrRowButton);
    CHECK(s.title_row == -1);
    char text[SR_ANN_TEXT_MAX];
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Saved. Read. buttons: left Cancel, right OK");
}

static void test_primary_font_low_on_screen_is_not_title(void) {
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 20, 40, SrLayerFullscreen, SrFontPrimary, false, false, 0, 0, "Wrong PIN!");
    SrScreen s;
    sr_screen_build(&f, &s);
    CHECK(s.title_row == -1);
    char text[SR_ANN_TEXT_MAX];
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Wrong PIN!");
}

static void test_describe_with_center_button_and_no_focus(void) {
    SrFrame f;
    frame_init(&f, SrLayerWindow);
    add(&f, 64, 20, SrLayerWindow, SrFontPrimary, false, false, 0, 0, "Delete file?");
    add(&f, 64, 34, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "key.sub");
    add(&f, 60, 62, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "Delete");
    SrScreen s;
    sr_screen_build(&f, &s);
    char text[SR_ANN_TEXT_MAX];
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Delete file?. key.sub. buttons: center Delete");
}
```

Add the calls in `main` after `test_status_rows_kept_apart();`:

```c
    test_focus_by_hint_and_position();
    test_focus_by_inversion_and_buttons();
    test_primary_font_low_on_screen_is_not_title();
    test_describe_with_center_button_and_no_focus();
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

Expected: failures in the new tests (focus text empty, description empty).

- [ ] **Step 3: Implement focus text and description**

In `screen_model.c`, replace the two stubs `sr_screen_focus_text` and `sr_screen_describe` with:

```c
size_t sr_screen_focus_text(const SrScreen* screen, char* out, size_t out_size) {
    if(out_size == 0) return 0;
    out[0] = '\0';
    for(uint8_t i = 0; i < screen->row_count; i++) {
        const SrRow* row = &screen->rows[i];
        if(row->kind != SrRowFocus) continue;
        if(out[0] != '\0') sr_append(out, out_size, ", ");
        sr_append(out, out_size, row->text);
    }
    return strlen(out);
}

static void sr_append_position(char* out, size_t out_size, const SrRow* row) {
    if(!row->count) return;
    char pos[32];
    snprintf(pos, sizeof(pos), ", %u of %u", (unsigned)row->index, (unsigned)row->count);
    sr_append(out, out_size, pos);
}

static const char* sr_button_side(const SrRow* row) {
    if(row->x < 40) return "left";
    if(row->x > 88) return "right";
    return "center";
}

static void sr_append_buttons(const SrScreen* screen, char* out, size_t out_size) {
    bool first = true;
    for(uint8_t i = 0; i < screen->row_count; i++) {
        const SrRow* row = &screen->rows[i];
        if(row->kind != SrRowButton) continue;
        if(first) {
            if(out[0] != '\0') sr_append(out, out_size, ". ");
            sr_append(out, out_size, "buttons: ");
            first = false;
        } else {
            sr_append(out, out_size, ", ");
        }
        sr_append(out, out_size, sr_button_side(row));
        sr_append(out, out_size, " ");
        sr_append(out, out_size, row->text);
    }
}

size_t sr_screen_describe(const SrScreen* screen, char* out, size_t out_size) {
    if(out_size == 0) return 0;
    out[0] = '\0';
    if(screen->title_row >= 0) {
        sr_append(out, out_size, screen->rows[screen->title_row].text);
    }
    for(uint8_t i = 0; i < screen->row_count; i++) {
        const SrRow* row = &screen->rows[i];
        if(row->kind != SrRowNormal || (int8_t)i == screen->title_row) continue;
        if(out[0] != '\0') sr_append(out, out_size, ". ");
        sr_append(out, out_size, row->text);
    }
    for(uint8_t i = 0; i < screen->row_count; i++) {
        const SrRow* row = &screen->rows[i];
        if(row->kind != SrRowFocus) continue;
        if(out[0] != '\0') sr_append(out, out_size, ". ");
        sr_append(out, out_size, row->text);
        sr_append_position(out, out_size, row);
    }
    sr_append_buttons(screen, out, out_size);
    if(screen->overflow) sr_append(out, out_size, ", and more");
    return strlen(out);
}
```

- [ ] **Step 4: Run the tests to see them pass**

```bash
/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

Expected: `0 failures`.

- [ ] **Step 5: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/screen_model.c && git commit -m "screen reader: focus text and screen description"
cd /Users/robin/Downloads/flipper-access && git add tests/host/test_screen_model.c && git commit -m "tests: focus, title, buttons, description"
```

---

### Task 4: Frame to frame diff and announcements

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_model.c` (replace the stubs `sr_model_init`, `sr_model_process`)
- Modify: `tests/host/test_screen_model.c`

**Interfaces:**
- Consumes: Task 2 and 3 functions.
- Produces: `void sr_model_init(SrModel*, uint8_t verbosity)`; `size_t sr_model_process(SrModel*, const SrFrame*, uint32_t now_ms, bool key_recent, SrAnnouncement* out, size_t out_max)`. After a call, `model->prev` holds the screen of the frame just processed; the service reads it for `sr screen` and the Tab key.

Rules implemented, in this order for each frame:

1. First frame ever: a `SrAnnScreen` with the description, or `SrAnnHome` ("Home screen") when there is no content and the content layer is the desktop.
2. Screen change: content layer differs, or `has_content` differs, or the title text differs, or fewer than half of the previous rows (status bar excluded, roles ignored) are present in the new frame. Roles are ignored so that a list scrolling by one row, where the same texts swap between focus and normal, is not mistaken for a new screen. Announcement: title, then the focus text (with position when verbosity is 2), or all Normal rows when there is no focus, then buttons. Kind `SrAnnScreen`, interrupt true. When the new frame has no content: `SrAnnHome` on the desktop layer, nothing otherwise.
3. Focus change: the focus text differs and is non empty. Kind `SrAnnFocus`, interrupt true, with position when verbosity is 2.
4. Typed character: the screen has a keyboard, and a Normal row grew by exactly one character at the end compared with a previous Normal row on the same baseline. Kind `SrAnnTyped`, text is the character, or "space". A row that shrank by one character gives "deleted".
5. Other changed Normal rows: joined with ". ". Immediate when `key_recent`; otherwise at most once per 1500 ms and cut to 80 characters. Kind `SrAnnChange`, interrupt false.
6. Identical: nothing.

- [ ] **Step 1: Write the failing tests**

Add to `tests/host/test_screen_model.c` before `main`:

```c
static SrFrame menu_frame(const char* prev, const char* sel, const char* next) {
    SrFrame f;
    frame_init(&f, SrLayerDesktop);
    add(&f, 22, 14, SrLayerDesktop, SrFontSecondary, false, false, 0, 0, prev);
    add(&f, 22, 36, SrLayerDesktop, SrFontPrimary, false, true, 2, 9, sel);
    add(&f, 22, 58, SrLayerDesktop, SrFontSecondary, false, false, 0, 0, next);
    return f;
}

static void test_first_frame_announces_screen(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f = menu_frame("Sub-GHz", "125 kHz RFID", "NFC");
    size_t n = sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnScreen);
    CHECK(out[0].interrupt);
    CHECK_STR(out[0].text, "125 kHz RFID");
}

static void test_focus_move_announces_focus_only(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f1 = menu_frame("Sub-GHz", "125 kHz RFID", "NFC");
    sr_model_process(&m, &f1, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    SrFrame f2 = menu_frame("125 kHz RFID", "NFC", "Infrared");
    size_t n = sr_model_process(&m, &f2, 1200, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnFocus);
    CHECK_STR(out[0].text, "NFC");
    // identical frame again: silence
    n = sr_model_process(&m, &f2, 1500, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);
}

static void test_verbose_focus_includes_position(void) {
    SrModel m;
    sr_model_init(&m, 2);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f1 = menu_frame("Sub-GHz", "125 kHz RFID", "NFC");
    sr_model_process(&m, &f1, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    SrFrame f2 = menu_frame("125 kHz RFID", "NFC", "Infrared");
    sr_model_process(&m, &f2, 1200, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK_STR(out[0].text, "NFC, 2 of 9");
}

static void test_new_screen_announces_title_and_focus(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f1 = menu_frame("Sub-GHz", "125 kHz RFID", "NFC");
    sr_model_process(&m, &f1, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    SrFrame f2;
    frame_init(&f2, SrLayerWindow);
    add(&f2, 4, 24, SrLayerWindow, SrFontPrimary, false, false, 0, 0, "Settings");
    add(&f2, 6, 40, SrLayerWindow, SrFontSecondary, true, true, 1, 10, "Bluetooth");
    add(&f2, 6, 56, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "LCD and Notifications");
    size_t n = sr_model_process(&m, &f2, 1300, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnScreen);
    CHECK_STR(out[0].text, "Settings. Bluetooth");
}

static void test_dialog_without_focus_reads_everything(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f;
    frame_init(&f, SrLayerWindow);
    add(&f, 64, 20, SrLayerWindow, SrFontPrimary, false, false, 0, 0, "Delete file?");
    add(&f, 64, 34, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "key.sub");
    add(&f, 10, 62, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "Cancel");
    add(&f, 100, 62, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "Delete");
    size_t n = sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK_STR(out[0].text, "Delete file?. key.sub. buttons: left Cancel, right Delete");
}

static void test_spontaneous_changes_are_rate_limited(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 36, 31, SrLayerFullscreen, SrFontPrimary, false, false, 0, 0, "Wrong PIN!");
    add(&f, 64, 38, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Timeout: 5s");
    sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    strncpy(f.records[1].text, "Timeout: 4s", SR_TEXT_MAX - 1);
    size_t n = sr_model_process(&m, &f, 2000, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnChange);
    CHECK(!out[0].interrupt);
    CHECK_STR(out[0].text, "Timeout: 4s");
    strncpy(f.records[1].text, "Timeout: 3s", SR_TEXT_MAX - 1);
    n = sr_model_process(&m, &f, 3000, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);
    strncpy(f.records[1].text, "Timeout: 2s", SR_TEXT_MAX - 1);
    n = sr_model_process(&m, &f, 4000, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    strncpy(f.records[1].text, "Timeout: 1s", SR_TEXT_MAX - 1);
    n = sr_model_process(&m, &f, 4100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
}

static SrFrame keyboard_frame(const char* typed) {
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 2, 8, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Name");
    if(typed[0]) add(&f, 4, 22, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, typed);
    add(&f, 1, 40, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "qwertyuiop");
    add(&f, 20, 52, SrLayerFullscreen, SrFontKeyboard, true, true, 0, 0, "s");
    return f;
}

static void test_typing_announces_the_character(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f1 = keyboard_frame("ab");
    sr_model_process(&m, &f1, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    SrFrame f2 = keyboard_frame("abs");
    size_t n = sr_model_process(&m, &f2, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnTyped);
    CHECK_STR(out[0].text, "s");
    SrFrame f3 = keyboard_frame("ab");
    n = sr_model_process(&m, &f3, 1200, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK_STR(out[0].text, "deleted");
}

static void test_home_screen_and_loading(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f1 = menu_frame("Sub-GHz", "125 kHz RFID", "NFC");
    sr_model_process(&m, &f1, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    SrFrame loading;
    frame_init(&loading, SrLayerWindow);
    size_t n = sr_model_process(&m, &loading, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);
    SrFrame home;
    frame_init(&home, SrLayerDesktop);
    add(&home, 100, 8, SrLayerStatusRight, SrFontPrimary, false, false, 0, 0, "12:34");
    n = sr_model_process(&m, &home, 1200, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnHome);
    CHECK_STR(out[0].text, "Home screen");
    n = sr_model_process(&m, &home, 1300, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);
}

static void test_overflow_is_mentioned(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f = menu_frame("Sub-GHz", "125 kHz RFID", "NFC");
    f.overflow = true;
    sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK_STR(out[0].text, "125 kHz RFID, and more");
}
```

Add the calls in `main` after `test_describe_with_center_button_and_no_focus();`:

```c
    test_first_frame_announces_screen();
    test_focus_move_announces_focus_only();
    test_verbose_focus_includes_position();
    test_new_screen_announces_title_and_focus();
    test_dialog_without_focus_reads_everything();
    test_spontaneous_changes_are_rate_limited();
    test_typing_announces_the_character();
    test_home_screen_and_loading();
    test_overflow_is_mentioned();
```

- [ ] **Step 2: Run the tests to see them fail**

```bash
/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

Expected: many failures (the stub returns 0 announcements).

- [ ] **Step 3: Implement the model**

In `screen_model.c`, replace the stubs `sr_model_init` and `sr_model_process` with:

```c
void sr_model_init(SrModel* model, uint8_t verbosity) {
    memset(model, 0, sizeof(*model));
    model->verbosity = verbosity;
}

static void sr_emit(
    SrAnnouncement* out,
    size_t out_max,
    size_t* n,
    SrAnnKind kind,
    bool interrupt,
    const char* text) {
    if(*n >= out_max) return;
    SrAnnouncement* a = &out[*n];
    a->kind = kind;
    a->interrupt = interrupt;
    sr_copy(a->text, sizeof(a->text), text);
    (*n)++;
}

static bool sr_screen_has_text(const SrScreen* screen, const char* text) {
    for(uint8_t i = 0; i < screen->row_count; i++) {
        if(screen->rows[i].kind == SrRowStatus) continue;
        if(strcmp(screen->rows[i].text, text) == 0) return true;
    }
    return false;
}

static const char* sr_title_text(const SrScreen* screen) {
    return screen->title_row >= 0 ? screen->rows[screen->title_row].text : "";
}

static bool sr_screen_changed(const SrScreen* prev, const SrScreen* cur) {
    if(prev->content_layer != cur->content_layer) return true;
    if(prev->has_content != cur->has_content) return true;
    if(strcmp(sr_title_text(prev), sr_title_text(cur)) != 0) return true;
    // Fewer than half of the previous rows still present, ignoring their roles: a list
    // that scrolled by one keeps most rows, a new screen keeps almost none.
    unsigned total = 0, kept = 0;
    for(uint8_t i = 0; i < prev->row_count; i++) {
        const SrRow* row = &prev->rows[i];
        if(row->kind == SrRowStatus) continue;
        total++;
        if(sr_screen_has_text(cur, row->text)) kept++;
    }
    return total > 0 && kept * 2 < total;
}

static void sr_screen_announcement(const SrModel* model, const SrScreen* s, char* out, size_t out_size) {
    out[0] = '\0';
    char focus[SR_ANN_TEXT_MAX];
    sr_screen_focus_text(s, focus, sizeof(focus));
    if(s->title_row >= 0) sr_append(out, out_size, sr_title_text(s));
    if(focus[0] != '\0') {
        if(out[0] != '\0') sr_append(out, out_size, ". ");
        sr_append(out, out_size, focus);
        if(model->verbosity >= 2) {
            for(uint8_t i = 0; i < s->row_count; i++) {
                if(s->rows[i].kind == SrRowFocus && s->rows[i].count) {
                    sr_append_position(out, out_size, &s->rows[i]);
                    break;
                }
            }
        }
    } else {
        for(uint8_t i = 0; i < s->row_count; i++) {
            const SrRow* row = &s->rows[i];
            if(row->kind != SrRowNormal || (int8_t)i == s->title_row) continue;
            if(out[0] != '\0') sr_append(out, out_size, ". ");
            sr_append(out, out_size, row->text);
        }
    }
    if(model->verbosity >= 1) sr_append_buttons(s, out, out_size);
    if(s->overflow) sr_append(out, out_size, ", and more");
}

static bool sr_typed_character(const SrScreen* prev, const SrScreen* cur, char* out, size_t out_size) {
    if(!cur->has_keyboard || !prev->has_keyboard) return false;
    for(uint8_t i = 0; i < cur->row_count; i++) {
        const SrRow* now = &cur->rows[i];
        if(now->kind != SrRowNormal) continue;
        for(uint8_t j = 0; j < prev->row_count; j++) {
            const SrRow* was = &prev->rows[j];
            if(was->kind != SrRowNormal) continue;
            if((now->y - was->y) > SR_ROW_Y_TOLERANCE || (was->y - now->y) > SR_ROW_Y_TOLERANCE) continue;
            size_t ln = strlen(now->text), lw = strlen(was->text);
            if(ln == lw + 1 && strncmp(now->text, was->text, lw) == 0) {
                char c = now->text[lw];
                if(c == ' ') {
                    sr_copy(out, out_size, "space");
                } else {
                    out[0] = c;
                    out[1] = '\0';
                }
                return true;
            }
            if(lw == ln + 1 && strncmp(now->text, was->text, ln) == 0) {
                sr_copy(out, out_size, "deleted");
                return true;
            }
        }
    }
    return false;
}

size_t sr_model_process(
    SrModel* model,
    const SrFrame* frame,
    uint32_t now_ms,
    bool key_recent,
    SrAnnouncement* out,
    size_t out_max) {
    size_t n = 0;
    SrScreen* cur = &model->current;
    sr_screen_build(frame, cur);

    char text[SR_ANN_TEXT_MAX];
    bool first = !model->have_prev;
    bool changed = first || sr_screen_changed(&model->prev, cur);

    if(changed) {
        if(cur->has_content) {
            sr_screen_announcement(model, cur, text, sizeof(text));
            sr_emit(out, out_max, &n, SrAnnScreen, true, text);
        } else if(cur->content_layer == SrLayerDesktop) {
            sr_emit(out, out_max, &n, SrAnnHome, true, "Home screen");
        }
    } else {
        char focus_now[SR_ANN_TEXT_MAX];
        char focus_was[SR_ANN_TEXT_MAX];
        sr_screen_focus_text(cur, focus_now, sizeof(focus_now));
        sr_screen_focus_text(&model->prev, focus_was, sizeof(focus_was));
        if(focus_now[0] != '\0' && strcmp(focus_now, focus_was) != 0) {
            sr_copy(text, sizeof(text), focus_now);
            if(model->verbosity >= 2) {
                for(uint8_t i = 0; i < cur->row_count; i++) {
                    if(cur->rows[i].kind == SrRowFocus && cur->rows[i].count) {
                        sr_append_position(text, sizeof(text), &cur->rows[i]);
                        break;
                    }
                }
            }
            sr_emit(out, out_max, &n, SrAnnFocus, true, text);
        } else if(sr_typed_character(&model->prev, cur, text, sizeof(text))) {
            sr_emit(out, out_max, &n, SrAnnTyped, true, text);
        } else {
            text[0] = '\0';
            for(uint8_t i = 0; i < cur->row_count; i++) {
                const SrRow* row = &cur->rows[i];
                if(row->kind != SrRowNormal) continue;
                if(sr_screen_has_text(&model->prev, row->text)) continue;
                if(text[0] != '\0') sr_append(text, sizeof(text), ". ");
                sr_append(text, sizeof(text), row->text);
            }
            if(text[0] != '\0') {
                bool allowed = key_recent || (now_ms - model->last_spontaneous_ms) >= SR_SPONTANEOUS_MS;
                if(allowed) {
                    if(!key_recent) {
                        model->last_spontaneous_ms = now_ms;
                        if(strlen(text) > SR_SPONTANEOUS_MAX) text[SR_SPONTANEOUS_MAX] = '\0';
                    }
                    sr_emit(out, out_max, &n, SrAnnChange, false, text);
                }
            }
        }
    }

    memcpy(&model->prev, cur, sizeof(SrScreen));
    model->have_prev = true;
    return n;
}
```

- [ ] **Step 4: Run the tests to see them pass**

```bash
/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

Expected: `0 failures`. If `test_focus_move_announces_focus_only` fails on the "identical frame" check, the cause is usually `last_spontaneous_ms` handling; the identical frame must produce no changed rows at all.

- [ ] **Step 5: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/screen_model.c && git commit -m "screen reader: frame diff and announcements"
cd /Users/robin/Downloads/flipper-access && git add tests/host/test_screen_model.c && git commit -m "tests: announcements, rate limit, typing, home screen"
```

---

### Task 5: Canvas text tap and GUI frame lifecycle

**Files:**
- Modify: `Momentum-Firmware/applications/services/gui/canvas_i.h`
- Modify: `Momentum-Firmware/applications/services/gui/canvas.c`
- Modify: `Momentum-Firmware/applications/services/gui/gui_i.h`
- Modify: `Momentum-Firmware/applications/services/gui/gui.c`

**Interfaces:**
- Produces (canvas_i.h): `CanvasTapRecord`, `CanvasTapCallback`, `canvas_tap_set_callback`, `canvas_tap_set_layer`, `canvas_tap_flush`, `canvas_tap_hint_focus`, `canvas_tap_hint_full_text`, `canvas_tap_note`, constants `CANVAS_TAP_TEXT_MAX` (48), `CANVAS_TAP_LAYER_UNKNOWN` (255), `CANVAS_TAP_FONT_CUSTOM` (255).
- Produces (gui_i.h): `GuiTap` struct with `frame_begin(void*)`, `text(const CanvasTapRecord*, void*)`, `frame_end(void*, uint8_t content_layer)`; `void gui_tap_set(Gui* gui, const GuiTap* tap, void* context)`.
- Threading: all callbacks run on the GUI thread with the GUI mutex held. They must not call any `gui_*` function and must not block.

- [ ] **Step 1: Add the tap types and fields to canvas_i.h**

In `canvas_i.h`, after the line `#define ICON_DECOMPRESSOR_BUFFER_SIZE (128u * 64 / 8)` add:

```c
#define CANVAS_TAP_TEXT_MAX      48
#define CANVAS_TAP_LAYER_UNKNOWN 255
#define CANVAS_TAP_FONT_CUSTOM   255
```

Inside the `extern "C"` block, before `/** Canvas structure` add:

```c
/** One drawn string, reported to the screen reader tap */
typedef struct {
    int16_t x; /**< absolute framebuffer x of the string start, after alignment */
    int16_t y; /**< absolute framebuffer baseline y */
    uint8_t layer; /**< GuiLayer being drawn, or CANVAS_TAP_LAYER_UNKNOWN */
    uint8_t font; /**< Font, or CANVAS_TAP_FONT_CUSTOM */
    bool inverted; /**< logical colour was ColorWhite, i.e. text on a filled box */
    bool focus; /**< a focus hint applied to this string */
    uint16_t index; /**< 1-based position from the focus hint, 0 if unknown */
    uint16_t count; /**< item count from the focus hint, 0 if unknown */
    char text[CANVAS_TAP_TEXT_MAX];
} CanvasTapRecord;

typedef void (*CanvasTapCallback)(const CanvasTapRecord* record, void* context);
```

In `struct Canvas`, after `FuriMutex* mutex;` add:

```c
    // Screen reader text tap
    CanvasTapCallback tap_callback;
    void* tap_context;
    uint8_t tap_layer;
    uint8_t tap_font;
    bool tap_hint_focus;
    uint16_t tap_hint_index;
    uint16_t tap_hint_count;
    bool tap_hint_full;
    bool tap_hint_verify;
    char tap_hint_text[CANVAS_TAP_TEXT_MAX];
    bool tap_run_active;
    int16_t tap_run_next_x;
    CanvasTapRecord tap_run;
```

After the declaration of `canvas_remove_framebuffer_callback(...)` and before `#ifdef __cplusplus` add:

```c
/** Install the screen reader tap. NULL callback disables it. GUI service only. */
void canvas_tap_set_callback(Canvas* canvas, CanvasTapCallback callback, void* context);

/** Tag the layer that is about to be drawn (GuiLayer value). */
void canvas_tap_set_layer(Canvas* canvas, uint8_t layer);

/** Report a pending glyph run. Call at frame end before the frame is handed over. */
void canvas_tap_flush(Canvas* canvas);

/** The next drawn string is the focused item. index is 1-based, 0 if unknown. */
void canvas_tap_hint_focus(Canvas* canvas, uint16_t index, uint16_t count);

/** The next drawn string is a shortened or scrolled fragment of full_text.
 * With verify_prefix, the hint is used only if the drawn string (minus a trailing "...")
 * is a prefix of full_text. */
void canvas_tap_hint_full_text(Canvas* canvas, const char* full_text, bool verify_prefix);

/** Report text that is shown as an icon (for example the Save key), as if drawn at x, y. */
void canvas_tap_note(Canvas* canvas, int32_t x, int32_t y, const char* text);
```

- [ ] **Step 2: Implement the tap in canvas.c**

In `canvas.c`, in `canvas_init` after `canvas->mutex = furi_mutex_alloc(FuriMutexTypeNormal);` add:

```c
    // Screen reader text tap starts disabled
    canvas->tap_callback = NULL;
    canvas->tap_context = NULL;
    canvas->tap_layer = CANVAS_TAP_LAYER_UNKNOWN;
    canvas->tap_font = FontSecondary;
    canvas->tap_hint_focus = false;
    canvas->tap_hint_full = false;
    canvas->tap_run_active = false;
```

After `canvas_unlock` (before `void canvas_reset`) add the tap implementation:

```c
static bool canvas_tap_logical_inverted(const Canvas* canvas) {
    uint8_t color = canvas->fb.draw_color;
    if(color != ColorWhite && color != ColorBlack) return false; // XOR
    bool raw_white = (color == ColorWhite);
    return raw_white != momentum_settings.dark_mode;
}

static void canvas_tap_fill(Canvas* canvas, CanvasTapRecord* record, int32_t x, int32_t y) {
    memset(record, 0, sizeof(*record));
    record->x = (int16_t)x;
    record->y = (int16_t)y;
    record->layer = canvas->tap_layer;
    record->font = canvas->tap_font;
    record->inverted = canvas_tap_logical_inverted(canvas);
    if(canvas->tap_hint_focus) {
        record->focus = true;
        record->index = canvas->tap_hint_index;
        record->count = canvas->tap_hint_count;
        canvas->tap_hint_focus = false;
    }
}

static bool canvas_tap_is_prefix_fragment(const char* drawn, const char* full) {
    size_t len = strlen(drawn);
    if(len >= 3 && strcmp(drawn + len - 3, "...") == 0) len -= 3;
    return strncmp(drawn, full, len) == 0;
}

void canvas_tap_flush(Canvas* canvas) {
    furi_assert(canvas);
    if(!canvas->tap_run_active) return;
    canvas->tap_run_active = false;
    if(canvas->tap_callback) canvas->tap_callback(&canvas->tap_run, canvas->tap_context);
}

static void canvas_tap_text(Canvas* canvas, int32_t x, int32_t y, const char* str) {
    if(!canvas->tap_callback) {
        canvas->tap_hint_focus = false;
        canvas->tap_hint_full = false;
        return;
    }
    canvas_tap_flush(canvas);
    CanvasTapRecord record;
    canvas_tap_fill(canvas, &record, x, y);
    const char* text = str;
    if(canvas->tap_hint_full) {
        if(!canvas->tap_hint_verify || canvas_tap_is_prefix_fragment(str, canvas->tap_hint_text)) {
            text = canvas->tap_hint_text;
        }
        canvas->tap_hint_full = false;
    }
    strlcpy(record.text, text, sizeof(record.text));
    canvas->tap_callback(&record, canvas->tap_context);
}

static void canvas_tap_glyph(Canvas* canvas, int32_t x, int32_t y, uint16_t ch) {
    if(!canvas->tap_callback) {
        canvas->tap_hint_focus = false;
        canvas->tap_hint_full = false;
        return;
    }
    canvas->tap_hint_full = false;
    if(ch < 0x20 || ch > 0x7E) ch = '?';
    bool inverted = canvas_tap_logical_inverted(canvas);
    bool continues = canvas->tap_run_active && !canvas->tap_hint_focus &&
                     canvas->tap_run.y == y && canvas->tap_run.layer == canvas->tap_layer &&
                     canvas->tap_run.font == canvas->tap_font &&
                     canvas->tap_run.inverted == inverted && x >= canvas->tap_run_next_x &&
                     strlen(canvas->tap_run.text) < CANVAS_TAP_TEXT_MAX - 1;
    if(!continues) {
        canvas_tap_flush(canvas);
        canvas_tap_fill(canvas, &canvas->tap_run, x, y);
        canvas->tap_run_active = true;
    }
    size_t len = strlen(canvas->tap_run.text);
    canvas->tap_run.text[len] = (char)ch;
    canvas->tap_run.text[len + 1] = '\0';
    canvas->tap_run_next_x = (int16_t)(x + 1);
}

void canvas_tap_set_callback(Canvas* canvas, CanvasTapCallback callback, void* context) {
    furi_check(canvas);
    canvas->tap_run_active = false;
    canvas->tap_hint_focus = false;
    canvas->tap_hint_full = false;
    canvas->tap_callback = callback;
    canvas->tap_context = context;
}

void canvas_tap_set_layer(Canvas* canvas, uint8_t layer) {
    furi_assert(canvas);
    canvas_tap_flush(canvas);
    canvas->tap_layer = layer;
}

void canvas_tap_hint_focus(Canvas* canvas, uint16_t index, uint16_t count) {
    furi_assert(canvas);
    canvas->tap_hint_focus = true;
    canvas->tap_hint_index = index;
    canvas->tap_hint_count = count;
}

void canvas_tap_hint_full_text(Canvas* canvas, const char* full_text, bool verify_prefix) {
    furi_assert(canvas);
    if(!canvas->tap_callback || !full_text) return;
    strlcpy(canvas->tap_hint_text, full_text, sizeof(canvas->tap_hint_text));
    canvas->tap_hint_full = true;
    canvas->tap_hint_verify = verify_prefix;
}

void canvas_tap_note(Canvas* canvas, int32_t x, int32_t y, const char* text) {
    furi_assert(canvas);
    if(!text) return;
    x += canvas->offset_x;
    y += canvas->offset_y;
    canvas_tap_text(canvas, x, y, text);
}
```

Then hook the existing functions:

In `canvas_set_font`, after `furi_check(canvas);` add `canvas->tap_font = font;`.

In `canvas_set_custom_u8g2_font`, after `furi_check(canvas);` add `canvas->tap_font = CANVAS_TAP_FONT_CUSTOM;`.

In `canvas_draw_str`, replace the last line `u8g2_DrawUTF8(&canvas->fb, x, y, str);` with:

```c
    canvas_tap_text(canvas, x, y, str);
    u8g2_DrawUTF8(&canvas->fb, x, y, str);
```

In `canvas_draw_str_aligned`, replace the last line `u8g2_DrawUTF8(&canvas->fb, x, y, str);` (after the two switch statements) with:

```c
    canvas_tap_text(canvas, x, y, str);
    u8g2_DrawUTF8(&canvas->fb, x, y, str);
```

In `canvas_draw_glyph`, replace `u8g2_DrawGlyph(&canvas->fb, x, y, ch);` with:

```c
    canvas_tap_glyph(canvas, x, y, ch);
    u8g2_DrawGlyph(&canvas->fb, x, y, ch);
```

`strlcpy`, `strlen`, `strncmp`, `memset` come from `<string.h>`, which `furi.h` already includes. `momentum_settings` is already included in this file.

- [ ] **Step 3: Add the GUI side in gui_i.h and gui.c**

In `gui_i.h`, after the `ARRAY_DEF(ViewPortArray, ViewPort*, M_PTR_OPLIST);` line add:

```c
/** Screen reader tap: frame lifecycle plus the canvas text callback.
 * All three run on the GUI thread with the GUI mutex held. */
typedef struct {
    void (*frame_begin)(void* context);
    CanvasTapCallback text;
    void (*frame_end)(void* context, uint8_t content_layer);
} GuiTap;
```

In `struct Gui`, after `FuriPubSub* ascii_events;` add:

```c
    // Screen reader tap
    const GuiTap* tap;
    void* tap_context;
```

After the struct, add the declaration (next to the other internal functions such as `gui_view_port_find_enabled`):

```c
/** Install or remove (tap == NULL) the screen reader tap. */
void gui_tap_set(Gui* gui, const GuiTap* tap, void* context);
```

In `gui.c`:

Replace `gui_redraw_fs` with:

```c
static bool gui_redraw_fs(Gui* gui) {
    canvas_set_orientation(gui->canvas, CanvasOrientationHorizontal);
    canvas_frame_set(gui->canvas, 0, 0, GUI_DISPLAY_WIDTH, GUI_DISPLAY_HEIGHT);
    ViewPort* view_port = gui_view_port_find_enabled(gui->layers[GuiLayerFullscreen]);
    if(view_port) {
        canvas_tap_set_layer(gui->canvas, GuiLayerFullscreen);
        view_port_draw(view_port, gui->canvas);
        return true;
    } else {
        return false;
    }
}
```

In `gui_redraw_status_bar`, in the right side loop, before the line `view_port_draw(view_port, gui->canvas);` that follows the `canvas_frame_set(gui->canvas, x - momentum_settings.bar_borders, ...)` call, add:

```c
            canvas_tap_set_layer(gui->canvas, GuiLayerStatusBarRight);
```

and in the left side loop, before the `view_port_draw(view_port, gui->canvas);` that follows `canvas_frame_set(gui->canvas, x, GUI_STATUS_BAR_Y + 2, width, GUI_STATUS_BAR_WORKAREA_HEIGHT);`, add:

```c
                canvas_tap_set_layer(gui->canvas, GuiLayerStatusBarLeft);
```

Replace `gui_redraw_window` and `gui_redraw_desktop` with:

```c
static bool gui_redraw_window(Gui* gui) {
    canvas_set_orientation(gui->canvas, CanvasOrientationHorizontal);
    canvas_frame_set(gui->canvas, GUI_WINDOW_X, GUI_WINDOW_Y, GUI_WINDOW_WIDTH, GUI_WINDOW_HEIGHT);
    ViewPort* view_port = gui_view_port_find_enabled(gui->layers[GuiLayerWindow]);
    if(view_port) {
        canvas_tap_set_layer(gui->canvas, GuiLayerWindow);
        view_port_draw(view_port, gui->canvas);
        return true;
    }
    return false;
}

static bool gui_redraw_desktop(Gui* gui) {
    canvas_set_orientation(gui->canvas, CanvasOrientationHorizontal);
    canvas_frame_set(gui->canvas, 0, 0, GUI_DISPLAY_WIDTH, GUI_DISPLAY_HEIGHT);
    ViewPort* view_port = gui_view_port_find_enabled(gui->layers[GuiLayerDesktop]);
    if(view_port) {
        canvas_tap_set_layer(gui->canvas, GuiLayerDesktop);
        view_port_draw(view_port, gui->canvas);
        return true;
    }

    return false;
}
```

Replace `gui_redraw` with:

```c
static void gui_redraw(Gui* gui) {
    furi_assert(gui);
    gui_lock(gui);

    do {
        if(gui->direct_draw) break;

        canvas_reset(gui->canvas);
        canvas_tap_set_layer(gui->canvas, CANVAS_TAP_LAYER_UNKNOWN);
        if(gui->tap) gui->tap->frame_begin(gui->tap_context);
        uint8_t content_layer = CANVAS_TAP_LAYER_UNKNOWN;

        if(gui_is_lockdown(gui)) {
            if(gui_redraw_desktop(gui)) content_layer = GuiLayerDesktop;
            bool need_attention =
                (gui_view_port_find_enabled(gui->layers[GuiLayerWindow]) != 0 ||
                 gui_view_port_find_enabled(gui->layers[GuiLayerFullscreen]) != 0);
            if(momentum_settings.lockscreen_statusbar) {
                gui_redraw_status_bar(gui, need_attention);
            }
        } else {
            if(gui_redraw_fs(gui)) {
                content_layer = GuiLayerFullscreen;
            } else {
                if(gui_redraw_window(gui)) {
                    content_layer = GuiLayerWindow;
                } else if(gui_redraw_desktop(gui)) {
                    content_layer = GuiLayerDesktop;
                }
                gui_redraw_status_bar(gui, false);
            }
        }

        canvas_tap_flush(gui->canvas);
        canvas_commit(gui->canvas);
        if(gui->tap) gui->tap->frame_end(gui->tap_context, content_layer);
    } while(false);

    gui_unlock(gui);
}
```

After `gui_redraw`, add:

```c
void gui_tap_set(Gui* gui, const GuiTap* tap, void* context) {
    furi_check(gui);
    gui_lock(gui);
    gui->tap = tap;
    gui->tap_context = context;
    canvas_tap_set_callback(gui->canvas, tap ? tap->text : NULL, context);
    gui_unlock(gui);
}
```

In `gui_alloc`, after `gui->canvas = canvas_init();` add:

```c
    gui->tap = NULL;
    gui->tap_context = NULL;
```

- [ ] **Step 4: Build**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt 2>&1 | grep -E "error|warning|Firmware size|\.text|\.free_flash|API version" | head -20
```

Expected: no errors, `API version 87.1 is up to date`, `.free_flash` within a few hundred bytes of the previous build. If `gui_lock` is reported as undeclared, move `gui_tap_set` below the static `gui_lock`/`gui_unlock` definitions in gui.c.

- [ ] **Step 5: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/gui/canvas_i.h applications/services/gui/canvas.c applications/services/gui/gui_i.h applications/services/gui/gui.c && git commit -m "gui: screen reader text tap and frame lifecycle"
```

---

### Task 6: Screen reader service and the `sr screen`, `sr on`, `sr off`, `sr status` commands

**Files:**
- Create: `Momentum-Firmware/applications/services/screen_reader/application.fam`
- Create: `Momentum-Firmware/applications/services/screen_reader/screen_reader.h`
- Create: `Momentum-Firmware/applications/services/screen_reader/screen_reader.c`
- Create: `Momentum-Firmware/applications/services/screen_reader/screen_reader_cli.h`
- Create: `Momentum-Firmware/applications/services/screen_reader/screen_reader_cli.c`
- Modify: `Momentum-Firmware/applications/services/application.fam` (add `"screen_reader"` to `provides`)

**Interfaces:**
- Consumes: `GuiTap`, `gui_tap_set` (Task 5); the screen model (Tasks 2 to 4); `momentum_settings.screen_reader` (Task 1); `RECORD_GUI`, `RECORD_INPUT_EVENTS`, `RECORD_CLI`.
- Produces: record `RECORD_SCREEN_READER` ("screen_reader") holding a `ScreenReader*`; `screen_reader_get_frame(ScreenReader*, SrFrame*)`, `screen_reader_get_screen(ScreenReader*, SrScreen*)`, `screen_reader_set_watch_queue(ScreenReader*, FuriMessageQueue*)`, `screen_reader_set_enabled(ScreenReader*, bool)`, `screen_reader_is_enabled(ScreenReader*)`, `screen_reader_get_stats(ScreenReader*, ScreenReaderStats*)`; console command `sr` with subcommands `screen`, `on`, `off`, `status`, `help` (Task 7 adds `watch`).

- [ ] **Step 1: Write the manifest and register the service**

Create `applications/services/screen_reader/application.fam`:

```python
App(
    appid="screen_reader",
    name="ScreenReaderSrv",
    apptype=FlipperAppType.SERVICE,
    entry_point="screen_reader_srv",
    cdefines=["SRV_SCREEN_READER"],
    requires=["gui", "input", "cli"],
    stack_size=3 * 1024,
    order=110,
)
```

In `applications/services/application.fam`, add `"screen_reader",` to the `provides` list after `"power",`.

- [ ] **Step 2: Write the service header**

Create `applications/services/screen_reader/screen_reader.h`:

```c
/**
 * @file screen_reader.h
 * Screen reader service: captures drawn text, models it, and announces changes.
 */
#pragma once

#include <furi.h>
#include "screen_model.h"

#ifdef __cplusplus
extern "C" {
#endif

#define RECORD_SCREEN_READER "screen_reader"

typedef struct ScreenReader ScreenReader;

typedef struct {
    uint32_t frames; /**< frames processed */
    uint32_t dropped_frames; /**< frames the GUI could not hand over in time */
    uint32_t announcements;
} ScreenReaderStats;

/** Copy the last captured frame (raw records). */
void screen_reader_get_frame(ScreenReader* sr, SrFrame* out);

/** Copy the screen description of the last processed frame. */
void screen_reader_get_screen(ScreenReader* sr, SrScreen* out);

/** Attach a queue of SrAnnouncement that receives every announcement. NULL detaches. */
void screen_reader_set_watch_queue(ScreenReader* sr, FuriMessageQueue* queue);

/** Turn the reader on or off and save the setting. */
void screen_reader_set_enabled(ScreenReader* sr, bool enabled);

bool screen_reader_is_enabled(ScreenReader* sr);

void screen_reader_get_stats(ScreenReader* sr, ScreenReaderStats* out);

#ifdef __cplusplus
}
#endif
```

- [ ] **Step 3: Write the service**

Create `applications/services/screen_reader/screen_reader.c`:

```c
#include "screen_reader.h"
#include "screen_reader_cli.h"

#include <furi.h>
#include <gui/gui_i.h>
#include <gui/canvas_i.h>
#include <input/input.h>
#include <momentum/settings.h>

#define TAG "ScreenReader"

#define SR_FLAG_FRAME     (1 << 0)
#define SR_FLAG_ALL       (SR_FLAG_FRAME)
#define SR_SETTLE_MS      50
#define SR_MAX_LATENCY_MS 300
#define SR_KEY_RECENT_MS  500

struct ScreenReader {
    FuriThreadId thread_id;
    FuriMutex* mutex;
    Gui* gui;

    // Written on the GUI thread between frame_begin and frame_end
    bool capturing;
    SrFrame filling;

    // Shared, guarded by mutex
    SrFrame ready;
    bool ready_valid;
    FuriMessageQueue* watch_queue;
    ScreenReaderStats stats;
    SrFrame working;
    SrModel model;
    SrAnnouncement announcements[SR_MAX_ANNOUNCEMENTS];

    // Input
    FuriPubSub* input_events;
    FuriPubSubSubscription* input_subscription;
    volatile uint32_t last_press_tick;
};

static void sr_lock(ScreenReader* sr) {
    furi_check(furi_mutex_acquire(sr->mutex, FuriWaitForever) == FuriStatusOk);
}

static void sr_unlock(ScreenReader* sr) {
    furi_check(furi_mutex_release(sr->mutex) == FuriStatusOk);
}

// GUI thread. Must be fast, must not call gui_* functions.
static void sr_frame_begin(void* context) {
    ScreenReader* sr = context;
    sr->capturing = momentum_settings.screen_reader;
    sr->filling.count = 0;
    sr->filling.overflow = false;
    sr->filling.content_layer = SrLayerUnknown;
}

static void sr_text(const CanvasTapRecord* record, void* context) {
    ScreenReader* sr = context;
    if(!sr->capturing) return;
    if(sr->filling.count >= SR_MAX_RECORDS) {
        sr->filling.overflow = true;
        return;
    }
    SrRecord* r = &sr->filling.records[sr->filling.count++];
    r->x = record->x;
    r->y = record->y;
    r->layer = record->layer;
    r->font = record->font;
    r->inverted = record->inverted;
    r->focus = record->focus;
    r->index = record->index;
    r->count = record->count;
    strlcpy(r->text, record->text, sizeof(r->text));
}

static void sr_frame_end(void* context, uint8_t content_layer) {
    ScreenReader* sr = context;
    if(!sr->capturing) return;
    sr->filling.content_layer = content_layer;
    // Short wait: the service only holds the mutex for a memcpy
    if(furi_mutex_acquire(sr->mutex, 2) == FuriStatusOk) {
        memcpy(&sr->ready, &sr->filling, sizeof(SrFrame));
        sr->ready_valid = true;
        furi_mutex_release(sr->mutex);
        furi_thread_flags_set(sr->thread_id, SR_FLAG_FRAME);
    } else {
        sr->stats.dropped_frames++;
    }
}

static void sr_input_callback(const void* value, void* context) {
    const InputEvent* event = value;
    ScreenReader* sr = context;
    if(event->type == InputTypePress) {
        sr->last_press_tick = furi_get_tick();
    }
}

// Runs the model under the mutex (well under a millisecond) so that the console
// commands never read a half written screen description.
static void sr_process(ScreenReader* sr) {
    sr_lock(sr);
    if(sr->ready_valid) {
        memcpy(&sr->working, &sr->ready, sizeof(SrFrame));
        sr->ready_valid = false;
        uint32_t now = furi_get_tick();
        bool key_recent = (now - sr->last_press_tick) < SR_KEY_RECENT_MS;
        sr->model.verbosity = momentum_settings.sr_verbosity;
        size_t n = sr_model_process(
            &sr->model, &sr->working, now, key_recent, sr->announcements, SR_MAX_ANNOUNCEMENTS);
        sr->stats.frames++;
        sr->stats.announcements += n;
        for(size_t i = 0; i < n; i++) {
            if(sr->watch_queue) {
                furi_message_queue_put(sr->watch_queue, &sr->announcements[i], 0);
            }
        }
    }
    sr_unlock(sr);
}

void screen_reader_get_frame(ScreenReader* sr, SrFrame* out) {
    furi_check(sr && out);
    sr_lock(sr);
    memcpy(out, sr->ready_valid ? &sr->ready : &sr->working, sizeof(SrFrame));
    sr_unlock(sr);
}

void screen_reader_get_screen(ScreenReader* sr, SrScreen* out) {
    furi_check(sr && out);
    sr_lock(sr);
    memcpy(out, &sr->model.prev, sizeof(SrScreen));
    sr_unlock(sr);
}

void screen_reader_set_watch_queue(ScreenReader* sr, FuriMessageQueue* queue) {
    furi_check(sr);
    sr_lock(sr);
    sr->watch_queue = queue;
    sr_unlock(sr);
}

void screen_reader_set_enabled(ScreenReader* sr, bool enabled) {
    furi_check(sr);
    momentum_settings.screen_reader = enabled;
    momentum_settings_save();
    if(enabled) {
        // Announce the current screen on the next frame
        sr_lock(sr);
        sr->model.have_prev = false;
        sr_unlock(sr);
        gui_update(sr->gui);
    }
}

bool screen_reader_is_enabled(ScreenReader* sr) {
    UNUSED(sr);
    return momentum_settings.screen_reader;
}

void screen_reader_get_stats(ScreenReader* sr, ScreenReaderStats* out) {
    furi_check(sr && out);
    sr_lock(sr);
    *out = sr->stats;
    sr_unlock(sr);
}

static const GuiTap screen_reader_tap = {
    .frame_begin = sr_frame_begin,
    .text = sr_text,
    .frame_end = sr_frame_end,
};

int32_t screen_reader_srv(void* p) {
    UNUSED(p);
    ScreenReader* sr = malloc(sizeof(ScreenReader));
    memset(sr, 0, sizeof(ScreenReader));
    sr->thread_id = furi_thread_get_current_id();
    sr->mutex = furi_mutex_alloc(FuriMutexTypeNormal);
    sr_model_init(&sr->model, momentum_settings.sr_verbosity);

    sr->input_events = furi_record_open(RECORD_INPUT_EVENTS);
    sr->input_subscription = furi_pubsub_subscribe(sr->input_events, sr_input_callback, sr);

    sr->gui = furi_record_open(RECORD_GUI);
    gui_tap_set(sr->gui, &screen_reader_tap, sr);

    furi_record_create(RECORD_SCREEN_READER, sr);
    screen_reader_cli_register(sr);
    FURI_LOG_I(TAG, "Started, enabled=%d", momentum_settings.screen_reader);

    bool pending = false;
    uint32_t pending_since = 0;
    while(true) {
        uint32_t timeout = FuriWaitForever;
        if(pending) {
            uint32_t waited = furi_get_tick() - pending_since;
            timeout = waited >= SR_MAX_LATENCY_MS ? 0 : SR_SETTLE_MS;
        }
        uint32_t flags = furi_thread_flags_wait(SR_FLAG_ALL, FuriFlagWaitAny, timeout);
        if(flags & FuriFlagError) {
            // Timeout: the screen has settled, or waited long enough
            pending = false;
            sr_process(sr);
        } else if(flags & SR_FLAG_FRAME) {
            if(!pending) pending_since = furi_get_tick();
            pending = true;
        }
    }
    return 0;
}
```

`gui_update` is declared in `gui_i.h`. `strlcpy` is available through `furi.h`.

- [ ] **Step 4: Write the console command**

Create `applications/services/screen_reader/screen_reader_cli.h`:

```c
#pragma once

#include "screen_reader.h"

/** Register the "sr" console command. Called once by the service. */
void screen_reader_cli_register(ScreenReader* sr);
```

Create `applications/services/screen_reader/screen_reader_cli.c`:

```c
#include "screen_reader_cli.h"

#include <furi.h>
#include <cli/cli.h>
#include <toolbox/cli/cli_command.h>
#include <toolbox/cli/cli_ansi.h>
#include <toolbox/args.h>
#include <toolbox/pipe.h>
#include <input/input.h>
#include <momentum/settings.h>

static const char* sr_layer_name(uint8_t layer) {
    switch(layer) {
    case SrLayerDesktop:
        return "desktop";
    case SrLayerWindow:
        return "window";
    case SrLayerStatusLeft:
        return "status-left";
    case SrLayerStatusRight:
        return "status-right";
    case SrLayerFullscreen:
        return "fullscreen";
    default:
        return "none";
    }
}

static const char* sr_font_name(uint8_t font) {
    switch(font) {
    case SrFontPrimary:
        return "primary";
    case SrFontSecondary:
        return "secondary";
    case SrFontKeyboard:
        return "keyboard";
    case SrFontBigNumbers:
        return "bignumbers";
    case SrFontBatteryPercent:
        return "battery";
    default:
        return "custom";
    }
}

static const char* sr_kind_name(SrAnnKind kind) {
    switch(kind) {
    case SrAnnFocus:
        return "focus";
    case SrAnnScreen:
        return "screen";
    case SrAnnChange:
        return "change";
    case SrAnnTyped:
        return "typed";
    case SrAnnHome:
        return "home";
    default:
        return "?";
    }
}

static void sr_cli_usage(void) {
    printf("Usage: sr <command>\r\n");
    printf("  screen   print the captured screen and how it reads\r\n");
    printf("  watch    stream announcements; arrows, Enter, Backspace drive the device\r\n");
    printf("  on|off   enable or disable the screen reader (saved)\r\n");
    printf("  status   show state and counters\r\n");
}

static void sr_cli_screen(ScreenReader* sr) {
    SrFrame* frame = malloc(sizeof(SrFrame));
    screen_reader_get_frame(sr, frame);
    printf(
        "records: %u%s, content layer: %s\r\n",
        (unsigned)frame->count,
        frame->overflow ? " (overflow)" : "",
        sr_layer_name(frame->content_layer));
    for(size_t i = 0; i < frame->count; i++) {
        const SrRecord* r = &frame->records[i];
        printf(
            "%-12s x=%3d y=%3d %-10s%s%s",
            sr_layer_name(r->layer),
            (int)r->x,
            (int)r->y,
            sr_font_name(r->font),
            r->inverted ? " inverted" : "",
            r->focus ? " FOCUS" : "");
        if(r->count) printf(" %u/%u", (unsigned)r->index, (unsigned)r->count);
        printf(" \"%s\"\r\n", r->text);
    }
    free(frame);

    SrScreen* screen = malloc(sizeof(SrScreen));
    screen_reader_get_screen(sr, screen);
    char* text = malloc(SR_ANN_TEXT_MAX);
    sr_screen_describe(screen, text, SR_ANN_TEXT_MAX);
    printf("reads as: %s\r\n", text);
    free(text);
    free(screen);
}

static void sr_cli_status(ScreenReader* sr) {
    ScreenReaderStats stats;
    screen_reader_get_stats(sr, &stats);
    printf("enabled: %s\r\n", screen_reader_is_enabled(sr) ? "yes" : "no");
    printf(
        "rate: %lu, volume: %lu, verbosity: %lu\r\n",
        (unsigned long)momentum_settings.sr_rate,
        (unsigned long)momentum_settings.sr_volume,
        (unsigned long)momentum_settings.sr_verbosity);
    printf(
        "frames: %lu, dropped: %lu, announcements: %lu\r\n",
        (unsigned long)stats.frames,
        (unsigned long)stats.dropped_frames,
        (unsigned long)stats.announcements);
    printf("free heap: %zu\r\n", memmgr_get_free_heap());
}

static void sr_cli_watch(PipeSide* pipe, ScreenReader* sr);

static void sr_cli_execute(PipeSide* pipe, FuriString* args, void* context) {
    ScreenReader* sr = context;
    FuriString* cmd = furi_string_alloc();
    do {
        if(!args_read_string_and_trim(args, cmd)) {
            sr_cli_usage();
            break;
        }
        if(furi_string_cmp_str(cmd, "screen") == 0) {
            sr_cli_screen(sr);
        } else if(furi_string_cmp_str(cmd, "watch") == 0) {
            sr_cli_watch(pipe, sr);
        } else if(furi_string_cmp_str(cmd, "on") == 0) {
            screen_reader_set_enabled(sr, true);
            printf("screen reader on\r\n");
        } else if(furi_string_cmp_str(cmd, "off") == 0) {
            screen_reader_set_enabled(sr, false);
            printf("screen reader off\r\n");
        } else if(furi_string_cmp_str(cmd, "status") == 0) {
            sr_cli_status(sr);
        } else {
            sr_cli_usage();
        }
    } while(false);
    furi_string_free(cmd);
}

void screen_reader_cli_register(ScreenReader* sr) {
    CliRegistry* registry = furi_record_open(RECORD_CLI);
    cli_registry_add_command(registry, "sr", CliCommandFlagParallelSafe, sr_cli_execute, sr);
    furi_record_close(RECORD_CLI);
}

// Task 7 fills this in. Until then, watch just explains itself.
static void sr_cli_watch(PipeSide* pipe, ScreenReader* sr) {
    UNUSED(pipe);
    UNUSED(sr);
    printf("watch is not implemented yet\r\n");
}
```

`memmgr_get_free_heap` comes from `<furi.h>` (furi/core/memmgr.h).

- [ ] **Step 5: Build and flash**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt 2>&1 | grep -E "error|warning|\.free_flash|API version" | head -20
```

Expected: builds, API version unchanged. Then flash:

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt flash_usb 2>&1 | tail -5; P=/dev/cu.usbmodemflip_R0skie1; gone=0; t0=$(date +%s); while [ $(( $(date +%s) - t0 )) -lt 300 ]; do if [ -e $P ]; then [ $gone -eq 1 ] && break; else gone=1; fi; sleep 2; done; sleep 6; /Users/robin/Downloads/flipper-access/.venv/bin/python /Users/robin/Downloads/flipper-access/tools/flipper_cli.py "info device" | grep -E "firmware.(version|branch.name|origin.fork)"
```

Expected: the port disappears and returns within about two minutes; `firmware.origin.fork : Momentum` and a version string that is not `mntm-012` (a local build shows the git describe of the branch).

- [ ] **Step 6: Test on the device**

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/flipper_cli.py "sr status" "sr on" "input send ok short" && sleep 1 && .venv/bin/python tools/flipper_cli.py "sr screen" "sr status"
```

Expected: `sr status` first shows `enabled: no`; after `sr on` and the OK press, `sr screen` lists the main menu records with the List style rows at y=14, 36, 58 (the middle one in the primary font), `content layer: desktop`, and `reads as:` containing the middle item's name. The counters in `sr status` are greater than zero. If `sr screen` shows `records: 0`, check that `sr on` printed `screen reader on` and that a frame was drawn after enabling (press a key).

Then leave the menu:

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/flipper_cli.py "input send back short" && sleep 1 && .venv/bin/python tools/flipper_cli.py "sr screen"
```

Expected: `records:` shows only the status bar clock (if any), `content layer: desktop`, and `reads as:` is empty.

- [ ] **Step 7: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader applications/services/application.fam && git commit -m "screen reader service with sr screen, on, off, status"
```

---

### Task 7: `sr watch` with keyboard driving

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_reader_cli.c` (replace the placeholder `sr_cli_watch`)

**Interfaces:**
- Consumes: `screen_reader_set_watch_queue`, `screen_reader_get_screen`, `sr_screen_describe`, `RECORD_INPUT_EVENTS`, `RECORD_ASCII_EVENTS`, pipe API.
- Produces: `sr watch` behaviour: prints `<kind>: <text>` lines; arrow keys, Enter, Backspace send Short button presses; Tab prints `screen: <description>`; printable characters are sent as ascii events (they type into on screen keyboards); Ctrl-C stops.

- [ ] **Step 1: Implement watch**

Replace the placeholder `sr_cli_watch` at the bottom of `screen_reader_cli.c` with:

```c
static void sr_cli_press(FuriPubSub* input, InputKey key) {
    InputEvent event;
    memset(&event, 0, sizeof(event));
    event.key = key;
    event.type = InputTypePress;
    furi_pubsub_publish(input, &event);
    event.type = InputTypeShort;
    furi_pubsub_publish(input, &event);
    event.type = InputTypeRelease;
    furi_pubsub_publish(input, &event);
}

static void sr_cli_print_screen(ScreenReader* sr) {
    SrScreen* screen = malloc(sizeof(SrScreen));
    screen_reader_get_screen(sr, screen);
    char* text = malloc(SR_ANN_TEXT_MAX);
    sr_screen_describe(screen, text, SR_ANN_TEXT_MAX);
    printf("screen: %s\r\n", text);
    free(text);
    free(screen);
}

static void sr_cli_watch(PipeSide* pipe, ScreenReader* sr) {
    FuriMessageQueue* queue = furi_message_queue_alloc(8, sizeof(SrAnnouncement));
    SrAnnouncement* announcement = malloc(sizeof(SrAnnouncement));
    FuriPubSub* input = furi_record_open(RECORD_INPUT_EVENTS);
    FuriPubSub* ascii = furi_record_open(RECORD_ASCII_EVENTS);

    printf("Watching. Arrows move, Enter is OK, Backspace is Back, Tab reads the screen,\r\n");
    printf("letters type into text fields. Ctrl+C stops.\r\n");
    screen_reader_set_watch_queue(sr, queue);
    sr_cli_print_screen(sr);

    bool run = true;
    while(run && pipe_state(pipe) == PipeStateOpen) {
        if(furi_message_queue_get(queue, announcement, 20) == FuriStatusOk) {
            printf("%s: %s\r\n", sr_kind_name(announcement->kind), announcement->text);
        }
        while(run && pipe_bytes_available(pipe)) {
            char c = getchar();
            if(c == CliKeyETX) {
                run = false;
            } else if(c == CliKeyEsc) {
                char c2 = 0, c3 = 0;
                if(pipe_receive(pipe, &c2, 1) && c2 == '[' && pipe_receive(pipe, &c3, 1)) {
                    if(c3 == 'A') sr_cli_press(input, InputKeyUp);
                    if(c3 == 'B') sr_cli_press(input, InputKeyDown);
                    if(c3 == 'C') sr_cli_press(input, InputKeyRight);
                    if(c3 == 'D') sr_cli_press(input, InputKeyLeft);
                }
            } else if(c == CliKeyCR || c == CliKeyLF) {
                sr_cli_press(input, InputKeyOk);
            } else if(c == CliKeyBackspace || c == CliKeyDEL) {
                sr_cli_press(input, InputKeyBack);
            } else if(c == CliKeyTab) {
                sr_cli_print_screen(sr);
            } else if(c >= 0x20 && c < 0x7F) {
                AsciiEvent event = {.value = (uint8_t)c};
                furi_pubsub_publish(ascii, &event);
            }
        }
    }

    screen_reader_set_watch_queue(sr, NULL);
    furi_record_close(RECORD_ASCII_EVENTS);
    furi_record_close(RECORD_INPUT_EVENTS);
    furi_message_queue_free(queue);
    free(announcement);
    printf("stopped\r\n");
}
```

Also remove the forward declaration comment line `// Task 7 fills this in.` if it is still there. Keep the forward declaration `static void sr_cli_watch(PipeSide* pipe, ScreenReader* sr);` above `sr_cli_execute`.

- [ ] **Step 2: Build and flash**

Run the same build and flash commands as Task 6 Step 5.

- [ ] **Step 3: Test with a scripted session**

Write the scratch script `/private/tmp/claude-501/-Users-robin-Downloads-flipper-access/7e80a801-93d5-46fa-87ee-69f4f7bb6964/scratchpad/watch_try.py` (or any scratch path):

```python
import serial, time, re
PORT = "/dev/cu.usbmodemflip_R0skie1"
ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
def read_for(ser, seconds):
    t0 = time.time(); buf = b""
    while time.time() - t0 < seconds:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk: buf += chunk
        else: time.sleep(0.02)
    return ANSI.sub(b"", buf).decode(errors="replace")
with serial.Serial(PORT, 230400, timeout=0.1) as ser:
    ser.write(b"\r"); time.sleep(0.4); ser.read(ser.in_waiting)
    ser.write(b"sr on\r"); print(read_for(ser, 0.5))
    ser.write(b"sr watch\r"); print(read_for(ser, 0.8))
    for key, name in [(b"\r", "OK"), (b"\x1b[B", "Down"), (b"\x1b[B", "Down"), (b"\r", "OK"), (b"\x1b[B", "Down"), (b"\t", "Tab"), (b"\x7f", "Back"), (b"\x7f", "Back")]:
        ser.write(key); print(f"--- sent {name}"); print(read_for(ser, 0.9).strip())
    ser.write(b"\x03"); print(read_for(ser, 0.5))
```

Run it:

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python /private/tmp/claude-501/-Users-robin-Downloads-flipper-access/7e80a801-93d5-46fa-87ee-69f4f7bb6964/scratchpad/watch_try.py
```

Expected sequence: `screen: ` (empty or the clock) at start; after OK `screen: <first main menu item>`; after each Down a `focus: <item>` line; after OK on a main app a `screen: <title>. <first item>` line (for Sub-GHz: `screen: Read`), after Down `focus: Read RAW`; Tab prints `screen: ...` with all visible rows; Backspace twice returns to the main menu and then the desktop with `home: Home screen`; Ctrl-C prints `stopped`.

Note: until Task 8 the main menu's List style has no focus hint, so its `screen:` and `focus:` lines will show the rows joined rather than the selected item. Check the mechanics here, and re-run this script after Task 8 for the exact texts.

- [ ] **Step 4: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/screen_reader_cli.c && git commit -m "screen reader: sr watch with keyboard driving"
```

---

### Task 8: Focus hints in the modules and full text hints in elements

**Files:**
- Modify: `Momentum-Firmware/applications/services/gui/elements.c` (`elements_string_fit_width`, `elements_scrollable_text_line_centered`)
- Modify: `Momentum-Firmware/applications/services/gui/modules/submenu.c`
- Modify: `Momentum-Firmware/applications/services/gui/modules/variable_item_list.c`
- Modify: `Momentum-Firmware/applications/services/gui/modules/menu.c`
- Modify: `Momentum-Firmware/applications/services/gui/modules/file_browser.c`
- Modify: `Momentum-Firmware/applications/services/gui/modules/button_menu.c`
- Modify: `Momentum-Firmware/applications/services/gui/modules/text_input.c`

**Interfaces:**
- Consumes: `canvas_tap_hint_focus`, `canvas_tap_hint_full_text`, `canvas_tap_note` from Task 5, included via `#include <gui/canvas_i.h>`.

- [ ] **Step 1: elements.c**

Add `#include <gui/canvas_i.h>` after `#include <gui/canvas.h>`.

In `elements_string_fit_width`, change the beginning of the `if(len_px > width)` block so the original is hinted before it is chopped:

```c
    size_t len_px = canvas_string_width(canvas, furi_string_get_cstr(string));
    if(len_px > width) {
        canvas_tap_hint_full_text(canvas, furi_string_get_cstr(string), true);
        width -= canvas_string_width(canvas, "...");
```

In `elements_scrollable_text_line_centered`, right before the final `if(centered) {` that draws, add:

```c
    canvas_tap_hint_full_text(canvas, furi_string_get_cstr(string), false);
```

- [ ] **Step 2: submenu.c**

Add `#include <gui/canvas_i.h>` next to the other includes at the top of the file.

In the draw callback, before the block that starts with `FuriString* disp_str = furi_string_alloc_set(SubmenuItemArray_cref(it)->label);` add:

```c
            if(position == model->position) {
                canvas_tap_hint_focus(
                    canvas, position + 1, SubmenuItemArray_size(model->items));
            }
```

Since `elements_string_fit_width` may set a full text hint after this, both hints apply to the following `canvas_draw_str`, which is the intended behaviour.

- [ ] **Step 3: variable_item_list.c**

Add `#include <gui/canvas_i.h>` at the top.

Before the `elements_scrollable_text_line(canvas, 6, item_text_y, label_width, item->label, ...)` call add:

```c
            if(position == model->position) {
                canvas_tap_hint_focus(
                    canvas, position + 1, VariableItemArray_size(model->items));
            }
```

Before the `elements_scrollable_text_line_centered(canvas, (115 + value_pos_x) / 2 + 1, ...)` call (after the `"<"` draw) add:

```c
                if(position == model->position) {
                    canvas_tap_hint_focus(
                        canvas, position + 1, VariableItemArray_size(model->items));
                }
```

- [ ] **Step 4: menu.c**

Add `#include <gui/canvas_i.h>` at the top.

In `case MenuStyleList:`, before the `elements_scrollable_text_line(canvas, 22, 14 + 22 * i, 98, name, scroll_counter, false);` call add:

```c
                if(i == 1) canvas_tap_hint_focus(canvas, position + 1, items_count);
```

- [ ] **Step 5: file_browser.c**

Add `#include <gui/canvas_i.h>` at the top.

In `browser_draw_list`, before the `elements_scrollable_text_line(canvas, 15, Y_OFFSET + 9 + i * FRAME_HEIGHT, ...)` call add:

```c
        if(!model->list_loading && model->item_idx == idx) {
            canvas_tap_hint_focus(canvas, (uint16_t)(idx + 1), (uint16_t)model->item_cnt);
        }
```

- [ ] **Step 6: button_menu.c**

Add `#include <gui/canvas_i.h>` at the top.

In `button_menu_draw_text`, after `bool draw_static = true;` add:

```c
    if(selected) canvas_tap_hint_focus(canvas, 0, 0);
```

- [ ] **Step 7: text_input.c**

Add `#include <gui/canvas_i.h>` at the top.

In the keyboard loop, replace

```c
            canvas_set_color(canvas, ColorBlack);
            if(icon != NULL) {
                canvas_draw_icon(
```

with

```c
            canvas_set_color(canvas, ColorBlack);
            if(icon != NULL) {
                if(selected) {
                    const char* name = "Save";
                    if(keys[column].text == SWITCH_KEYBOARD_KEY) name = "Switch keyboard";
                    if(keys[column].text == BACKSPACE_KEY) name = "Backspace";
                    canvas_tap_hint_focus(canvas, 0, 0);
                    canvas_tap_note(
                        canvas,
                        keyboard_origin_x + keys[column].x,
                        keyboard_origin_y + keys[column].y,
                        name);
                }
                canvas_draw_icon(
```

and, in the `else` branch, after `canvas_set_color(canvas, ColorWhite);` inside `if(selected) { ... }` add:

```c
                    canvas_tap_hint_focus(canvas, 0, 0);
```

- [ ] **Step 8: Build, flash, and check with sr screen**

Build and flash as in Task 6 Step 5. Then:

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/flipper_cli.py "sr on" "input send ok short" && sleep 1 && .venv/bin/python tools/flipper_cli.py "sr screen"
```

Expected: the middle main menu row is marked `FOCUS 1/N` and `reads as:` is the selected app's name alone. Then open Settings and a long label list:

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/flipper_cli.py "input send back short" "loader open Settings" && sleep 1.5 && .venv/bin/python tools/flipper_cli.py "sr screen"
```

Expected: the first settings entry (`Bluetooth`) is `FOCUS 1/11` and the full label `LCD and Notifications` appears untruncated even though the display shows it shortened. Open `LCD and Notifications` and press Down twice with `input send down short`; `sr screen` then shows the focused row as label plus value, for example `Backlight Time 30s`, with the `<` and `>` records present but not in `reads as:`.

Leave with Back presses:

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/flipper_cli.py "input send back short" "input send back short" "input send back short"
```

- [ ] **Step 9: Re-run the watch script from Task 7 and record the output**

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python /private/tmp/claude-501/-Users-robin-Downloads-flipper-access/7e80a801-93d5-46fa-87ee-69f4f7bb6964/scratchpad/watch_try.py
```

Expected: `screen:` after OK names the selected app only; `focus:` lines name single items; inside Sub-GHz the `screen:` line reads `Read` and Down gives `focus: Read RAW`.

- [ ] **Step 10: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/gui/elements.c applications/services/gui/modules/submenu.c applications/services/gui/modules/variable_item_list.c applications/services/gui/modules/menu.c applications/services/gui/modules/file_browser.c applications/services/gui/modules/button_menu.c applications/services/gui/modules/text_input.c && git commit -m "gui modules: focus and full text hints for the screen reader"
```

---

### Task 9: Device walk through script and documentation

**Files:**
- Create: `tools/sr_drive.py` (project repo)
- Modify: `README.md` (project repo)

**Interfaces:**
- Consumes: the `sr` command from Tasks 6 to 8.
- Produces: `tools/sr_drive.py`, which runs a scripted walk and checks expected announcement texts, exit code 1 on mismatch. `tools/sr_drive.py --interactive` keeps `sr watch` open and passes the terminal's keys through, which is the tethered screen reader for daily use.

- [ ] **Step 1: Write the script**

Create `tools/sr_drive.py`:

```python
#!/usr/bin/env python3
"""Drive the Flipper through the screen reader console stream.

  tools/sr_drive.py               run the scripted checks and report mismatches
  tools/sr_drive.py --interactive open sr watch and pass this terminal's keys through
                                  (arrows, Enter, Backspace, Tab, letters; Ctrl-C ends)

Needs the screen reader firmware. The port is auto-detected; override with FLIPPER_PORT.
"""
import glob, os, re, sys, time, termios, tty, select
import serial

ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
PORT = os.environ.get("FLIPPER_PORT") or (sorted(glob.glob("/dev/cu.usbmodemflip_*")) + [None])[0]

KEYS = {"ok": b"\r", "up": b"\x1b[A", "down": b"\x1b[B", "right": b"\x1b[C", "left": b"\x1b[D", "back": b"\x7f", "tab": b"\t"}

# (key to send, substring that must appear in the reply lines within 1.5 s)
SCRIPT = [
    ("ok", "screen:"),         # desktop -> main menu
    ("down", "focus:"),
    ("down", "focus:"),
    ("back", "home: Home screen"),
    ("ok", "screen:"),
    ("ok", "screen:"),         # open the selected app
    ("down", "focus:"),
    ("back", "screen:"),       # back to the main menu
    ("back", "home: Home screen"),
]


def read_for(ser, seconds):
    t0 = time.time(); buf = b""
    while time.time() - t0 < seconds:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
        else:
            time.sleep(0.02)
    return ANSI.sub(b"", buf).decode(errors="replace").replace("\r\n", "\n")


def start_watch(ser):
    ser.write(b"\r"); time.sleep(0.4); ser.read(ser.in_waiting)
    ser.write(b"sr on\r"); read_for(ser, 0.5)
    ser.write(b"sr watch\r")
    return read_for(ser, 0.8)


def scripted(ser):
    print(start_watch(ser))
    failures = 0
    for key, expect in SCRIPT:
        ser.write(KEYS[key])
        out = read_for(ser, 1.5).strip()
        ok = expect in out
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'} {key:5s} expected '{expect}' got: {out.replace(chr(10), ' | ')}")
    ser.write(b"\x03"); read_for(ser, 0.5)
    print(f"{failures} failures")
    return failures


def interactive(ser):
    print(start_watch(ser), end="")
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            r, _, _ = select.select([fd, ser.fileno()], [], [], 0.05)
            if fd in r:
                data = os.read(fd, 8)
                if data == b"\x03":
                    ser.write(b"\x03"); break
                ser.write(data)
            if ser.fileno() in r or ser.in_waiting:
                chunk = ser.read(ser.in_waiting or 1)
                if chunk:
                    sys.stdout.write(ANSI.sub(b"", chunk).decode(errors="replace")); sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    print(read_for(ser, 0.5))


def main():
    if not PORT:
        sys.exit("no Flipper port found")
    with serial.Serial(PORT, 230400, timeout=0.1) as ser:
        if "--interactive" in sys.argv:
            interactive(ser)
            return 0
        return scripted(ser)


if __name__ == "__main__":
    sys.exit(main())
```

```bash
chmod +x /Users/robin/Downloads/flipper-access/tools/sr_drive.py
```

- [ ] **Step 2: Run the scripted checks**

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/sr_drive.py
```

Expected: `0 failures`. A `FAIL` on the first `ok` usually means the device was not on the home screen; press Back on it a few times with `tools/flipper_cli.py "input send back short"` and rerun.

- [ ] **Step 3: Document**

In `README.md`, under `## Folder contents`, add:

```markdown
- `tools/sr_drive.py`: scripted check of the screen reader console stream, and with
  `--interactive` a tethered screen reader: arrows, Enter, Backspace drive the device, Tab
  reads the screen, letters type into text fields, Ctrl-C ends.
- `tools/run_host_tests.sh`: unit tests for the screen model, run with clang on the Mac.
- `tests/host/`: the unit tests.
```

Under `## Useful commands` add:

```markdown
Screen reader console commands (firmware from the `screen-reader` branch):

    .venv/bin/python tools/flipper_cli.py "sr on"
    .venv/bin/python tools/flipper_cli.py "sr screen"
    .venv/bin/python tools/flipper_cli.py "sr status"

`sr watch` is interactive; use `tools/sr_drive.py --interactive`.
```

Replace the plan list at the end of the README with:

```markdown
## Plan

1. Done: terminal access, backup, Momentum install.
2. Done: CLI explored, helper tools written.
3. Done: source build environment set up, first app built and running.
4. Done: speech demo; SAM default voice judged intelligible.
5. Done: phase 1 of the screen reader: text capture, screen model, console mirror.
6. Next: phase 2, on device speech (SAM in the firmware with DMA playback).
```

- [ ] **Step 4: Commit**

```bash
cd /Users/robin/Downloads/flipper-access && git add tools/sr_drive.py README.md && git commit -m "sr_drive: scripted and interactive console screen reader"
```

---

## Self review notes

Spec coverage for phase 1: tap (section 4) Task 5 and 8; screen model (section 5) Tasks 2 to 4; service (section 6) Task 6; console command (section 7) Tasks 6 and 7; settings (section 10) Task 1; testing (section 13) Tasks 2 to 4 host tests, Task 9 device script. Speech (section 8) and hotkeys (section 9) are phase 2 and 3 and intentionally absent. The pronunciation table (section 5) is applied before speech only, so it belongs to phase 2.

Type consistency: `SrFrame.content_layer` is set by the service from the `frame_end` argument; `CanvasTapRecord` and `SrRecord` have identical field names and text sizes (48) so the copy in `sr_text` is field by field; `sr_screen_describe` output format is what both the tests and `sr screen` print; `SrModel.prev` is what `screen_reader_get_screen` copies.
