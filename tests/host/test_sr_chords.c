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

static SrChordCommand feed_in(bool reader_on, InputKey key, InputType type, uint32_t ms) {
    drop = elong = true; // must be written by the call
    return sr_chords_feed(&s, reader_on, key, type, ms, &drop, &elong);
}

/** An event while the reader is on */
static SrChordCommand feed(InputKey key, InputType type, uint32_t ms) {
    return feed_in(true, key, type, ms);
}

/** An event while the reader is off, when Back and Down held long is the only chord */
static SrChordCommand feed_off(InputKey key, InputType type, uint32_t ms) {
    return feed_in(false, key, type, ms);
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
    // Two quick chords while Back is held under 300 ms, so Back ends with a Short, not a Long
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop);
    CHECK(feed(InputKeyUp, InputTypePress, 100) == SrChordReadAll && drop);
    CHECK(feed(InputKeyUp, InputTypeShort, 150) == SrChordNone && drop);
    CHECK(feed(InputKeyUp, InputTypeRelease, 150) == SrChordNone && drop);
    // A second chord in the same hold: Down, like OK, decides on its Short or its Long
    CHECK(feed(InputKeyDown, InputTypePress, 200) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeShort, 250) == SrChordStatus && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 250) == SrChordNone && drop);
    // Back's Short is dropped after a chord, its Release passes, no Long emitted
    CHECK(feed(InputKeyBack, InputTypeShort, 280) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeRelease, 280) == SrChordNone && !drop && !elong);
}

static void test_chord_ok_short_and_long(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone);
    CHECK(feed(InputKeyOk, InputTypePress, 100) == SrChordNone && drop); // OK decides later
    CHECK(feed(InputKeyOk, InputTypeShort, 200) == SrChordRepeat && drop);
    CHECK(feed(InputKeyOk, InputTypeRelease, 200) == SrChordNone && drop);
    // Back's own Long after a chord is dropped and not kept for the release
    CHECK(feed(InputKeyBack, InputTypeLong, 300) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeRepeat, 450) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyOk, InputTypePress, 500) == SrChordNone && drop);
    CHECK(feed(InputKeyOk, InputTypeLong, 800) == SrChordSpell && drop);
    CHECK(feed(InputKeyOk, InputTypeRepeat, 950) == SrChordNone && drop);
    CHECK(feed(InputKeyOk, InputTypeRelease, 1000) == SrChordNone && drop); // no Short after Long
    // Held past 300 ms, Back ends without a Short: its Release passes, no Long emitted
    CHECK(feed(InputKeyBack, InputTypeRelease, 1100) == SrChordNone && !drop && !elong);
}

static void test_chord_after_back_long(void) {
    // The usual timing on the device: Back is held past its Long before the chord key comes
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeLong, 300) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeRepeat, 450) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyUp, InputTypePress, 500) == SrChordReadAll && drop);
    CHECK(feed(InputKeyBack, InputTypeRepeat, 600) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyUp, InputTypeShort, 600) == SrChordNone && drop);
    CHECK(feed(InputKeyUp, InputTypeRelease, 600) == SrChordNone && drop);
    // The chord cancels the held-back Long: the Release passes and no Long is emitted
    CHECK(feed(InputKeyBack, InputTypeRelease, 700) == SrChordNone && !drop && !elong);
}

static void test_chord_ok_long_then_short(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop);
    CHECK(feed(InputKeyOk, InputTypePress, 100) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeLong, 300) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyOk, InputTypeLong, 400) == SrChordSpell && drop);
    // input.c sends no Short after a Long; should one come, it must not run Repeat after Spell
    CHECK(feed(InputKeyOk, InputTypeShort, 450) == SrChordNone && drop);
    CHECK(feed(InputKeyOk, InputTypeRelease, 500) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 600) == SrChordNone && !drop && !elong);
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
    CHECK(feed(InputKeyDown, InputTypePress, 400) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeShort, 450) == SrChordStatus && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 450) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 500) == SrChordNone && !drop);
}

static void test_chord_down_short_is_status(void) {
    // Back and a short Down reads the status bar, on Down's Short, as OK's Short repeats
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop);
    CHECK(feed(InputKeyDown, InputTypePress, 100) == SrChordNone && drop); // Down decides later
    CHECK(feed(InputKeyDown, InputTypeShort, 200) == SrChordStatus && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 200) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeShort, 250) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeRelease, 250) == SrChordNone && !drop && !elong);
}

static void test_chord_down_long_toggles(void) {
    // Back and Down held long turns the reader off, once, and never reads the status bar. The
    // console's sequence: input send back press starts no timer, so Back has no Long here
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyDown, InputTypePress, 10) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeLong, 20) == SrChordToggleReader && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 30) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 40) == SrChordNone && !drop && !elong);
}

