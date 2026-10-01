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

/** An inverted secondary string that the dialog helpers marked as a button: 1 left, 2 center,
 * 3 right. */
static void add_button(SrFrame* f, int x, int y, uint8_t side, const char* text) {
    add(f, x, y, SrLayerWindow, SrFontSecondary, true, false, 0, 0, text);
    f->records[f->count - 1].button = side;
}

/** A note as canvas_tap_hint_note records it: no position, the secondary font, normal colour. */
static void add_note(SrFrame* f, uint8_t layer, bool focus, const char* text) {
    add(f, 0, 0, layer, SrFontSecondary, false, focus, 0, 0, text);
    f->records[f->count - 1].note = true;
}

/** A note as canvas_tap_hint_note_at records it: at the start and baseline it names, the
 * secondary font, normal colour, never a focus. */
static void add_note_at(SrFrame* f, int x, int y, uint8_t layer, const char* text) {
    add(f, x, y, layer, SrFontSecondary, false, false, 0, 0, text);
    f->records[f->count - 1].note = true;
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

static void test_describe_mentions_overflow(void) {
    SrFrame f;
    frame_init(&f, SrLayerWindow);
    add(&f, 6, 40, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "Read");
    f.overflow = true;
    SrScreen s;
    sr_screen_build(&f, &s);
    char text[SR_ANN_TEXT_MAX];
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Read, and more");
    CHECK(s.overflow);
}

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
    CHECK(out[0].interrupt);
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
    CHECK(out[0].kind == SrAnnFocus);
    CHECK(out[0].interrupt);
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

/** Every change on the same screen is reported, also without a key press and however quickly
 * they come: the service says them at most once per change delay, always the latest
 * (sr_throttle). Without a key press within 500 ms the text is cut at 80 characters. */
static void test_spontaneous_changes_are_all_reported(void) {
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
    n = sr_model_process(&m, &f, 2100, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnChange);
    CHECK_STR(out[0].text, "Timeout: 3s");
    strncpy(f.records[1].text, "Timeout: 2s", SR_TEXT_MAX - 1);
    n = sr_model_process(&m, &f, 2200, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK_STR(out[0].text, "Timeout: 2s");
    strncpy(f.records[1].text, "Timeout: 1s", SR_TEXT_MAX - 1);
    n = sr_model_process(&m, &f, 2300, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK_STR(out[0].text, "Timeout: 1s");
    // The same frame again: nothing changed, nothing said
    n = sr_model_process(&m, &f, 2400, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);

    // Three new rows of 39 characters join to 121: cut at 80 without a key, whole with one
    SrFrame long_rows;
    frame_init(&long_rows, SrLayerFullscreen);
    add(&long_rows, 36, 31, SrLayerFullscreen, SrFontPrimary, false, false, 0, 0, "Wrong PIN!");
    add(&long_rows, 64, 38, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Timeout: 1s");
    const char* row = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"; // 39 characters
    add(&long_rows, 2, 46, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, row);
    add(&long_rows, 2, 54, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, row);
    add(&long_rows, 2, 60, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, row);
    n = sr_model_process(&m, &long_rows, 2500, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnChange);
    CHECK(strlen(out[0].text) == 80);
    // Back to the two rows: three of five rows went away, which reads as a new screen
    n = sr_model_process(&m, &f, 2600, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnScreen);
    CHECK(out[0].interrupt);
    CHECK_STR(out[0].text, "Wrong PIN!. Timeout: 1s");
    n = sr_model_process(&m, &long_rows, 2700, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnChange);
    CHECK(strlen(out[0].text) > 80);
}

/** One keyboard row as text_input draws it: the keys before the selected one, the selected key
 * inverted with a focus hint, and the keys after it, all on the same baseline. */
static SrFrame keyboard_frame(const char* typed, char selected) {
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 2, 8, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Name");
    if(typed[0]) add(&f, 4, 22, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, typed);
    add(&f, 1, 40, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "q");
    char key[2] = {selected, '\0'};
    add(&f, 8, 40, SrLayerFullscreen, SrFontKeyboard, true, true, 0, 0, key);
    add(&f, 15, 40, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "ertyuiop");
    return f;
}

static void test_keyboard_focus_is_the_single_key(void) {
    SrFrame f1 = keyboard_frame("", 'w');
    SrScreen s;
    sr_screen_build(&f1, &s);
    char focus[SR_ANN_TEXT_MAX];
    sr_screen_focus_text(&s, focus, sizeof(focus));
    CHECK_STR(focus, "w");

    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    sr_model_process(&m, &f1, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    SrFrame f2 = keyboard_frame("", 'e');
    size_t n = sr_model_process(&m, &f2, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnFocus);
    CHECK(out[0].interrupt);
    CHECK_STR(out[0].text, "e");
}

static void test_typing_announces_the_character(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f1 = keyboard_frame("ab", 's');
    sr_model_process(&m, &f1, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    SrFrame f2 = keyboard_frame("abs", 's');
    size_t n = sr_model_process(&m, &f2, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnTyped);
    CHECK(out[0].interrupt);
    CHECK_STR(out[0].text, "s");
    SrFrame f3 = keyboard_frame("ab", 's');
    n = sr_model_process(&m, &f3, 1200, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnTyped);
    CHECK(out[0].interrupt);
    CHECK_STR(out[0].text, "deleted");
}

/** A text input as text_input.c draws it with the fork's hints: the prompt at the top in the
 * secondary font, the name in the field (drawn inverted while the default name is selected), the
 * keys in the keyboard font, and the selected key with a focus hint; Save is an icon, named by a
 * focus note in the keyboard font. */
static SrFrame text_input_frame(const char* field, bool field_selected, const char* key) {
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 2, 8, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Name the signal");
    add(&f, 4, 22, SrLayerFullscreen, SrFontSecondary, field_selected, false, 0, 0, field);
    add(&f, 1, 40, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "qwertyuiop");
    add(&f, 1, 52, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "asdfghjkl");
    add(&f, 1, 64, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "zxcvbnm");
    add(&f, 100, 64, SrLayerFullscreen, SrFontKeyboard, true, true, 0, 0, key);
    return f;
}

/** A number input as number_input.c draws it: the prompt at the top, the value in the field, the
 * keys in the keyboard font, the selected one inverted. */
static SrFrame number_input_frame(const char* prompt, const char* value, bool hints) {
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    if(prompt[0]) add(&f, 2, 9, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, prompt);
    add(&f, 8, 25, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, value);
    add(&f, 7, 41, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "01234");
    add(&f, 7, 53, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "5678");
    add(&f, 51, 53, SrLayerFullscreen, SrFontKeyboard, true, hints, 0, 0, "9");
    return f;
}

// G2 of the review of 2026-09-28: a keyboard opened with only its key, "Save" or "9", since its
// prompt is in the secondary font and the model read only the title and the focus
static void test_keyboard_opens_with_prompt_and_value(void) {
    SrModel m;
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    sr_model_init(&m, 1);
    SrFrame f = text_input_frame("RAW_433", true, "Save");
    size_t n = sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnScreen);
    CHECK_STR(out[0].text, "Name the signal. RAW_433. Save");

    sr_model_init(&m, 1);
    f = number_input_frame("Frequency", "433", false);
    n = sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnScreen);
    CHECK_STR(out[0].text, "Frequency. 433. 9");

    // Without a prompt the field is read, but it is not the title: the title stays what the
    // screen is, while the field changes with every key
    SrScreen s;
    f = number_input_frame("", "433", false);
    sr_screen_build(&f, &s);
    CHECK(s.on_keyboard && s.title_row < 0);
    sr_model_init(&m, 1);
    n = sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK_STR(out[0].text, "433. 9");

    // Text in the keyboard font without a focus is no keyboard (a text box in hex, a terminal):
    // its top line in the secondary font is no title
    SrFrame t;
    frame_init(&t, SrLayerWindow);
    add(&t, 2, 8, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "Received");
    add(&t, 0, 20, SrLayerWindow, SrFontKeyboard, false, false, 0, 0, "00 11 22 33");
    sr_screen_build(&t, &s);
    CHECK(s.has_keyboard && !s.on_keyboard && s.title_row < 0);
}

/** A byte input as byte_input.c draws it with the fork's hints, while a key is selected: the
 * prompt, the value as a plain note, the bytes drawn one digit at a time in the keyboard font
 * with the digit being edited inverted, and the two rows of keys with the selected one hinted. */
static SrFrame byte_input_frame(
    const char* value_note,
    const char* digits_before,
    const char* edited,
    char key) {
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 2, 9, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Enter the key");
    add_note(&f, SrLayerFullscreen, false, value_note);
    add(&f, 10, 25, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, digits_before);
    add(&f, 24, 25, SrLayerFullscreen, SrFontKeyboard, true, false, 0, 0, edited);
    add(&f, 30, 25, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "5678");
    add(&f, 7, 43, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "01234567");
    add(&f, 7, 57, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "89");
    char k[2] = {key, '\0'};
    add(&f, 29, 57, SrLayerFullscreen, SrFontKeyboard, true, true, 0, 0, k);
    add(&f, 40, 57, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "BCDEF");
    return f;
}

// G1 of the review of 2026-09-28: the byte input opened as "3, 3", the digit being edited and the
// key, both inverted; with the key hinted and the value in a note it says the prompt, the value
// and the key, and a key press says the new value only, not the digits drawn one by one
static void test_byte_input_reads_its_value(void) {
    SrModel m;
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    sr_model_init(&m, 1);
    SrFrame f = byte_input_frame("12 34 56 78, byte 2 of 4", "124", "3", 'A');
    size_t n = sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnScreen);
    CHECK_STR(out[0].text, "Enter the key. 12 34 56 78, byte 2 of 4. A");

    // OK on A: the first digit of byte 2 is A, the second is next
    f = byte_input_frame("12 A4 56 78, byte 2 of 4, digit 2", "12A", "4", 'A');
    n = sr_model_process(&m, &f, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnChange);
    CHECK_STR(out[0].text, "12 A4 56 78, byte 2 of 4, digit 2");
}

// G3 of the review of 2026-09-28: in the number input, moving from 9 onto the sign or Save key
// was said, interrupting, as the typed character "9", since the key row "5678" became "56789"
// once the 9 was no longer selected. Key rows take no part in the typed rule; with the keys named
// the move says the key
static void test_key_rows_are_never_typed(void) {
    SrModel m;
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    // A key row one character longer, the focus unchanged: no typed character, and on a keyboard
    // the key rows are no news either
    sr_model_init(&m, 1);
    SrFrame f = text_input_frame("RAW_433", false, "Save");
    sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    SrFrame g = text_input_frame("RAW_433", false, "Save");
    snprintf(g.records[4].text, SR_TEXT_MAX, "zxcvbnm,");
    size_t n = sr_model_process(&m, &g, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);

    // The number input's move from the 9 onto the sign key, with the keys named as it now draws
    // them: the 9 joins its row, and the move says the key
    sr_model_init(&m, 1);
    f = number_input_frame("Frequency", "433", true);
    sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    frame_init(&g, SrLayerFullscreen);
    add(&g, 2, 9, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Frequency");
    add(&g, 8, 25, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "433");
    add(&g, 7, 41, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "01234");
    add(&g, 7, 53, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, "56789");
    add(&g, 62, 48, SrLayerFullscreen, SrFontKeyboard, false, true, 0, 0, "Change sign");
    n = sr_model_process(&m, &g, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnFocus);
    CHECK_STR(out[0].text, "Change sign");

    // Back onto the 9, and OK: a digit typed into the field is still a typed character
    f = number_input_frame("Frequency", "433", true);
    n = sr_model_process(&m, &f, 1200, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnFocus);
    CHECK_STR(out[0].text, "9");
    f = number_input_frame("Frequency", "4339", true);
    n = sr_model_process(&m, &f, 1300, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnTyped);
    CHECK_STR(out[0].text, "9");
}

/** The text input's keys in one case, the field as given (no row when empty, as an empty field
 * draws only the cursor) and a focused key or note. */
static SrFrame text_input_case_frame(const char* field, bool upper, const char* focus) {
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 2, 8, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Name the signal");
    if(field[0]) add(&f, 4, 22, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, field);
    const char* rows[3] = {"qwertyuiop", "sdfghjkl", "zxcvbnm"};
    if(upper) {
        rows[0] = "QWERTYUIOP";
        rows[1] = "SDFGHJKL";
        rows[2] = "ZXCVBNM";
    }
    for(int i = 0; i < 3; i++) {
        add(&f, 1, 40 + 12 * i, SrLayerFullscreen, SrFontKeyboard, false, false, 0, 0, rows[i]);
    }
    add(&f, 100, 64, SrLayerFullscreen, SrFontKeyboard, true, true, 0, 0, focus);
    return f;
}

// G4 of the review of 2026-09-28: deleting the last character was a new screen, "Backspace",
// since an empty field turns the keys to upper case and most rows then differed, and so was the
// first character typed; the cursor mode was silent
static void test_text_input_edges(void) {
    SrModel m;
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    sr_model_init(&m, 1);
    SrFrame f = text_input_case_frame("a", false, "Backspace");
    sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    f = text_input_case_frame("", true, "Backspace");
    size_t n = sr_model_process(&m, &f, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnTyped);
    CHECK_STR(out[0].text, "deleted");

    // The first character into the empty field: the keys go to lower case, the selected A too,
    // and the character is said, not the key
    sr_model_init(&m, 1);
    f = text_input_case_frame("", true, "A");
    sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    f = text_input_case_frame("A", false, "a");
    n = sr_model_process(&m, &f, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnTyped);
    CHECK_STR(out[0].text, "A");

    // Up into the cursor mode: no key is selected, and the text input's note is the focus; Left
    // moves it
    f = text_input_case_frame("A", false, "Cursor after A, 1 of 1");
    n = sr_model_process(&m, &f, 1200, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnFocus);
    CHECK_STR(out[0].text, "Cursor after A, 1 of 1");
    f = text_input_case_frame("A", false, "Cursor at the start, 0 of 1");
    n = sr_model_process(&m, &f, 1300, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnFocus);
    CHECK_STR(out[0].text, "Cursor at the start, 0 of 1");

    // A name longer than the field: text_input draws "..." and the tail, and its full text hint
    // makes the tail the whole name, so a character typed is said as one
    sr_model_init(&m, 1);
    f = text_input_case_frame("... RAW_433_long_name", false, "x");
    sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    f = text_input_case_frame("... RAW_433_long_namex", false, "x");
    n = sr_model_process(&m, &f, 1100, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnTyped);
    CHECK_STR(out[0].text, "x");
}

// S2 of the review of 2026-09-28: rows, announcements and the change said without a key press
// were cut inside a word, whose fragment speech spelled and logged as a missing word. They end
// after their last whole word
static void test_cuts_end_at_a_word(void) {
    SrModel m;
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    sr_model_init(&m, 1);
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 36, 31, SrLayerFullscreen, SrFontPrimary, false, false, 0, 0, "Wrong PIN!");
    add(&f, 64, 38, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Timeout: 1s");
    sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    // Joined with ". ", the 80th character falls inside the second row's "foxtrot"
    const char* words = "alpha bravo charlie delta echo foxtrot golf";
    add(&f, 2, 46, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, words);
    add(&f, 2, 54, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, words);
    add(&f, 2, 60, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, words);
    size_t n = sr_model_process(&m, &f, 1100, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnChange);
    size_t len = strlen(out[0].text);
    CHECK(len > 60 && len <= 80);
    CHECK_STR(out[0].text + len - 4, "echo");

    // A row of more than 63 characters, two records on one baseline: the 64th character falls
    // inside "julietts"
    SrFrame r;
    frame_init(&r, SrLayerFullscreen);
    add(&r, 2, 30, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, words);
    const char* more = "hotels indias julietts kilos";
    add(&r, 90, 30, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, more);
    SrScreen s;
    sr_screen_build(&r, &s);
    len = strlen(s.rows[0].text);
    CHECK(len <= SR_ROW_TEXT_MAX - 1 && len > 40);
    CHECK_STR(s.rows[0].text + len - 6, "indias");
}

// G7 of the review of 2026-09-28: a dialog with four lines of text lost its buttons, as the
// announcement is cut at 159 characters and the buttons came last ("... buttons: l"). The text
// is cut after a whole word instead and the buttons stay
static void test_long_dialog_keeps_its_buttons(void) {
    SrModel m;
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    sr_model_init(&m, 1);
    SrFrame f;
    frame_init(&f, SrLayerWindow);
    add(&f, 64, 10, SrLayerWindow, SrFontPrimary, false, false, 0, 0, "Delete the file?");
    const char* lines[4] = {
        "Every signal saved in it goes with it, and",
        "the favourites that name it are lost too, as",
        "are the notes kept beside it on the card and",
        "any copy that the archive made of it before"};
    for(int i = 0; i < 4; i++) {
        add(&f, 2, 22 + 10 * i, SrLayerWindow, SrFontSecondary, false, false, 0, 0, lines[i]);
    }
    add_button(&f, 2, 63, 1, "Cancel");
    add_button(&f, 90, 63, 3, "Delete");
    size_t n = sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnScreen);
    size_t len = strlen(out[0].text);
    const char* buttons = "buttons: left Cancel, right Delete";
    CHECK(len < SR_ANN_TEXT_MAX && len > strlen(buttons));
    CHECK_STR(out[0].text + len - strlen(buttons), buttons);
    CHECK(strncmp(out[0].text, "Delete the file?. Every signal", 30) == 0);
}

// G6 of the review of 2026-09-28: keys drawn one character at a time make runs such as
// "qwertyuiop", which Back and Up read as words. On a keyboard the description leaves them out
static void test_keyboard_description_leaves_out_the_keys(void) {
    SrFrame f = text_input_frame("RAW_433", false, "Save");
    SrScreen s;
    sr_screen_build(&f, &s);
    char text[SR_DESCRIBE_TEXT_MAX];
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Name the signal. RAW_433. Save");
    // Text in the keyboard font on a screen that is no keyboard is still read
    SrFrame t;
    frame_init(&t, SrLayerWindow);
    add(&t, 0, 20, SrLayerWindow, SrFontKeyboard, false, false, 0, 0, "00 11 22 33");
    sr_screen_build(&t, &s);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "00 11 22 33");
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
    CHECK(out[0].interrupt);
    CHECK_STR(out[0].text, "Home screen");
    n = sr_model_process(&m, &home, 1300, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);
}

static void test_desktop_bubbles_do_not_reannounce_the_screen(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame home;
    frame_init(&home, SrLayerDesktop);
    add(&home, 100, 8, SrLayerStatusRight, SrFontPrimary, false, false, 0, 0, "12:34");
    size_t n = sr_model_process(&m, &home, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnHome);

    // A speech bubble appears: a quiet change, not a new screen.
    SrFrame bubble = home;
    add(&bubble, 60, 20, SrLayerDesktop, SrFontSecondary, false, false, 0, 0, "I am happy");
    n = sr_model_process(&m, &bubble, 3000, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnChange);
    CHECK(!out[0].interrupt);
    CHECK_STR(out[0].text, "I am happy");

    // It vanishes again: the desktop's own text went away, which says "Home screen" once and
    // without interrupting; the service keeps it silent without a key press, as it keeps the
    // bubble itself. The next frame without text says nothing.
    n = sr_model_process(&m, &home, 5000, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnHome);
    CHECK(!out[0].interrupt);
    CHECK_STR(out[0].text, "Home screen");
    n = sr_model_process(&m, &home, 5500, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);

    // Coming back from another screen does announce the home screen.
    SrFrame menu;
    frame_init(&menu, SrLayerFullscreen);
    add(&menu, 22, 36, SrLayerFullscreen, SrFontPrimary, false, true, 2, 9, "NFC");
    n = sr_model_process(&m, &menu, 6000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnScreen);
    n = sr_model_process(&m, &home, 7000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnHome);
    CHECK(out[0].interrupt);
}

static void test_last_list_row_is_not_a_button(void) {
    SrFrame f;
    SrScreen s;
    frame_init(&f, SrLayerWindow);
    add(&f, 6, 60, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "Extra Actions");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK(s.rows[0].kind == SrRowFocus);
    frame_init(&f, SrLayerWindow);
    add(&f, 6, 61, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "Save");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK(s.rows[0].kind == SrRowButton);
}

static void test_button_side_comes_from_the_hint(void) {
    SrFrame f;
    SrScreen s;
    char text[SR_ANN_TEXT_MAX];

    frame_init(&f, SrLayerWindow);
    add_button(&f, 70, 61, 3, "Delete");
    sr_screen_build(&f, &s);
    CHECK(s.rows[0].kind == SrRowButton);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "buttons: right Delete");

    frame_init(&f, SrLayerWindow);
    add_button(&f, 64, 61, 2, "Continue");
    sr_screen_build(&f, &s);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "buttons: center Continue");

    // No hint: the old geometric rule still applies, for third party apps.
    frame_init(&f, SrLayerWindow);
    add(&f, 100, 62, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "OK");
    sr_screen_build(&f, &s);
    CHECK(s.rows[0].kind == SrRowButton);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "buttons: right OK");
}

