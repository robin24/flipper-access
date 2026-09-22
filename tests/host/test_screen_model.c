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
