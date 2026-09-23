#include <math.h>
#include <stdio.h>
#include <string.h>
#include "speech_pcm.h"

static int failures = 0, checks = 0;
#define CHECK(cond)                                                            \
    do {                                                                       \
        checks++;                                                              \
        if(!(cond)) {                                                          \
            failures++;                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);            \
        }                                                                      \
    } while(0)

// The Text to SAM app's SetAUDIO curve
static uint8_t demo_curve(uint8_t x) {
    float data = x;
    data /= 255.0f;
    data -= 0.5f;
    data *= 4.0f;
    data = tanhf(data);
    data += 0.5f;
    data *= 255.0f;
    if(data < 0) {
        data = 0;
    } else if(data > 255) {
        data = 255;
    }
    return (uint8_t)data;
}

static uint8_t emitted[64];
static size_t emitted_count;
static size_t abort_at = 1000;

static bool collect(uint8_t duty, void* context) {
    (void)context;
    if(emitted_count >= abort_at) return false;
    if(emitted_count < sizeof(emitted)) emitted[emitted_count] = duty;
    emitted_count++;
    return true;
}

// Beyond the brief. This collector keeps a long sequence so runs of one value can be checked.
static uint8_t seq[4096];
static size_t seq_count;

static bool collect_seq(uint8_t duty, void* context) {
    (void)context;
    if(seq_count < sizeof(seq)) seq[seq_count] = duty;
    seq_count++;
    return true;
}

// Counts through the context pointer only.
static bool count_only(uint8_t duty, void* context) {
    (void)duty;
    size_t* n = context;
    (*n)++;
    return true;
}

// Accepts `limit` duty bytes, then refuses.
typedef struct {
    size_t limit;
    size_t count;
    uint8_t last;
} Limited;

static bool collect_limited(uint8_t duty, void* context) {
    Limited* l = context;
    if(l->count >= l->limit) return false;
    l->count++;
    l->last = duty;
    return true;
}

// True when seq[first .. first + count) was collected and holds only duty.
static bool run_is(size_t first, size_t count, uint8_t duty) {
    if(first + count > sizeof(seq) || first + count > seq_count) return false;
    for(size_t i = first; i < first + count; i++) {
        if(seq[i] != duty) return false;
    }
    return true;
}

static bool lut_is_monotone(const SpeechPcm* pcm) {
    for(int x = 0; x < 255; x++) {
        if(pcm->lut[x] > pcm->lut[x + 1]) return false;
    }
    return true;
}

static void test_delta_zero(const uint8_t v[5], const uint8_t want[5]) {
    SpeechPcm pcm;

    // delta 0 without overhead: nothing is held, so nothing is emitted and no time passes
    speech_pcm_init(&pcm, 100, 0);
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 0, collect_seq, NULL));
    CHECK(seq_count == 0);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 0 && pcm.slots == 0);
    CHECK(pcm.now_ns == 0 && pcm.next_slot_ns == 0);

    // delta 7 is still 0 us after the integer division by 8
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 7, collect_seq, NULL));
    CHECK(seq_count == 0);
    CHECK(pcm.subsamples == 10 && pcm.nominal_us == 0 && pcm.now_ns == 0);

    // delta 0 with 5 us overhead: each value lasts 5 us, so the marks at 0 and 20 us see
    // values 0 and 4 while the nominal time stays 0
    speech_pcm_init(&pcm, 100, 5000);
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 0, collect_seq, NULL));
    CHECK(seq_count == 2);
    CHECK(seq[0] == want[0] && seq[1] == want[4]);
    CHECK(pcm.nominal_us == 0 && pcm.slots == 2);
    CHECK(pcm.now_ns == 25000 && pcm.next_slot_ns == 40000);
}

