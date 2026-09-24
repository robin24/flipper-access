# Polish Round Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three things Robin asked for after a day of use: the Rate setting is shown only when SAM is the voice; rapid same-screen changes such as progress bars are spoken at most once per adjustable interval with the latest text; the vocabulary generator extracts the strings of the apps actually on the card.

**Architecture:** A pure, host-tested throttle module in the screen reader holds a same-screen change until an interval has passed since the last spoken change, always keeping the latest text; the service loop wakes when it is due. The setting `sr_change_ms` lives with the other reader settings and the Accessibility scene exposes it; the scene rebuilds its list when the voice changes so Rate appears only with SAM. The generator maps the `.fap` files on the card to their source folders through the application manifests.

**Tech Stack:** Momentum firmware (fbt, GCC 12, -Wall -Wextra -Werror), C11 host tests with clang and sanitizers, Python 3 generator with the firmware's storage helper.

**Spec:** docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md sections 6, 10 and 17; Robin's observations of 2026-09-24 (this plan's goal) are the requirement.

## Global Constraints

- Firmware repo /Users/robin/Downloads/flipper-access/Momentum-Firmware, branch screen-reader (head af4ee0952); project repo /Users/robin/Downloads/flipper-access, main (head bf6feee). Commit only your own files with explicit `git add` then `git commit -m "<subject>" -- <the same files>`; do not push; never commit inside applications/external; never delete or move the repo-root `voice/`.
- Image under 880,640 bytes: `tools/flash_headroom.sh` after every firmware build (4,584 bytes spare now; report the new figure). `./fbt` shows only "API version 87.2 is up to date" and the two pre-existing external manifest warnings; `./fbt lint` exit 0; host runner green with new tests under sanitizers.
- Device: /dev/cu.usbmodemflip_R0skie1; a background log capture holds the console (`pgrep -f flipper_log.py`, kill it before device work, restart it at the end with `nohup .venv/bin/python tools/flipper_log.py docs/measurements/logs/2026-09-24-session.txt > /dev/null 2>&1 &` from the project root); console via `.venv/bin/python tools/flipper_cli.py "<command>"`; never `loader close`; before a flash confirm idle (`loader info` no application, `sr status` announcements flat 30 s; the user may be using it, wait and retry up to ten minutes); `sr screen` first after a flash; leave the device idle on the home screen, reader on, voice on, speech idle.
- Announcements of kind SrAnnScreen, SrAnnFocus, SrAnnHome, SrAnnLock and SrAnnTyped are never delayed; only SrAnnChange (same-screen text changes) is throttled.

---

### Task 1: Change throttle in the reader, setting, console

