// The type from furi_hal_serial_types.h that lib/momentum/settings.h uses, for its host test
#pragma once
#include <furi.h>

typedef enum {
    FuriHalSerialIdUsart,
    FuriHalSerialIdLpuart,
    FuriHalSerialIdMax,
} FuriHalSerialId;
