// The parts of furi.h that the desktop's slideshow view uses, for its host test,
// tests/host/test_desktop_slideshow.c, which also defines the functions.
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>

#define furi_assert(x) ((void)(x))

typedef struct FuriTimer FuriTimer;
typedef void (*FuriTimerCallback)(void* context);
typedef enum {
    FuriTimerTypeOnce,
    FuriTimerTypePeriodic,
} FuriTimerType;

FuriTimer* furi_timer_alloc(FuriTimerCallback callback, FuriTimerType type, void* context);
void furi_timer_free(FuriTimer* timer);
void furi_timer_start(FuriTimer* timer, uint32_t ticks);
void furi_timer_stop(FuriTimer* timer);
uint32_t furi_kernel_get_tick_frequency(void);
