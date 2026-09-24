### Task 1: Spelled fallback and letter names

**Goal:** a word without a clip is spelled letter by letter with the letter and digit clips instead of being spoken by SAM; single letters are recorded by their names so "N F C" no longer sounds like "capital N capital F capital C"; the eight words the device logged get clips.

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/speech_voice.h`, `speech_voice.c`, `speech.c`
- Modify: `tests/host/test_speech_voice.c`
- Modify: `tools/voice_names.txt`, `tools/voice_build.py` (spoken_text), `README.md`

**Firmware**

`speech_voice.h`: add `#define SPEECH_VOICE_LETTER_GAP_MS 60` and

```c
/** The clip name that spells one character: "ay" for a, the letter itself for b to z, the
 *  digit itself for 0 to 9. False for anything else (the character is skipped). */
bool speech_voice_letter_clip(char c, char out[3]);
```

`speech_voice.c`:

```c
bool speech_voice_letter_clip(char c, char out[3]) {
    if(c == 'a') {
        out[0] = 'a';
        out[1] = 'y';
        out[2] = '\0';
        return true;
    }
    if((c >= 'b' && c <= 'z') || (c >= '0' && c <= '9')) {
        out[0] = c;
        out[1] = '\0';
        return true;
    }
    return false;
}
```

`speech.c`: add after `speech_sam_word`:

```c
/**
 * A word the vocabulary lacks is spelled with the letter and digit clips, a short gap between
 * them; a character whose clip is missing too is spoken by SAM as the last resort.
 */
static void speech_spell_word(Speech* speech, const char* word, const SamVoice* voice) {
    char name[3];
    for(const char* p = word; *p != '\0' && !speech->aborted; p++) {
        if(!speech_voice_letter_clip(*p, name)) continue;
        if(p != word && !speech_push_silence(speech, SPEECH_VOICE_LETTER_GAP_MS)) return;
        if(speech_voice_path(name, speech->path, sizeof(speech->path)) > 0 &&
           speech_play_clip(speech, speech->path)) {
            continue;
        }
        speech_sam_word(speech, name, voice);
    }
}
```

In `speech_speak_words`, the fallback branch calls `speech_spell_word(speech, word.word, voice)` instead of `speech_sam_word(...)`; the fallback and missing counting stay as they are. Update the comment on `SpeechVoiceStats.fallback_words` ("words spelled letter by letter since boot"). `speech_sam_word` stays (used for a missing letter clip and by nothing else).

`tests/host/test_speech_voice.c`: add checks for `speech_voice_letter_clip`: 'a' → "ay", 'b' → "b", 'z' → "z", '0' → "0", '7' → "7", '-' → false, 'A' → false (names are lower case), '\'' → false.

**Generator**

`tools/voice_names.txt`: one line per letter, tab separated, the clip name and the words `say` should speak so that the letter is heard by its name and nothing else:

```
a	a
b	bee
c	see
d	dee
e	ee
f	eff
g	gee
h	aitch
i	eye
j	jay
k	kay
l	ell
m	em
n	en
o	oh
p	pee
q	cue
r	are
s	ess
t	tee
u	you
v	vee
w	double you
x	ex
y	why
z	zee
```
Keep the existing `ay	A` line? No: change it to `ay	ay` (the clip for the letter A must not be "capital A" either). Keep `fye	fi`.

`tools/voice_build.py` `spoken_text`: the single-letter rule becomes `return word` (lower case) after the names lookup, so an unlisted letter is never spoken as "capital X"; digits stay number words. The manifest hash covers the spoken text, so `--extract` (or any run) remakes the 27 letter clips automatically.

**README**: the fallback paragraph says a missing word is spelled letter by letter with the recorded letters (60 ms between letters), SAM speaks a letter only when its clip is missing or the voice is off; the letter names live in tools/voice_names.txt; the routine command remains `tools/voice_build.py --extract --pull-missing --sync`.

**Device**

1. Build: `./fbt` clean, `./fbt lint` exit 0, `tools/flash_headroom.sh` above zero; host runner green (private TMPDIR).
2. Commit firmware "screen reader: missing words are spelled with the letter clips" and project "voice_build: letters by their names; host tests: letter clips" (own files, pathspec commits); docs in the same project commit or a second one.
3. Flash (`./fbt flash_usb`, wait, `sr screen` first, `info device`). Then `.venv/bin/python tools/voice_build.py --extract --pull-missing --sync 2>&1 | tail -8`: expect 27 remade letter clips plus the pulled words (the device has rickroll, nfcv, u2f, notifications, packs, fuzzer, tesla, stock; u2f is skipped by the filter), sent in seconds; guard lines printed; `sr voice status` on afterwards.
4. Verify, verbatim: `sr say NFC GPIO LCD` → `sr voice status` clips +10, fallback +0; `sr say u2f` → clips +3 (you, two, eff: the clips u, 2, f), fallback +1, missing +1; `sr say zzyzx` → clips +5, fallback +1; `sr say Tesla stock fuzzer` → clips +3, fallback +0; one sr_drive scripted session: 0 failures, underruns unchanged; `free` before and after. Leave the device idle on the home screen, reader on, voice on.
