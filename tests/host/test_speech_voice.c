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

    // Apostrophes are left out of the clip name; the pause still comes from the last character
    const char* contractions = "Don't do it, it's fine. rock'n'roll' '";
    pos = 0;
    expect_word(contractions, &pos, "dont", SPEECH_VOICE_GAP_MS);
    expect_word(contractions, &pos, "do", SPEECH_VOICE_GAP_MS);
    expect_word(contractions, &pos, "it", SPEECH_VOICE_COMMA_MS);
    expect_word(contractions, &pos, "its", SPEECH_VOICE_GAP_MS);
    expect_word(contractions, &pos, "fine", SPEECH_VOICE_STOP_MS);
    expect_word(contractions, &pos, "rocknroll", SPEECH_VOICE_GAP_MS);
    expect_word(contractions, &pos, "", SPEECH_VOICE_GAP_MS); // an apostrophe alone is no word
    CHECK(speech_voice_next_word(contractions, &pos, &w) == false);
    // The cut counts the characters kept, not the apostrophes left out
    pos = 0;
    expect_word("a'bcdefghijklmnopqrstuvwxyzabcdefgh", &pos, "abcdefghijklmnopqrstuvwxyzabcde",
                SPEECH_VOICE_GAP_MS);
}

// Reference FNV-1a 32 bit, written independently of the module under test
static uint32_t ref_hash(const char* word) {
    uint32_t h = 2166136261u;
    for(const unsigned char* p = (const unsigned char*)word; *p; p++) {
        h ^= *p;
        h *= 16777619u;
    }
    return h;
}

static void expect_path(const char* word) {
    char out[SPEECH_VOICE_PATH_MAX];
    char want[SPEECH_VOICE_PATH_MAX + 16];
    snprintf(want, sizeof(want), "/ext/sr/voice/%02x/%s.raw",
             (unsigned)(ref_hash(word) % SPEECH_VOICE_BUCKETS), word);
    size_t n = speech_voice_path(word, out, sizeof(out));
    checks++;
    if(n != strlen(want) || strcmp(out, want) != 0) {
        failures++;
        printf("FAIL path(\"%s\") got %zu \"%s\", want \"%s\"\n", word, n, n ? out : "", want);
    }
}

static void test_paths(void) {
    char out[SPEECH_VOICE_PATH_MAX];
    // Pinned: the generator on the computer must put these words in the same folders
    CHECK(speech_voice_hash("settings") == 0x68067b08u);
    CHECK(speech_voice_path("settings", out, sizeof(out)) == strlen("/ext/sr/voice/08/settings.raw"));
    CHECK(strcmp(out, "/ext/sr/voice/08/settings.raw") == 0);
    CHECK(speech_voice_path("7", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voice/36/7.raw") == 0);
    CHECK(speech_voice_path("ay", out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voice/0f/ay.raw") == 0);
    SpeechVoiceWord w;
    size_t pos = 0;
    CHECK(speech_voice_next_word("don't", &pos, &w) == true);
    CHECK(strcmp(w.word, "dont") == 0);
    CHECK(speech_voice_path(w.word, out, sizeof(out)) > 0);
    CHECK(strcmp(out, "/ext/sr/voice/0e/dont.raw") == 0);
    CHECK(speech_voice_hash("") == 2166136261u);
    CHECK(speech_voice_path("", out, sizeof(out)) == 0);
    CHECK(speech_voice_path("settings", out, 20) == 0);

    // Against the reference: the module's hash and the two hex digit folder for many words
    const char* words[] = {"settings", "sub", "gigahertz", "home", "screen", "'odd", "b", "0",
                           "zebrafish", "moonbeam", "systems", "types", "cycles", "its"};
    for(size_t i = 0; i < sizeof(words) / sizeof(words[0]); i++) {
        CHECK(speech_voice_hash(words[i]) == ref_hash(words[i]));
        expect_path(words[i]);
    }
    char word[16];
    bool used[SPEECH_VOICE_BUCKETS] = {false};
    for(int i = 0; i < 2000; i++) {
        snprintf(word, sizeof(word), "w%d", i);
        CHECK(speech_voice_hash(word) == ref_hash(word));
        expect_path(word);
        used[ref_hash(word) % SPEECH_VOICE_BUCKETS] = true;
    }
    int buckets = 0;
    for(int i = 0; i < SPEECH_VOICE_BUCKETS; i++)
        buckets += used[i];
    CHECK(buckets == SPEECH_VOICE_BUCKETS); // the words spread over every folder

    // The longest word fits the buffer
    const char* longest = "abcdefghijklmnopqrstuvwxyzabcde";
    CHECK(strlen(longest) == SPEECH_VOICE_WORD_MAX - 1);
    CHECK(speech_voice_path(longest, out, sizeof(out)) == strlen(out));
    CHECK(strlen(out) < SPEECH_VOICE_PATH_MAX);
    expect_path(longest);
}

static void expect_letter(char c, const char* want) {
    char out[3] = {'x', 'x', 'x'};
    bool got = speech_voice_letter_clip(c, out);
    checks++;
    if(want ? (!got || strcmp(out, want) != 0) : got) {
        failures++;
        printf("FAIL letter_clip(0x%02x) got %s \"%.3s\", want %s\n", (unsigned)(unsigned char)c,
               got ? "true" : "false", got ? out : "", want ? want : "false");
    }
}

static void test_letters(void) {
    // The clips that spell a missing word: a by its name, so that it is not the article
    expect_letter('a', "ay");
    expect_letter('b', "b");
    expect_letter('z', "z");
    expect_letter('0', "0");
    expect_letter('7', "7");
    expect_letter('-', NULL);
    expect_letter('A', NULL); // clip names are lower case
    expect_letter('\'', NULL);
    // Every character value: b to z and 0 to 9 are their own clip, anything else is skipped
    for(int i = 0; i < 256; i++) {
        char c = (char)i;
        if(c == 'a') continue;
        char want[2] = {c, '\0'};
        bool named = (c >= 'b' && c <= 'z') || (c >= '0' && c <= '9');
        expect_letter(c, named ? want : NULL);
    }
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
    test_letters();
    test_missing();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
