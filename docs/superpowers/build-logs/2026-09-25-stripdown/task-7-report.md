# Task 7 report: Documents

Commit: `1c687bc` "docs: stripdown as built; README without SAM, with the Animations row and the
card changes" on branch `main`, project repo. Only the three named files were staged and
committed (`git add README.md docs/roadmap.md
docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md`, then `git commit -m "..." --
<the same three files>`); not pushed. Working tree is clean after the commit.

## What I read first

- The task brief: `.superpowers/sdd/2026-09-25-firmware-stripdown/task-7-brief.md`.
- The stripdown spec: `docs/superpowers/specs/2026-09-25-firmware-stripdown-design.md` (all 13
  sections).
- The measurements file in full: `docs/measurements/2026-09-25-stripdown.txt` (all sections:
  Flash, Static RAM, Idle heap, RAM probe, Device pass 1-8).
- The three target files in full, before editing.
- Spot-checked several documented facts against the read-only firmware repo
  (`Momentum-Firmware/`, branch `screen-reader`, head `cc7212c6c`): `fbt_options.py`'s exclusion
  lists, `tests/fbt/test_exclusions.py`'s existence, `animation_manager.c`'s guard functions and
  the `anims_enabled` latch in `animation_manager_alloc`, `SpeechVoiceStats.muted`'s doc comment,
  and `subghz/application.fam`'s `apptype=FlipperAppType.APP`. All matched what I wrote.

## Design spec: `docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md`

