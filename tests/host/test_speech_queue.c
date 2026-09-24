#include <stdio.h>
#include <string.h>
#include "speech_queue.h"

static int failures = 0, checks = 0;
#define CHECK(cond)                                                            \
    do {                                                                       \
        checks++;                                                              \
        if(!(cond)) {                                                          \
            failures++;                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);            \
        }                                                                      \
    } while(0)

// Pops the next item and compares its text.
static bool pops(SpeechQueue* q, const char* want) {
    SpeechItem item;
    return speech_queue_pop(q, &item) && strcmp(item.text, want) == 0;
}

// Pushes n plain items named "item first" .. "item first + n - 1".
static void push_numbered(SpeechQueue* q, unsigned first, unsigned n) {
    for(unsigned i = 0; i < n; i++) {
        char text[24];
        snprintf(text, sizeof(text), "item %u", first + i);
        speech_queue_push(q, text, false, false);
    }
}

static bool pops_numbered(SpeechQueue* q, unsigned n) {
    char text[24];
    snprintf(text, sizeof(text), "item %u", n);
    return pops(q, text);
}

static void test_capacity_edges(void) {
    SpeechQueue q;
    SpeechItem item;
    speech_queue_init(&q);

    // Exactly at capacity nothing is dropped
    push_numbered(&q, 0, SPEECH_QUEUE_CAPACITY);
    CHECK(speech_queue_count(&q) == SPEECH_QUEUE_CAPACITY);
    CHECK(q.dropped == 0);

    // One over: the oldest goes, is counted, and the rest keep their order
    push_numbered(&q, SPEECH_QUEUE_CAPACITY, 1);
    CHECK(speech_queue_count(&q) == SPEECH_QUEUE_CAPACITY);
    CHECK(q.dropped == 1);
    for(unsigned i = 1; i <= SPEECH_QUEUE_CAPACITY; i++) CHECK(pops_numbered(&q, i));
    CHECK(!speech_queue_pop(&q, &item));
    CHECK(speech_queue_count(&q) == 0);

    // Three over: three more dropped, the last CAPACITY items remain in order
    push_numbered(&q, 0, SPEECH_QUEUE_CAPACITY + 3);
    CHECK(speech_queue_count(&q) == SPEECH_QUEUE_CAPACITY);
    CHECK(q.dropped == 4);
    for(unsigned i = 3; i < SPEECH_QUEUE_CAPACITY + 3; i++) CHECK(pops_numbered(&q, i));
    CHECK(!speech_queue_pop(&q, &item));

    // Clearing a full queue by interrupt or stop is not a drop
    push_numbered(&q, 0, SPEECH_QUEUE_CAPACITY);
    speech_queue_push(&q, "urgent", true, false);
    CHECK(q.dropped == 4);
    CHECK(speech_queue_count(&q) == 1);
    CHECK(pops(&q, "urgent"));
    push_numbered(&q, 0, SPEECH_QUEUE_CAPACITY);
    speech_queue_stop(&q);
    CHECK(q.dropped == 4);
    CHECK(speech_queue_count(&q) == 0);
}

static void test_ring_wraps(void) {
    // The ring keeps order once the head has moved on and the tail wraps around
    SpeechQueue q;
    speech_queue_init(&q);
    push_numbered(&q, 0, 3);
    CHECK(pops_numbered(&q, 0));
    CHECK(pops_numbered(&q, 1));
    push_numbered(&q, 3, 3);
    CHECK(speech_queue_count(&q) == 4);
    CHECK(q.dropped == 0);
    for(unsigned i = 2; i < 6; i++) CHECK(pops_numbered(&q, i));
    CHECK(speech_queue_count(&q) == 0);

    // Many rounds through the ring, one item at a time
    bool in_order = true;
    for(unsigned round = 0; round < 100; round++) {
        push_numbered(&q, round, 1);
        if(!pops_numbered(&q, round)) in_order = false;
    }
    CHECK(in_order);
    CHECK(q.dropped == 0);
    CHECK(speech_queue_count(&q) == 0);
}

