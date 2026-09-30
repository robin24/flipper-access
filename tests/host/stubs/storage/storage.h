// The parts of storage.h that lib/momentum/settings.c uses, for its host test. On Momentum every
// /int path is a folder on the card, /ext/.int (storage_process_alias in storage_processing.c),
// so the test's fake card holds the settings file, and nothing can be read or written without it.
#pragma once
#include <furi.h>

#define RECORD_STORAGE          "storage"
#define STORAGE_INT_PATH_PREFIX "/int"
#define INT_PATH(path)          STORAGE_INT_PATH_PREFIX "/" path

typedef struct Storage Storage;

typedef enum {
    FSE_OK,
    FSE_NOT_READY,
    FSE_EXIST,
    FSE_NOT_EXIST,
    FSE_INVALID_PARAMETER,
    FSE_DENIED,
    FSE_INVALID_NAME,
    FSE_INTERNAL,
    FSE_NOT_IMPLEMENTED,
    FSE_ALREADY_OPEN,
} FS_Error;

FS_Error storage_sd_status(Storage* storage);
