// The parts of flipper_format.h that lib/momentum/settings.c uses, for its host test, which keeps
// the file as key and value lines on its fake card.
#pragma once
#include <furi.h>
#include <storage/storage.h>

typedef struct FlipperFormat FlipperFormat;

FlipperFormat* flipper_format_file_alloc(Storage* storage);
void flipper_format_free(FlipperFormat* flipper_format);
bool flipper_format_file_open_existing(FlipperFormat* flipper_format, const char* path);
bool flipper_format_file_open_always(FlipperFormat* flipper_format, const char* path);
bool flipper_format_rewind(FlipperFormat* flipper_format);

bool flipper_format_read_string(FlipperFormat* flipper_format, const char* key, FuriString* data);
bool flipper_format_read_int32(
    FlipperFormat* flipper_format,
    const char* key,
    int32_t* data,
    const uint16_t data_size);
bool flipper_format_read_uint32(
    FlipperFormat* flipper_format,
    const char* key,
    uint32_t* data,
    const uint16_t data_size);
bool flipper_format_read_bool(
    FlipperFormat* flipper_format,
    const char* key,
    bool* data,
    const uint16_t data_size);

bool flipper_format_write_string_cstr(
    FlipperFormat* flipper_format,
    const char* key,
    const char* data);
bool flipper_format_write_int32(
    FlipperFormat* flipper_format,
    const char* key,
    const int32_t* data,
    const uint16_t data_size);
bool flipper_format_write_uint32(
    FlipperFormat* flipper_format,
    const char* key,
    const uint32_t* data,
    const uint16_t data_size);
bool flipper_format_write_bool(
    FlipperFormat* flipper_format,
    const char* key,
    const bool* data,
    const uint16_t data_size);