static void test_chord_down_long_after_back_long(void) {
    // The usual timing on the device: Back held past its Long before Down, Down past its own
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeLong, 300) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeRepeat, 450) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyDown, InputTypePress, 500) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRepeat, 600) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyDown, InputTypeLong, 800) == SrChordToggleReader && drop);
    CHECK(feed(InputKeyDown, InputTypeRepeat, 950) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 1000) == SrChordNone && drop);
    // The chord took Back's held-back Long: the Release passes and no Long is emitted
    CHECK(feed(InputKeyBack, InputTypeRelease, 1100) == SrChordNone && !drop && !elong);
}

static void test_chord_down_long_then_short(void) {
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop);
    CHECK(feed(InputKeyDown, InputTypePress, 100) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeLong, 400) == SrChordToggleReader && drop);
    // input.c sends no Short after a Long; should one come, it must not read the status bar
    CHECK(feed(InputKeyDown, InputTypeShort, 450) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 500) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 600) == SrChordNone && !drop && !elong);
}

static void test_chord_down_outlives_back(void) {
    // Down is the chord key from its Press while Back is held: as with OK, its Long still
    // names the command after Back has gone, and its events stay the reader's until released
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone);
    CHECK(feed(InputKeyDown, InputTypePress, 100) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeShort, 200) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyBack, InputTypeRelease, 200) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyDown, InputTypeLong, 400) == SrChordToggleReader && drop);
    CHECK(feed(InputKeyDown, InputTypeRepeat, 550) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 600) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypePress, 700) == SrChordNone && !drop); // plain again
}

static void test_off_down_outlives_back(void) {
    // With the reader off, Back let go before Down's Long: no chord had run yet, so Back's Short
    // passes as Back's own, and Down, still the chord key, toggles at its Long all the same
    sr_chords_init(&s);
    CHECK(feed_off(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypePress, 100) == SrChordNone && drop);
    CHECK(feed_off(InputKeyBack, InputTypeShort, 200) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 200) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypeLong, 400) == SrChordToggleReader && drop);
    CHECK(feed(InputKeyDown, InputTypeRepeat, 550) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 600) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypePress, 700) == SrChordNone && !drop); // plain again
}

static void test_down_long_without_back(void) {
    // Down held long without Back is Down held long, with the reader on or off
    sr_chords_init(&s);
    CHECK(feed(InputKeyDown, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyDown, InputTypeLong, 300) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyDown, InputTypeRepeat, 450) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyDown, InputTypeRelease, 500) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypePress, 1000) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypeLong, 1300) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypeRepeat, 1450) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 1500) == SrChordNone && !drop && !elong);
    // Nor when Back comes while Down is already held: Down was no chord key at its Press
    CHECK(feed_off(InputKeyDown, InputTypePress, 2000) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypePress, 2100) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypeLong, 2300) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 2350) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeShort, 2380) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 2380) == SrChordNone && !drop && !elong);
}

static void test_off_back_up_passes(void) {
    // With the reader off, Back and Up are two ordinary keys (on the home screen Up opens the
    // lock menu), and so are Back with OK and with Right
    sr_chords_init(&s);
    CHECK(feed_off(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyUp, InputTypePress, 100) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyUp, InputTypeShort, 150) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyUp, InputTypeRelease, 150) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeShort, 200) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 200) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypePress, 1000) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyOk, InputTypePress, 1050) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyOk, InputTypeShort, 1100) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyOk, InputTypeRelease, 1100) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyRight, InputTypePress, 1150) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyRight, InputTypeShort, 1200) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyRight, InputTypeRelease, 1200) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeShort, 1250) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 1250) == SrChordNone && !drop && !elong);
}

static void test_off_back_alone(void) {
    // Back on its own is as with the reader on: a short press at once, a long press on the
    // release, since at Back's Long the machine cannot tell yet whether Down will follow
    sr_chords_init(&s);
    CHECK(feed_off(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeShort, 100) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 100) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypePress, 1000) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeLong, 1300) == SrChordNone && drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeRepeat, 1450) == SrChordNone && drop && !elong);
    // Up and a long OK while Back is held long are their own, and Back's Long still comes
    CHECK(feed_off(InputKeyUp, InputTypePress, 1500) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyUp, InputTypeShort, 1550) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyUp, InputTypeRelease, 1550) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyOk, InputTypePress, 1600) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyOk, InputTypeLong, 1900) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyOk, InputTypeRelease, 2000) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 2100) == SrChordNone && !drop && elong);
}

static void test_off_down_long_toggles(void) {
    // The one chord with the reader off, dropping what it drops with the reader on: the
    // console's sequence first, then the usual timing, where the chord takes Back's Long
    sr_chords_init(&s);
    CHECK(feed_off(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypePress, 10) == SrChordNone && drop);
    CHECK(feed_off(InputKeyDown, InputTypeLong, 20) == SrChordToggleReader && drop);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 30) == SrChordNone && drop);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 40) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypePress, 1000) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeLong, 1300) == SrChordNone && drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeRepeat, 1450) == SrChordNone && drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypePress, 1500) == SrChordNone && drop);
    CHECK(feed_off(InputKeyDown, InputTypeLong, 1800) == SrChordToggleReader && drop);
    CHECK(feed_off(InputKeyDown, InputTypeRepeat, 1950) == SrChordNone && drop);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 2000) == SrChordNone && drop);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 2100) == SrChordNone && !drop && !elong);
}

