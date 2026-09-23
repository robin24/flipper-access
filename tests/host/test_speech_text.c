#include <stdio.h>
#include <string.h>
#include "speech_text.h"

static int failures = 0;
static int checks = 0;

static void expect(const char* in, const char* want) {
    char out[SPEECH_TEXT_MAX];
    speech_text_expand(in, out, sizeof(out));
    checks++;
    if(strcmp(out, want) != 0) {
        failures++;
        printf("FAIL expand(\"%s\")\n  got  \"%s\"\n  want \"%s\"\n", in, out, want);
    }
}

#define CHECK(cond)                                                            \
    do {                                                                       \
        checks++;                                                              \
        if(!(cond)) {                                                          \
            failures++;                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);            \
        }                                                                      \
    } while(0)

static void test_words_and_numbers(void) {
    expect("Settings. Bluetooth, 1 of 11", "Settings. Bluetooth, one of eleven");
    expect("125 kHz RFID", "one hundred twenty five kilohertz R F I D");
    expect("433.92 MHz", "four hundred thirty three point nine two megahertz");
    expect("Mood: Happy. Level: 1. 18/100", "Mood, Happy. Level, one. eighteen slash one hundred");
    expect("Battery: 87%", "Battery, eighty seven percent");
    expect("2026", "two thousand twenty six");
    expect("1234567", "one two three four five six seven");
    expect("04 A2 FF", "zero four ay 2 F F");
    expect("12:34", "twelve thirty four");
    expect("100", "one hundred");
    expect("105", "one hundred five");
    expect("1000", "one thousand");
    expect("0", "zero");
}

static void test_acronyms_and_terms(void) {
    expect("NFC", "N F C");
    expect("Sub-GHz", "sub gigahertz");
    expect("OK", "okay");
    expect("U2F", "U 2 F");
    expect("GPIO", "G P I O");
    expect("ON", "ON");
    expect("Read RAW", "Read RAW");
    expect("iButton", "eye button");
    expect("Wrong PIN!", "Wrong pin!");
    expect("Point the remote at IR port and press the button", "Point the remote at I R port and press the button");
    expect("125kHz", "one hundred twenty five kilohertz");
    expect("Text to SAM", "Text to SAM");
    expect("MNTM", "momentum");
    expect("A", "ay");
    // Rule 8: pieces of at most 20 characters. The word has 34 letters, so the first piece is
    // its first 20 ("Supercalifragilistic") and the second the remaining 14.
    expect("Supercalifragilisticexpialidocious", "Supercalifragilistic expialidocious");
}

static void test_punctuation(void) {
    expect("buttons: left Retry, right More", "buttons, left Retry, right More");
    expect("key.sub", "key dot sub");
    expect("Don't move", "Don't move");
    expect("Home screen", "Home screen");
    expect("Hold card next to Flipper's back", "Hold card next to Flipper's back");
    expect("some_file_name", "some file name");
    expect("caf\xc3\xa9 au lait", "caf au lait");
    expect("  spaced   out  ", "spaced out");
    expect("", "");
    expect("a (b) [c] <d> |e| \"f\"", "a b c d e f");
}

static void test_single_characters(void) {
    expect("w", "W");
    expect("5", "five");
    expect(".", "dot");
    expect(",", "comma");
    expect(" ", "space");
    expect("_", "underscore");
    expect("space", "space");
    expect("deleted", "deleted");
}

