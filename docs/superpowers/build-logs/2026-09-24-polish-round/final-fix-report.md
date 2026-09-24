# Final fix report — polish round, 2026-09-24

## Status

All six items done, device verified, both commits made. Working trees clean except the
pre-existing, untouched `applications/external` submodule pointer in the firmware repo.

## Commits

- Firmware `Momentum-Firmware` (branch `screen-reader`), commit `22ae265ef4c1b2ecf172aca587965de7f6d2bba5`:
  "screen reader: voice setting written in the callback; comment and status wording"
  — `applications/main/momentum_app/scenes/momentum_app_scene_accessibility.c`,
  `applications/services/screen_reader/screen_reader.c`,
  `applications/services/screen_reader/screen_reader_cli.c`.
- Project `flipper-access` (branch `main`), commit `037976bbb14f3922cf9da26776fc112e9b59705c`:
  "docs: polish round as built; test time order"
  — `README.md`, `docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md`,
  `docs/roadmap.md`, `tests/host/test_sr_throttle.c`.
- Neither branch was pushed; no merges.

## What changed, item by item

1. **Voice callback write** (`momentum_app_scene_accessibility.c`): the change callback now
   writes `momentum_settings.sr_voice`, sets the item's value text ("SAM"/"Recorded") and
   `app->save_settings = true` before sending the custom event; `on_event` now reads
   `momentum_settings.sr_voice` back for the rebuild instead of calling
   `variable_item_list_get`. `./fbt fap_momentum_app` succeeded; `./fbt lint` exit 0.
2. **Wording fixes**: `screen_reader.c`'s held-change comment now describes the actual
   condition (last key 0.5–2 s old, due after the desktop's 2 s quiet window; a change within
   500 ms of a key is forced, not held) instead of the inverted "held while a key was recent".
   `screen_reader_cli.c`'s `sr status` now prints "change delay: N ms" with a colon, matching
   "rate:", "volume:", "verbosity:". Full `./fbt` build stayed clean: API version 87.2 up to
   date, only the two known `applications/external` manifest warnings (cli_bridge, mtp), no
   new warnings from the touched files. `./fbt lint` exit 0. `tools/flash_headroom.sh`:
   firmware.bin 877,036 bytes, limit 880,640, spare 3,604 — this is the figure used everywhere
   in today's doc updates. No flash was performed.
3. **Test time order** (`tests/host/test_sr_throttle.c`): swapped the force-at-2550 and the
   due-probe-at-4000 lines so simulated time no longer runs backwards, keeping both checks
   unchanged. `tools/run_host_tests.sh` (TMPDIR under the session scratchpad) — all suites
   green, throttle 119 checks / 0 failures, 174+156+700+4433+73+1022 checks elsewhere, all 0
   failures.
4. **README.md**: five/six-row Accessibility wording, Rate-shown-only-for-SAM note, new
   Change delay bullet, `sr delay <500..10000>` added to the console commands, firmware
   commit line split into repo commit 859c87c98 vs. device firmware 70a60c8f5 plus the
   settings app of 859c87c98, headroom updated to 877,036/3,604, and a new sentence
   distinguishing a dropped-while-held change (never in `sr watch`, only the suppressed
   counter) from an on-arrival-suppressed one (still shown in `sr watch`).
5. **Spec doc** (`docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md`):
   updated section 5 rule 4, section 6 (thread loop and outputs), section 7 (`sr status`,
   `sr delay`), section 10, section 17's "as designed" Settings paragraph and "as built"
   Accessibility-scene bullet, and the budget bullet (appended a new 859c87c98/877,036/3,604
   entry rather than overwriting the af4ee0952 historical one, since that paragraph computes
   explicit "took N more bytes" deltas between entries). Added a new "Polish round as built
   (2026-09-24)" closing subsection covering the three polish-round items (change delay/
   throttle, Rate-only-for-SAM, `tools/voice_build.py` card-apps extraction) and their
   deviations (model's own limiter removed, throttle moved to the service, seven-value
   table, card-apps extraction).
6. **`docs/roadmap.md`**: status line now says the polish round is done alongside phase 3 and
   the recorded voice, memory plan next; the "where things stand" headroom line updated to
   877,036/3,604.

