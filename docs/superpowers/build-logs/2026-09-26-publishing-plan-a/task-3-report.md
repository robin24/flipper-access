# Task 3 Report: `tools/card_prune.py`, its test, and the card cleanup

Status: **DONE** — test written first and seen to fail for the right reason, tool written verbatim from the brief, test passes, runner updated and green end to end. On the device: the dry run's plan kept exactly the three folders the brief names, the real run removed the other 34 with no errors, the ten voice trial clips and their folder are gone, and the generator's routine pass restored the voice, pulled and cleared `missing.txt`, and left the voice on. Commit `3ade569` pushed to `origin/main`.

## Steps 1-5: host (TDD)

### Step 1-2: the failing test

Wrote `tests/fbt/test_card_prune.py` verbatim from the brief, then ran it:

```
$ python3 tests/fbt/test_card_prune.py
Traceback (most recent call last):
  File "/Users/robin/Downloads/flipper-access/tests/fbt/test_card_prune.py", line 11, in <module>
    from card_prune import DEFAULT_KEEP, plan  # noqa: E402
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
ModuleNotFoundError: No module named 'card_prune'
```
Exit code 1. Matches the brief's expectation exactly.

### Step 3-4: the tool, and the passing test

Wrote `tools/card_prune.py` verbatim from the brief. Then:

```
$ python3 tests/fbt/test_card_prune.py
card prune: 8 of 8 checks passed
```
Exit code 0 — all 8 checks pass.

This ran under the system `python3`, which has no `serial` module (`python3 -c "import serial"` → `ModuleNotFoundError: No module named 'serial'`), so the module-imports-without-pyserial requirement (the `except SystemExit` guard around the `flipper_cli` import) was genuinely exercised, not just present in the source.

### Step 5: the runner

Appended the brief's exact block to `tools/run_host_tests.sh` (same shape as the two `python3` blocks before it, at the end of the file). Ran the full runner:

```
$ ./tools/run_host_tests.sh
195 checks, 0 failures
speech text: 968 checks, 0 failures
speech queue: 156 checks, 0 failures
speech PCM: 597 checks, 0 failures
speech voice: 4433 checks, 0 failures
chords: 208 checks, 0 failures
throttle: 119 checks, 0 failures
fbt exclusions: 0 failures
subghz sources: 50 on disk, 50 quoted, 0 unquoted, 0 missing
card prune: 8 of 8 checks passed
```
Exit code 0, green end to end, ending with the card prune line as expected.

I also diffed the three fenced code blocks in the brief against the files on disk programmatically (`test file matches: True`, `tool file matches: True`, `runner block present at end: True`) — the test and tool are byte-for-byte what the brief specifies.

## Steps 6-7: device

Device confirmed idle at `/dev/cu.usbmodemflip_Delphi1` before starting. `tools/uart_log.py` (PID 90851, logging to `docs/measurements/logs/2026-09-25-uart.txt`) was running throughout and left untouched.

### Step 6: card prune, dry run then real

```
$ .venv/bin/python tools/card_prune.py --dry
running build 6451e86e; 37 folders in /ext/update; keeping 3: f7-update-1.4.3, f7-update-mntm-012, f7-update-mntm-screen-reader-6451e86e
would remove f7-update-mntm-screen-reader-08e80106
... (34 lines total)
would remove 34 folders
```
1.17 s total. The plan kept exactly the three folders the brief names — the two rollback packages and the running build's folder (hash `6451e86e`, as `info device` reports) — and nothing else. Per the binding rule, I checked this before running the real removal; it matched, so I proceeded.

```
$ .venv/bin/python tools/card_prune.py
running build 6451e86e; 37 folders in /ext/update; keeping 3: f7-update-1.4.3, f7-update-mntm-012, f7-update-mntm-screen-reader-6451e86e
removing f7-update-mntm-screen-reader-08e80106
... (34 lines total)
removed 34 folders
```
5.125 s total (`0.13s user 0.12s system`), no errors from any `storage remove`.

```
$ .venv/bin/python tools/flipper_cli.py "storage list /ext/update"
== storage list /ext/update
	[D] f7-update-1.4.3
	[D] f7-update-mntm-012
	[D] f7-update-mntm-screen-reader-6451e86e
```
Exactly the three kept folders remain. Matches the brief's expectation in full (37 total, 34 removed, the named three kept).

### Step 6: the ten voice trial clips

```
$ .venv/bin/python tools/flipper_cli.py "storage list /ext/sr/clips"
== storage list /ext/sr/clips
	[F] 1_samantha.raw 182276b
	[F] 2_samantha_hp.raw 182276b
	[F] 3_samantha_slow_hp.raw 200257b
	[F] 4_samantha_hp_loud.raw 182276b
	[F] 5_alex_hp.raw 219669b
	[F] 6_daniel_hp.raw 202897b
	[F] 7_fred_hp.raw 224502b
	[F] 8_fred.raw 224502b
	[F] 9_samantha_hp_g13.raw 182276b
	[F] 10_samantha_hp_g16.raw 182276b
```
Ten files, as the context said. Removed all ten plus the folder in one `flipper_cli.py` call (12 commands total, including the confirming list):

