#define _POSIX_C_SOURCE 200809L // fork, pipe and waitpid under -std=c11
// Host test of Momentum's settings file, lib/momentum/settings.c, compiled against the stand-in
// headers in tests/host/stubs. On Momentum /int is a folder on the card, so the fake card here
// holds the settings file: without the card nothing can be read or written. Each scenario runs in
// a child process of its own, which starts from the compiled defaults as a boot does.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#include <flipper_format/flipper_format.h>
#include <furi_hal.h>
#include <rgb_backlight.h>
#include "settings_i.h"

static int failures = 0;
static int checks = 0;
#define CHECK(cond)                                        \
    do {                                                   \
        checks++;                                          \
        if(!(cond)) {                                      \
            failures++;                                    \
            printf("FAIL line %d: %s\n", __LINE__, #cond); \
        }                                                  \
    } while(0)
#define CHECK_STR(actual, expected)                                                               \
    do {                                                                                          \
        checks++;                                                                                 \
        if(strcmp((actual), (expected)) != 0) {                                                   \
            failures++;                                                                           \
            printf("FAIL line %d: got \"%s\" expected \"%s\"\n", __LINE__, (actual), (expected)); \
        }                                                                                         \
    } while(0)

// The fake card and the settings file on it, one key and value per line
#define CARD_LINES 96
static bool card_mounted;
static bool card_has_file;
static struct {
    char key[40];
    char value[80];
} card_file[CARD_LINES];
static size_t card_lines;

static void card_set(const char* key, const char* value) {
    size_t i = 0;
    while(i < card_lines && strcmp(card_file[i].key, key) != 0)
        i++;
    if(i == card_lines) {
        if(card_lines == CARD_LINES) return;
        card_lines++;
    }
    snprintf(card_file[i].key, sizeof(card_file[i].key), "%s", key);
    snprintf(card_file[i].value, sizeof(card_file[i].value), "%s", value);
}

/** The value on the card for key, or "(none)" */
static const char* card_get(const char* key) {
    for(size_t i = 0; i < card_lines; i++)
        if(strcmp(card_file[i].key, key) == 0) return card_file[i].value;
    return "(none)";
}

/** A card holding a settings file whose values differ from the compiled defaults, as Robin's does */
static void card_insert_with_own_settings(void) {
    card_mounted = true;
    card_has_file = true;
    card_lines = 0;
    card_set("dark_mode", "true");
    card_set("lock_on_boot", "false");
    card_set("sr_volume", "10");
    card_set("sr_voice_set", "samantha");
}

// The stand-ins' functions: furi.h, furi_hal.h, rgb_backlight.h, storage.h and flipper_format.h
struct FuriString {
    char text[128];
};

FuriString* furi_string_alloc(void) {
    return calloc(1, sizeof(FuriString));
}

void furi_string_free(FuriString* string) {
    free(string);
}

const char* furi_string_get_cstr(const FuriString* string) {
    return string->text;
}

void* furi_record_open(const char* name) {
    return (void*)name;
}

void furi_record_close(const char* name) {
    (void)name;
}

size_t test_strlcpy(char* dst, const char* src, size_t size) {
    size_t length = strlen(src);
    if(size) {
        size_t n = length < size - 1 ? length : size - 1;
        memcpy(dst, src, n);
        dst[n] = '\0';
    }
    return length;
}

bool furi_hal_is_normal_boot(void) {
    return true;
}

void rgb_backlight_load_settings(bool enabled) {
    (void)enabled;
}

FS_Error storage_sd_status(Storage* storage) {
    (void)storage;
    return card_mounted ? FSE_OK : FSE_NOT_READY;
}

struct FlipperFormat {
    bool open;
};

FlipperFormat* flipper_format_file_alloc(Storage* storage) {
    (void)storage;
    return calloc(1, sizeof(FlipperFormat));
}

void flipper_format_free(FlipperFormat* flipper_format) {
    free(flipper_format);
}

bool flipper_format_file_open_existing(FlipperFormat* flipper_format, const char* path) {
    (void)path;
    flipper_format->open = card_mounted && card_has_file;
    return flipper_format->open;
}

/** Creates the file, or empties it, as opening for writing does */
bool flipper_format_file_open_always(FlipperFormat* flipper_format, const char* path) {
    (void)path;
    flipper_format->open = card_mounted;
    if(flipper_format->open) {
        card_has_file = true;
        card_lines = 0;
    }
    return flipper_format->open;
}

bool flipper_format_rewind(FlipperFormat* flipper_format) {
    return flipper_format->open;
}

static const char* read_value(FlipperFormat* flipper_format, const char* key) {
    if(!flipper_format->open) return NULL;
    const char* value = card_get(key);
    return strcmp(value, "(none)") == 0 ? NULL : value;
}

bool flipper_format_read_string(FlipperFormat* flipper_format, const char* key, FuriString* data) {
    const char* value = read_value(flipper_format, key);
    if(value) snprintf(data->text, sizeof(data->text), "%s", value);
    return value != NULL;
}

bool flipper_format_read_int32(
    FlipperFormat* flipper_format,
    const char* key,
    int32_t* data,
    const uint16_t data_size) {
    (void)data_size;
    const char* value = read_value(flipper_format, key);
    if(value) *data = (int32_t)strtol(value, NULL, 10);
    return value != NULL;
}

bool flipper_format_read_uint32(
    FlipperFormat* flipper_format,
    const char* key,
    uint32_t* data,
    const uint16_t data_size) {
    (void)data_size;
    const char* value = read_value(flipper_format, key);
    if(value) *data = (uint32_t)strtoul(value, NULL, 10);
    return value != NULL;
}

bool flipper_format_read_bool(
    FlipperFormat* flipper_format,
    const char* key,
    bool* data,
    const uint16_t data_size) {
    (void)data_size;
    const char* value = read_value(flipper_format, key);
    if(value) *data = strcmp(value, "true") == 0;
    return value != NULL;
}

bool flipper_format_write_string_cstr(
    FlipperFormat* flipper_format,
    const char* key,
    const char* data) {
    if(flipper_format->open) card_set(key, data);
    return flipper_format->open;
}

bool flipper_format_write_int32(
    FlipperFormat* flipper_format,
    const char* key,
    const int32_t* data,
    const uint16_t data_size) {
    (void)data_size;
    char value[16];
    snprintf(value, sizeof(value), "%ld", (long)*data);
    return flipper_format_write_string_cstr(flipper_format, key, value);
}

bool flipper_format_write_uint32(
    FlipperFormat* flipper_format,
    const char* key,
    const uint32_t* data,
    const uint16_t data_size) {
    (void)data_size;
    char value[16];
    snprintf(value, sizeof(value), "%lu", (unsigned long)*data);
    return flipper_format_write_string_cstr(flipper_format, key, value);
}

bool flipper_format_write_bool(
    FlipperFormat* flipper_format,
    const char* key,
    const bool* data,
    const uint16_t data_size) {
    (void)data_size;
    return flipper_format_write_string_cstr(flipper_format, key, *data ? "true" : "false");
}

/** A boot without a card, then a card goes in. Until flipper_mount_callback has loaded the
 *  settings from it, RAM holds the compiled defaults, and a save in that moment, a screen reader
 *  chord, must not write them over the settings on the card. */
static void test_card_inserted_after_boot(void) {
    card_mounted = false;
    momentum_settings_load(); // any load without a card: it reads nothing and must not count
    CHECK(momentum_settings.sr_volume == 80);
    momentum_settings.sr_volume = 90; // Back and Right, silent without the card
    momentum_settings_save(); // nowhere to write

    card_insert_with_own_settings();
    momentum_settings.sr_volume = 100; // Back and Right again, as the card goes in
    momentum_settings_save();
    CHECK_STR(card_get("dark_mode"), "true");
    CHECK_STR(card_get("lock_on_boot"), "false");
    CHECK_STR(card_get("sr_volume"), "10");
    CHECK_STR(card_get("sr_voice_set"), "samantha");

    momentum_settings_load(); // flipper_mount_callback
    CHECK(momentum_settings.dark_mode);
    CHECK(!momentum_settings.lock_on_boot);
    CHECK(momentum_settings.sr_volume == 10);
    CHECK_STR(momentum_settings.sr_voice_set, "samantha");
}

/** A boot with the card: the settings are loaded from it, and a change is saved to it. */
static void test_boot_with_card(void) {
    card_insert_with_own_settings();
    momentum_settings_load();
    CHECK(momentum_settings.sr_volume == 10);
    momentum_settings.sr_volume = 20;
    momentum_settings_save();
    CHECK_STR(card_get("sr_volume"), "20");
    CHECK_STR(card_get("dark_mode"), "true");
    CHECK_STR(card_get("sr_voice_set"), "samantha");
}

/** A card with no settings file yet, a new one: the defaults stand, and the first change makes
 *  the file. */
static void test_card_without_settings(void) {
    card_mounted = true;
    card_has_file = false;
    card_lines = 0;
    momentum_settings_load();
    CHECK(momentum_settings.sr_volume == 80);
    momentum_settings.sr_volume = 40;
    momentum_settings_save();
    CHECK(card_has_file);
    CHECK_STR(card_get("sr_volume"), "40");
    CHECK_STR(card_get("dark_mode"), "false");
}

/** The card taken out while the device runs, and a card put in, here one with its own volume.
 *  Until flipper_mount_callback has loaded that card's settings, a save in that moment, a screen
 *  reader chord, must not write the settings of the card before, still in RAM, over them. */
static void test_card_changed_while_running(void) {
    card_insert_with_own_settings();
    momentum_settings_load(); // the boot
    CHECK(momentum_settings.sr_volume == 10);

    card_mounted = false;
    momentum_settings_card_removed(); // flipper_mount_callback, on the unmount
    momentum_settings_save(); // nowhere to write

    card_insert_with_own_settings();
    card_set("sr_volume", "50");
    momentum_settings.sr_volume = 20; // Back and Left as the card goes in
    momentum_settings_save();
    CHECK_STR(card_get("sr_volume"), "50");
    CHECK_STR(card_get("dark_mode"), "true");

    momentum_settings_load(); // flipper_mount_callback, on the mount
    CHECK(momentum_settings.sr_volume == 50);
    momentum_settings.sr_volume = 60;
    momentum_settings_save();
    CHECK_STR(card_get("sr_volume"), "60");
}

/** Runs one scenario in a child process, which starts from the compiled defaults, and adds its
 *  counts, which the child writes to a pipe, to this process's. */
static void run(void (*test)(void)) {
    int pipe_fds[2];
    if(pipe(pipe_fds) != 0) {
        perror("pipe");
        exit(1);
    }
    fflush(stdout);
    pid_t child = fork();
    if(child < 0) {
        perror("fork");
        exit(1);
    }
    if(child == 0) {
        close(pipe_fds[0]);
        checks = 0; // the child's own counts, not the ones it inherited
        failures = 0;
        test();
        int counts[2] = {checks, failures};
        fflush(stdout);
        _exit(write(pipe_fds[1], counts, sizeof(counts)) == sizeof(counts) ? 0 : 1);
    }
    close(pipe_fds[1]);
    int counts[2] = {0, 0};
    ssize_t got = read(pipe_fds[0], counts, sizeof(counts));
    close(pipe_fds[0]);
    int status = 0;
    waitpid(child, &status, 0);
    if(got != sizeof(counts) || !WIFEXITED(status) || WEXITSTATUS(status) != 0) {
        printf("FAIL: a scenario ended without its counts\n");
        counts[0]++;
        counts[1]++;
    }
    checks += counts[0];
    failures += counts[1];
}

int main(void) {
    run(test_card_inserted_after_boot);
    run(test_boot_with_card);
    run(test_card_without_settings);
    run(test_card_changed_while_running);
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