static void test_chunks(void) {
    char chunk[SPEECH_CHUNK_MAX + 1];
    size_t pos = 0;
    const char* one = "Hello world";
    CHECK(speech_text_next_chunk(one, &pos, chunk, sizeof(chunk)) == 11);
    CHECK(strcmp(chunk, "Hello world") == 0);
    CHECK(speech_text_next_chunk(one, &pos, chunk, sizeof(chunk)) == 0);

    const char* three =
        "Sentence number one has some words in it. "
        "Sentence number two has some more words in it. "
        "Sentence number three is the last one.";
    pos = 0;
    size_t n = speech_text_next_chunk(three, &pos, chunk, sizeof(chunk));
    CHECK(n == 41);
    CHECK(strcmp(chunk, "Sentence number one has some words in it.") == 0);
    n = speech_text_next_chunk(three, &pos, chunk, sizeof(chunk));
    CHECK(n == 46);
    CHECK(strcmp(chunk, "Sentence number two has some more words in it.") == 0);
    n = speech_text_next_chunk(three, &pos, chunk, sizeof(chunk));
    CHECK(n == 38);
    CHECK(strcmp(chunk, "Sentence number three is the last one.") == 0);
    CHECK(speech_text_next_chunk(three, &pos, chunk, sizeof(chunk)) == 0);

    char words[151];
    words[0] = '\0';
    for(int i = 0; i < 30; i++) strcat(words, i ? " word" : "word");
    pos = 0;
    n = speech_text_next_chunk(words, &pos, chunk, sizeof(chunk));
    CHECK(n == 79);
    CHECK(chunk[78] == 'd' && chunk[79] == '\0');
    n = speech_text_next_chunk(words, &pos, chunk, sizeof(chunk));
    CHECK(n == 69);
    CHECK(speech_text_next_chunk(words, &pos, chunk, sizeof(chunk)) == 0);

    char solid[121];
    memset(solid, 'x', 120);
    solid[120] = '\0';
    pos = 0;
    CHECK(speech_text_next_chunk(solid, &pos, chunk, sizeof(chunk)) == 80);
    CHECK(speech_text_next_chunk(solid, &pos, chunk, sizeof(chunk)) == 40);

    pos = 0;
    const char* commas = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu, nu xi omicron pi rho sigma tau upsilon phi chi psi omega alpha";
    n = speech_text_next_chunk(commas, &pos, chunk, sizeof(chunk));
    CHECK(chunk[n - 1] == ',');
}

// Rule 1: every name in the list, both cases of A, upper casing of other letters.
static void test_rule1_every_name(void) {
    expect("a", "ay");
    expect("z", "Z");
    expect("Q", "Q");
    expect("9", "nine");
    expect("-", "dash");
    expect("/", "slash");
    expect(":", "colon");
    expect(";", "semicolon");
    expect("!", "exclamation mark");
    expect("?", "question mark");
    expect("'", "apostrophe");
    expect("\"", "quote");
    expect("+", "plus");
    expect("*", "star");
    expect("=", "equals");
    expect("%", "percent");
    expect("&", "and");
    expect("#", "number");
    expect("@", "at");
    expect("(", "open paren");
    expect(")", "close paren");
    expect("[", "open bracket");
    expect("]", "close bracket");
    // A lone byte outside printable ASCII has no name: rule 9 makes it a space, which is dropped.
    expect("\x01", "");
    expect("\xc3", "");
}

// Rule 3: every replacement, and only on an exact match.
static void test_rule3_terms(void) {
    expect("SubGHz", "sub gigahertz");
    expect("kHz", "kilohertz");
    expect("MHz", "megahertz");
    expect("GHz", "gigahertz");
    expect("Hz", "hertz");
    expect("dBm", "dee bee em");
    expect("dB", "dee bee");
    expect("Ok", "okay");
    expect("PIN", "pin");
    expect("Wi-Fi", "why fye");
    expect("WiFi", "why fye");
    expect("mAh", "milliamp hours");
    expect("ok", "ok");
    expect("khz", "khz");
    expect("Pin", "Pin");
    expect("HZ", "H Z");
    expect("Sub-GHz: Read", "sub gigahertz, Read");
}

// Rule 4: periods split at every period with "dot" between the parts; hyphens split into parts
// that are processed as tokens.
static void test_rule4_periods_and_hyphens(void) {
    expect("key_1.sub", "key one dot sub");
    expect("1.2.3", "one dot two dot three");
    expect("192.168.1.1", "one hundred ninety two dot one hundred sixty eight dot one dot one");
    expect("my-file.sub", "my file dot sub");
    expect("Sub-GHz.sub", "sub gigahertz dot sub");
    expect("read-only", "read only");
    expect("on-the-fly", "on the fly");
    expect("1-2", "one two");
    expect("20-MHz", "twenty megahertz");
    expect(
        "378-481, 749-962 MHz",
        "three hundred seventy eight four hundred eighty one, "
        "seven hundred forty nine nine hundred sixty two megahertz");
}