```
$ .venv/bin/python tools/flipper_cli.py "storage remove /ext/sr/clips/1_samantha.raw" ... "storage remove /ext/sr/clips/10_samantha_hp_g16.raw" "storage remove /ext/sr/clips" "storage list /ext/sr"
== storage remove /ext/sr/clips/1_samantha.raw
...(no output = no error, for all ten removes and the folder remove)...
== storage list /ext/sr
	[D] voice
	[F] missing.txt 70b
```
`clips` is gone; `voice` and `missing.txt` are present, as expected.

### Step 7: the routine generator pass

```
$ .venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync
extract: 6260 distinct strings from the firmware sources, 71 bubble texts
extract: 10517 words; longest: ...
card apps: 160 faps, 160 matched, 7627 words added; unmatched: (none)
voice: silenced for the transfer
>100%, chunk  1 of  1 @ 4.11 kb/s
skipped 7 words that cannot be clips
pulled 3 missing words from the device
voice: restored
10526 words, 4 to make with say Samantha rate 175 highpass 500 gain 1.3 soft 16000
made 4 clips, 0 failed, 2 s; vocabulary 10789 words in /Users/robin/Downloads/flipper-access/voice
voice: silenced for the transfer
... (chunked upload progress) ...
sync: 4 sent, 10785 skipped, 0 missing, 0 failed, 1 s
voice: restored
```
6.9 s total. 0 failed throughout.

```
$ .venv/bin/python tools/flipper_cli.py "sr voice status"
== sr voice status
voice: on, vocabulary yes say Samantha rate 175 highpass 500 gain 1.3 soft 16000, clips 1404, fallback 17, missing 7, muted 0, open max 66 ms, last 26 ms
```
Voice is on, with the Samantha settings line, as expected. Confirmed `missing.txt` is actually gone from the card (not just claimed by the log line):
```
$ .venv/bin/python tools/flipper_cli.py "storage list /ext/sr"
== storage list /ext/sr
	[D] voice
```
Only `voice/` remains under `/ext/sr` — `missing.txt` is cleared, `clips/` stays gone.

The `missing 7` in the status line is not the file (confirmed cleared above): I checked the firmware source (`speech_voice.c:114`, `speech.c:357-358`) — it's a live in-RAM counter of distinct missing words encountered since boot, incremented once per boot per word, independent of the `/ext/sr/missing.txt` file that `pull_missing()` reads and removes. Since the device hasn't rebooted, that counter carries over; it's cosmetic and not something the brief's expectations for this step depend on.

Never sent `loader close`. Never touched `/ext/sr/voice` except through this one `voice_build.py` command. Never touched the repository-root `voice/` directory directly (it's gitignored; `voice_build.py` writes there itself, as designed). Removed nothing from the card beyond the pruned packages and `/ext/sr/clips`.

## Step 8: commit and push

```
$ git add tools/card_prune.py tests/fbt/test_card_prune.py tools/run_host_tests.sh
$ git commit -m "card_prune: old update packages leave the card, the running build and the rollback packages stay

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>" -- tools/card_prune.py tests/fbt/test_card_prune.py tools/run_host_tests.sh
$ git push
```

Result: commit `3ade569`, pushed `d5eb9ae..3ade569 main -> main` to `origin` (the only remote). `git status` clean afterward. Diff stat: `tests/fbt/test_card_prune.py | 53 ++`, `tools/card_prune.py | 107 ++`, `tools/run_host_tests.sh | 7 ++`, 3 files changed, 167 insertions, 0 deletions — exactly the three files the brief names, nothing else staged or committed.

## Files changed

- `tools/card_prune.py` (new) — the prune tool, verbatim from the brief.
- `tests/fbt/test_card_prune.py` (new) — its test, verbatim from the brief.
- `tools/run_host_tests.sh` (modified) — appended the card-prune block, same shape as the two blocks before it.

## Deviations

None from the required code or commands. The task's per-step attribution line differs from the brief's literal text: the brief's own commit-message block ends with `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`, but my task instructions explicitly said to end the message "with your own Co-Authored-By line as your harness gives it" — so I used `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` (this session's actual attribution) instead of copying the brief's literal name. This was an explicit instruction, not an improvisation.

## Concerns

None blocking. Two things worth flagging for the record, both already resolved above:

1. The generator's actual numbers (3 words pulled, 4 clips made) came in under the brief's "about seven" estimate, and the whole pass took under 7 seconds rather than the context's "one to three minutes" estimate — both were stated as rough expectations, not requirements, and every actual pass/fail condition the brief lists (clips made and sent, voice restored, missing.txt cleared, status shows voice on with the Samantha line) was met.
2. The commit-attribution line was resolved per explicit task instruction (see Deviations) rather than left as an open question — noting it here only because a sibling task's report (Task 2) flagged a similar point as an unresolved concern; in this task the instructions were unambiguous.
