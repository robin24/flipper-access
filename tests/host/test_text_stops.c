#include <stdio.h>
#include <string.h>
#include "text_stops.h"

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

static uint8_t width_6(char c, void* context) {
    (void)c;
    (void)context;
    return 6;
}

static uint8_t width_2(char c, void* context) {
    (void)c;
    (void)context;
    return 2;
}

static uint8_t width_0(char c, void* context) {
    (void)c;
    (void)context;
    return 0;
}

static uint8_t width_200(char c, void* context) {
    (void)c;
    (void)context;
    return 200;
}

/** 20 characters to a row, 5 rows to the display */
static const TextStopsLayout layout = {
    .glyph_width = width_6,
    .context = NULL,
    .row_width = 120,
    .rows_max = 5,
};

/** Twelve words of nine letters joined by spaces, 119 characters, and a newline. */
static const char twelve_words[] =
    "aaaaaaaaa aaaaaaaaa aaaaaaaaa aaaaaaaaa aaaaaaaaa aaaaaaaaa "
    "aaaaaaaaa aaaaaaaaa aaaaaaaaa aaaaaaaaa aaaaaaaaa aaaaaaaaa\n";

static void test_row_breaks_at_space(void) {
    const char* text = "With compatible marauder firmware";
    TextStopsRow row;
    text_stops_row(text, 0, &layout, &row);
    CHECK(row.start == 0);
    CHECK(row.length == 15);
    CHECK(row.next == 16);
    CHECK(row.ends == TextStopsBreakSpace);
    text_stops_row(text, 16, &layout, &row);
    CHECK(row.start == 16);
    CHECK(row.length == 17);
    CHECK(row.next == 33);
    CHECK(row.ends == TextStopsBreakEnd);
}

static void test_row_exact_fit(void) {
    TextStopsRow row;
    text_stops_row("aaaaaaaaaaaaaaaaaaaa bbb", 0, &layout, &row);
    CHECK(row.length == 20);
    CHECK(row.next == 21);
    CHECK(row.ends == TextStopsBreakSpace);
    text_stops_row("aaaaaaaaaaaaaaaaaaaa\nb", 0, &layout, &row);
    CHECK(row.length == 20);
    CHECK(row.next == 21);
    CHECK(row.ends == TextStopsBreakLine);
    text_stops_row("aaaaaaaaaaaaaaaaaaaa\r\nb", 0, &layout, &row);
    CHECK(row.length == 20);
    CHECK(row.next == 22);
    CHECK(row.ends == TextStopsBreakLine);
}

static void test_row_long_word(void) {
    const char* text = "xxxxxxxxxxxxxxxxxxxxxxxxx";
    TextStopsRow row;
    text_stops_row(text, 0, &layout, &row);
    CHECK(row.length == 20);
    CHECK(row.next == 20);
    CHECK(row.ends == TextStopsBreakWord);
    text_stops_row(text, 20, &layout, &row);
    CHECK(row.length == 5);
    CHECK(row.next == 25);
    CHECK(row.ends == TextStopsBreakEnd);
}

static void test_row_leading_spaces(void) {
    // The indent of Marauder's list -c stays in the row, and is no place to break it
    TextStopsRow row;
    text_stops_row("  xxxxxxxxxxxxxxxxxxxxxxxx", 0, &layout, &row);
    CHECK(row.length == 20);
    CHECK(row.next == 20);
    CHECK(row.ends == TextStopsBreakWord);
    text_stops_row("  [0] aaaaaaaaaaaaaaaaaaaaa", 0, &layout, &row);
    CHECK(row.length == 5);
    CHECK(row.next == 6);
    CHECK(row.ends == TextStopsBreakSpace);
}

static void test_row_carriage_return(void) {
    const char* text = "one\r\ntwo\r\n";
    TextStopsRow row;
    text_stops_row(text, 0, &layout, &row);
    CHECK(row.length == 3);
    CHECK(row.next == 5);
    CHECK(row.ends == TextStopsBreakLine);
    text_stops_row(text, 5, &layout, &row);
    CHECK(row.length == 3);
    CHECK(row.next == 10);
    CHECK(row.ends == TextStopsBreakLine);
    text_stops_row(text, 10, &layout, &row);
    CHECK(row.length == 0);
    CHECK(row.next == 10);
    CHECK(row.ends == TextStopsBreakEnd);
    text_stops_row("one\r", 0, &layout, &row);
    CHECK(row.length == 3);
    CHECK(row.ends == TextStopsBreakEnd);
}

