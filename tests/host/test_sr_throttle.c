#include <stdio.h>
#include <string.h>
#include "sr_throttle.h"

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
#define CHECK_STR(actual, expected)                                                               \
    do {                                                                                          \
        checks++;                                                                                 \
        if(strcmp((actual), (expected)) != 0) {                                                   \
            failures++;                                                                           \
            printf("FAIL line %d: got \"%s\" expected \"%s\"\n", __LINE__, (actual), (expected)); \
        }                                                                                         \
    } while(0)

static SrThrottle t;
static char out[SR_ANN_TEXT_MAX];

/** sr_throttle_due into out, which is filled with junk first so a copy must terminate it. */
static bool due(uint32_t now_ms, uint32_t interval_ms) {
    memset(out, '#', sizeof(out));
    return sr_throttle_due(&t, now_ms, interval_ms, out, sizeof(out));
}

/** A progress bar at a change delay of 1500 ms: the first change is said at once, the ones after
 *  it are held, each replacing the one before, and the latest is said when its time comes. */
static void test_progress_bar(void) {
    sr_throttle_init(&t);
    CHECK(!t.pending);
    CHECK(sr_throttle_wait_ms(&t, 1000, 1500) == 0); // nothing held
    CHECK(sr_throttle_offer(&t, "12 percent", 1000, 1500)); // the first change: at once
    CHECK(!t.pending);
    CHECK(sr_throttle_wait_ms(&t, 1000, 1500) == 0);

    CHECK(!sr_throttle_offer(&t, "15 percent", 1300, 1500)); // held
    CHECK(t.pending);
    CHECK(sr_throttle_wait_ms(&t, 1300, 1500) == 1200);
    CHECK(!sr_throttle_offer(&t, "19 percent", 1700, 1500)); // replaces the held one
    CHECK(t.pending);
    CHECK(sr_throttle_wait_ms(&t, 1700, 1500) == 800); // 2500 - 1700

    CHECK(!due(2400, 1500));
    CHECK(t.pending);
    CHECK(sr_throttle_wait_ms(&t, 2400, 1500) == 100);
    CHECK(due(2500, 1500));
    CHECK_STR(out, "19 percent"); // the latest, not "15 percent"
    CHECK(!t.pending);
    CHECK(sr_throttle_wait_ms(&t, 2500, 1500) == 0);
    CHECK(!due(2500, 1500)); // said once only
    CHECK(!due(9000, 1500));

    // The interval counts from 2500, when the held change was said
    CHECK(!sr_throttle_offer(&t, "done", 2600, 1500));
    CHECK(sr_throttle_wait_ms(&t, 2600, 1500) == 1400);
    CHECK(!due(3999, 1500));
    CHECK(due(4000, 1500));
    CHECK_STR(out, "done");
    CHECK(!t.pending);
}

/** A due change that the service loop has not collected yet is late, not lost: the wait is 0. */
static void test_late_collection(void) {
    sr_throttle_init(&t);
    CHECK(sr_throttle_offer(&t, "a", 1000, 1500));
    CHECK(!sr_throttle_offer(&t, "b", 1100, 1500));
    CHECK(sr_throttle_wait_ms(&t, 2500, 1500) == 0);
    CHECK(sr_throttle_wait_ms(&t, 7000, 1500) == 0);
    CHECK(due(7000, 1500));
    CHECK_STR(out, "b");
    // Said at 7000: the next change waits for 8500
    CHECK(!sr_throttle_offer(&t, "c", 7100, 1500));
    CHECK(sr_throttle_wait_ms(&t, 7100, 1500) == 1400);
}

/** A change offered once the interval has passed is said at once, and a change still held from
 *  before is dropped: the newer text wins. */
static void test_said_at_once_drops_the_held_change(void) {
    sr_throttle_init(&t);
    CHECK(sr_throttle_offer(&t, "a", 1000, 1500));
    CHECK(!sr_throttle_offer(&t, "b", 1100, 1500));
    CHECK(sr_throttle_offer(&t, "c", 2600, 1500));
    CHECK(!t.pending);
    CHECK(!due(9000, 1500));
    CHECK(sr_throttle_wait_ms(&t, 2600, 1500) == 0);
    // Said at 2600
    CHECK(!sr_throttle_offer(&t, "d", 4000, 1500));
    CHECK(sr_throttle_offer(&t, "e", 4100, 1500));
    CHECK(!t.pending);
}

