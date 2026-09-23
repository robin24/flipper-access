#include <cstdio>
#include <cstring>
#include <math.h> // the shim next to this file: lroundf, and tanhf renamed to sam_ref_tanhf
#include "stm32_sam.h"
#include <stm32wbxx_ll_tim.h>
#include "../sam_cases.h"

TIM_TypeDef tim16_stub;

static unsigned long long n_values, sum_f, hash;
static uint32_t pending_f;
static float last_curve_input;

extern "C" void furi_delay_us(uint32_t us) {
    pending_f = us;
}

// The original's SetAUDIO hands (raw / 255 - 0.5) * 4 to tanhf before it writes the timer; the
// shim routes that call here, so the raw value can be recovered from the argument
extern "C" float sam_ref_tanhf(float value) {
    last_curve_input = value;
    return 0.0f;
}

void LL_TIM_OC_SetCompareCH1(TIM_TypeDef* t, uint32_t v) {
    (void)t;
    (void)v;
    unsigned x = (unsigned)lroundf((last_curve_input / 4.0f + 0.5f) * 255.0f);
    n_values++;
    sum_f += pending_f;
    hash = (hash ^ ((unsigned long long)x * 131u + pending_f)) * 1099511628211ULL;
    pending_f = 0;
}

int main() {
    for(size_t i = 0; i < SAM_CASE_COUNT; i++) {
        const SamCase* c = &sam_cases[i];
        char buf[256];
        memset(buf, 0, sizeof(buf));
        strncpy(buf, c->text, sizeof(buf) - 1);
        n_values = 0;
        sum_f = 0;
        hash = 1469598103934665603ULL;
        STM32SAM voice; // a fresh instance per case: same resets as one sam_speak call
        voice.begin();
        voice.setVoice(c->pitch, c->speed, c->mouth, c->throat);
        voice.say(buf);
        printf("case %zu n=%llu sum_f=%llu hash=%016llx\n", i, n_values, sum_f, hash);
    }
    return 0;
}
