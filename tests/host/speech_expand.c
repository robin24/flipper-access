// Runs the pronunciation layer on every line of standard input and prints the expansion:
// the vocabulary generator uses it so the clips on the card match the words the device asks for.
#include <stdio.h>
#include <string.h>
#include "speech_text.h"

int main(void) {
    static char line[4096];
    static char out[SPEECH_TEXT_MAX];
    while(fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = '\0';
        speech_text_expand(line, out, sizeof(out));
        puts(out);
    }
    return 0;
}