/** A new screen or focus drops the held change; when the last change was said is kept. */
static void test_clear(void) {
    sr_throttle_init(&t);
    CHECK(sr_throttle_offer(&t, "12 percent", 1000, 1500));
    CHECK(!sr_throttle_offer(&t, "15 percent", 1200, 1500));
    sr_throttle_clear(&t);
    CHECK(!t.pending);
    CHECK(sr_throttle_wait_ms(&t, 1200, 1500) == 0);
    CHECK(!due(1200, 1500));
    CHECK(!due(9000, 1500));
    // A clear does not reset the time of the last change said: within the interval a change is
    // still held
    CHECK(!sr_throttle_offer(&t, "20 percent", 1400, 1500));
    CHECK(t.pending);
    CHECK(sr_throttle_wait_ms(&t, 1400, 1500) == 1100);
    sr_throttle_clear(&t);
    CHECK(!sr_throttle_offer(&t, "21 percent", 2499, 1500));
    sr_throttle_clear(&t);
    // Once the interval has passed since the last change said, a change is said at once
    CHECK(sr_throttle_offer(&t, "22 percent", 2500, 1500));
    CHECK(!t.pending);
    // A clear with nothing held is harmless
    sr_throttle_clear(&t);
    CHECK(!t.pending);
    CHECK(!due(9000, 1500));
}

/** The first change after init is said at once whatever the time, also at tick 0. */
static void test_first_change_at_once(void) {
    sr_throttle_init(&t);
    CHECK(sr_throttle_offer(&t, "a", 0, 3000));
    CHECK(!sr_throttle_offer(&t, "b", 1, 3000));
    CHECK(sr_throttle_wait_ms(&t, 1, 3000) == 2999);
    sr_throttle_init(&t);
    CHECK(sr_throttle_offer(&t, "a", 5, 3000));
    sr_throttle_init(&t);
    CHECK(sr_throttle_offer(&t, "a", 0xFFFFFFF0u, 3000));
}

/** Interval 0 says every change at once. */
static void test_interval_zero(void) {
    sr_throttle_init(&t);
    CHECK(sr_throttle_offer(&t, "a", 1000, 0));
    CHECK(sr_throttle_offer(&t, "b", 1000, 0));
    CHECK(sr_throttle_offer(&t, "c", 1001, 0));
    CHECK(!t.pending);
    CHECK(sr_throttle_wait_ms(&t, 1001, 0) == 0);
    CHECK(!due(1001, 0));
}

/** A text longer than SR_ANN_TEXT_MAX - 1 characters is cut there; a smaller buffer gets as
 *  much as fits, terminated. */
static void test_long_text_is_cut(void) {
    char long_text[SR_ANN_TEXT_MAX + 40];
    memset(long_text, 'a', sizeof(long_text) - 1);
    long_text[sizeof(long_text) - 1] = '\0';
    sr_throttle_init(&t);
    CHECK(sr_throttle_offer(&t, "first", 1000, 1500));
    CHECK(!sr_throttle_offer(&t, long_text, 1100, 1500));
    CHECK(strlen(t.text) == SR_ANN_TEXT_MAX - 1);
    CHECK(due(2500, 1500));
    CHECK(strlen(out) == SR_ANN_TEXT_MAX - 1);
    CHECK(out[0] == 'a' && out[SR_ANN_TEXT_MAX - 2] == 'a');

    char small[8];
    memset(small, '#', sizeof(small));
    CHECK(!sr_throttle_offer(&t, "12 percent", 2600, 1500));
    CHECK(sr_throttle_due(&t, 4000, 1500, small, sizeof(small)));
    CHECK_STR(small, "12 perc");
    CHECK(!t.pending);
}

/** The tick wraps after 0xFFFFFFFF: the time since the last change said is counted across it. */
static void test_wrap_around(void) {
    sr_throttle_init(&t);
    CHECK(sr_throttle_offer(&t, "a", 0xFFFFFC00u, 1000)); // said 1024 ms before the wrap
    CHECK(!sr_throttle_offer(&t, "b", 0xFFFFFF00u, 1000)); // 768 ms later: held
    CHECK(sr_throttle_wait_ms(&t, 0xFFFFFF00u, 1000) == 232);
    CHECK(!due(0xFFFFFFE0u, 1000)); // 992 ms
    CHECK(sr_throttle_wait_ms(&t, 0xFFFFFFE0u, 1000) == 8);
    CHECK(sr_throttle_wait_ms(&t, 0x00000010u, 1000) == 0); // 1040 ms, past the wrap
    CHECK(due(0x00000100u, 1000)); // 1280 ms
    CHECK_STR(out, "b");
    // Said at 0x100: an offer 999 ms later is held, one 1000 ms later said
    CHECK(!sr_throttle_offer(&t, "c", 0x00000100u + 999, 1000));
    CHECK(sr_throttle_offer(&t, "d", 0x00000100u + 1000, 1000));
}

int main(void) {
    test_progress_bar();
    test_late_collection();
    test_said_at_once_drops_the_held_change();
    test_clear();
    test_first_change_at_once();
    test_interval_zero();
    test_long_text_is_cut();
    test_wrap_around();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
