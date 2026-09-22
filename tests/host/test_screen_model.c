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

    // It vanishes again: nothing to say.
    n = sr_model_process(&m, &home, 5000, false, out, SR_MAX_ANNOUNCEMENTS);
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

static void test_overflow_is_mentioned(void) {
    SrModel m;
    sr_model_init(&m, 1);
    SrAnnouncement out[SR_MAX_ANNOUNCEMENTS];
    SrFrame f = menu_frame("Sub-GHz", "125 kHz RFID", "NFC");
    f.overflow = true;
    sr_model_process(&m, &f, 1000, true, out, SR_MAX_ANNOUNCEMENTS);
    CHECK_STR(out[0].text, "125 kHz RFID, and more");
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
    test_spontaneous_changes_are_rate_limited();
    test_keyboard_focus_is_the_single_key();
    test_typing_announces_the_character();
    test_home_screen_and_loading();
    test_desktop_bubbles_do_not_reannounce_the_screen();
    test_last_list_row_is_not_a_button();
    test_button_side_comes_from_the_hint();
    test_parent_folder_and_loading_rows();
    test_overflow_is_mentioned();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