// Rule 5: leading digits are a number, the rest is processed on its own.
static void test_rule5_digits_then_letters(void) {
    expect("868MHz", "eight hundred sixty eight megahertz");
    expect("FAAC SLH 868MHz", "F ay ay C S L H eight hundred sixty eight megahertz");
    expect("2FA", "two F ay");
    expect("3V3", "three V 3");
    expect("100mAh", "one hundred milliamp hours");
    expect("0dBm", "zero dee bee em");
    expect("10dBm +", "ten dee bee em plus");
    expect("007px", "zero zero seven px");
    // Rule 4 comes before rule 5: a decimal glued to its unit is not a decimal number token, so
    // it splits at the period with "dot". Flagged in the report.
    expect("433.92MHz", "four hundred thirty three dot ninety two megahertz");
}

// Rule 6: words up to six digits without a leading zero, digits otherwise, "point" for decimals.
static void test_rule6_numbers(void) {
    expect("19", "nineteen");
    expect("20", "twenty");
    expect("21", "twenty one");
    expect("110", "one hundred ten");
    expect("1010", "one thousand ten");
    expect("1100", "one thousand one hundred");
    expect("10000", "ten thousand");
    expect("100000", "one hundred thousand");
    expect("123456", "one hundred twenty three thousand four hundred fifty six");
    expect("999999", "nine hundred ninety nine thousand nine hundred ninety nine");
    expect("1000000", "one zero zero zero zero zero zero");
    expect("Use kHz values, like 433920", "Use kilohertz values, like four hundred thirty three thousand nine hundred twenty");
    expect("0.5", "zero point five");
    expect("3.14159", "three point one four one five nine");
    expect("10.0", "ten point zero");
    expect("00", "zero zero");
    expect("007", "zero zero seven");
    expect("01.5", "zero one point five");
    expect("1234567.89", "one two three four five six seven point eight nine");
}

// Rule 7: two to five upper case letters and digits with a letter are spelled unless the word is
// in the stop list; six or more, mixed case, or a lone letter are copied.
static void test_rule7_spelling_and_stop_list(void) {
    expect("ERROR", "ERROR");
    expect("HELLO", "H E L L O");
    expect("SECRET", "SECRET");
    expect("OKAY", "OKAY");
    expect("GO", "GO");
    expect("IO", "I O");
    expect("T5577", "T 5 5 7 7");
    expect("AM650", "ay M 6 5 0");
    expect("EM4100", "EM4100");
    expect("USB", "U S B");
    expect("AA", "ay ay");
    expect("NFC ON", "N F C ON");
    expect("APPS", "APPS");
    expect("ZERO", "ZERO");
    expect("Nfc", "Nfc");
    expect("ABCDE", "ay B C D E");
    expect("ABCDEF", "ABCDEF");
    expect("Press B", "Press B");
}

// Rule 8: pieces of at most 20 characters, cut greedily.
static void test_rule8_long_tokens(void) {
    expect("abcdefghijklmnopqrst", "abcdefghijklmnopqrst");
    expect("abcdefghijklmnopqrstu", "abcdefghijklmnopqrst u");
    expect("abcdefghijklmnopqrstabcdefghijklmnopqrst", "abcdefghijklmnopqrst abcdefghijklmnopqrst");
    expect("abcdefghijklmnopqrstabcdefghijklmnopqrstu", "abcdefghijklmnopqrst abcdefghijklmnopqrst u");
    expect("Antidisestablishmentarianism", "Antidisestablishment arianism");
    expect(
        "Pneumonoultramicroscopicsilicovolcanoconiosis",
        "Pneumonoultramicrosc opicsilicovolcanocon iosis");
}

