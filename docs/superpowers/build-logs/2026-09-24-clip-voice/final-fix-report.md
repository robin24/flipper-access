# Final review: fix implementation report

Five findings from the final review, fixed on branch `main` on top of 512b949. No firmware
change, no device access, `voice/` untouched.

## Finding 1: wrong folder count in the rollout log

`docs/measurements/2026-09-24-voice-rollout.txt` line 3 said the first rollout used "26 folders
by first letter" (letters only). The first rollout actually used one folder per first character
across letters and digits, i.e. 36 (confirmed by line 140's "36 of 36 first-letter folders
removed"). Changed "26" to "36".

## Finding 2: mixed letter/digit tokens silently never get clips

`README.md` "Known limits" gets a new bullet, placed right after the "Words longer than 16
letters" bullet:

> Tokens that mix letters and digits (for example `md5`, `i2c`, `p1`) never get a clip: the
> generator's word filter accepts letters-only words up to 16 characters or a single digit. They
> are spoken by SAM every time, logged as missing once per boot, and dropped by
> `--pull-missing`.

`tools/voice_build.py`'s `load_list()` now counts non-blank tokens that `clip_name()` rejects
(mixed-alnum words, overlong words, etc.) and prints `skipped N words that cannot be clips` when
N is not zero. This fires for any word list `load_list` reads, including a pulled `missing.txt`,
so a pull that yields fewer clips than the file had words is now explained in the log output
instead of silently vanishing. Blank lines and comment-only lines are not counted (they were
already silently ignored and aren't "words that fail the filter").

Smoke-tested locally (no device): a list containing `hello`, `md5`, `i2c`, `p1`, `world`, a blank
line, a comment line, `7`, and a 50-letter word produced `skipped 4 words that cannot be clips`
and returned exactly `{hello, world, 7}` — the 4 skips are `md5`, `i2c`, `p1`, and the overlong
word.

## Finding 3: sync failure mode left undocumented

`README.md`, the bullet on the recorded voice being silenced during a transfer, gains one
sentence: if the transfer dies hard (power loss, a killed process, a dead port), the `finally`
block that restores the setting may not run, so the saved setting stays off and the device
speaks with SAM until `sr voice on` is typed. This matches `voice_off`/`voice_on`'s use in
`sync()`, `pull_missing()`, and `remove_legacy()` in `tools/voice_build.py`: each only restores
the voice from a `finally` clause that assumes the process is still alive to run it.

## Finding 4: mischaracterized margin in the rollout log

`docs/measurements/2026-09-24-voice-rollout.txt` line 54 called a measured 38 ms clip open "well
under 41 ms", which overstates the margin (38 ms is only ~3 ms, not "well", under the 41 ms
half-ring budget). Changed "an open well under 41 ms" to "an open of about 38 ms, just under the
41 ms half" (with a comma added around the appositive for grammar). The sentence now reads: "So
an open of about 38 ms, just under the 41 ms half, can already cause an underrun: "types", at
about 38 ms, underran three times out of three."

## Finding 5: routine command missing `--extract`

`README.md`'s missing-word workflow bullet is the only place in the README where this command
appears. Updated from `.venv/bin/python tools/voice_build.py --pull-missing --sync` to
`.venv/bin/python tools/voice_build.py --extract --pull-missing --sync`, and extended the
explanation: `--extract` is there because the spoken spelling of apostrophe words comes from the
extraction (`extract_words()`'s `originals` mapping merged into `names`), not from `missing.txt`,
which has already lost its apostrophes before it's written to the card (per the existing Known
limits bullet on that same page). Searched the whole repo for other occurrences of
`--pull-missing --sync`; the only other places it appears are historical measurement entries in
`docs/measurements/2026-09-24-voice-rollout.txt` (lines 23, 74, 166) and planning docs under
`docs/superpowers/plans/` and `docs/superpowers/specs/`, which are out of scope (records of what
was actually run / historical design docs, not the "routine command" being corrected, and not in
the allowed commit file list).

## Verification

**`python3 -m py_compile tools/voice_build.py`**

```
(no output, exit 0)
```

**`tools/voice_build.py --check --out /private/tmp/claude-501/-Users-robin-Downloads-flipper-access/7e5c805a-c471-4df7-96ca-14e7ee87ded9/scratchpad/fw1/chk`**

```
check settings: ok 0.61 s, quiet edges True, peak ok True 
check sub: ok 0.43 s, quiet edges True, peak ok True 
check gigahertz: ok 0.70 s, quiet edges True, peak ok True 
check one: ok 0.41 s, quiet edges True, peak ok True 
check ay: ok 0.79 s, quiet edges True, peak ok True 
check b: ok 0.79 s, quiet edges True, peak ok True 
check 7: ok 0.47 s, quiet edges True, peak ok True 
check okay: ok 0.57 s, quiet edges True, peak ok True 
check home: ok 0.41 s, quiet edges True, peak ok True 
check percent: ok 0.57 s, quiet edges True, peak ok True 
EXIT_CODE=0
```

Ten of ten `ok`, exit 0, as required.

## Files touched

- `README.md`
- `docs/measurements/2026-09-24-voice-rollout.txt`
- `tools/voice_build.py`

`voice/` (the built vocabulary) was not touched. No firmware files were touched. No device was
accessed.