- Head of section 8: inserted the exact paragraph the brief specified ("SAM left the firmware on
  2026-09-25 ... section 18 says what remains."), right after the "## 8. Speech engine" heading,
  before the existing "Source: the SAM code ..." paragraph. Nothing else in section 8, or in any
  section 1-17, was touched (they stay as history, per the brief).
- New "## 18. Stripdown as built (2026-09-25)" appended at the end of the file, covering, in
  order: the build options and what they exclude (with the two build-config deviations and their
  reasons: `test_js` had to be named explicitly because of the plugin-parent rule, `js_app` also
  had to leave the `system_apps` metapackage); the JavaScript engine out (API kept at 87.2, and
  why); Sub-GHz built in; SAM out of the engine (mute semantics, the missing-letter rule,
  `speech_set_volume`, `SpeechVoiceStats.muted`, the settings fields removed, the Rate/Voice rows
  gone, the chunking gone, the SAM tests/tools gone); the `desktop_anims` setting, the six named
  guards, the level-up rule (written with the exact sentence the brief specified: "granted at the
  next dolphin deed or card event, or at boot once the final fix of this round is in"), and the
  reboot rule; the animation-manager-latch deviation with its reason (crash-window avoidance); the
  card cleanup by the updater and the eleven Apps-browser folders; and the Task 6 figures (flash
  after each step, idle heap on/off with the "new mail" animation caveat, the Sub-GHz and NFC rows
  of the RAM probe).

## `docs/roadmap.md`

- Status line (was line 5): now says "Status on 2026-09-25 ... the memory plan (steps 2 to 4: ...)
  are done. Next: the fork and release mechanics."
- "Why a fork" JS figure (was line 11): "(on the order of 100 KB of flash)" became "(41 KB of
  flash, measured)".
- Memory-plan list items 2, 3, 4: rewritten as "done 2026-09-25" with figures (idle heap for
  animations; JS-out and Sub-GHz-in flash deltas, the API decision, and Sub-GHz's free heap with
  the reader on; SAM-out flash and static-RAM savings and the final image size). Item 1 (recorded
  voice) untouched.
- Licensing line (was line 44): removed the SAM sentence, kept the GPL-3 clause and the Piper
  clause.
- Also fixed, beyond the brief's explicit line list, because leaving them would have failed the
  self-review gate ("no sentence still says ... Sub-GHz does not fit"): the "Documentation for
  blind users first" bullet's known-limits parenthetical dropped "Sub-GHz memory until step 3"
  (that step is now done); the "Memory plan, in order" intro sentence was changed from present to
  past tense ("Where phase 3 and the polish round left it, before this plan: ... ran out of memory
  and restarted the device") so it reads as history, not a current claim, and gained a pointer to
  step 4's final figures.

## `README.md`

- Device state: the Firmware bullet now names the 2026-09-25 stripdown round, commit `cc7212c6c`,
  API 87.2, and the final flash figure. Added a bullet that the games, the JavaScript runner and
  the screen reader's own SAM synthesizer are gone. Rewrote the Sub-GHz bullet: built into the
  firmware again, works with the reader on (53,064 / 51,136 bytes), and NFC read is now the
  heaviest app (23,232 bytes) — this replaces the old predictive bullet about the recorded voice's
  ring cutting into a Sub-GHz-still-crashes future. Left the Text to SAM app bullet in place, with
  one added clause noting it's Momentum's own app, separate from our engine.
- Back chords: removed the "speech rate has no chord ... `sr rate`" bullet.
- Accessibility settings: "five rows with the recorded voice, six with SAM" became "four rows";
  removed the Voice and Rate bullets; the four remaining rows (Screen Reader, Volume, Verbosity,
  Change delay) are unchanged.
- Home screen section: added a paragraph that animations are off by default (so no idle animation
  or bubble), where the Animations row lives (Momentum, Interface, Graphics, first row, OFF/ON),
  and that changing it reboots the device; kept the bubble-timing sentence but scoped it to "With
  animations on".
- Locking and unlocking: checked against the brief's item 8 and the measurements file's Device
  pass step 3. The section already said "Select Lock in the lock menu and press OK. A short list
  offers Keypad Lock, PIN Code Lock and PIN Lock + OFF ... Up and Down choose, and OK locks" —
  this already describes OK-on-Lock opening a three-item menu with OK-on-Keypad-Lock (the default
  focus) locking, matching the observed flow exactly. No edit was needed here; I did not change
  it.
- Known limits: removed the Sub-GHz and the dolphin-bubbles bullets; added the exact sentence the
  brief specified about the SD card and `/ext/sr/voice`.
- Folder contents: `tools/run_host_tests.sh`'s description dropped "the SAM port (checked against
  the original C++ synthesizer)" and gained "finishing with `tests/fbt/test_exclusions.py`";
  removed the dedicated `tools/sam_calibrate.py` bullet; added a `tests/fbt/test_exclusions.py`
  bullet.
- Useful commands: dropped `sr rate <40..120>` from the saved-settings sentence; replaced the
  `tools/sam_calibrate.py --verify` sentence with "`sr voice off` mutes until `sr voice on` or a
  reboot; the generator uses it around a sync."
- Recorded voice: "from the SD card instead of SAM" became "from the SD card"; "SAM speaks a
  letter only when its clip is missing too, and everything when the voice is off" became "A
  letter whose clip is missing too is skipped and noted; with the voice off nothing is played."
  Console commands: the `sr voice on`/`sr voice off` bullet rewritten as mute/unmute, not saved,
  on after reboot (SAM is no longer an alternative to switch to); `sr voice status` gained an
  "items completed muted" bullet. Sync note: "the saved setting then stays off, and the device
  speaks with SAM until `sr voice on` is typed" became "the device stays muted until `sr voice on`
  is typed or it reboots."
- Plan: item 8 marked done (2026-09-25) with one line per change (build exclusions, Sub-GHz back
  in, animations off by default, final flash/heap figures); item 9 added ("the fork and release
  mechanics").
- Also changed, for internal consistency: "Last updated 2026-09-24" in the opening paragraph
  became "2026-09-25", since the file now documents the 2026-09-25 round throughout.

## Figures quoted, and their source

Every flash and RAM figure I wrote in all three files traces to
`docs/measurements/2026-09-25-stripdown.txt`, cross-checked line by line while drafting:

- Round-start flash 877,036 (3,604 spare); JS-out 835,748 (44,892 spare, 41,288 less); Sub-GHz-in
  877,776 (2,864 spare, 42,028 more); SAM-out 862,432 (18,208 spare, 15,344 less); animations
  862,588 (18,052 spare, 156 more); round total 14,448 less — all from the "Section: Flash" block
  (lines 10-16).
- Static RAM 5,897 now vs 9,580 before, 3,683 less — "Section: Static RAM" (line 29).
- Idle heap 116,672 / 116,752 (animations off, two boots) and 116,736 (animations on, but reading
  the built-in "new mail" animation, not a card one) — "Section: Idle heap" (lines 36-41) plus the
  ruling at line 43 that ties it to a pending dolphin level-up.
- Sub-GHz Read 53,064, Frequency Analyzer 51,136, and the 2026-09-23 comparison (Read 2,080,
  Frequency Analyzer crashed) — "Section: RAM probe" (line 50).
- NFC Read 23,232 — same section (line 51).
- The eleven Apps-browser folders and their names — "6. The card" (lines 666-681).
- "Excluded 45 external apps by configuration" and "API version 87.2 is up to date" — quoted
  verbatim from lines 18-19.
- The "41 KB of flash, measured" wording in the roadmap is the brief's own specified phrase for
  that line; 41,288 bytes is closer to 40 KB at 1024 bytes/KB, but matches "41 KB" as a decimal
  (1000-byte) rounding, and I used the brief's exact wording as instructed.
- The lock-flow reading ("PIN Code Lock. PIN Lock + OFF. Keypad Lock, 1 of 3") used to verify the
  README's "Locking and unlocking" section is from "3. Lock and unlock" (lines 225-232).
- Code-level facts (guard function names, the `desktop_anims` field, `SpeechVoiceStats.muted`,
  the exclusion lists, `subghz`'s `apptype`) were verified directly against the read-only
  `Momentum-Firmware/` tree, not just the spec prose.

## Self-review

- Every figure quoted in the three files appears in `docs/measurements/2026-09-25-stripdown.txt`
  with the same value (checked above), except the one figure the brief itself dictated verbatim
  ("41 KB of flash, measured" for the roadmap's JS line), which I used as given.
- Grepped all three files afterward for "SAM speaks", "does not fit", "runs out of memory" /
  "restarts the device" (present tense), "bubbles are read" (unqualified), "Rate row", "Voice
  row", "five rows" / "six rows". Remaining hits are: the Text to SAM demo app's name (unrelated,
  Momentum's own app); the patch filename `text2sam-cli-mode.patch`; historical Plan entries
  ("Done: speech demo; SAM default voice judged intelligible", "Done: phase 2 ... SAM ..."), left
  as past-tense history; sections 16/17 of the design spec (explicitly out of scope, "do not
  rewrite the older sections"); the new section 18's own sentence "the Rate row and the Voice row
  are gone" (states their absence, not their existence); README's bubble sentence, now scoped to
  "With animations on"; and roadmap's memory-plan intro, now past tense and explicitly framed as
  "before this plan". No sentence I left standing makes a present-tense claim that SAM speaks,
  that Sub-GHz doesn't fit, that bubbles are read by default, or that the Rate/Voice rows exist.
- Section 18's deviations list is complete against the task's "what was built" list: the two
  build-config deviations (`test_js`, `js_app`/`system_apps`) with reasons; the animation-manager
  latch-at-alloc deviation with its reason; and the level-up timing sentence in the brief's exact
  wording. I did not label the long-screen ruling or the lock-flow observation as "spec
  deviations" in section 18, because the brief's explicit content list for section 18 only asked
  for flash figures, idle heap on/off, and the Sub-GHz/NFC probe rows from Task 6 — not those two
  items, which belong to README verification (lock flow, handled, no edit needed) and to
  Section 11's testing ruling (not requested for section 18).
- Re-read each edited passage once linearly, as prose, the way Robin's screen reader would
  present it: no tables, no layout-dependent phrasing, units spelled out where they carry
  numbers.

## Concerns

- None that block. One judgment call: the roadmap's "Documentation for blind users first" bullet
  and its "Memory plan, in order" intro sentence were outside the brief's literal line list, but I
  edited them anyway (see "Also fixed" above) because leaving them would have contradicted the
  explicit self-review gate. If the controller wants strictly brief-scoped diffs only, these two
  small edits (roadmap.md, the "known limits" parenthetical and the intro sentence's tense) are
  the ones to look at first; they are minimal and factual, not restructuring.
- "Locking and unlocking" in the README needed no change — I verified this rather than assuming
  the brief implied an existing bug. Flagging this explicitly in case the controller expected a
  visible diff there.