static void test_empty_queue(void) {
    SpeechQueue q;
    SpeechItem item;
    speech_queue_init(&q);

    // Pop from empty fails and leaves the output alone
    memset(&item, 0, sizeof(item));
    item.generation = 77;
    item.replaceable = true;
    memcpy(item.text, "untouched", sizeof("untouched"));
    CHECK(!speech_queue_pop(&q, &item));
    CHECK(item.generation == 77 && item.replaceable && strcmp(item.text, "untouched") == 0);
    CHECK(speech_queue_count(&q) == 0);

    // Interrupt while empty: a new generation with the one item in it
    uint32_t g = q.generation;
    speech_queue_push(&q, "alone", true, false);
    CHECK(q.generation == g + 1);
    CHECK(speech_queue_count(&q) == 1);
    CHECK(speech_queue_pop(&q, &item));
    CHECK(strcmp(item.text, "alone") == 0 && item.generation == g + 1 && !item.replaceable);

    // Stop while empty still bumps the generation
    g = q.generation;
    speech_queue_stop(&q);
    CHECK(q.generation == g + 1);
    CHECK(speech_queue_count(&q) == 0);
    CHECK(!speech_queue_pop(&q, &item));

    // An interrupting replaceable item on an empty queue is simply appended
    speech_queue_push(&q, "change", true, true);
    CHECK(speech_queue_count(&q) == 1);
    CHECK(speech_queue_pop(&q, &item));
    CHECK(item.replaceable && strcmp(item.text, "change") == 0);

    // An empty text is a valid item
    speech_queue_push(&q, "", false, false);
    CHECK(speech_queue_count(&q) == 1);
    CHECK(speech_queue_pop(&q, &item) && item.text[0] == '\0');
}

static void test_replace_rules(void) {
    SpeechQueue q;
    SpeechItem item;
    speech_queue_init(&q);

    // A replaceable item after a non replaceable one is appended and both keep their order
    speech_queue_push(&q, "change 1", false, true);
    speech_queue_push(&q, "focus", false, false);
    speech_queue_push(&q, "change 2", false, true);
    CHECK(speech_queue_count(&q) == 3);
    CHECK(pops(&q, "change 1"));
    CHECK(pops(&q, "focus"));
    CHECK(pops(&q, "change 2"));

    // A non replaceable item never overwrites a replaceable tail
    speech_queue_push(&q, "change", false, true);
    speech_queue_push(&q, "focus", false, false);
    CHECK(speech_queue_count(&q) == 2);
    CHECK(pops(&q, "change"));
    CHECK(pops(&q, "focus"));

    // Only the tail is looked at: a replaceable item deeper in the queue stays
    speech_queue_push(&q, "change 1", false, true);
    speech_queue_push(&q, "focus", false, false);
    speech_queue_push(&q, "change 2", false, true);
    speech_queue_push(&q, "change 3", false, true);
    CHECK(speech_queue_count(&q) == 3);
    CHECK(pops(&q, "change 1"));
    CHECK(pops(&q, "focus"));
    CHECK(pops(&q, "change 3"));

    // Replacing at the tail of a full queue drops nothing
    push_numbered(&q, 0, SPEECH_QUEUE_CAPACITY - 1);
    speech_queue_push(&q, "change 1", false, true);
    CHECK(speech_queue_count(&q) == SPEECH_QUEUE_CAPACITY);
    uint32_t dropped = q.dropped;
    speech_queue_push(&q, "change 2", false, true);
    CHECK(speech_queue_count(&q) == SPEECH_QUEUE_CAPACITY);
    CHECK(q.dropped == dropped);
    for(unsigned i = 0; i < SPEECH_QUEUE_CAPACITY - 1; i++) CHECK(pops_numbered(&q, i));
    CHECK(pops(&q, "change 2"));

    // The replacement takes the current generation and flag, and a shorter text leaves no tail
    speech_queue_push(&q, "a long change", false, true);
    speech_queue_push(&q, "x", false, true);
    CHECK(speech_queue_pop(&q, &item));
    CHECK(item.replaceable && item.generation == q.generation && strcmp(item.text, "x") == 0);

    // A plain item reports replaceable false
    speech_queue_push(&q, "focus", false, false);
    CHECK(speech_queue_pop(&q, &item) && !item.replaceable);
}

static void test_text_limit(void) {
    SpeechQueue q;
    SpeechItem item;
    char text[SPEECH_ITEM_TEXT_MAX + 1];
    speech_queue_init(&q);

    // Exactly the item size minus the terminator is kept whole
    memset(text, 'y', SPEECH_ITEM_TEXT_MAX - 1);
    text[SPEECH_ITEM_TEXT_MAX - 1] = '\0';
    speech_queue_push(&q, text, false, false);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, text) == 0);

    // One more character is cut, and the item stays terminated
    memset(text, 'y', SPEECH_ITEM_TEXT_MAX);
    text[SPEECH_ITEM_TEXT_MAX] = '\0';
    speech_queue_push(&q, text, false, false);
    CHECK(speech_queue_pop(&q, &item));
    CHECK(strlen(item.text) == SPEECH_ITEM_TEXT_MAX - 1);
    CHECK(strncmp(item.text, text, SPEECH_ITEM_TEXT_MAX - 1) == 0);
}


