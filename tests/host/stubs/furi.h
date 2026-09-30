// The parts of furi.h that lib/momentum/settings.c uses, for the host test of the settings,
// tests/host/test_momentum_settings.c, which also defines the functions.
#pragma once
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#define COUNT_OF(x)            (sizeof(x) / sizeof((x)[0]))
#define CLAMP(x, upper, lower) ((x) > (upper) ? (upper) : ((x) < (lower) ? (lower) : (x)))

#define FURI_LOG_E(tag, ...) ((void)(tag))
#define FURI_LOG_W(tag, ...) ((void)(tag))
#define FURI_LOG_I(tag, ...) ((void)(tag))
#define FURI_LOG_D(tag, ...) ((void)(tag))

typedef struct FuriString FuriString;
FuriString* furi_string_alloc(void);
void furi_string_free(FuriString* string);
const char* furi_string_get_cstr(const FuriString* string);

void* furi_record_open(const char* name);
void furi_record_close(const char* name);

// strlcpy is in the C library on the Mac but not in every Linux one
size_t test_strlcpy(char* dst, const char* src, size_t size);
#define strlcpy test_strlcpy