static void test_largest_delta(const uint8_t v[5], const uint8_t want[5]) {
    // 65535 / 8 = 8191 us per value, 40955 us in all: the marks in [0, 40955 us) number
    // ceil(40955 / 20) = 2048. Value k covers [8191 k, 8191 (k + 1)) us and so holds
    // ceil(409.55 (k + 1)) - ceil(409.55 k) marks: 410, 410, 409, 410, 409.
    SpeechPcm pcm;
    speech_pcm_init(&pcm, 100, 0);
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 65535, collect_seq, NULL));
    CHECK(seq_count == 2048);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 40955 && pcm.slots == 2048);
    CHECK(pcm.now_ns == 40955000 && pcm.next_slot_ns == 40960000);
    CHECK(run_is(0, 410, want[0]));
    CHECK(run_is(410, 410, want[1]));
    CHECK(run_is(820, 409, want[2]));
    CHECK(run_is(1229, 410, want[3]));
    CHECK(run_is(1639, 409, want[4]));

    // With 1 ms of overhead each value lasts 9191 us, 45955 us in all: ceil(45955 / 20) = 2298
    speech_pcm_init(&pcm, 100, 1000000);
    size_t n = 0;
    CHECK(speech_pcm_push(&pcm, v, 65535, count_only, &n));
    CHECK(n == 2298 && pcm.slots == 2298 && pcm.nominal_us == 40955);
    CHECK(pcm.now_ns == 45955000);
}

static void test_overhead(const uint8_t v[5], const uint8_t want[5]) {
    SpeechPcm pcm;

    // No overhead: delta 160 is 20 us, one mark per value
    speech_pcm_init(&pcm, 100, 0);
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 160, collect_seq, NULL));
    CHECK(seq_count == 5);
    for(int k = 0; k < 5; k++) CHECK(run_is((size_t)k, 1, want[k]));
    CHECK(pcm.nominal_us == 100 && pcm.slots == 5 && pcm.now_ns == 100000);

    // 100 us overhead: every value lasts 120 us, six marks each; the nominal time ignores it
    speech_pcm_init(&pcm, 100, 100000);
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 160, collect_seq, NULL));
    CHECK(seq_count == 30);
    for(int k = 0; k < 5; k++) CHECK(run_is((size_t)(6 * k), 6, want[k]));
    CHECK(pcm.nominal_us == 100 && pcm.slots == 30 && pcm.now_ns == 600000);

    // 7 us overhead: 27 us per value, the marks at 0,20,40,60,80,100,120 see values 0,0,1,2,2,3,4
    speech_pcm_init(&pcm, 100, 7000);
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 160, collect_seq, NULL));
    CHECK(seq_count == 7);
    const uint8_t order[7] = {0, 0, 1, 2, 2, 3, 4};
    for(int k = 0; k < 7; k++) CHECK(seq[k] == want[order[k]]);
    CHECK(pcm.now_ns == 135000 && pcm.next_slot_ns == 140000);
}

static void test_carry(uint32_t overhead_ns) {
    // Over many pushes with random deltas the marks emitted must be exactly those in
    // [0, total time): the remainder carries from push to push, so no time is lost or gained
    SpeechPcm pcm;
    speech_pcm_init(&pcm, 100, overhead_ns);
    const uint8_t v[5] = {100, 115, 128, 140, 155};
    uint32_t seed = 2026;
    uint64_t total_ns = 0;
    uint32_t nominal_us = 0;
    size_t emitted_slots = 0;
    bool all_accepted = true;
    for(int i = 0; i < 10000; i++) {
        seed = seed * 1664525u + 1013904223u;
        uint16_t delta = (uint16_t)((seed >> 16) & 0x0FFFu);
        uint32_t hold_us = delta / 8u;
        total_ns += 5ull * (hold_us * 1000ull + overhead_ns);
        nominal_us += 5u * hold_us;
        if(!speech_pcm_push(&pcm, v, delta, count_only, &emitted_slots)) all_accepted = false;
    }
    CHECK(all_accepted);
    uint64_t want_slots = (total_ns + SPEECH_SLOT_NS - 1) / SPEECH_SLOT_NS;
    CHECK(emitted_slots == want_slots);
    CHECK(pcm.slots == want_slots);
    CHECK(pcm.subsamples == 50000);
    CHECK(pcm.nominal_us == nominal_us);
    CHECK(pcm.now_ns == total_ns);
    CHECK(pcm.next_slot_ns == want_slots * SPEECH_SLOT_NS);
    // within one slot of the total time
    CHECK(emitted_slots * SPEECH_SLOT_NS >= total_ns);
    CHECK(emitted_slots * SPEECH_SLOT_NS < total_ns + SPEECH_SLOT_NS);
}