static void test_off_short_down_is_lost(void) {
    // With the reader off, Down pressed while Back is held is held back until its Long: a short
    // one is lost, since its Press cannot be given back. No chord ran, so Back stays Back
    sr_chords_init(&s);
    CHECK(feed_off(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypePress, 50) == SrChordNone && drop);
    CHECK(feed_off(InputKeyDown, InputTypeShort, 150) == SrChordNone && drop);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 150) == SrChordNone && drop);
    CHECK(feed_off(InputKeyBack, InputTypeShort, 200) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 200) == SrChordNone && !drop && !elong);
    // Held past its Long around a short Down, Back's Long still comes on the release
    CHECK(feed_off(InputKeyBack, InputTypePress, 1000) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeLong, 1300) == SrChordNone && drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypePress, 1400) == SrChordNone && drop);
    CHECK(feed_off(InputKeyDown, InputTypeShort, 1500) == SrChordNone && drop);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 1500) == SrChordNone && drop);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 1600) == SrChordNone && !drop && elong);
}

static void test_toggle_changes_mode_mid_chord(void) {
    // The reader's thread turns the reader on or off while the keys are still held: the rest of
    // the chord comes in the other mode and is dropped all the same
    sr_chords_init(&s);
    CHECK(feed_off(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyBack, InputTypeLong, 300) == SrChordNone && drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypePress, 500) == SrChordNone && drop);
    CHECK(feed_off(InputKeyDown, InputTypeLong, 800) == SrChordToggleReader && drop);
    CHECK(feed(InputKeyBack, InputTypeRepeat, 900) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyDown, InputTypeRepeat, 950) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeRelease, 1000) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeRelease, 1100) == SrChordNone && !drop && !elong);
    // And from on to off
    CHECK(feed(InputKeyBack, InputTypePress, 2000) == SrChordNone && !drop && !elong);
    CHECK(feed(InputKeyDown, InputTypePress, 2100) == SrChordNone && drop);
    CHECK(feed(InputKeyBack, InputTypeLong, 2300) == SrChordNone && drop && !elong);
    CHECK(feed(InputKeyDown, InputTypeLong, 2400) == SrChordToggleReader && drop);
    CHECK(feed_off(InputKeyDown, InputTypeRepeat, 2550) == SrChordNone && drop);
    CHECK(feed_off(InputKeyBack, InputTypeRepeat, 2600) == SrChordNone && drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 2650) == SrChordNone && drop);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 2700) == SrChordNone && !drop && !elong);
    // Then, with the reader off, Down on its own is an ordinary key again
    CHECK(feed_off(InputKeyDown, InputTypePress, 3000) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypeShort, 3050) == SrChordNone && !drop && !elong);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 3050) == SrChordNone && !drop && !elong);
}

static void test_console_toggle_sequence(void) {
    // The console's chord with the reader on: input send back press, down press, down long,
    // down release, back release, where down long publishes Down's Press, Long and Release
    // itself. One toggle, and the reader is off for the rest; the last Release comes after Down
    // stopped being the chord key, and names no command either
    sr_chords_init(&s);
    CHECK(feed(InputKeyBack, InputTypePress, 0) == SrChordNone && !drop);
    CHECK(feed(InputKeyDown, InputTypePress, 10) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypePress, 20) == SrChordNone && drop);
    CHECK(feed(InputKeyDown, InputTypeLong, 20) == SrChordToggleReader && drop);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 20) == SrChordNone && drop);
    CHECK(feed_off(InputKeyDown, InputTypeRelease, 30) == SrChordNone && !drop);
    CHECK(feed_off(InputKeyBack, InputTypeRelease, 40) == SrChordNone && !drop && !elong);
}

int main(void) {
    test_plain_keys_pass();
    test_back_alone_short();
    test_back_alone_long_on_release();
    test_chord_up_and_down();
    test_chord_ok_short_and_long();
    test_chord_after_back_long();
    test_chord_ok_long_then_short();
    test_chord_volume();
    test_chord_key_outlives_back();
    test_second_key_while_chord_key_held();
    test_chord_down_short_is_status();
    test_chord_down_long_toggles();
    test_chord_down_long_after_back_long();
    test_chord_down_long_then_short();
    test_chord_down_outlives_back();
    test_off_down_outlives_back();
    test_down_long_without_back();
    test_off_back_up_passes();
    test_off_back_alone();
    test_off_down_long_toggles();
    test_off_short_down_is_lost();
    test_toggle_changes_mode_mid_chord();
    test_console_toggle_sequence();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