static void test_parent_folder_and_loading_rows(void) {
    SrFrame f;
    frame_init(&f, SrLayerWindow);
    add(&f, 15, 24, SrLayerWindow, SrFontSecondary, false, false, 0, 0, ". .");
    add(&f, 15, 36, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "---");
    SrScreen s;
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK_STR(s.rows[0].text, "Parent folder");
}

/** The status bar as the desktop draws it with its clock on: the clock and the battery
 * percentage on the right status layer, a pixel apart, each a row of its own. */
static void test_status_text(void) {
    SrFrame f;
    SrScreen s;
    char text[SR_ANN_TEXT_MAX];
    frame_init(&f, SrLayerDesktop);
    add(&f, 103, 9, SrLayerStatusRight, SrFontBatteryPercent, true, false, 0, 0, "100");
    add(&f, 78, 8, SrLayerStatusRight, SrFontPrimary, false, false, 0, 0, "14:05");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 2);
    sr_status_text(&s, text, sizeof(text));
    CHECK_STR(text, "14:05, battery 100 percent");

    // The bar style draws a charge between the colour steps as two digits in two colours: two
    // records a few pixels apart, read as one number
    frame_init(&f, SrLayerDesktop);
    add(&f, 78, 8, SrLayerStatusRight, SrFontPrimary, false, false, 0, 0, "14:05");
    add(&f, 107, 9, SrLayerStatusRight, SrFontBatteryPercent, true, false, 0, 0, "7");
    add(&f, 113, 9, SrLayerStatusRight, SrFontBatteryPercent, false, false, 0, 0, "5");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 3);
    sr_status_text(&s, text, sizeof(text));
    CHECK_STR(text, "14:05, battery 75 percent");

    // A buffer too small for the whole text still ends with a terminator
    char small[12];
    CHECK(sr_status_text(&s, small, sizeof(small)) == strlen(small));
    CHECK(strlen(small) < sizeof(small));

    // No status text at all: empty, and the reader says so
    frame_init(&f, SrLayerWindow);
    add(&f, 6, 30, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "Read");
    sr_screen_build(&f, &s);
    CHECK(sr_status_text(&s, text, sizeof(text)) == 0 && text[0] == '\0');
}

