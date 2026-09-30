// The type from furi_hal_version.h that lib/momentum/settings.h uses, for its host test
#pragma once
#include <furi.h>

typedef enum {
    FuriHalVersionColorUnknown = 0x00,
    FuriHalVersionColorBlack = 0x01,
    FuriHalVersionColorWhite = 0x02,
    FuriHalVersionColorTransparent = 0x03,
    FuriHalVersionColorCount,
} FuriHalVersionColor;