// Rule 9: what happens between tokens.
static void test_rule9_separators(void) {
    expect("12:34:56", "twelve thirty four fifty six");
    expect("Time: 12:34", "Time, twelve thirty four");
    expect("1: 2", "one, two");
    expect("A:B", "A, B");
    expect("Read/Write", "Read slash Write");
    expect("A&B", "A and B");
    expect("1+1=2", "one plus one equals two");
    expect("#1", "number one");
    expect("user@host", "user at host");
    expect("5*5", "five star five");
    expect("Hello , world", "Hello, world");
    expect("Really ?", "Really?");
    expect("Wow !", "Wow!");
    expect("Wait ...", "Wait...");
    expect("a\tb\nc", "a b c");
    expect("\"quoted\"", "quoted");
    expect("'single'", "single");
    expect("x\x01y", "x y");
    expect("x\x7fy", "x y");
    expect("x\xffy", "x y");
    expect("x\xe2\x80\xa6", "x");
    expect("\xffx", "x");
    expect("x[y", "x y");
    expect("x{y", "x y");
    expect("x|y", "x y");
    expect("x<y>z", "x y z");
    expect("x]y}z", "x y z");
}

// Rule 9 for every byte value: the output is printable ASCII, and every byte outside printable
// ASCII is a space.
static void test_rule9_every_byte(void) {
    for(int b = 1; b < 256; b++) {
        char in[4] = {'x', (char)b, 'y', '\0'};
        char out[SPEECH_TEXT_MAX];
        speech_text_expand(in, out, sizeof(out));
        int printable = 1;
        for(const char* p = out; *p; p++) {
            if((unsigned char)*p < 0x20 || (unsigned char)*p > 0x7E) printable = 0;
        }
        CHECK(printable);
        if(b < 0x20 || b > 0x7E) {
            checks++;
            if(strcmp(out, "x y") != 0) {
                failures++;
                printf("FAIL expand(\"x\\x%02x" "y\") got \"%s\" want \"x y\"\n", b, out);
            }
        }
        char one[2] = {(char)b, '\0'};
        speech_text_expand(one, out, sizeof(out));
        printable = 1;
        for(const char* p = out; *p; p++) {
            if((unsigned char)*p < 0x20 || (unsigned char)*p > 0x7E) printable = 0;
        }
        CHECK(printable);
    }
}

// Rule 10: the corners of chunking.
static void test_rule10_chunk_edges(void) {
    char chunk[SPEECH_CHUNK_MAX + 1];
    size_t pos = 0;
    size_t n;

    // leading spaces are skipped, trailing spaces trimmed, the position ends at the length
    const char* padded = "   Hello   ";
    n = speech_text_next_chunk(padded, &pos, chunk, sizeof(chunk));
    CHECK(n == 5);
    CHECK(strcmp(chunk, "Hello") == 0);
    CHECK(speech_text_next_chunk(padded, &pos, chunk, sizeof(chunk)) == 0);
    CHECK(pos == strlen(padded));

    // nothing left
    pos = 0;
    CHECK(speech_text_next_chunk("", &pos, chunk, sizeof(chunk)) == 0);
    CHECK(chunk[0] == '\0');
    pos = 0;
    CHECK(speech_text_next_chunk("     ", &pos, chunk, sizeof(chunk)) == 0);

    // a sentence end within the limit wins over a later comma
    const char* mixed = "First. alpha, beta, gamma, delta, epsilon, zeta, eta, theta, iota, kappa, "
                        "lambda, mu, nu, xi";
    pos = 0;
    n = speech_text_next_chunk(mixed, &pos, chunk, sizeof(chunk));
    CHECK(n == 6);
    CHECK(strcmp(chunk, "First.") == 0);
    n = speech_text_next_chunk(mixed, &pos, chunk, sizeof(chunk));
    CHECK(n == 78);
    CHECK(chunk[n - 1] == ',');
    n = speech_text_next_chunk(mixed, &pos, chunk, sizeof(chunk));
    CHECK(n == 6);
    CHECK(strcmp(chunk, "nu, xi") == 0);
    CHECK(speech_text_next_chunk(mixed, &pos, chunk, sizeof(chunk)) == 0);

    // a period not followed by a space is not a sentence end: the cut falls at the last space
    char decimal[100];
    decimal[0] = '\0';
    for(int i = 0; i < 8; i++) strcat(decimal, "word ");
    strcat(decimal, "3.14");
    for(int i = 0; i < 10; i++) strcat(decimal, " word");
    CHECK(strlen(decimal) == 94);
    pos = 0;
    n = speech_text_next_chunk(decimal, &pos, chunk, sizeof(chunk));
    CHECK(n == 79);
    CHECK(strstr(chunk, "3.14 word") != NULL);
    CHECK(chunk[78] == 'd');
    n = speech_text_next_chunk(decimal, &pos, chunk, sizeof(chunk));
    CHECK(n == 14);
    CHECK(strcmp(chunk, "word word word") == 0);

    // question and exclamation marks end sentences; a rest of exactly the limit fits
    char qe[120] = "Is it? Yes it is! ";
    for(int i = 0; i < 80; i++) strcat(qe, "x");
    pos = 0;
    n = speech_text_next_chunk(qe, &pos, chunk, sizeof(chunk));
    CHECK(n == 17);
    CHECK(strcmp(chunk, "Is it? Yes it is!") == 0);
    n = speech_text_next_chunk(qe, &pos, chunk, sizeof(chunk));
    CHECK(n == 80);
    CHECK(chunk[0] == 'x' && chunk[79] == 'x' && chunk[80] == '\0');
    CHECK(speech_text_next_chunk(qe, &pos, chunk, sizeof(chunk)) == 0);

    // a sentence end on the last character within the limit
    char edge[100];
    edge[0] = '\0';
    for(int i = 0; i < 79; i++) strcat(edge, "x");
    strcat(edge, ". more");
    pos = 0;
    n = speech_text_next_chunk(edge, &pos, chunk, sizeof(chunk));
    CHECK(n == 80);
    CHECK(chunk[79] == '.');
    n = speech_text_next_chunk(edge, &pos, chunk, sizeof(chunk));
    CHECK(n == 4);
    CHECK(strcmp(chunk, "more") == 0);

    // the buffer can be smaller than the chunk limit
    char small[11];
    const char* short_words = "Hello world foo";
    pos = 0;
    n = speech_text_next_chunk(short_words, &pos, small, sizeof(small));
    CHECK(n == 5);
    CHECK(strcmp(small, "Hello") == 0);
    n = speech_text_next_chunk(short_words, &pos, small, sizeof(small));
    CHECK(n == 9);
    CHECK(strcmp(small, "world foo") == 0);
    CHECK(speech_text_next_chunk(short_words, &pos, small, sizeof(small)) == 0);
}