static void test_focus_with_position(void) {
    SrFrame f;
    SrScreen s;
    char text[SR_ANN_TEXT_MAX];
    frame_init(&f, SrLayerFullscreen);
    add(&f, 22, 14, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Sub-GHz");
    add(&f, 22, 36, SrLayerFullscreen, SrFontPrimary, false, true, 3, 11, "Apps");
    sr_screen_build(&f, &s);
    sr_focus_with_position(&s, text, sizeof(text));
    CHECK_STR(text, "Apps, 3 of 11");

    // No position known: just the focus text
    frame_init(&f, SrLayerWindow);
    add(&f, 6, 30, SrLayerWindow, SrFontSecondary, true, false, 0, 0, "Read");
    sr_screen_build(&f, &s);
    sr_focus_with_position(&s, text, sizeof(text));
    CHECK_STR(text, "Read");

    // No focus: empty, and the reader says so
    frame_init(&f, SrLayerWindow);
    add(&f, 6, 30, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "Read");
    sr_screen_build(&f, &s);
    CHECK(sr_focus_with_position(&s, text, sizeof(text)) == 0 && text[0] == '\0');
}

/** A universal remote: the label drawn as text, the selected button's name as a focus note. */
static SrFrame remote_frame(const char* button) {
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 22, 10, SrLayerFullscreen, SrFontPrimary, false, false, 0, 0, "TVs");
    add_note(&f, SrLayerFullscreen, true, button);
    return f;
}