// File items: a clip to play from the card takes the whole queue, like an interrupting push.
static void test_file_items(void) {
    SpeechQueue q;
    SpeechItem item;
    speech_queue_init(&q);

    // One file after two texts: the queue holds that one item, of a new generation, with the
    // path in text, the rate, file true and replaceable false
    speech_queue_push(&q, "one", false, false);
    speech_queue_push(&q, "two", false, false);
    uint32_t g = q.generation;
    speech_queue_push_file(&q, "/ext/sr/clips/2_samantha_hp.raw", 16000);
    CHECK(q.generation == g + 1);
    CHECK(speech_queue_count(&q) == 1);
    CHECK(speech_queue_pop(&q, &item));
    CHECK(item.file && item.rate == 16000 && !item.replaceable);
    CHECK(strcmp(item.text, "/ext/sr/clips/2_samantha_hp.raw") == 0);
    CHECK(item.generation == g + 1);
    CHECK(!speech_queue_pop(&q, &item));

    // Text items carry file false and rate 0, also after a file item went through
    speech_queue_push(&q, "words", false, true);
    CHECK(speech_queue_pop(&q, &item));
    CHECK(!item.file && item.rate == 0 && item.replaceable);

    // A file item is not replaceable: a replaceable text after it is appended, not merged
    speech_queue_push_file(&q, "/ext/a.raw", 8000);
    speech_queue_push(&q, "change", false, true);
    CHECK(speech_queue_count(&q) == 2);
    CHECK(speech_queue_pop(&q, &item) && item.file && item.rate == 8000);
    CHECK(speech_queue_pop(&q, &item) && !item.file && strcmp(item.text, "change") == 0);

    // A file never merges into a replaceable tail either: it clears the queue instead
    speech_queue_push(&q, "change", false, true);
    speech_queue_push_file(&q, "/ext/b.raw", 32000);
    CHECK(speech_queue_count(&q) == 1);
    CHECK(speech_queue_pop(&q, &item) && item.file && item.rate == 32000);
    CHECK(strcmp(item.text, "/ext/b.raw") == 0);

    // A file clears a full queue without counting drops, and a stop drops a waiting file
    push_numbered(&q, 0, SPEECH_QUEUE_CAPACITY);
    uint32_t dropped = q.dropped;
    speech_queue_push_file(&q, "/ext/c.raw", 16000);
    CHECK(q.dropped == dropped && speech_queue_count(&q) == 1);
    speech_queue_stop(&q);
    CHECK(speech_queue_count(&q) == 0);
    CHECK(!speech_queue_pop(&q, &item));

    // A long path is cut like text and stays terminated
    char path[SPEECH_ITEM_TEXT_MAX + 10];
    memset(path, 'p', sizeof(path) - 1);
    path[0] = '/';
    path[sizeof(path) - 1] = '\0';
    speech_queue_push_file(&q, path, 16000);
    CHECK(speech_queue_pop(&q, &item) && item.file);
    CHECK(strlen(item.text) == SPEECH_ITEM_TEXT_MAX - 1);
    CHECK(strncmp(item.text, path, SPEECH_ITEM_TEXT_MAX - 1) == 0);
}

// Spelled items: the focus spelled on Back plus OK held takes the whole queue like an
// interrupting push, and only push_spelled sets spell.
static void test_spelled_items(void) {
    SpeechQueue q;
    SpeechItem item;
    speech_queue_init(&q);

    // One push_spelled after a text: one item, of a new generation, spell true, the text kept
    speech_queue_push(&q, "one", false, false);
    uint32_t g = q.generation;
    speech_queue_push_spelled(&q, "Apps");
    CHECK(q.generation == g + 1);
    CHECK(speech_queue_count(&q) == 1);
    CHECK(speech_queue_pop(&q, &item));
    CHECK(item.spell && !item.file && !item.replaceable && item.rate == 0);
    CHECK(strcmp(item.text, "Apps") == 0);

    // Text and file pushes that reuse the slot of a spelled item leave spell false
    speech_queue_push_spelled(&q, "Apps");
    speech_queue_push(&q, "words", true, false);
    CHECK(speech_queue_pop(&q, &item) && !item.spell && strcmp(item.text, "words") == 0);
    speech_queue_push_spelled(&q, "Apps");
    speech_queue_push_file(&q, "/ext/a.raw", 16000);
    CHECK(speech_queue_pop(&q, &item) && item.file && !item.spell);

    // A spelled item is not replaceable: a replaceable text after it is appended
    speech_queue_push_spelled(&q, "Apps");
    speech_queue_push(&q, "change", false, true);
    CHECK(speech_queue_count(&q) == 2);
    CHECK(speech_queue_pop(&q, &item) && item.spell && strcmp(item.text, "Apps") == 0);
    CHECK(speech_queue_pop(&q, &item) && !item.spell && strcmp(item.text, "change") == 0);
}

