#include <stdio.h>
#include <string.h>
#include "speech_voice.h"

static int failures = 0;
static int checks = 0;
#define CHECK(cond)                                                     \
    do {                                                                \
        checks++;                                                       \
        if(!(cond)) {                                                   \
            failures++;                                                 \
            printf("FAIL line %d: %s\n", __LINE__, #cond);              \
        }                                                               \
    } while(0)

static void expect_word(const char* text, size_t* pos, const char* word, unsigned pause) {
    SpeechVoiceWord w;
    memset(&w, 0x55, sizeof(w));
    bool got = speech_voice_next_word(text, pos, &w);
    checks++;
    if(!got || strcmp(w.word, word) != 0 || w.pause_ms != pause) {
        failures++;
        printf("FAIL next_word(\"%s\") got %s \"%s\" %u, want \"%s\" %u\n", text,
               got ? "true" : "false", w.word, (unsigned)w.pause_ms, word, pause);
    }
}

static void test_words(void) {
    const char* text = "Sub gigahertz. Apps, one of eleven! U I D, zero four? end";
    size_t pos = 0;
    expect_word(text, &pos, "sub", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "gigahertz", SPEECH_VOICE_STOP_MS);
    expect_word(text, &pos, "apps", SPEECH_VOICE_COMMA_MS);
    expect_word(text, &pos, "one", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "of", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "eleven", SPEECH_VOICE_STOP_MS);
    expect_word(text, &pos, "u", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "i", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "d", SPEECH_VOICE_COMMA_MS);
    expect_word(text, &pos, "zero", SPEECH_VOICE_GAP_MS);
    expect_word(text, &pos, "four", SPEECH_VOICE_STOP_MS);
    expect_word(text, &pos, "end", SPEECH_VOICE_GAP_MS);
    SpeechVoiceWord w;
    CHECK(speech_voice_next_word(text, &pos, &w) == false);
    CHECK(speech_voice_next_word(text, &pos, &w) == false); // stays at the end

    // Punctuation on its own is a pause without a word; leading punctuation is stripped
    pos = 0;
    expect_word(". five", &pos, "", SPEECH_VOICE_STOP_MS);
    expect_word(". five", &pos, "five", SPEECH_VOICE_GAP_MS);
    pos = 0;
    expect_word(",, x", &pos, "", SPEECH_VOICE_COMMA_MS);
    pos = 0;
    expect_word("  spaced   out  ", &pos, "spaced", SPEECH_VOICE_GAP_MS);
    expect_word("  spaced   out  ", &pos, "out", SPEECH_VOICE_GAP_MS);
    CHECK(speech_voice_next_word("  spaced   out  ", &pos, &w) == false);
    pos = 0;
    CHECK(speech_voice_next_word("", &pos, &w) == false);
    pos = 0;
    CHECK(speech_voice_next_word("   ", &pos, &w) == false);

    // Semicolon and colon pause like a comma; a word is cut at 31 characters
    pos = 0;
    expect_word("a; b: c", &pos, "a", SPEECH_VOICE_COMMA_MS);
    expect_word("a; b: c", &pos, "b", SPEECH_VOICE_COMMA_MS);
    expect_word("a; b: c", &pos, "c", SPEECH_VOICE_GAP_MS);
    const char* longword = "abcdefghijklmnopqrstuvwxyzabcdefghij.";
    pos = 0;
    expect_word(longword, &pos, "abcdefghijklmnopqrstuvwxyzabcde", SPEECH_VOICE_STOP_MS);
    CHECK(pos == strlen(longword));
}

static void test_paths(void) {
    char out[SPEECH_VOICE_PATH_MAX];
    CHECK(speech_voice_path("settings", out, sizeof(out)) == strlen("/ext/sr/voice/s/settings.raw"));
    CHECK(strcmp(out, "/ext/sr/voice/s/settings.raw") == 0);
    CHECK(speech_voice_path("7", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voice/7/7.raw") == 0);
    CHECK(speech_voice_path("ay", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voice/a/ay.raw") == 0);
    CHECK(speech_voice_path("'odd", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voice/_/'odd.raw") == 0);
    CHECK(speech_voice_path("", out, sizeof(out)) == 0);
    CHECK(speech_voice_path("settings", out, 20) == 0);
    // The longest word fits the buffer
    const char* longest = "abcdefghijklmnopqrstuvwxyzabcde";
    CHECK(strlen(longest) == SPEECH_VOICE_WORD_MAX - 1);
    CHECK(speech_voice_path(longest, out, sizeof(out)) == strlen(out));
    CHECK(strlen(out) < SPEECH_VOICE_PATH_MAX);
}

static void test_missing(void) {
    SpeechVoiceState s;
    speech_voice_state_init(&s);
    CHECK(speech_voice_log_count(&s) == 0);
    CHECK(speech_voice_missing(&s, "bahncard") == true);
    CHECK(speech_voice_missing(&s, "bahncard") == false); // once per boot
    CHECK(speech_voice_missing(&s, "") == false);
    CHECK(s.missing_words == 1);
    CHECK(speech_voice_log_count(&s) == 1);
    CHECK(strcmp(speech_voice_log_word(&s, 0), "bahncard") == 0);
    speech_voice_log_clear(&s);
    CHECK(speech_voice_log_count(&s) == 0);
    CHECK(speech_voice_missing(&s, "bahncard") == false); // still remembered after the log

    // The log holds SPEECH_VOICE_LOG_MAX words per utterance; more are not recorded at all,
    // so a later utterance logs them
    char word[16];
    for(int i = 0; i < SPEECH_VOICE_LOG_MAX; i++) {
        snprintf(word, sizeof(word), "w%d", i);
        CHECK(speech_voice_missing(&s, word) == true);
    }
    CHECK(speech_voice_missing(&s, "overflow") == false);
    CHECK(speech_voice_log_count(&s) == SPEECH_VOICE_LOG_MAX);
    speech_voice_log_clear(&s);
    CHECK(speech_voice_missing(&s, "overflow") == true);
    speech_voice_log_clear(&s);

    // The set forgets the oldest word after SPEECH_VOICE_MISSING_SET newer ones
    speech_voice_state_init(&s);
    CHECK(speech_voice_missing(&s, "first") == true);
    speech_voice_log_clear(&s);
    for(int i = 0; i < SPEECH_VOICE_MISSING_SET; i++) {
        snprintf(word, sizeof(word), "n%d", i);
        CHECK(speech_voice_missing(&s, word) == true);
        speech_voice_log_clear(&s);
    }
    CHECK(speech_voice_missing(&s, "first") == true);
    CHECK(s.missing_words == SPEECH_VOICE_MISSING_SET + 2);
}

int main(void) {
    test_words();
    test_paths();
    test_missing();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