static void test_volume(const uint8_t v[5]) {
    SpeechPcm pcm;

    // Volume 0: every entry is the silence value, so a push emits nothing but silence
    speech_pcm_init(&pcm, 0, 0);
    uint8_t silence = speech_pcm_silence(&pcm);
    CHECK(silence == 127);
    bool all_silent = true;
    for(int x = 0; x < 256; x++) {
        if(pcm.lut[x] != silence) all_silent = false;
    }
    CHECK(all_silent);
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 160, collect_seq, NULL));
    CHECK(seq_count == 5);
    CHECK(run_is(0, 5, silence));

    // Volume 100 reproduces the demo curve, clips at both ends, and is what anything above
    // 100 is treated as
    speech_pcm_init(&pcm, 100, 0);
    uint8_t full[256];
    memcpy(full, pcm.lut, sizeof(full));
    CHECK(full[0] == 0 && full[255] == 255);
    CHECK(speech_pcm_silence(&pcm) == demo_curve(128));
    speech_pcm_set_volume(&pcm, 200);
    CHECK(memcmp(full, pcm.lut, sizeof(full)) == 0);
    speech_pcm_set_volume(&pcm, 255);
    CHECK(memcmp(full, pcm.lut, sizeof(full)) == 0);

    // Every volume keeps the curve non decreasing
    for(int volume = 0; volume <= 100; volume += 25) {
        speech_pcm_set_volume(&pcm, (uint8_t)volume);
        CHECK(lut_is_monotone(&pcm));
    }

    // A volume change leaves the timing alone, and the next push uses the new table, which
    // pulls the loud and the quiet value toward the middle
    speech_pcm_set_volume(&pcm, 100);
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 160, collect_seq, NULL));
    speech_pcm_set_volume(&pcm, 50);
    CHECK(pcm.now_ns == 100000 && pcm.next_slot_ns == 100000 && pcm.slots == 5);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 100);
    seq_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 160, collect_seq, NULL));
    CHECK(seq_count == 5);
    for(int k = 0; k < 5; k++) CHECK(seq[k] == pcm.lut[v[k]]);
    CHECK(pcm.lut[v[4]] < full[v[4]]);
    CHECK(pcm.lut[v[0]] > full[v[0]]);
}

static void test_stop(const uint8_t v[5], const uint8_t want[5]) {
    SpeechPcm pcm;

    // Refused at the first mark: nothing is sent or counted
    speech_pcm_init(&pcm, 100, 0);
    Limited none = {0, 0, 0};
    CHECK(!speech_pcm_push(&pcm, v, 160, collect_limited, &none));
    CHECK(none.count == 0 && pcm.slots == 0);
    CHECK(pcm.next_slot_ns == 0 && pcm.now_ns == 0);

    // Refused at the fourth of seven marks (5 us overhead): the push stops there, slots counts
    // the three that were taken, the third of them is value 1, and the fourth mark at 60 us is
    // still pending while value 2 had begun at 50 us
    speech_pcm_init(&pcm, 100, 5000);
    Limited three = {3, 0, 0};
    CHECK(!speech_pcm_push(&pcm, v, 160, collect_limited, &three));
    CHECK(three.count == 3 && pcm.slots == 3);
    CHECK(three.last == want[1]);
    CHECK(pcm.next_slot_ns == 60000 && pcm.now_ns == 50000);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 100);

    // A push with no mark to emit cannot be refused
    speech_pcm_init(&pcm, 100, 0);
    Limited still = {0, 0, 0};
    CHECK(speech_pcm_push(&pcm, v, 0, collect_limited, &still));
    CHECK(still.count == 0);

    // After a reset the stage starts over, keeping its table and overhead, and a willing
    // emitter gets all seven marks
    speech_pcm_init(&pcm, 100, 5000);
    Limited one = {1, 0, 0};
    CHECK(!speech_pcm_push(&pcm, v, 160, collect_limited, &one));
    speech_pcm_reset(&pcm);
    CHECK(pcm.slots == 0 && pcm.now_ns == 0 && pcm.next_slot_ns == 0);
    CHECK(pcm.subsamples == 0 && pcm.nominal_us == 0);
    CHECK(pcm.overhead_ns == 5000 && pcm.lut[v[0]] == want[0]);
    Limited seven = {100, 0, 0};
    CHECK(speech_pcm_push(&pcm, v, 160, collect_limited, &seven));
    CHECK(seven.count == 7 && pcm.slots == 7);
}