static void test_note_rows(void) {
    SrFrame f;
    SrScreen s;
    char text[SR_ANN_TEXT_MAX];

    // One drawn title and one focus note: the title stays the title, the note is the focus
    f = remote_frame("Power");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 2);
    CHECK(s.title_row >= 0);
    CHECK_STR(s.title_row >= 0 ? s.rows[s.title_row].text : "", "TVs");
    CHECK(s.rows[0].kind == SrRowFocus);
    CHECK_STR(s.rows[0].text, "Power");
    CHECK(s.has_content);
    sr_screen_focus_text(&s, text, sizeof(text));
    CHECK_STR(text, "Power");
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "TVs. Power");

    // A note without focus is a normal row
    frame_init(&f, SrLayerDesktop);
    add_note(&f, SrLayerDesktop, false, "Locked, press Back three times to unlock");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK(s.rows[0].kind == SrRowNormal);
    CHECK(s.title_row == -1);
    CHECK(s.has_content);

    // A note is never the title, even in the primary font at the top of the screen
    frame_init(&f, SrLayerWindow);
    add_note(&f, SrLayerWindow, false, "Settings");
    f.records[0].font = SrFontPrimary;
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK(s.title_row == -1);

    // A note never joins a string drawn on its baseline (the lock screen's clock slides through
    // the top rows while its cover moves)
    frame_init(&f, SrLayerDesktop);
    add(&f, 0, 1, SrLayerDesktop, SrFontSecondary, false, false, 0, 0, "14:05");
    add_note(&f, SrLayerDesktop, false, "Locked, press Back three times to unlock");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 2);
    CHECK_STR(s.rows[0].text, "Locked, press Back three times to unlock");
    CHECK_STR(s.rows[1].text, "14:05");
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Locked, press Back three times to unlock. 14:05");

    // Notes are read first, also before text drawn above the top edge: while the lock screen's
    // cover slides down, its date is still at a negative baseline
    frame_init(&f, SrLayerDesktop);
    add(&f, 0, -16, SrLayerDesktop, SrFontSecondary, false, false, 0, 0, "24-09-2026");
    add(&f, 0, 0, SrLayerDesktop, SrFontBigNumbers, false, false, 0, 0, "16:10");
    add_note(&f, SrLayerDesktop, false, "Locked, press Back three times to unlock");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 3);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Locked, press Back three times to unlock. 24-09-2026. 16:10");
}

