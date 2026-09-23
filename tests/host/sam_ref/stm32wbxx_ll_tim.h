#pragma once
#include <stdint.h>

typedef struct {
    uint32_t Prescaler, CounterMode, Autoreload, ClockDivision, RepetitionCounter;
} LL_TIM_InitTypeDef;

typedef struct {
    uint32_t OCMode, OCState, OCNState, CompareValue, OCPolarity, OCNPolarity, OCIdleState,
        OCNIdleState;
} LL_TIM_OC_InitTypeDef;

typedef struct {
    int unused;
} TIM_TypeDef;

extern TIM_TypeDef tim16_stub;
#define TIM16 (&tim16_stub)
#define LL_TIM_CHANNEL_CH1    1u
#define LL_TIM_OCMODE_PWM1    6u
#define LL_TIM_OCSTATE_ENABLE 1u

static inline int LL_TIM_Init(TIM_TypeDef* t, LL_TIM_InitTypeDef* i) {
    (void)t;
    (void)i;
    return 0;
}
static inline int LL_TIM_OC_Init(TIM_TypeDef* t, uint32_t c, LL_TIM_OC_InitTypeDef* i) {
    (void)t;
    (void)c;
    (void)i;
    return 0;
}
static inline void LL_TIM_EnableAllOutputs(TIM_TypeDef* t) {
    (void)t;
}
static inline void LL_TIM_EnableCounter(TIM_TypeDef* t) {
    (void)t;
}
void LL_TIM_OC_SetCompareCH1(TIM_TypeDef* t, uint32_t v);