int main(void) {
    SpeechPcm pcm;

    // Full volume reproduces the demo curve exactly, zero volume is the mid level
    speech_pcm_init(&pcm, 100, 0);
    for(int x = 0; x < 256; x++) CHECK(pcm.lut[x] == demo_curve((uint8_t)x));
    CHECK(speech_pcm_silence(&pcm) == demo_curve(128));
    speech_pcm_set_volume(&pcm, 0);
    for(int x = 0; x < 256; x++) CHECK(pcm.lut[x] == 127);
    speech_pcm_set_volume(&pcm, 50);
    CHECK(pcm.lut[0] < pcm.lut[128] && pcm.lut[128] < pcm.lut[255]);
    CHECK(pcm.lut[255] < demo_curve(255));

    // Identity mapping for the timing checks: volume 100, values chosen on the flat parts
    speech_pcm_set_volume(&pcm, 100);
    const uint8_t v[5] = {100, 115, 128, 140, 155};
    uint8_t want[5];
    for(int k = 0; k < 5; k++) want[k] = pcm.lut[v[k]];

    // delta 160 and no overhead: 20 us per value, one slot each
    speech_pcm_reset(&pcm);
    emitted_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 160, collect, NULL));
    CHECK(emitted_count == 5);
    for(int k = 0; k < 5; k++) CHECK(emitted[k] == want[k]);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 100 && pcm.slots == 5);

    // delta 162 rounds down to 20 us like the demo's integer division
    speech_pcm_reset(&pcm);
    emitted_count = 0;
    speech_pcm_push(&pcm, v, 162, collect, NULL);
    CHECK(emitted_count == 5);

    // a value shorter than a slot is skipped
    speech_pcm_reset(&pcm);
    emitted_count = 0;
    speech_pcm_push(&pcm, v, 4, collect, NULL);
    CHECK(emitted_count == 0);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 0);

    // with 5 us of overhead every value lasts 25 us: slots fall on 0,20,40,60,80,100,120
    speech_pcm_init(&pcm, 100, 5000);
    emitted_count = 0;
    speech_pcm_push(&pcm, v, 160, collect, NULL);
    CHECK(emitted_count == 7);
    const uint8_t order[7] = {0, 0, 1, 2, 3, 4, 4};
    for(int k = 0; k < 7; k++) CHECK(emitted[k] == want[order[k]]);

    // time keeps running across calls: the next call continues from 125 us
    emitted_count = 0;
    speech_pcm_push(&pcm, v, 160, collect, NULL);
    CHECK(emitted_count == 6);

    // abort propagates
    speech_pcm_reset(&pcm);
    emitted_count = 0;
    abort_at = 3;
    CHECK(!speech_pcm_push(&pcm, v, 160, collect, NULL));
    CHECK(emitted_count == 3);

    // Beyond the brief: delta edges, overhead, carry over many pushes, volume, refusal
    test_delta_zero(v, want);
    test_largest_delta(v, want);
    test_overhead(v, want);
    test_carry(0);
    test_carry(3300);
    test_volume(v);
    test_stop(v, want);

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