// Behaviour the rule list does not decide. These pin what the code does today so a change is
// noticed; the report lists each one.
static void test_beyond_the_rule_list(void) {
    // Single character names beyond rule 1's list.
    expect("{", "open brace");
    expect("}", "close brace");
    expect("<", "less than");
    expect(">", "greater than");
    expect("|", "bar");
    expect("\\", "backslash");
    expect("^", "caret");
    expect("~", "tilde");
    expect("`", "backtick");
    expect("$", "dollar");
    // Printable characters rule 9 does not list become a space like the listed ones.
    expect("a; b", "a b");
    expect("a - b", "a b");
    expect("x\\y", "x y");
    expect("a ~ b", "a b");
    expect("a ^ b $ c", "a b c");
    // A hyphen before a number is not in a token, so the sign is lost (see the report).
    expect("-90dBm", "ninety dee bee em");
    // Rule 5 leaves a lone A behind a digit as a one letter token, which rule 8 copies.
    expect("04 1A 2B", "zero four one A two B");
    // The output buffer: truncated, always terminated; a null input gives an empty string.
    char small[8];
    CHECK(speech_text_expand("Hello world", small, sizeof(small)) == 7);
    CHECK(strcmp(small, "Hello w") == 0);
    CHECK(speech_text_expand(NULL, small, sizeof(small)) == 0);
    CHECK(small[0] == '\0');
}

int main(void) {
    test_words_and_numbers();
    test_acronyms_and_terms();
    test_punctuation();
    test_single_characters();
    test_chunks();
    test_rule1_every_name();
    test_rule3_terms();
    test_rule4_periods_and_hyphens();
    test_rule5_digits_then_letters();
    test_rule6_numbers();
    test_rule7_spelling_and_stop_list();
    test_rule8_long_tokens();
    test_rule9_separators();
    test_rule9_every_byte();
    test_rule10_chunk_edges();
    test_beyond_the_rule_list();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