static void test_note_focus_moves(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame menu;
    frame_init(&menu, SrLayerFullscreen);
    add(&menu, 4, 11, SrLayerFullscreen, SrFontPrimary, false, false, 0, 0, "Universal Remotes");
    add(&menu, 6, 25, SrLayerFullscreen, SrFontSecondary, true, true, 1, 10, "TVs");
    sr_model_process(&m, &menu, 1000, true, out, SR_MAX_ANNOUNCEMENTS);

    SrFrame f = remote_frame("Power");
    size_t n = sr_model_process(&m, &f, 1200, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnScreen);
    CHECK(out[0].interrupt);
    CHECK_STR(out[0].text, "TVs. Power");

    f = remote_frame("Mute");
    n = sr_model_process(&m, &f, 1400, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnFocus);
    CHECK(out[0].interrupt);
    CHECK_STR(out[0].text, "Mute");

    // The same button again: silence
    n = sr_model_process(&m, &f, 1600, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);
}

/** The desktop's own screens (the lock menu, the power off dialog, the lock screen) stay on the
 * desktop layer; closing them leaves the home screen with no text, which is said. */
static void test_desktop_text_gone_says_home(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame home;
    frame_init(&home, SrLayerDesktop);
    add(&home, 100, 8, SrLayerStatusRight, SrFontPrimary, false, false, 0, 0, "12:34");
    size_t n = sr_model_process(&m, &home, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnHome && out[0].interrupt);

    // The lock menu opens: its tiles are icons, the selected one is a focus note
    SrFrame lock_menu;
    frame_init(&lock_menu, SrLayerDesktop);
    add_note(&lock_menu, SrLayerDesktop, true, "Lock");
    n = sr_model_process(&m, &lock_menu, 2000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnFocus);
    CHECK_STR(out[0].text, "Lock");
    strncpy(lock_menu.records[0].text, "Bluetooth on", SR_TEXT_MAX - 1);
    n = sr_model_process(&m, &lock_menu, 2500, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnFocus);
    CHECK_STR(out[0].text, "Bluetooth on");

    // Back closes it: the home screen, said after what is being said
    n = sr_model_process(&m, &home, 3000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnHome);
    CHECK(!out[0].interrupt);
    CHECK_STR(out[0].text, "Home screen");
    n = sr_model_process(&m, &home, 3500, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);

    // The power off dialog runs on the desktop layer too
    SrFrame dialog;
    frame_init(&dialog, SrLayerDesktop);
    add(&dialog, 64, 10, SrLayerDesktop, SrFontPrimary, false, false, 0, 0, "Turn Off Device?");
    add_button(&dialog, 10, 61, 1, "Battery");
    add_button(&dialog, 100, 61, 3, "Power Off");
    sr_model_process(&m, &dialog, 4000, true, out, SR_MAX_ANNOUNCEMENTS);
    n = sr_model_process(&m, &home, 5000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnHome);
    CHECK(!out[0].interrupt);

    // Status text alone does not count: a clock that changes on the home screen says nothing
    SrFrame later = home;
    strncpy(later.records[0].text, "12:35", SR_TEXT_MAX - 1);
    n = sr_model_process(&m, &later, 6000, false, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 0);
}

