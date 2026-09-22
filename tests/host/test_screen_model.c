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

int main(void) {
    test_normalize();
    test_rows_join_and_sort();
    test_status_rows_kept_apart();
    test_focus_by_hint_and_position();
    test_focus_by_inversion_and_buttons();
    test_primary_font_low_on_screen_is_not_title();
    test_describe_with_center_button_and_no_focus();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
