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
    expect("Mood: Happy. Level: 1. 18/100", "Mood, Happy. Level, one. eighteen of one hundred");
    expect("Battery: 87%", "Battery, eighty seven percent");
    expect("2026", "two thousand twenty six");
    expect("1234567", "one two three four five six seven");
    expect("04 A2 FF", "zero four ay two F F");
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
    expect("U2F", "U two F");
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
}

// Rule 5: a number, decimal or not, then letters: a term, spelled when one to five upper case
// letters outside the stop list, copied otherwise.
static void test_rule5_digits_then_letters(void) {
    expect("868MHz", "eight hundred sixty eight megahertz");
    expect("FAAC SLH 868MHz", "F ay ay C S L H eight hundred sixty eight megahertz");
    expect("2FA", "two F ay");
    // "V3" is not letters only, so the token is not rule 5's shape; rule 7 spells it by runs.
    expect("3V3", "three V three");
    expect("100mAh", "one hundred milliamp hours");
    expect("0dBm", "zero dee bee em");
    expect("10dBm +", "ten dee bee em plus");
    expect("007px", "zero zero seven px");
    expect("433.92MHz", "four hundred thirty three point nine two megahertz");
    expect("3.3V", "three point three V");
    expect("1.5mAh", "one point five milliamp hours");
    expect("12.MHz", "twelve dot megahertz");
    expect("1A", "one ay");
    expect("9F", "nine F");
    expect("10s", "ten s");
    expect("04 1A 2B", "zero four one ay two B");
    expect("12AT", "twelve AT");
    expect("4GB", "four G B");
    expect("12ABCDEF", "twelve ABCDEF");
    expect("1ABCDE", "one ay B C D E");
    expect("1K", "one K");
}

// Rule 6: words up to four digits without a leading zero, digits otherwise, "point" for decimals.
static void test_rule6_numbers(void) {
    expect("19", "nineteen");
    expect("20", "twenty");
    expect("21", "twenty one");
    expect("110", "one hundred ten");
    expect("1010", "one thousand ten");
    expect("1100", "one thousand one hundred");
    expect("9999", "nine thousand nine hundred ninety nine");
    expect("10000", "one zero zero zero zero");
    expect("14443", "one four four four three");
    expect("65535", "six five five three five");
    expect("100000", "one zero zero zero zero zero");
    expect("123456", "one two three four five six");
    expect("999999", "nine nine nine nine nine nine");
    expect("433920000", "four three three nine two zero zero zero zero");
    expect("1000000", "one zero zero zero zero zero zero");
    expect("Use kHz values, like 433920", "Use kilohertz values, like four three three nine two zero");
    expect("0.5", "zero point five");
    expect("3.14159", "three point one four one five nine");
    expect("10.0", "ten point zero");
    expect("00", "zero zero");
    expect("007", "zero zero seven");
    expect("01.5", "zero one point five");
    expect("1234567.89", "one two three four five six seven point eight nine");
    expect("12345.6", "one two three four five point six");
}