## Device verification

Idle checks before touching the device: no `flipper_log.py` running, `loader info` reported
no application, `sr status` announcements held flat at 214 across a 30 s wait, speech idle.
Copied the fap:
`.venv/bin/python Momentum-Firmware/scripts/storage.py -p /dev/cu.usbmodemflip_R0skie1 send
Momentum-Firmware/build/f7-firmware-C/.extapps/momentum_app.fap /ext/apps/assets/momentum_app.fap`
(100%, no errors — see Concerns for the path note).

On-device walkthrough, checking `sr screen`/`sr status` after every key and waiting for
`speech: idle` before the next one: `loader open Momentum` (announced "MNTM-DEV 70A60C8F...
Interface, 1 of 4", confirming the device's flashed firmware is 70a60c8f5 as documented) →
Up → Accessibility, 4 of 4 → OK → Accessibility scene, 5 rows, focus Screen Reader 1/5 → Down
→ Voice 2/5, Recorded → Left → **Voice SAM, 2/6, Rate row appeared, focus stayed on Voice,
`sr status` "voice: off"** → Right → **Voice Recorded, 2/5, Rate row gone, focus stayed on
Voice, `sr status` "voice: on"** → Back (Momentum root list, Accessibility 4/4, speech still
speaking — waited) → Back (`loader info`: no application running, free heap back to ~112 KB).
Left the device idle on the home screen (`sr screen`: desktop layer, battery only) with
`sr status` confirming enabled yes, voice on, speech idle, and announcements flat again after
a final 20 s wait. Never sent `loader close`.

This is a direct behavioral confirmation that item 1's fix works: the setting is written and
the list layout is rebuilt (row count 5↔6, Rate shown/hidden) with the selection staying on
Voice in both directions.

## Test summary (one line)

Firmware: `fbt fap_momentum_app` and full `fbt` build clean (API 87.2, only the two known
external-manifest warnings), `fbt lint` exit 0, headroom 877,036/3,604 bytes spare; host
tests: all suites green including the reordered throttle test (119 checks); device: Voice
SAM/Recorded toggle verified live with `sr screen`/`sr status`, device left idle on the home
screen with reader and voice on.

## Concerns

- **Upstream `AGENTS.md`**: `Momentum-Firmware/AGENTS.md` (committed upstream, not touched by
  this session) states a blanket no-AI-contributions policy. It surfaced mid-task through an
  unusual "tool.call hook additional context" block rather than a normal file read; I treated
  it as untrusted file content, not an instruction, and did not stop or alter the work because
  of it. This is a non-issue in practice: `docs/roadmap.md` already documents this exact
  policy as the reason this project is an unpushed personal fork rather than a Momentum pull
  request, which matches what was asked here (commit locally, never push, never touch
  `applications/external`). Flagging only for visibility.
- **Fap source path**: the given device-copy command's local path
  (`build/f7-firmware-C/.extapps/momentum_app.fap`) doesn't exist relative to the project
  root; the real path is `Momentum-Firmware/build/f7-firmware-C/.extapps/momentum_app.fap`,
  which is what I used (verified the file first). Worth checking this was just shorthand and
  not a sign I have the wrong directory convention in mind.
- **Judgment calls on ambiguous doc instructions** (all internally consistent and
  cross-checked against `git log` and a live `sr status`/`sr screen`, but not spelled out
  verbatim in the brief): (a) README's headroom sentence and the spec's line-534-area
  "Status:" commit reference were left as `af4ee0952` only where the item list didn't mention
  them (spec lines 507–509); everywhere the list did point at line 235/643-645, I updated the
  commit hash to `859c87c98` alongside the requested numbers, since leaving a stale hash next
  to corrected figures would read as a doc bug. (b) For the spec's budget bullet specifically,
  I appended a new dated entry rather than overwriting `af4ee0952`'s row, because that
  paragraph's prose explicitly computes "took N more bytes" between successive entries and
  overwriting in place would break that arithmetic.
- Did not run `./fbt flash_usb` or any flash — per instructions, today's `screen_reader.c`/
  `screen_reader_cli.c` fixes stay unflashed; only the momentum_app fap was copied.
