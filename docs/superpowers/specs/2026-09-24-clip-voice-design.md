# Recorded voice for the Flipper Zero screen reader: design

Date: 2026-09-24. Status: as built 2026-09-24. Approved by Robin on 2026-09-24: the design was agreed in conversation, and the build authorised without further approval. The measurements are in `docs/measurements/2026-09-24-voice-rollout.txt`.

As built, the implementation differs from the text below in these points:

- Word sources: only the core apps and services are read. These are `applications/main`, `services`, `settings` and `system`, plus `lib/toolbox`; the rest of `applications/` is left out. The community apps would multiply the vocabulary for nothing.
- Clip names: a name is lower case letters, up to 16 of them, or a single digit. Words with an apostrophe, words with digits inside and longer words have no clips, so SAM speaks them.
- Processing order: high-pass, peak normalise, then gain and limiter. After that, silence is trimmed on the finished signal and 15 ms of zeros are added at each end.
- Sync: it sends the manifest's clips and voice.txt, and records what it sent in `voice/synced.json`. It does not compare sizes on the card. `--sync-all` resends everything. The recorded voice is off on the device during a transfer and back on afterwards.
- `sr voice status` shows the settings line read at the first utterance after boot. After a sync that changes the line, the new one shows after a reboot.
- Open defect in the timing safety of section 5. The assumption that a directory of a few hundred entries keeps an open under 10 ms does not hold.
  - On the device, a lookup costs about 0.17 ms per directory entry. At the end of the largest folder, with 315 clips, it takes 65 ms.
  - The worker can only stall for what is left of the playing half of the ring, at most 41 ms, not 82 ms, before the stall counts as an underrun.
  - Words near the end of the large folders therefore cause underruns: 41 during the rollout verification. The acceptance test of 0 underruns is not met.
  - Smaller folders are the fix. They are not built yet.

## 1. Goal

Replace SAM as the everyday voice of the screen reader with recorded speech played from the SD card: a vocabulary of word clips made on a computer from a high quality voice, played word by word through the existing speaker path. SAM stays as the fallback for words the vocabulary lacks, so nothing is ever left unspoken. The choice rests on a listening test on 2026-09-24: macOS Samantha clips through the piezo were "much much better" than SAM and "easily understandable"; the settings Robin chose are Samantha at her default rate 175, a first order high-pass at 500 Hz, gain 1.3 through a tanh limiter, 16 kHz, 8-bit.

## 2. Facts the design rests on

- The speech engine (phase 2) plays 8-bit values through a PCM stage, a 4096 byte DMA ring and TIM16 PWM at 50 kHz. `sr play <path> <rate>` (commit 54794522b) streams a raw unsigned 8-bit file from the card in 512 byte reads with `speech_pcm_push_raw`; an 11.4 s clip played with 0 underruns and a 0.4 percent timing error, and `sr stop` and a key press cut it like an utterance.
- The pronunciation layer (`speech_text`) turns any announcement into ASCII words: replacements (sub gigahertz, kilohertz, okay), numbers as words, spelled letters with A as "ay", punctuation names, and it attaches sentence punctuation to the previous word. Its output is the canonical word stream of the device, so a vocabulary built by running the same C code on the computer matches the device exactly.
- The card is exFAT. A directory lookup scans entries linearly, so one directory of thousands of files would cost tens of milliseconds per open; a few hundred entries per directory cost a few milliseconds. The ring holds 82 ms of audio, so the worker has that long to open the next word once the current one is pushed.
- Flash headroom is 10,884 bytes under the updater's limit (880,640 bytes); heap headroom at the NFC read worst case is 23.8 KB. The voice must cost only a few KB of flash and no new heap beyond a path buffer.
- Apple's voices are licensed for use on the Mac; redistributing clips made with them is not clearly permitted. A release needs a freely licensed voice (Piper, MIT engine, permissive voice models) as the generator's default, with `say` as a personal option.

## 3. Vocabulary on the card

- Location: `/ext/sr/voice/<initial>/<word>.raw`, where `<initial>` is the word's first character (a to z, 0 to 9, `_` for anything else) and `<word>` is the lower case ASCII word as the pronunciation layer emits it (letters, digits, apostrophe). Sentence punctuation never appears in a name.
- Format: raw unsigned 8-bit PCM, mono, 16,000 samples per second, 128 is silence, silence trimmed to 15 ms at each end. Letters are spoken by name ("b" is "bee"), `ay` is the letter A, digits `0` to `9` are the digit words.
- A `voice.txt` file at `/ext/sr/voice/` records the generator settings (backend, voice, rate, high-pass, gain, limiter) so `sr voice` can report them and the generator can tell a settings change from a missing clip.
- Missing words: the device appends words it could not find to `/ext/sr/missing.txt`, one per line, at most once per boot per word (a 64 entry hash set in RAM), written after the utterance that needed them so playback is never delayed.