// Rule 7: upper case letters and digits, two or more with a letter, outside the stop list, are
// spelled by runs: one to five letters character by character (a stop word run as a word),
// longer letter runs as a word, one to three digits as a number, longer digit runs digit by
// digit. Mixed case is copied.
static void test_rule7_spelling_and_stop_list(void) {
    expect("ERROR", "ERROR");
    expect("SET AT", "SET AT");
    expect("HEX", "HEX");
    expect("IN", "IN");
    expect("ID", "I D");
    expect("HELLO", "H E L L O");
    expect("SECRET", "SECRET");
    expect("OKAY", "OKAY");
    expect("GO", "GO");
    expect("IO", "I O");
    expect("T5577", "T five five seven seven");
    expect("AM650", "ay M six hundred fifty");
    expect("EM4100", "E M four one zero zero");
    expect("DS1990A", "D S one nine nine zero ay");
    expect("NTAG215", "N T ay G two hundred fifteen");
    expect("ISO14443", "I S O one four four four three");
    expect("MIFARE", "MIFARE");
    expect("MODE1", "MODE one");
    expect("A1", "ay one");
    expect("UID: 04 A2 B3 C4", "U I D, zero four ay two B three C four");
    expect("X007", "X zero zero seven");
    expect("SET1", "SET one");
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
    expect("A:B", "ay, B");
    expect("Read/Write", "Read slash Write");
    expect("A&B", "ay and B");
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

// Rule 11: a hyphen before a digit, at the start or after a character that is not alphanumeric,
// is "minus"; a hyphen before a space or a letter is still a space, inside a token rules 4 and
// 12 apply.
static void test_rule11_minus(void) {
    expect("-90dBm", "minus ninety dee bee em");
    expect("TX power -10dBm", "T X power minus ten dee bee em");
    expect("-", "dash");
    expect("- 90", "ninety");
    expect("Ch-3", "Ch three");
    expect("(-5)", "minus five");
    expect("-0.5", "minus zero point five");
    expect("-5-3", "minus five to three");
    expect("a -b", "a b");
    expect("RSSI: -70", "R S S I, minus seventy");
}

// Rule 12: a hyphen with a digit on at least one side: "to" as the only hyphen between two digit
// runs of the same length, a space between a digit run and two or more letters, "dash"
// otherwise; hyphens between letters keep rule 4.
static void test_rule12_ranges(void) {
    expect(
        "378-481, 749-962 MHz",
        "three hundred seventy eight to four hundred eighty one, "
        "seven hundred forty nine to nine hundred sixty two megahertz");
    expect("2026-09-23", "two thousand twenty six dash zero nine dash twenty three");
    expect("1-2", "one to two");
    expect("1-2-3", "one dash two dash three");
    expect("a-1-2", "a dash one dash two");
    expect("20-MHz", "twenty megahertz");
    expect("14443-3", "one four four four three dash three");
    expect("1-10", "one dash ten");
    expect("100-99", "one hundred dash ninety nine");
    expect("4-bytes", "four bytes");
    expect("1-Day", "one Day");
    expect("NFC-A 4-bytes UID", "N F C ay four bytes U I D");
    expect("A-1", "ay dash one");
    expect("100-200-A", "one hundred dash two hundred dash ay");
    expect("ab-12", "ab twelve");
    expect("a-12", "a dash twelve");
    expect("1-A2", "one dash ay two");
    expect("4-bytes-A", "four bytes ay");
    expect("ISO14443-3A", "I S O one four four four three dash three ay");
    expect(
        "Tech: ISO 14443-3A (NFC-A)",
        "Tech, I S O one four four four three dash three ay N F C ay");
    expect(
        "Tech: ISO 14443-3 (NFC-A)",
        "Tech, I S O one four four four three dash three N F C ay");
    expect("NFC-A", "N F C ay");
    expect("10-20%", "ten to twenty percent");
    expect("on-the-fly", "on the fly");
}

// Rule 13: a token that is the single upper case letter A is "ay"; lower case a is the article.
static void test_rule13_upper_a(void) {
    expect("NFC-A", "N F C ay");
    expect("Type A", "Type ay");
    expect("a key", "a key");
    expect("A", "ay");
    expect("Plan A or B", "Plan ay or B");
    expect("A.", "ay.");
}

// Rule 14: a slash between two digits is "of", as the Passport's points read; a slash next to a
// letter, even with a digit on its other side, or at the start stays "slash". The Passport's line
// at the highest level (Max Level!) has no slash.
static void test_rule14_slash_of(void) {
    expect("1/3", "one of three");
    expect("/ext/apps", "slash ext slash apps");
    expect("a/b", "a slash b");
    expect("a/5", "a slash five");
    expect("Max Level!", "Max Level!");
}

// SPEECH_TEXT_MAX: a 160 character hex dump expands without being cut. The dump mixes the
// pair shapes of a real screen; each expected word comes from rules 5, 6 and 7.
static void test_text_buffer(void) {
    static const char* const pairs[16] = {
        "0A", "1B", "2C", "3D", "4E", "5F", "6A", "7B", "8C", "9D", "77", "33", "88", "AA", "FF", "00"};
    static const char* const words[16] = {
        "zero ay", "one B", "two C", "three D", "four E", "five F", "six ay", "seven B",
        "eight C", "nine D", "seventy seven", "thirty three", "eighty eight", "ay ay", "F F",
        "zero zero"};
    char in[161] = "UID:";
    char want[SPEECH_TEXT_MAX] = "U I D,";
    for(int k = 0; k < 52; k++) {
        strcat(in, " ");
        strcat(in, pairs[k % 16]);
        strcat(want, " ");
        strcat(want, words[k % 16]);
    }
    CHECK(strlen(in) == 160);
    char out[SPEECH_TEXT_MAX];
    size_t n = speech_text_expand(in, out, sizeof(out));
    CHECK(n == strlen(out));
    CHECK(strcmp(out, want) == 0);
    CHECK(n > 400); // a 400 byte buffer would have cut this text
    CHECK(n > strlen("three D") && strcmp(out + n - strlen("three D"), "three D") == 0);

    // A dump of two digit pairs is the heaviest screen, about 4.7 times its length.
    static const char* const digit_pairs[8] = {"77", "78", "87", "88", "33", "99", "66", "44"};
    static const char* const digit_words[8] = {
        "seventy seven", "seventy eight", "eighty seven", "eighty eight", "thirty three",
        "ninety nine", "sixty six", "forty four"};
    strcpy(in, "UID:");
    strcpy(want, "U I D,");
    for(int k = 0; k < 52; k++) {
        strcat(in, " ");
        strcat(in, digit_pairs[k % 8]);
        strcat(want, " ");
        strcat(want, digit_words[k % 8]);
    }
    CHECK(strlen(in) == 160);
    n = speech_text_expand(in, out, sizeof(out));
    CHECK(n == strlen(out));
    CHECK(strcmp(out, want) == 0);
    CHECK(n > 640); // a 640 byte buffer would have cut this text
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
    // A rule 7 letter run longer than 20 characters is copied in rule 8's pieces.
    expect("ABCDEFGHIJKLMNOPQRSTUVWXYZ1", "ABCDEFGHIJKLMNOPQRST UVWXYZ one");
    // The output buffer: truncated, always terminated; a null input gives an empty string.
    char small[8];
    CHECK(speech_text_expand("Hello world", small, sizeof(small)) == 7);
    CHECK(strcmp(small, "Hello w") == 0);
    CHECK(speech_text_expand(NULL, small, sizeof(small)) == 0);
    CHECK(small[0] == '\0');
}

static void expect_spell(const char* in, const char* want) {
    char out[SPEECH_TEXT_MAX];
    size_t n = speech_text_spell_copy(in, out, sizeof(out));
    checks++;
    if(strcmp(out, want) != 0 || n != strlen(want)) {
        failures++;
        printf(
            "FAIL spell_copy(\"%s\")\n  got  \"%s\" (%u)\n  want \"%s\"\n",
            in,
            out,
            (unsigned)n,
            want);
    }
}

// The text of an item to be spelled: its letters and digits in runs, single spaces between
// runs, none at the ends
static void test_spell_copy(void) {
    expect_spell("Apps, 3 of 11", "Apps 3 of 11");
    expect_spell("Sub-GHz", "Sub GHz");
    expect_spell("125 kHz RFID", "125 kHz RFID");
    // A run of 46 is split after 31 characters, the longest word the clip player takes whole
    expect_spell(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789abcdefghij",
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ01234 56789abcdefghij");
    expect_spell("ABCDEFGHIJKLMNOPQRSTUVWXYZ01234", "ABCDEFGHIJKLMNOPQRSTUVWXYZ01234");
    // Nothing to spell
    expect_spell("_", "");
    expect_spell("!?.,-_ ()", "");
    expect_spell("", "");
    // Separators at the ends and in a row, and bytes outside ASCII, leave single spaces only
    expect_spell("  _Tesla__charge.sub_ ", "Tesla charge sub");
    expect_spell("caf\xc3\xa9 au lait", "caf au lait");

    // A small buffer cuts the text and never leaves a space at its end; a null text is empty
    char small[6];
    CHECK(speech_text_spell_copy("Apps 3 of 11", small, sizeof(small)) == 4);
    CHECK(strcmp(small, "Apps") == 0);
    CHECK(speech_text_spell_copy("Sub-GHz", small, sizeof(small)) == 5);
    CHECK(strcmp(small, "Sub G") == 0);
    CHECK(speech_text_spell_copy(NULL, small, sizeof(small)) == 0 && small[0] == '\0');
    CHECK(speech_text_spell_copy("Apps", NULL, 0) == 0);
}

int main(void) {
    test_words_and_numbers();
    test_acronyms_and_terms();
    test_punctuation();
    test_single_characters();
    test_rule1_every_name();
    test_rule3_terms();
    test_rule4_periods_and_hyphens();
    test_rule5_digits_then_letters();
    test_rule6_numbers();
    test_rule7_spelling_and_stop_list();
    test_rule8_long_tokens();
    test_rule9_separators();
    test_rule9_every_byte();
    test_rule11_minus();
    test_rule12_ranges();
    test_rule13_upper_a();
    test_rule14_slash_of();
    test_text_buffer();
    test_beyond_the_rule_list();
    test_spell_copy();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
