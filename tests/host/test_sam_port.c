#include <stdio.h>
#include <string.h>
#include "sam.h"
#include "sam_cases.h"

static unsigned long long n_values, sum_f, hash;
static size_t consumed;

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
    sam_speak(c->text, &voice, record, NULL, &consumed);
    return hash;
}

// Hard cases at the maximum length: English, letters separated by spaces, and a random text of
// dense symbols whose phoneme list overflows (it made the original loop forever)
static const char hard_english[] =
    "The Flipper Zero screen reader speaks every menu, every file name and every message "
    "on the screen, so that people who cannot see the display can still use the device on "
    "their own. This sentence is long on purpose, so it fills the reciter to the brim.";
static const char hard_symbols[] =
    "!GxP>~C#)hC Kf . ^h \325e ^}b \365S_b' %'r HmoBR xk0' #r-B+EBc.X!P.2mxe6m2OB\351T'2x"
    ">*PhCLeHDh.@NX 9VHpC\246+ p\2613T%e R}\\S `_dV `3bP)\" :^LgufUr9^HAh .S `K\257[lSjam"
    "A \"w ~&N+yVuP\247Z3-UL:aOHdl Z9|{X_:lmR[&OJbUYf*NW Y\\2l{%3'$. l\"t!J\?d-_H mgQo%D{"
    "&J-\"o41\361\\B(d ,Ew yi\262@   R";
static char hard_spaced_letters[SAM_MAX_INPUT + 1]; // "A B C ...", filled in main
_Static_assert(sizeof(hard_english) - 1 == SAM_MAX_INPUT, "hard_english is SAM_MAX_INPUT long");
_Static_assert(sizeof(hard_symbols) - 1 == SAM_MAX_INPUT, "hard_symbols is SAM_MAX_INPUT long");

int main(void) {
    int failures = 0;
    unsigned long long case_hash[SAM_CASE_COUNT];
    for(size_t i = 0; i < SAM_CASE_COUNT; i++) {
        case_hash[i] = run_case(&sam_cases[i]);
        printf("case %zu n=%llu sum_f=%llu hash=%016llx\n", i, n_values, sum_f, hash);
        if(consumed != strlen(sam_cases[i].text)) {
            printf(
                "FAIL case %zu consumed %zu of %zu\n", i, consumed, strlen(sam_cases[i].text));
            failures++;
        }
    }

    // Aborting stops rendering at the callback that said so, and leaves no trace: the next call
    // renders exactly as it did in the case loop above
    SamVoice voice = SAM_VOICE_DEFAULT;
    static const unsigned abort_points[] = {10, 500, 5000};
    for(size_t i = 0; i < sizeof(abort_points) / sizeof(abort_points[0]); i++) {
        abort_point = abort_points[i];
        abort_calls = 0;
        bool completed = sam_speak(sam_cases[0].text, &voice, abort_at_point, NULL, NULL);
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

    // The reciter's phoneme string holds 120 characters: a longer text is rendered up to a word
    // boundary, and a second call renders the rest
    static const char overflow_text[] =
        "The quick brown fox jumps over the lazy dog and keeps running across the wide green "
        "field until night falls on the quiet town";
    size_t total = strlen(overflow_text);
    size_t first = 0;
    n_values = 0;
    bool first_ok = sam_speak(overflow_text, &voice, record, NULL, &first);
    unsigned long long first_values = n_values;
    if(!first_ok || first == 0 || first >= total || overflow_text[first - 1] != ' ' ||
       first_values == 0) {
        printf(
            "FAIL reciter overflow, first call: ok=%d consumed=%zu of %zu values=%llu\n",
            first_ok,
            first,
            total,
            first_values);
        failures++;
    } else {
        size_t rest = 0;
        n_values = 0;
        bool rest_ok = sam_speak(overflow_text + first, &voice, record, NULL, &rest);
        if(!rest_ok || rest != total - first || n_values == 0) {
            printf(
                "FAIL reciter overflow, second call: ok=%d consumed=%zu of %zu values=%llu\n",
                rest_ok,
                rest,
                total - first,
                n_values);
            failures++;
        }
    }

    // Texts the original synthesizer never returns from, or overruns its tables or output arrays
    // on; the port must finish and produce sound
    for(size_t i = 0; i < SAM_MAX_INPUT; i++) {
        hard_spaced_letters[i] = (i % 2) ? ' ' : (char)('A' + (i / 2) % 26);
    }
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
        hard_english,
        hard_spaced_letters,
        hard_symbols,
    };
    for(size_t i = 0; i < sizeof(hard_cases) / sizeof(hard_cases[0]); i++) {
        n_values = 0;
        bool ok = sam_speak(hard_cases[i], &voice, record, NULL, NULL);
        if(!ok || n_values == 0) {
            printf("FAIL hard case %zu: ok=%d values=%llu\n", i, ok, n_values);
            failures++;
        }
    }

    // Rejected inputs, which report nothing consumed
    size_t rejected = 12345;
    if(sam_speak("", &voice, record, NULL, &rejected) || rejected != 0) {
        printf("FAIL empty text accepted or consumed=%zu\n", rejected);
        failures++;
    }
    char too_long[SAM_MAX_INPUT + 2];
    memset(too_long, 'a', sizeof(too_long) - 1);
    too_long[sizeof(too_long) - 1] = '\0';
    rejected = 12345;
    if(sam_speak(too_long, &voice, record, NULL, &rejected) || rejected != 0) {
        printf("FAIL over long text accepted or consumed=%zu\n", rejected);
        failures++;
    }

    printf("port checks: %d failures\n", failures);
    return failures ? 1 : 0;
}