/** A screen that has only notes is still a screen with text: it is read, not called home. */
static void test_note_only_screen_is_read(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame lock_menu;
    frame_init(&lock_menu, SrLayerDesktop);
    add_note(&lock_menu, SrLayerDesktop, true, "Lock");
    size_t n = sr_model_process(&m, &lock_menu, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1);
    CHECK(out[0].kind == SrAnnScreen);
    CHECK_STR(out[0].text, "Lock");
}

/** The Passport at level 2 with 7 of its 100 points: four lines drawn at x 59, the points in the
 * battery font, and after them the note naming the level they lead to. */
static SrFrame passport_frame(void) {
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add(&f, 59, 10, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Delphi");
    add(&f, 59, 22, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Mood: Happy");
    add(&f, 59, 34, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Level: 2");
    add(&f, 59, 42, SrLayerFullscreen, SrFontBatteryPercent, false, false, 0, 0, "XP 7/100");
    add_note_at(&f, 100, 42, SrLayerFullscreen, "to level 3");
    return f;
}

static void test_positioned_note(void) {
    SrFrame f;
    SrScreen s;
    char text[SR_DESCRIBE_TEXT_MAX];

    // A note with a place joins the row on its baseline, after the text drawn to its left
    frame_init(&f, SrLayerFullscreen);
    add(&f, 59, 42, SrLayerFullscreen, SrFontBatteryPercent, false, false, 0, 0, "XP 7/100");
    add_note_at(&f, 100, 42, SrLayerFullscreen, "to level 3");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK_STR(s.rows[0].text, "XP 7/100 to level 3");
    CHECK(s.rows[0].kind == SrRowNormal);

    // Its place decides where it is read, not the order it was recorded in
    frame_init(&f, SrLayerFullscreen);
    add_note_at(&f, 100, 42, SrLayerFullscreen, "to level 3");
    add(&f, 59, 42, SrLayerFullscreen, SrFontBatteryPercent, false, false, 0, 0, "XP 7/100");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK_STR(s.rows[0].text, "XP 7/100 to level 3");

    // The whole Passport: the points line keeps its place, after the level
    f = passport_frame();
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 4);
    CHECK(s.title_row == -1);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Delphi. Mood: Happy. Level: 2. XP 7/100 to level 3");

    // Off the baseline of the text beside it, a note with a place begins a row of its own, in
    // its place, and that row is no title
    frame_init(&f, SrLayerFullscreen);
    add(&f, 59, 34, SrLayerFullscreen, SrFontPrimary, false, false, 0, 0, "Level: 2");
    add(&f, 59, 42, SrLayerFullscreen, SrFontBatteryPercent, false, false, 0, 0, "XP 7/100");
    add_note_at(&f, 100, 38, SrLayerFullscreen, "to level 3");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 3);
    CHECK_STR(s.rows[1].text, "to level 3");
    CHECK(s.rows[1].note);
    CHECK(s.title_row == -1);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Level: 2. to level 3. XP 7/100");

    // A plain note, at x 0, y 0, is still read first, a row of its own
    frame_init(&f, SrLayerFullscreen);
    add(&f, 59, 42, SrLayerFullscreen, SrFontBatteryPercent, false, false, 0, 0, "XP 7/100");
    add_note_at(&f, 100, 42, SrLayerFullscreen, "to level 3");
    add_note(&f, SrLayerFullscreen, false, "Passport");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 2);
    CHECK_STR(s.rows[0].text, "Passport");
    CHECK_STR(s.rows[1].text, "XP 7/100 to level 3");

    // A note with a place is never the title, even in the primary font at the top of the
    // screen; text drawn after it on its baseline joins its row, which stays no title
    frame_init(&f, SrLayerWindow);
    add_note_at(&f, 2, 12, SrLayerWindow, "Settings");
    f.records[0].font = SrFontPrimary;
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK(s.title_row == -1);
    frame_init(&f, SrLayerWindow);
    add_note_at(&f, 2, 12, SrLayerWindow, "Wi-Fi");
    add(&f, 40, 12, SrLayerWindow, SrFontPrimary, false, false, 0, 0, "Settings");
    sr_screen_build(&f, &s);
    CHECK(s.row_count == 1);
    CHECK_STR(s.rows[0].text, "Wi-Fi Settings");
    CHECK(s.title_row == -1);
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

/** A string marked as the screen's title, as canvas_tap_hint_title marks the next drawn one. */
static void add_title(SrFrame* f, int x, int y, uint8_t layer, uint8_t font, const char* text) {
    add(f, x, y, layer, font, false, false, 0, 0, text);
    f->records[f->count - 1].title = true;
}

/** The file browser's tab name, drawn small at the top and marked as the title: a new tab is a
 *  new screen, said with its name before the focus, and read first. */
static void test_title_hint_names_the_screen(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f;
    frame_init(&f, SrLayerFullscreen);
    add_title(&f, 17, 9, SrLayerFullscreen, SrFontSecondary, "NFC");
    add(&f, 15, 24, SrLayerFullscreen, SrFontSecondary, true, true, 1, 3, "Fun_Files");
    add(&f, 15, 36, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "RickRoll");
    size_t n = sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnScreen);
    CHECK_STR(out[0].text, "NFC. Fun_Files");

    // The next tab draws its rows in the same places: its title tells it apart
    frame_init(&f, SrLayerFullscreen);
    add_title(&f, 17, 9, SrLayerFullscreen, SrFontSecondary, "Infrared");
    add(&f, 15, 24, SrLayerFullscreen, SrFontSecondary, true, true, 1, 2, "remote");
    add(&f, 15, 36, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "Samsung");
    n = sr_model_process(&m, &f, 1500, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnScreen);
    CHECK_STR(out[0].text, "Infrared. remote");

    SrScreen s;
    char text[SR_ANN_TEXT_MAX];
    sr_screen_build(&f, &s);
    CHECK(s.title_row == 0);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Infrared. Samsung. remote, 1 of 2");
}

