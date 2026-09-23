#include <math.h>
#include <stdio.h>
#include <string.h>
#include "sam.h"
#include "sam_cases.h"

static unsigned long long n_values, sum_f, hash;

// The Text to SAM app's SetAUDIO curve, reproduced operation for operation
static uint32_t demo_curve(uint8_t x) {
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
    return (uint32_t)data;
}

static bool record(const uint8_t values[5], uint16_t delta, void* context) {
    (void)context;
    uint32_t f = delta / 8;
    for(int k = 0; k < 5; k++) {
        n_values++;
        sum_f += f;
        hash = (hash ^ ((unsigned long long)demo_curve(values[k]) * 131u + f)) *
               1099511628211ULL;
    }
    return true;
}

static unsigned abort_calls;
static bool abort_after_1000(const uint8_t values[5], uint16_t delta, void* context) {
    (void)values;
    (void)delta;
    (void)context;
    abort_calls++;
    return abort_calls < 1000;
}

static unsigned long long run_case(const SamCase* c) {
    n_values = 0;
    sum_f = 0;
    hash = 1469598103934665603ULL;
    SamVoice voice = {c->pitch, c->speed, c->mouth, c->throat};
    sam_speak(c->text, &voice, record, NULL);
    return hash;
}

int main(void) {
    int failures = 0;
    for(size_t i = 0; i < SAM_CASE_COUNT; i++) {
        run_case(&sam_cases[i]);
        printf("case %zu n=%llu sum_f=%llu hash=%016llx\n", i, n_values, sum_f, hash);
    }

    // Aborting stops rendering at the callback that said so
    SamVoice voice = SAM_VOICE_DEFAULT;
    abort_calls = 0;
    bool completed = sam_speak(sam_cases[0].text, &voice, abort_after_1000, NULL);
    if(completed || abort_calls != 1000) {
        printf("FAIL abort: completed=%d calls=%u\n", completed, abort_calls);
        failures++;
    }

    // An aborted call leaves no trace: the next call renders exactly as a fresh one
    unsigned long long fresh = run_case(&sam_cases[1]);
    abort_calls = 0;
    sam_speak(sam_cases[0].text, &voice, abort_after_1000, NULL);
    unsigned long long after_abort = run_case(&sam_cases[1]);
    if(fresh != after_abort) {
        printf("FAIL state: fresh=%016llx after_abort=%016llx\n", fresh, after_abort);
        failures++;
    }

    // Rejected inputs
    if(sam_speak("", &voice, record, NULL)) {
        printf("FAIL empty text accepted\n");
        failures++;
    }
    char too_long[SAM_MAX_INPUT + 2];
    memset(too_long, 'a', sizeof(too_long) - 1);
    too_long[sizeof(too_long) - 1] = '\0';
    if(sam_speak(too_long, &voice, record, NULL)) {
        printf("FAIL over long text accepted\n");
        failures++;
    }

    printf("port checks: %d failures\n", failures);
    return failures ? 1 : 0;
}