// Pops the next item and checks it is a plain part of generation g, not replaceable.
static bool pops_part(SpeechQueue* q, SpeechItem* item, uint32_t g) {
    return speech_queue_pop(q, item) && item->generation == g && !item->replaceable &&
           !item->file && !item->spell;
}

// A whole screen read on request: longer than an item, so it goes in parts of at most
// SPEECH_ITEM_TEXT_MAX - 1 characters, cut after the last ". " or ", " that fits, else at the
// last space, else at the limit. The first part interrupts, the rest follow it.
static void test_parts(void) {
    SpeechQueue q;
    SpeechItem item;
    char text[5 * SPEECH_ITEM_TEXT_MAX];
    speech_queue_init(&q);

    // A text that fits is one interrupting item
    speech_queue_push(&q, "old", false, false);
    uint32_t g = q.generation;
    CHECK(speech_queue_push_parts(&q, "Settings. Bluetooth, 1 of 11") == 1);
    CHECK(q.generation == g + 1 && speech_queue_count(&q) == 1);
    CHECK(pops_part(&q, &item, g + 1) && strcmp(item.text, "Settings. Bluetooth, 1 of 11") == 0);

    // Six rows of 38 characters, then the focus and the buttons, which must not be lost: the
    // first part ends with the fourth row, exactly at the limit, the second holds the rest
    text[0] = '\0';
    for(int i = 0; i < 6; i++) {
        char row[48];
        snprintf(row, sizeof(row), "%sRow %d with some words in it to be long", i ? ". " : "", i);
        strcat(text, row);
    }
    strcat(text, ". Apps, 3 of 11. buttons: left Back, right OK");
    speech_queue_push(&q, "old", false, false);
    g = q.generation;
    CHECK(speech_queue_push_parts(&q, text) == 2);
    CHECK(speech_queue_count(&q) == 2);
    CHECK(pops_part(&q, &item, g + 1) && strlen(item.text) == SPEECH_ITEM_TEXT_MAX - 1);
    CHECK(strncmp(item.text, "Row 0 ", 6) == 0 && strstr(item.text, ". Row 3 ") != NULL);
    CHECK(strcmp(item.text + strlen(item.text) - 8, "be long.") == 0);
    CHECK(pops_part(&q, &item, g + 1) && strncmp(item.text, "Row 4 ", 6) == 0);
    CHECK(strcmp(item.text + strlen(item.text) - 8, "right OK") == 0);

    // The last ", " counts as much as the last ". ": a list after an early sentence end
    strcpy(text, "Head.");
    for(int i = 0; i < 40; i++)
        strcat(text, " word,");
    CHECK(speech_queue_push_parts(&q, text) == 2);
    CHECK(pops_part(&q, &item, q.generation));
    size_t n = strlen(item.text);
    CHECK(n > SPEECH_ITEM_TEXT_MAX - 8 && n <= SPEECH_ITEM_TEXT_MAX - 1 && item.text[n - 1] == ',');
    CHECK(pops_part(&q, &item, q.generation) && strncmp(item.text, "word,", 5) == 0);

    // No ". " or ", ": at the last space, and the space between the parts is dropped
    text[0] = '\0';
    for(int i = 0; i < 60; i++)
        strcat(text, "word ");
    CHECK(speech_queue_push_parts(&q, text) == 2);
    CHECK(pops_part(&q, &item, q.generation));
    n = strlen(item.text);
    CHECK(n <= SPEECH_ITEM_TEXT_MAX - 1 && strcmp(item.text + n - 4, "word") == 0);
    CHECK(pops_part(&q, &item, q.generation) && strncmp(item.text, "word", 4) == 0);

    // No space at all: cut at the limit, 159 + 159 + 82
    memset(text, 'x', 400);
    text[400] = '\0';
    CHECK(speech_queue_push_parts(&q, text) == 3);
    CHECK(pops_part(&q, &item, q.generation) && strlen(item.text) == SPEECH_ITEM_TEXT_MAX - 1);
    CHECK(pops_part(&q, &item, q.generation) && strlen(item.text) == SPEECH_ITEM_TEXT_MAX - 1);
    CHECK(pops_part(&q, &item, q.generation) && strlen(item.text) == 400 - 2 * 159);

    // More parts than the queue holds: the first SPEECH_QUEUE_CAPACITY are queued, the rest is
    // counted as dropped
    memset(text, 'x', 700);
    text[700] = '\0';
    uint32_t dropped = q.dropped;
    CHECK(speech_queue_push_parts(&q, text) == SPEECH_QUEUE_CAPACITY);
    CHECK(speech_queue_count(&q) == SPEECH_QUEUE_CAPACITY && q.dropped == dropped + 1);
    for(unsigned i = 0; i < SPEECH_QUEUE_CAPACITY; i++)
        CHECK(pops_part(&q, &item, q.generation) && strlen(item.text) == 159);

    // Nothing to say queues nothing and interrupts nothing
    speech_queue_push(&q, "keep", false, false);
    g = q.generation;
    CHECK(speech_queue_push_parts(&q, "") == 0 && speech_queue_push_parts(&q, "   ") == 0);
    CHECK(q.generation == g && speech_queue_count(&q) == 1);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "keep") == 0);
}