/** The file browser draws no folder name, so it gives it as a note marked as the title: entering
 *  a folder is a new screen said with the folder's name, and the parent folder entry, which has
 *  no position, is read without one even when verbose. */
static void test_title_note_names_the_folder(void) {
    SrModel m;
    sr_model_init(&m, 2);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f;
    frame_init(&f, SrLayerWindow);
    add_note(&f, SrLayerWindow, false, "apps");
    f.records[f.count - 1].title = true;
    add(&f, 15, 9, SrLayerWindow, SrFontSecondary, true, true, 0, 0, ". .");
    add(&f, 15, 21, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "GPIO");
    add(&f, 15, 33, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "Infrared");
    size_t n = sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnScreen);
    CHECK_STR(out[0].text, "apps. Parent folder");

    frame_init(&f, SrLayerWindow);
    add_note(&f, SrLayerWindow, false, "Sub-GHz");
    f.records[f.count - 1].title = true;
    add(&f, 15, 9, SrLayerWindow, SrFontSecondary, false, false, 0, 0, ". .");
    add(&f, 15, 21, SrLayerWindow, SrFontSecondary, true, true, 1, 2, "bruteforcer");
    add(&f, 15, 33, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "chief_cooker");
    n = sr_model_process(&m, &f, 1500, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK(n == 1 && out[0].kind == SrAnnScreen);
    CHECK_STR(out[0].text, "Sub-GHz. bruteforcer, 1 of 2");
}