static void test_row_char_limit(void) {
    char text[61];
    memset(text, 'i', 60);
    text[60] = '\0';
    TextStopsLayout narrow = layout;
    narrow.glyph_width = width_2;
    TextStopsRow row;
    text_stops_row(text, 0, &narrow, &row);
    CHECK(row.length == 47);
    CHECK(row.next == 47);
    CHECK(row.ends == TextStopsBreakWord);
}

static void test_row_always_advances(void) {
    char text[61];
    memset(text, 'x', 60);
    text[60] = '\0';
    TextStopsLayout zero = layout;
    zero.glyph_width = width_0;
    TextStopsRow row;
    text_stops_row(text, 0, &zero, &row);
    CHECK(row.length == 47);
    CHECK(row.ends == TextStopsBreakWord);

    TextStopsLayout wide = layout;
    wide.glyph_width = width_200;
    text_stops_row("xy", 0, &wide, &row);
    CHECK(row.length == 1);
    CHECK(row.next == 1);
    CHECK(row.ends == TextStopsBreakWord);
    text_stops_row("xy", 1, &wide, &row);
    CHECK(row.length == 1);
    CHECK(row.next == 2);
    CHECK(row.ends == TextStopsBreakEnd);
}

static bool silent(const char* line) {
    return text_stops_line_is_silent(line, strlen(line));
}

static void test_silent_lines(void) {
    CHECK(silent(""));
    CHECK(silent("   "));
    CHECK(silent("-----"));
    CHECK(silent(" - - "));
    CHECK(silent("|||"));
    CHECK(silent("\r"));
    CHECK(silent("\xE2\x9C\x93"));
    CHECK(!silent("a"));
    CHECK(!silent("> "));
    CHECK(!silent("====="));
    CHECK(!silent("[1]"));
    // Only the length given counts
    CHECK(text_stops_line_is_silent("--a", 2));
    CHECK(!text_stops_line_is_silent("--a", 3));
}

static void test_stops_of_a_list(void) {
    const char* text = "[1][CH:1] Example-Net -40\n[2][CH:6] Other-Net -71\n3 selected\n> ";
    TextStop stop;
    CHECK(text_stops_next(text, 0, &layout, &stop));
    CHECK(stop.start == 0);
    CHECK(stop.end == 25);
    CHECK(stop.next == 26);
    CHECK(stop.rows == 2);
    CHECK(stop.line_start);
    CHECK(stop.complete);
    CHECK(text_stops_next(text, stop.next, &layout, &stop));
    CHECK(stop.start == 26);
    CHECK(stop.complete);
    CHECK(text_stops_next(text, stop.next, &layout, &stop));
    CHECK(strncmp(text + stop.start, "3 selected", stop.end - stop.start) == 0);
    CHECK(stop.rows == 1);
    CHECK(stop.complete);
    CHECK(text_stops_next(text, stop.next, &layout, &stop));
    CHECK(text[stop.start] == '>');
    CHECK(!stop.complete);
    CHECK(!text_stops_next(text, stop.next, &layout, &stop));
}

static void test_stop_of_crlf_lines(void) {
    TextStop stop;
    const char* text = "one\r\n\r\ntwo\r\n";
    CHECK(text_stops_next(text, 0, &layout, &stop));
    CHECK(stop.start == 0);
    CHECK(stop.end == 3);
    CHECK(stop.next == 5);
    CHECK(stop.complete);
    CHECK(text_stops_next(text, stop.next, &layout, &stop));
    CHECK(stop.start == 7);
    CHECK(stop.end == 10);
    CHECK(!text_stops_next(text, stop.next, &layout, &stop));
    // A line of bytes the reader can't say is no stop of its own
    CHECK(text_stops_next("\xE2\x9C\x93\r\nname\r\n", 0, &layout, &stop));
    CHECK(stop.start == 5);
    // A name among them still is
    CHECK(text_stops_next("\xE2\x9C\x93 name\n", 0, &layout, &stop));
    CHECK(stop.start == 0);
}