## 4. The generator: tools/voice_build.py

One script makes and syncs the vocabulary; `tools/clip_make.py` (single test clips) shares its processing code.

- Word sources, merged and deduplicated: the base list `tools/voice_words.txt` (number words, letters, digits, units, the pronunciation layer's replacement and punctuation words, common UI words); every string literal in the firmware sources under `applications/` and `lib/toolbox/` run through the real pronunciation layer (a small host program, `tests/host/speech_expand.c`, built from `speech_text.c` on demand); and the device's `missing.txt` (`--pull-missing` fetches it).
- Backends: `say` (macOS, default when available, voice Samantha) and `piper` (any platform, a named model, resampled to 16 kHz). Options: `--voice`, `--rate`, `--highpass` (500), `--gain` (1.3), `--soft` (on), `--hz` (16000), `--backend`. Every option has Robin's choice as its default.
- Processing per word: synthesize, high-pass, trim silence (threshold 2 percent of full scale, 15 ms padding), peak normalise to 0.95, gain and tanh limiter, convert to 8-bit.
- Incremental: a local `voice/` directory (git-ignored) holds the clips and `manifest.json` (settings plus each word's settings hash); only missing or changed clips are made; `--sync` uploads only files the card lacks or that differ in size, creating directories as needed, and writes `voice.txt`. Progress is printed per hundred words; `--jobs` runs several synthesizer processes.
- Special names: `ay` is synthesized as "A", single letters as their upper case letter, digits as their words, `okay` as "okay"; a `tools/voice_names.txt` table holds any word whose spoken form differs from its name (for example `gigahertz` is spoken as written, `dbm` would be spelled by the layer, so it never appears).

## 5. Firmware: the voice module

- `speech_voice.h/.c` (pure C, host tested): walks an expanded announcement word by word and yields, for each word, its clip name (lower cased, punctuation stripped, mapped to the `<initial>/<word>.raw` path) and the pause that follows it: 40 ms between words, 150 ms after a comma, 300 ms after a period, question or exclamation mark. It also carries the missing-word set (64 hashes) and a small buffer of words to log after the utterance.
- `speech.c`: when the voice is enabled and an item is spoken, the worker takes the speaker once, then for each word: open `/ext/sr/voice/<initial>/<word>.raw`; if it opens, stream it in 512 byte reads through `speech_pcm_push_raw` at 62,500 ns per sample; if not, speak the word with SAM (upper cased, with a period) through the existing chunk path and record it as missing; then push the pause as silence samples. Abort, stop and interrupt work exactly as today (generation check between reads). The flush and speaker release are unchanged. After the utterance the missing words are appended to `missing.txt`.
- Settings and CLI: a saved setting `sr_voice` (on by default); `sr voice on|off|status` where status prints the voice.txt settings line, the count of words spoken by clip and by fallback since boot, and the missing count. `sr status` gains "voice: on, clips N, fallback M, missing K".
- When `/ext/sr/voice/` does not exist at boot the voice reports "no vocabulary" and everything falls back to SAM without logging (the log would only fill with the whole vocabulary).
- Memory: one extra file handle at alloc, a 96 byte path buffer, the 64 entry hash set (256 bytes) and the log buffer (8 words of 32 bytes) inside the Speech record. Flash: about 3 KB.
- Timing safety: the worker opens the next word after pushing the current word's last chunk, so the ring's 82 ms cover the open; a directory of a few hundred files keeps an open under 10 ms. Underruns are counted as today; the acceptance test is 0 underruns over sr_drive's two sessions and a 30 word announcement.

## 6. Testing

- Host: `tests/host/test_speech_voice.c` covers name mapping (case, punctuation, initial folder, non-letter initial), pauses, the hash set (no repeat within a session, eviction order), the log buffer, and the exact byte layout of a pause. The runner adds it under sanitizers.
- Generator: `tools/voice_build.py --check` synthesizes ten words into a temporary directory and verifies format, length bounds and trimming; the extraction step prints the word count and the ten longest words for a sanity read.
- Device: a partial vocabulary first (a few hundred words) to verify playback, fallback, logging and stop; then the full vocabulary; then sr_drive's two sessions with the voice on, a 30 word announcement, counters (underruns 0, fallback only for words outside the vocabulary), and a `--pull-missing` round trip.

## 7. Out of scope

Prosody beyond pauses, phrase level clips, packed vocabulary files, a rate control for clips (the vocabulary is regenerated at another rate instead), and any change to the console mirror.
