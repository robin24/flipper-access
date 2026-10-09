// The icon of a slideshow, for the host test of the desktop's slideshow view. The firmware's
// members are const, set by slideshow_load; the test's stand-in sets them directly.
#pragma once
#include <stdint.h>

typedef struct {
    uint16_t width;
    uint16_t height;
    uint8_t frame_count;
    uint8_t frame_rate;
    const uint8_t* const* frames;
} Icon;
