#include <cstdio>
#include <cstring>
#include "stm32_sam.h"
#include <stm32wbxx_ll_tim.h>
#include "../sam_cases.h"

TIM_TypeDef tim16_stub;

static unsigned long long n_values, sum_f, hash;
static uint32_t pending_f;

extern "C" void furi_delay_us(uint32_t us) {
    pending_f = us;
}

void LL_TIM_OC_SetCompareCH1(TIM_TypeDef* t, uint32_t v) {
    (void)t;
    n_values++;
    sum_f += pending_f;
    hash = (hash ^ ((unsigned long long)v * 131u + pending_f)) * 1099511628211ULL;
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