**Files:**
- Create: `Momentum-Firmware/applications/services/screen_reader/sr_throttle.h`, `sr_throttle.c`; `tests/host/test_sr_throttle.c`; Modify: `tools/run_host_tests.sh` (append a block)
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_reader.c` (service loop and sr_process), `screen_reader_cli.c` (status line), `lib/momentum/settings.h` (`uint32_t sr_change_ms;`), `lib/momentum/settings.c` (default 1500, `setting_uint(sr_change_ms, 500, 3000)`)

**Interfaces:**
- Produces: `typedef struct { char text[SR_ANN_TEXT_MAX]; bool pending; uint32_t last_said_ms; } SrThrottle; void sr_throttle_init(SrThrottle*); bool sr_throttle_offer(SrThrottle* t, const char* text, uint32_t now_ms, uint32_t interval_ms);` (true: say it now and record now; false: held as pending, replacing any earlier pending text); `bool sr_throttle_due(SrThrottle* t, uint32_t now_ms, uint32_t interval_ms, char* out, size_t out_size);` (true when a pending text's time has come: copies it out, clears pending, records now); `uint32_t sr_throttle_wait_ms(const SrThrottle* t, uint32_t now_ms, uint32_t interval_ms);` (0 when nothing is pending or it is due, else the remaining time); `void sr_throttle_clear(SrThrottle* t);` (a new screen or focus drops the pending change). `momentum_settings.sr_change_ms`.

- [ ] **Step 1: Test first**

Create `tests/host/test_sr_throttle.c` with the usual CHECK macro and these cases: init → offer("12 percent", 1000, 1500) is true (first change speaks at once); offer("15 percent", 1300) false and pending; offer("19 percent", 1700) false, pending replaced (due returns "19 percent", not "15 percent"); wait_ms at 1700 is 800 (2500 − 1700); due at 2400 false; due at 2500 true with "19 percent", pending cleared, wait_ms 0; offer("done", 2600) false (interval from 2500), due at 4000 true "done"; clear drops a pending text (due false); offer after clear at any time speaks at once only when interval has passed since last_said (a clear does not reset last_said); interval 0 always speaks at once; text longer than SR_ANN_TEXT_MAX − 1 is cut; wrap-around of now_ms across 0xFFFFFFFF handled (offer at 0xFFFFFF00, due at 0x00000100 with interval 1000 true). Append the runner block like the others (`test_sr_throttle.c` with `sr_throttle.c`, `-I "$SRC"`). Run: compile failure.

- [ ] **Step 2: The module**

`sr_throttle.c`: tick arithmetic with `(uint32_t)(now - last)` so wrap-around works; `offer` copies the text with strncpy and a terminator. `sr_throttle.h` documents each function as above. Runner green. Commit firmware "screen reader: change throttle module" and project "host tests: change throttle".

- [ ] **Step 3: The reader uses it**

In `screen_reader.c`: add `SrThrottle throttle;` to the struct, init at start. In `sr_process`, where an announcement of kind SrAnnChange would be passed to speech (after the desktop suppression decision): `if(sr_throttle_offer(&sr->throttle, a->text, furi_get_tick(), momentum_settings.sr_change_ms)) speech_say(... as today ...);` else nothing (the text is held). For every other kind that is spoken, call `sr_throttle_clear` first (a new screen, focus, home, lock or typed announcement supersedes a held change). In the service loop, compute the wait timeout as the minimum of today's timeout and `sr_throttle_wait_ms(...)` when something is pending (a pending change with wait 0 must be handled without waiting); after the wait, if `sr_throttle_due(&sr->throttle, furi_get_tick(), momentum_settings.sr_change_ms, text, sizeof)` returns true, `speech_say(sr->speech, text, false, true)` (not interrupting, replaceable, like a change). A key press (the existing input callback) does not clear the throttle, so a change made by the key is still spoken on time. Setting: `sr_change_ms` default 1500, range 500..3000, registered in the table; `sr status` prints `change delay N ms` on the rate line; `sr delay <ms>` sets and saves it (add to the usage text). Commit firmware "screen reader: same-screen changes spoken at most once per change delay".

- [ ] **Step 4: Build, flash, verify**

`./fbt`, `./fbt lint`, headroom, runner. Stop the log capture, idle check, `./fbt flash_usb`, `sr screen`, `info device`. Verify, verbatim: (1) Infrared, Universal Remotes, TVs, OK on Power (the sending popup with its percentage): count the utterances over the send (`sr status` before and after, and `sr watch` lines): at 1500 ms the announcements are spaced by at least the delay and the last one is the final state, never every step; (2) `sr delay 3000`, the same send: fewer announcements; `sr delay 500`: more; restore 1500 (`sr delay 1500`); (3) a focus change during a running bar is spoken at once (move in a menu while something changes, or use `sr say` timing with `sr watch`); (4) sr_drive's three sessions still pass (`--chords` included). Restart the log capture. Leave the device idle.

---

### Task 2: Accessibility scene: Rate only with SAM, Change delay item

**Files:**
- Modify: `Momentum-Firmware/applications/main/momentum_app/scenes/momentum_app_scene_accessibility.c`

**Interfaces:**
- Consumes: `momentum_settings.sr_voice`, `sr_change_ms` (Task 1), the existing items.
- Produces: the list rebuilt on a Voice change: with Recorded selected the rows are Screen Reader, Voice, Volume, Verbosity, Change delay; with SAM: Screen Reader, Voice, Rate, Volume, Verbosity, Change delay; the selection stays on the Voice row after a rebuild; Change delay shows "0.5 s" to "3 s" in steps of 0.5 (values 500 to 3000, index = (ms − 500) / 500, 6 values), writes `sr_change_ms` and sets `app->save_settings`.

- [ ] **Step 1: The scene**

Move the item construction into a static `build_list(app)` that resets the list, adds the rows in the order above (skipping Rate when `sr_voice` is true), sets each item's index and text as today, and finally `variable_item_list_set_selected_item(list, index_of_voice_row)` when called from the voice callback (pass the wanted selection as a parameter; on enter select the first row). The Voice change callback writes the setting, sets save_settings, then calls `build_list(app, VoiceRow)`. Because item indices shift when Rate is hidden, keep an enum for the row order and compute the Voice row's index for both layouts. Change delay: label "Change delay", 6 values, text `"%d.%d s"`-style without floats (500 → "0.5 s", 1000 → "1 s", 1500 → "1.5 s", 2000 → "2 s", 2500 → "2.5 s", 3000 → "3 s"), nearest-step index on enter like Rate.

- [ ] **Step 2: Build the fap, copy, verify, commit**

`./fbt fap_momentum_app`, `./fbt lint`, copy to the card path used before; device: open the app, Accessibility: with Voice Recorded the rows read without Rate; change Voice to SAM → the list is rebuilt, the focus stays on Voice, Down reaches Rate; back to Recorded → Rate gone; Change delay left/right moves in 0.5 s steps and `sr status` shows the new change delay after the next announcement; leave the app; the values persist. Commit "momentum settings: Rate only with SAM; Change delay".

---

### Task 3: Generator: the apps on the card

**Files:**
- Modify: `tools/voice_build.py`, `README.md` (the routine command and one paragraph), `tools/voice_words.txt` if a needed word is found

**Interfaces:**
- Produces: `--card-apps` (needs the device: `storage list` of `/ext/apps` and its category folders gives the `.fap` file names; each `<appid>.fap` maps to the directory whose `application.fam` declares `appid="<appid>"` under applications/external, applications/main, applications/system, applications/settings or applications/debug; every `.c` and `.h` under that directory is extracted like the core sources; a fap without a matching manifest is listed as skipped) and `--extract-all` (every app directory under applications/external), both feeding the same word pipeline; the run prints how many apps matched and how many words they added.

- [ ] **Step 1: Implement and check**

Parse manifests with a regex for `appid\s*=\s*"([^"]+)"` (a manifest may hold several App(...) blocks: take every appid). `--card-apps` opens the storage helper with the same voice guard as sync (the voice off while listing is not needed: listing is read-only; reuse `open_storage` without the guard), walks `/ext/apps` two levels deep (category folders), collects `*.fap` base names, maps them, extracts. Print "card apps: N faps, M matched, K words added; unmatched: a, b". `--extract-all`: all manifests under applications/external. Check without the device: `--extract-all --out <scratch> --limit 0`? (`--limit 0` means no limit today; use a dry mode: add `--dry` that builds the word list and prints the counts without making clips.) Run `--extract --extract-all --dry` and report the word count (expect several thousand). Then the device run: stop the log capture, `.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync --jobs 8` (report the matched apps, the new word count, the build time and the sync time; a few thousand new clips may take 20 to 40 minutes: say so before starting), then open BLE Spam (`loader open "BLE Spam"` or its name from `loader list`), navigate three screens with `input send down short` and `sr screen`, and read `sr voice status`: fallback must not rise; leave the app; restart the log capture. README: the routine command becomes `tools/voice_build.py --extract --card-apps --pull-missing --sync` with a sentence on `--extract-all`. Commit "voice_build: strings of the apps on the card; extract-all; dry run".
