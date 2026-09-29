/* The device's unpack of a tar, on the host: the firmware's own tar reader, lib/microtar, walked
 * the way tar_archive_unpack_to does it for `storage extract` and the updater
 * (lib/toolbox/tar/tar_archive.c, archive_extract_foreach_cb). A folder entry makes one folder,
 * whose parent must exist, as a mkdir on the card; a file is opened for writing in a folder that
 * must exist, since nothing makes the folders above it; any other entry, such as a PAX header, is
 * skipped with a warning. The walk stops at the first failure, as on the device.
 *
 *   tar_unpack ARCHIVE DEST
 *
 * Prints what it made and each skipped entry; exits 0 only when the whole archive was unpacked
 * and nothing was skipped. Built by tools/run_host_tests.sh for tests/fbt/test_voice_pack.py. */
#include "microtar.h"
#include "microtar-stdio.h"

#include <errno.h>
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>

typedef struct {
    const char* dest;
    unsigned folders;
    unsigned files;
    unsigned skipped;
} Unpack;

/* path_concat on the device: the destination, a slash, and the name without its slashes */
static void join(char* out, size_t size, const char* dest, const char* name) {
    while(*name == '/')
        name++;
    snprintf(out, size, "%s/%s", dest, name);
    size_t n = strlen(out);
    while(n > 0 && out[n - 1] == '/')
        out[--n] = '\0';
}

static int unpack_entry(mtar_t* tar, const mtar_header_t* h, void* arg) {
    Unpack* u = arg;
    char path[512];
    if(h->type == MTAR_TDIR) {
        if(strcmp(h->name, "/") == 0) return 0;
        join(path, sizeof(path), u->dest, h->name);
        if(mkdir(path, 0755) != 0 && errno != EEXIST) {
            printf("failed: folder %s: %s\n", h->name, strerror(errno));
            return -1;
        }
        u->folders++;
        return 0;
    }
    if(h->type != MTAR_TREG) {
        printf("skipped: %s, type %c\n", h->name, (char)h->type);
        u->skipped++;
        return 0;
    }
    join(path, sizeof(path), u->dest, h->name);
    FILE* f = fopen(path, "wb");
    if(!f) {
        printf("failed: file %s: %s\n", h->name, strerror(errno));
        return MTAR_EFAILURE;
    }
    char buf[512];
    int ok = 1;
    while(ok && !mtar_eof_data(tar)) {
        int n = mtar_read_data(tar, buf, sizeof(buf));
        ok = n > 0 && fwrite(buf, 1, (size_t)n, f) == (size_t)n;
    }
    fclose(f);
    if(!ok) {
        printf("failed: writing %s\n", h->name);
        return MTAR_EFAILURE;
    }
    u->files++;
    return 0;
}

int main(int argc, char** argv) {
    if(argc != 3) {
        fprintf(stderr, "usage: tar_unpack ARCHIVE DEST\n");
        return 2;
    }
    mtar_t tar;
    if(mtar_open(&tar, argv[1], "rb") != MTAR_ESUCCESS) {
        printf("failed: cannot open %s\n", argv[1]);
        return 1;
    }
    Unpack u = {.dest = argv[2]};
    int err = mtar_foreach(&tar, unpack_entry, &u);
    mtar_close(&tar);
    printf(
        "unpacked: %u folders, %u files, %u skipped%s\n",
        u.folders,
        u.files,
        u.skipped,
        err == MTAR_ESUCCESS ? "" : ", stopped early");
    return err == MTAR_ESUCCESS && u.skipped == 0 ? 0 : 1;
}
