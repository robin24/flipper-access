// The words the device looks up for each line of standard input, found as the speech engine
// finds them: the pronunciation layer's expansion, then speech_voice_next_word, each word with its
// clip folder, speech_voice_hash modulo the buckets. One output line per input line, the words as
// word/hh separated by spaces. Built by tools/run_host_tests.sh for tests/fbt/test_voice_parity.py.
#include <stdio.h>
#include <string.h>
#include "speech_text.h"
#include "speech_voice.h"

int main(void) {
    static char line[4096];
    static char out[SPEECH_TEXT_MAX];
    while(fgets(line, sizeof(line), stdin)) {
        line[strcspn(line, "\r\n")] = '\0';
        speech_text_expand(line, out, sizeof(out));
        size_t pos = 0;
        SpeechVoiceWord word;
        const char* sep = "";
        while(speech_voice_next_word(out, &pos, &word)) {
            if(!word.word[0]) continue;
            printf(
                "%s%s/%02x",
                sep,
                word.word,
                (unsigned)(speech_voice_hash(word.word) % SPEECH_VOICE_BUCKETS));
            sep = " ";
        }
        putchar('\n');
    }
    return 0;
}