int main(void) {
    SpeechQueue q;
    SpeechItem item;
    speech_queue_init(&q);
    CHECK(speech_queue_count(&q) == 0);
    CHECK(!speech_queue_pop(&q, &item));

    // Plain order
    speech_queue_push(&q, "one", false, false);
    speech_queue_push(&q, "two", false, false);
    CHECK(speech_queue_count(&q) == 2);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "one") == 0);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "two") == 0);
    CHECK(!speech_queue_pop(&q, &item));

    // Interrupt clears and starts a new generation
    uint32_t g0 = q.generation;
    speech_queue_push(&q, "old", false, false);
    speech_queue_push(&q, "new", true, false);
    CHECK(q.generation == g0 + 1);
    CHECK(speech_queue_count(&q) == 1);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "new") == 0);
    CHECK(item.generation == g0 + 1);

    // A replaceable item at the tail is overwritten by the next replaceable one
    speech_queue_push(&q, "focus", false, false);
    speech_queue_push(&q, "change 1", false, true);
    speech_queue_push(&q, "change 2", false, true);
    CHECK(speech_queue_count(&q) == 2);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "focus") == 0);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "change 2") == 0);

    // A replaceable item after a non replaceable tail is appended
    speech_queue_push(&q, "change 1", false, true);
    speech_queue_push(&q, "focus", false, false);
    speech_queue_push(&q, "change 2", false, true);
    CHECK(speech_queue_count(&q) == 3);
    speech_queue_stop(&q);
    CHECK(speech_queue_count(&q) == 0);

    // Full: the oldest is dropped and counted
    uint32_t dropped = q.dropped;
    speech_queue_push(&q, "a", false, false);
    speech_queue_push(&q, "b", false, false);
    speech_queue_push(&q, "c", false, false);
    speech_queue_push(&q, "d", false, false);
    speech_queue_push(&q, "e", false, false);
    CHECK(speech_queue_count(&q) == SPEECH_QUEUE_CAPACITY);
    CHECK(q.dropped == dropped + 1);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "b") == 0);

    // Stop bumps the generation so a running utterance notices
    uint32_t g1 = q.generation;
    speech_queue_stop(&q);
    CHECK(q.generation == g1 + 1);

    // Long text is cut to the item size
    char longtext[300];
    memset(longtext, 'x', sizeof(longtext) - 1);
    longtext[sizeof(longtext) - 1] = '\0';
    speech_queue_push(&q, longtext, true, false);
    CHECK(speech_queue_pop(&q, &item) && strlen(item.text) == SPEECH_ITEM_TEXT_MAX - 1);

    // Beyond the brief: capacity edges, ring wrap, the empty queue, replace rules, text limit
    test_capacity_edges();
    test_ring_wraps();
    test_empty_queue();
    test_replace_rules();
    test_text_limit();
    test_file_items();
    test_spelled_items();
    test_parts();

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
