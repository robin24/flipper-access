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

static void test_volume(void) {
    SpeechPcm pcm;
    const uint8_t v[5] = {100, 115, 128, 140, 155};

    // Volume 0: every entry is the silence value, so a push emits nothing but silence
    speech_pcm_init(&pcm, 0);
    uint8_t silence = speech_pcm_silence(&pcm);
    CHECK(silence == 127);
    bool all_silent = true;
    for(int x = 0; x < 256; x++) {
        if(pcm.lut[x] != silence) all_silent = false;
    }
    CHECK(all_silent);
    seq_count = 0;
    CHECK(speech_pcm_push_raw(&pcm, v, 5, 20000, collect_seq, NULL));
    CHECK(seq_count == 5);
    CHECK(run_is(0, 5, silence));

    // Volume 100 reproduces the demo curve, clips at both ends, and is what anything above
    // 100 is treated as
    speech_pcm_init(&pcm, 100);
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
    CHECK(speech_pcm_push_raw(&pcm, v, 5, 20000, collect_seq, NULL));
    speech_pcm_set_volume(&pcm, 50);
    CHECK(pcm.now_ns == 100000 && pcm.next_slot_ns == 100000 && pcm.slots == 5);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 100);
    seq_count = 0;
    CHECK(speech_pcm_push_raw(&pcm, v, 5, 20000, collect_seq, NULL));
    CHECK(seq_count == 5);
    for(int k = 0; k < 5; k++) CHECK(seq[k] == pcm.lut[v[k]]);
    CHECK(pcm.lut[v[4]] < full[v[4]]);
    CHECK(pcm.lut[v[0]] > full[v[0]]);

    // A reset starts the timing over and keeps the table
    speech_pcm_reset(&pcm);
    CHECK(pcm.slots == 0 && pcm.now_ns == 0 && pcm.next_slot_ns == 0);
    CHECK(pcm.subsamples == 0 && pcm.nominal_us == 0);
    CHECK(pcm.lut[v[0]] == full[v[0]] || pcm.lut[v[0]] > full[v[0]]);
}