static void test_long_line_splits_at_rows(void) {
    TextStop stop;
    CHECK(text_stops_next(twelve_words, 0, &layout, &stop));
    CHECK(stop.start == 0);
    CHECK(stop.end == 59);
    CHECK(stop.next == 60);
    CHECK(stop.rows == 3);
    CHECK(stop.line_start);
    CHECK(stop.complete);
    CHECK(text_stops_next(twelve_words, stop.next, &layout, &stop));
    CHECK(stop.start == 60);
    CHECK(stop.end == 119);
    CHECK(stop.rows == 3);
    CHECK(!stop.line_start);
    CHECK(stop.complete);
    CHECK(!text_stops_next(twelve_words, stop.next, &layout, &stop));
}

static void test_rows_max_limits_a_stop(void) {
    TextStopsLayout two_rows = layout;
    two_rows.rows_max = 2;
    TextStop stop;
    CHECK(text_stops_next(twelve_words, 0, &two_rows, &stop));
    CHECK(stop.rows == 2);
    CHECK(stop.end == 39);
    CHECK(stop.next == 40);
}

static void test_silent_lines_are_skipped(void) {
    const char* text = "one\n\n---\n   \ntwo\n";
    TextStop stop;
    CHECK(text_stops_next(text, 0, &layout, &stop));
    CHECK(stop.start == 0);
    CHECK(text_stops_next(text, stop.next, &layout, &stop));
    CHECK(stop.start == 13);
    CHECK(text_stops_prev(text, 13, &layout, &stop));
    CHECK(stop.start == 0);
    CHECK(!text_stops_prev(text, 0, &layout, &stop));
    CHECK(!text_stops_next("", 0, &layout, &stop));
    CHECK(!text_stops_next("\n\n---\n", 0, &layout, &stop));
    CHECK(!text_stops_prev("\n\n---\ntwo\n", 6, &layout, &stop));
}

static void test_stop_ends_before_a_silent_rest(void) {
    // A row that ends just before the line's end leaves no empty row in the stop
    TextStop stop;
    CHECK(text_stops_next("aaaaaaaaaaaaaaaaaaaa \nb\n", 0, &layout, &stop));
    CHECK(stop.rows == 1);
    CHECK(stop.end == 20);
    CHECK(stop.complete);
    CHECK(text_stops_next("aaaaaaaaaaaaaaaaaaaa \nb\n", stop.next, &layout, &stop));
    CHECK(stop.start == 22);
    CHECK(text_stops_next("aaaaaaaaaaaaaaaaaaaa ", 0, &layout, &stop));
    CHECK(stop.rows == 1);
    CHECK(!stop.complete);
}

static void test_prev_within_a_long_line(void) {
    TextStop stop;
    CHECK(text_stops_prev(twelve_words, 60, &layout, &stop));
    CHECK(stop.start == 0);
    CHECK(stop.rows == 3);
}

static void test_group_row(void) {
    TextStopsGroup group = {0};
    CHECK(text_stops_group_row(&group, 19, true, &layout));
    CHECK(!text_stops_group_row(&group, 19, false, &layout));
    CHECK(!text_stops_group_row(&group, 19, false, &layout));
    CHECK(group.chars == 59);
    CHECK(group.rows == 3);
    CHECK(text_stops_group_row(&group, 19, false, &layout));
    CHECK(group.chars == 19);
    CHECK(group.rows == 1);
    // A line start begins a stop however short the one before
    CHECK(text_stops_group_row(&group, 3, true, &layout));
    TextStopsLayout two_rows = layout;
    two_rows.rows_max = 2;
    TextStopsGroup rows = {0};
    CHECK(text_stops_group_row(&rows, 3, true, &two_rows));
    CHECK(!text_stops_group_row(&rows, 3, false, &two_rows));
    CHECK(text_stops_group_row(&rows, 3, false, &two_rows));
}

int main(void) {
    test_row_breaks_at_space();
    test_row_exact_fit();
    test_row_long_word();
    test_row_leading_spaces();
    test_row_carriage_return();
    test_row_char_limit();
    test_row_always_advances();
    test_silent_lines();
    test_stops_of_a_list();
    test_stop_of_crlf_lines();
    test_long_line_splits_at_rows();
    test_rows_max_limits_a_stop();
    test_silent_lines_are_skipped();
    test_stop_ends_before_a_silent_rest();
    test_prev_within_a_long_line();
    test_group_row();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
