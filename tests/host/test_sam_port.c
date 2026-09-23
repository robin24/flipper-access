#include <stdio.h>
#include <string.h>
#include "sam.h"
#include "sam_cases.h"

static unsigned long long n_values, sum_f, hash;

static bool record(const uint8_t values[5], uint16_t delta, void* context) {
    (void)context;
    uint32_t f = delta / 8;
    for(int k = 0; k < 5; k++) {
        n_values++;
        sum_f += f;
        hash = (hash ^ ((unsigned long long)values[k] * 131u + f)) * 1099511628211ULL;
    }
    return true;
}

static unsigned abort_calls;
static unsigned abort_point;
static bool abort_at_point(const uint8_t values[5], uint16_t delta, void* context) {
    (void)values;
    (void)delta;
    (void)context;
    abort_calls++;
    return abort_calls < abort_point;
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
    unsigned long long case_hash[SAM_CASE_COUNT];
    for(size_t i = 0; i < SAM_CASE_COUNT; i++) {
        case_hash[i] = run_case(&sam_cases[i]);
        printf("case %zu n=%llu sum_f=%llu hash=%016llx\n", i, n_values, sum_f, hash);
    }

    // Aborting stops rendering at the callback that said so, and leaves no trace: the next call
    // renders exactly as it did in the case loop above
    SamVoice voice = SAM_VOICE_DEFAULT;
    static const unsigned abort_points[] = {10, 500, 5000};
    for(size_t i = 0; i < sizeof(abort_points) / sizeof(abort_points[0]); i++) {
        abort_point = abort_points[i];
        abort_calls = 0;
        bool completed = sam_speak(sam_cases[0].text, &voice, abort_at_point, NULL);
        if(completed || abort_calls != abort_point) {
            printf(
                "FAIL abort at %u: completed=%d calls=%u\n", abort_point, completed, abort_calls);
            failures++;
        }
        unsigned long long after_abort = run_case(&sam_cases[1]);
        if(after_abort != case_hash[1]) {
            printf(
                "FAIL state after abort at %u: expected=%016llx got=%016llx\n",
                abort_point,
                case_hash[1],
                after_abort);
            failures++;
        }
    }

    // Texts the original synthesizer never returns from, or overruns its tables or output arrays
    // on; the port must finish and produce sound
    static const char* const hard_cases[] = {
        "UUUUUUUUU.",
        "OOOOOOOOOOOOOOOOOOO.",
        "XXXXXXXXXXXXXXXXXXX.",
        "ANTIDISESTABLISHMENTARIANISM.",
        "SUPERCALIFRAGILISTICEXPIALIDOCIOUS.",
        "READ",
        "CAT",
        "IT IS LATE",
        "SAVED. READ",
    };
    for(size_t i = 0; i < sizeof(hard_cases) / sizeof(hard_cases[0]); i++) {
        n_values = 0;
        bool ok = sam_speak(hard_cases[i], &voice, record, NULL);
        if(!ok || n_values == 0) {
            printf("FAIL hard case %zu: ok=%d values=%llu\n", i, ok, n_values);
            failures++;
        }
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
