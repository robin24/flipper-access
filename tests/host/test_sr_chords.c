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