/** A word that is drawn in pieces is read whole: a line the text box broke inside a word, a line
 *  the multiline wrapper broke with its dash at the break, and a word drawn letter-spaced. */
static void test_joined_pieces_read_as_one_word(void) {
    SrFrame f;
    SrScreen s;
    char text[SR_ANN_TEXT_MAX];

    // The file browser's delete dialog, its name broken by the text box
    frame_init(&f, SrLayerWindow);
    add(&f, 4, 12, SrLayerWindow, SrFontPrimary, false, false, 0, 0, "Delete SLIX2_2026-09-2");
    add(&f, 4, 24, SrLayerWindow, SrFontPrimary, false, false, 0, 0, "7_18,44,2.nfc?");
    f.records[f.count - 1].join = SrJoinDirect;
    add_button(&f, 2, 63, 1, "Cancel");
    add_button(&f, 90, 63, 3, "Delete");
    sr_screen_build(&f, &s);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Delete SLIX2_2026-09-27_18,44,2.nfc?. buttons: left Cancel, right Delete");

    // The multiline wrapper's dash goes, and a dash the text has stays
    frame_init(&f, SrLayerWindow);
    add(&f, 2, 30, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "Saved to the favour-");
    add(&f, 2, 40, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "ites, a well-");
    f.records[f.count - 1].join = SrJoinDropDash;
    add(&f, 2, 50, SrLayerWindow, SrFontSecondary, false, false, 0, 0, "known list");
    f.records[f.count - 1].join = SrJoinDirect;
    sr_screen_build(&f, &s);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "Saved to the favourites, a well-known list");

    // The DSi menu style's START, drawn as S, TAR and T on one baseline
    frame_init(&f, SrLayerFullscreen);
    add(&f, 55, 44, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "S");
    add(&f, 64, 44, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "TAR");
    f.records[f.count - 1].join = SrJoinDirect;
    add(&f, 73, 44, SrLayerFullscreen, SrFontSecondary, false, false, 0, 0, "T");
    f.records[f.count - 1].join = SrJoinDirect;
    add(&f, 64, 20, SrLayerFullscreen, SrFontSecondary, true, true, 1, 11, "Apps");
    sr_screen_build(&f, &s);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "START. Apps, 1 of 11");
}

/** elements_button_up and elements_button_down draw their labels inverted at the top: marked as
 *  buttons, up and down, they are read as such and never as the focus. */
static void test_up_and_down_buttons(void) {
    SrFrame f;
    SrScreen s;
    char text[SR_ANN_TEXT_MAX];
    frame_init(&f, SrLayerWindow);
    add_button(&f, 3, 9, 4, "Next");
    add_button(&f, 100, 9, 5, "Prev");
    add(&f, 64, 40, SrLayerWindow, SrFontPrimary, false, false, 0, 0, "433.92 MHz");
    sr_screen_build(&f, &s);
    CHECK(sr_screen_focus_text(&s, text, sizeof(text)) == 0);
    sr_screen_describe(&s, text, sizeof(text));
    CHECK_STR(text, "433.92 MHz. buttons: up Next, down Prev");
}

int main(void) {
    test_normalize();
    test_rows_join_and_sort();
    test_status_rows_kept_apart();
    test_focus_by_hint_and_position();
    test_focus_by_inversion_and_buttons();
    test_primary_font_low_on_screen_is_not_title();
    test_describe_with_center_button_and_no_focus();
    test_describe_mentions_overflow();
    test_first_frame_announces_screen();
    test_focus_move_announces_focus_only();
    test_verbose_focus_includes_position();
    test_new_screen_announces_title_and_focus();
    test_dialog_without_focus_reads_everything();
    test_spontaneous_changes_are_all_reported();
    test_keyboard_focus_is_the_single_key();
    test_typing_announces_the_character();
    test_keyboard_opens_with_prompt_and_value();
    test_byte_input_reads_its_value();
    test_key_rows_are_never_typed();
    test_text_input_edges();
    test_cuts_end_at_a_word();
    test_long_dialog_keeps_its_buttons();
    test_keyboard_description_leaves_out_the_keys();
    test_home_screen_and_loading();
    test_desktop_bubbles_do_not_reannounce_the_screen();
    test_last_list_row_is_not_a_button();
    test_button_side_comes_from_the_hint();
    test_parent_folder_and_loading_rows();
    test_overflow_is_mentioned();
    test_status_text();
    test_focus_with_position();
    test_note_rows();
    test_note_focus_moves();
    test_desktop_text_gone_says_home();
    test_note_only_screen_is_read();
    test_positioned_note();
    test_title_hint_names_the_screen();
    test_title_note_names_the_folder();
    test_joined_pieces_read_as_one_word();
    test_up_and_down_buttons();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