// Recorded clips: every sample held for the same time, through the slot accumulator.
static void test_push_raw(void) {
    SpeechPcm pcm;
    static uint8_t samples[16000];
    for(size_t i = 0; i < sizeof(samples); i++) samples[i] = (uint8_t)(128 + (i % 7) * 3);

    // 16000 samples held 62.5 us each, a one second clip at 16 kHz: 50000 slots exactly, and
    // the nominal time is the whole second although a sample is not a whole microsecond
    speech_pcm_init(&pcm, 100);
    size_t n = 0;
    CHECK(speech_pcm_push_raw(&pcm, samples, 16000, 62500, count_only, &n));
    CHECK(n == 50000 && pcm.slots == 50000);
    CHECK(pcm.subsamples == 16000);
    CHECK(pcm.nominal_us == 1000000);
    CHECK(pcm.now_ns == 1000000000ull && pcm.next_slot_ns == 1000000000ull);

    // Duty bytes go through the loudness table, and sample k covers [62.5 k, 62.5 (k + 1)) us:
    // the marks at 0, 20, 40, 60 see sample 0, at 80, 100, 120 sample 1, at 140, 160, 180
    // sample 2; 187.5 us of nominal time floor to 187
    speech_pcm_init(&pcm, 100);
    seq_count = 0;
    const uint8_t few[3] = {100, 128, 155};
    CHECK(speech_pcm_push_raw(&pcm, few, 3, 62500, collect_seq, NULL));
    CHECK(seq_count == 10);
    CHECK(run_is(0, 4, pcm.lut[100]));
    CHECK(run_is(4, 3, pcm.lut[128]));
    CHECK(run_is(7, 3, pcm.lut[155]));
    CHECK(pcm.subsamples == 3 && pcm.nominal_us == 187);

    // A refusal stops the push where it happens: the emitter took its five marks (four of
    // sample 0, one of sample 1), slots agrees, and the stage sits inside sample 1, which was
    // entered but not completed, with the refused mark still pending
    speech_pcm_init(&pcm, 100);
    Limited five = {5, 0, 0};
    CHECK(!speech_pcm_push_raw(&pcm, samples, 16000, 62500, collect_limited, &five));
    CHECK(five.count == 5 && pcm.slots == 5);
    CHECK(five.last == pcm.lut[samples[1]]);
    CHECK(pcm.now_ns == 62500 && pcm.next_slot_ns == 100000);
    CHECK(pcm.subsamples == 2 && pcm.nominal_us == 62);
    // and after a reset the same push goes through whole
    speech_pcm_reset(&pcm);
    n = 0;
    CHECK(speech_pcm_push_raw(&pcm, samples, 16000, 62500, count_only, &n));
    CHECK(n == 50000 && pcm.nominal_us == 1000000);

    // Split over two calls the carry loses nothing, wherever the split falls: the half slot
    // and the half microsecond left by an odd number of samples carry into the second call
    for(size_t first = 1; first < 16000; first += 3571) {
        speech_pcm_init(&pcm, 100);
        size_t a = 0, b = 0;
        CHECK(speech_pcm_push_raw(&pcm, samples, first, 62500, count_only, &a));
        CHECK(speech_pcm_push_raw(&pcm, samples + first, 16000 - first, 62500, count_only, &b));
        CHECK(a + b == 50000 && pcm.slots == 50000);
        CHECK(pcm.subsamples == 16000 && pcm.nominal_us == 1000000);
    }

    // 512 byte chunks, as the worker reads the card: 32 ms and 1600 slots each
    speech_pcm_init(&pcm, 100);
    n = 0;
    bool chunks_accepted = true;
    for(size_t off = 0; off < 16000; off += 512) {
        size_t len = 16000 - off < 512 ? 16000 - off : 512;
        if(!speech_pcm_push_raw(&pcm, samples + off, len, 62500, count_only, &n)) {
            chunks_accepted = false;
        }
    }
    CHECK(chunks_accepted);
    CHECK(n == 50000 && pcm.nominal_us == 1000000 && pcm.subsamples == 16000);

    // Samples shorter than a slot: at 32000 Hz a sample is 31.25 us, so 16000 of them are half
    // a second and 25000 slots, every other sample never seen; at 8000 Hz 125 us, 100000 slots
    speech_pcm_init(&pcm, 100);
    n = 0;
    CHECK(speech_pcm_push_raw(&pcm, samples, 16000, 31250, count_only, &n));
    CHECK(n == 25000 && pcm.slots == 25000);
    CHECK(pcm.nominal_us == 500000 && pcm.subsamples == 16000);
    speech_pcm_init(&pcm, 100);
    n = 0;
    CHECK(speech_pcm_push_raw(&pcm, samples, 16000, 125000, count_only, &n));
    CHECK(n == 100000 && pcm.nominal_us == 2000000);

    // An odd rate carries its remainder too: 11025 Hz is 90702 ns per sample after the
    // engine's integer division, 1451232000 ns in all, ceil(1451232000 / 20000) slots
    speech_pcm_init(&pcm, 100);
    n = 0;
    CHECK(speech_pcm_push_raw(&pcm, samples, 16000, 90702, count_only, &n));
    uint64_t total_ns = 16000ull * 90702ull;
    CHECK(n == (total_ns + SPEECH_SLOT_NS - 1) / SPEECH_SLOT_NS);
    CHECK(pcm.nominal_us == total_ns / 1000);
    CHECK(pcm.now_ns == total_ns);

    // No samples: nothing happens and nothing is refused
    n = 0;
    CHECK(speech_pcm_push_raw(&pcm, samples, 0, 62500, count_only, &n));
    CHECK(n == 0 && pcm.now_ns == total_ns);

    // The table applies: at volume 0 a clip is all silence
    speech_pcm_init(&pcm, 0);
    seq_count = 0;
    CHECK(speech_pcm_push_raw(&pcm, few, 3, 62500, collect_seq, NULL));
    CHECK(seq_count == 10 && run_is(0, 10, speech_pcm_silence(&pcm)));
}

int main(void) {
    SpeechPcm pcm;

    // Full volume reproduces the demo curve exactly, zero volume is the mid level
    speech_pcm_init(&pcm, 100);
    for(int x = 0; x < 256; x++) CHECK(pcm.lut[x] == demo_curve((uint8_t)x));
    CHECK(speech_pcm_silence(&pcm) == demo_curve(128));
    speech_pcm_set_volume(&pcm, 0);
    for(int x = 0; x < 256; x++) CHECK(pcm.lut[x] == 127);
    speech_pcm_set_volume(&pcm, 50);
    CHECK(pcm.lut[0] < pcm.lut[128] && pcm.lut[128] < pcm.lut[255]);
    CHECK(pcm.lut[255] < demo_curve(255));

    test_volume();
    test_push_raw();

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
