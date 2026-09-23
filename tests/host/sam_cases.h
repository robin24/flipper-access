#pragma once

typedef struct {
    const char* text;
    unsigned char pitch;
    unsigned char speed;
    unsigned char mouth;
    unsigned char throat;
} SamCase;

static const SamCase sam_cases[] = {
    {"Hello Robin. This is your Flipper Zero speaking.", 64, 72, 128, 128},
    {"The quick brown fox jumps over the lazy dog.", 64, 72, 128, 128},
    {"Settings. Bluetooth, one of eleven.", 64, 72, 128, 128},
    {"N F C. Read. Saved. Extra actions.", 64, 72, 128, 128},
    {"Point the remote at I R port and press the button.", 64, 72, 128, 128},
    {"Hello Robin. This is your Flipper Zero speaking.", 64, 100, 128, 128},
    {"Hello Robin. This is your Flipper Zero speaking.", 48, 72, 128, 128},
    {"Hello Robin. This is your Flipper Zero speaking.", 64, 50, 150, 200},
    {"W", 64, 72, 128, 128},
    {"w", 64, 72, 128, 128},
    {"", 64, 72, 128, 128},
};

#define SAM_CASE_COUNT (sizeof(sam_cases) / sizeof(sam_cases[0]))
