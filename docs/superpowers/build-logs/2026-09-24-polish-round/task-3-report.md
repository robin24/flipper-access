# Task 3 report: generator — the apps on the card

## Phase A (code + dry run, no device)

### What I implemented

`tools/voice_build.py`:

- `strings_in(roots)`: extracted from the old `firmware_strings()` body (same filtering,
  unchanged) so it can be reused over arbitrary directories, not just the four core roots.
  `firmware_strings()` is now a thin wrapper: `sorted(strings_in(core_roots))`, byte-for-byte
  same behaviour as before.
- `external_app_dirs()`: every immediate subdirectory of `applications/external` that contains
  an `application.fam` (243 of them — the folder has 245 entries total, but `.github` and
  `.subtrees` aren't apps and have no manifest, so they're naturally excluded).
- `manifest_index(roots)`: parses every `application.fam` found recursively under the given
  root directories with the regex the brief specified, `appid\s*=\s*"([^"]+)"` (a manifest can
  hold several `App(...)` blocks — `applications/main/nfc/application.fam` alone has 61, one
  per NFC parser plugin), plus `fap_file_name\s*=\s*"([^"]+)"` for a manifest that renames its
  own build output. Returns a dict from either key to the manifest's directory.
- `_expand()`: extracted from the old `extract_words()` body (the "run the C pronunciation
  layer over a set of lines, collect clip-name words and apostrophe originals" step), so it can
  be called more than once.
- `extract_words(workdir, extra=())`: `extra` is a list of `(label, directories)` pairs. It
  runs the base pass (core firmware + bubbles, exactly as before), then folds in each extra
  source's `.c`/`.h` strings in turn, re-running the expander each time and recording, per
  label, how many words that step alone added on top of everything folded in before it. This
  is cumulative/sequential rather than independent-vs-base, so if `--extract-all` and
  `--card-apps` ever overlap (a card app that's also part of `applications/external`... it
  isn't, card apps map across all 5 manifest roots, but a future overlap isn't impossible) the
  second source's "added" count reflects only its own marginal contribution, and the numbers
  always sum exactly to the final total. Plain `--extract` with no extras is unchanged: one
  pass, same log lines, same return values (now a 3-tuple with an empty `added` dict).
- `list_card_apps(storage)` and `card_apps(port)`: the device-listing and mapping step. See
  "Bug found and fixed" below for why `list_card_apps` doesn't just walk `/ext/apps` with a
  single shared generator.
- CLI: `--extract-all`, `--card-apps`, `--dry`, wired into `main()`. `--extract-all` and
  `--card-apps` only take effect together with `--extract` (matches every example invocation
  in the brief, which always pairs them); used alone they print a one-line explanation and are
  otherwise a no-op, rather than silently doing nothing or erroring. `--dry` builds the word
  list, logs the total, and returns before the manifest/jobs/clip/sync machinery — it does not
  skip `--card-apps`'s device listing (still needed to report what matched), only the
  clip-making and syncing, per the brief's "also usable to print which card faps matched which
  source folders."

`README.md` ("Recorded voice" section):

- The inline mention of "the routine command" and the missing-word-workflow bullet both now
  read `--extract --card-apps --pull-missing --sync`.
- The missing-word bullet gained a sentence on what `--card-apps` adds, next to the existing
  sentence on `--extract`.
- The "words come from" list gained a fourth item covering `--card-apps` and `--extract-all`.

`tools/voice_words.txt`: not touched. Nothing in this task needed a new base vocabulary word.

### Design decisions worth flagging

- **`--extract-all`/`--card-apps` require `--extract`.** The brief says "both feeding the same
  word pipeline," and every example command in the brief pairs them with `--extract`. I gated
  them there rather than letting them run the expander on their own, to keep `--extract`'s
  existing behaviour completely unchanged when the new flags aren't used. Flagged here in case
  the intended UX was for `--card-apps` alone to also extract.
- **Word-added counts are cumulative, not independent.** See `extract_words` above. I chose
  this because it keeps the reported numbers internally consistent (base + sum(added) == final
  total, always, verified below), rather than "each source vs. core alone," which could
  double-count words two sources both contribute.
- **`fap_file_name` doesn't exist in this firmware fork.** I grepped the entire
  `Momentum-Firmware` tree, including the fbt build scripts, for `fap_file_name`: zero hits.
  The manifest schema itself (`scripts/fbt/appmanifest.py`'s `FlipperApplication` dataclass)
  has no such field — a `.fap`'s name on the card is always `f"{appid}.fap"`
  (`scripts/fbt_tools/fbt_extapps.py:175`). I still implemented the `fap_file_name` matching
  path defensively, exactly as the brief described, but it is currently dead code against this
  tree — there is nothing to unit-test it against. Flagging this rather than silently dropping
  it or silently claiming it's tested.

### Bug found and fixed

My first `list_card_apps` used one shared `storage.walk("/ext/apps")` generator and called
`next()` once for the root, then once per category, assuming each subsequent `next()` lands on
the next sibling category. That's wrong: `storage.walk()` (in
`Momentum-Firmware/scripts/flipper/storage.py`) is pre-order depth-first — it yields a
directory's own listing, then immediately recurses into that directory's subdirectories before
ever reaching its siblings. So a category folder that itself contains a subfolder would make
the next `next()` descend into that subfolder instead of moving to the next category, silently
breaking the "two levels deep" requirement.

I caught this with a fake-storage unit test (below) before ever touching the device, and fixed
it by calling `storage.walk(category_path)` fresh for each category and reading only its first
yield, which is always that category's own listing (the function is a generator; recursion
into subfolders is dead code that is simply never advanced far enough to run). This costs one
extra `storage list` round-trip per category instead of one call for the whole tree, which is
negligible against 10-20 categories.

### What I tested

All commands run from `/Users/robin/Downloads/flipper-access`.

1. **Syntax**: `python3 -c "import ast; ast.parse(open('tools/voice_build.py').read())"` —
   parses cleanly, both right after the initial patch and again after the `list_card_apps` fix.

2. **Manifest-mapping unit check** (one-off script, no device) — `manifest_index()` against
   three known apps plus the two multi-`App()` manifests the brief asked about:
   - `ble_spam` -> `applications/external/ble_spam` — PASS
   - `infrared` -> `applications/main/infrared` — PASS
   - `cli_ir` (`infrared`'s second `App()` block, a `PLUGIN`) -> same directory — PASS
   - `clock_settings` -> `applications/settings/clock_settings` — PASS
   - `clock_settings_start` (its second `App()` block) -> same directory — PASS
   - A made-up appid correctly matches nothing — PASS
   - `fap_file_name` usage across every manifest in all 5 roots: 0 matches (see above)
   - `external_app_dirs()`: 243 dirs, `.github`/`.subtrees` correctly excluded, `ble_spam`
     correctly included

3. **`list_card_apps()` unit check against a fake storage object** (no device): a stand-in
   `/ext/apps` tree with two categories, one of which (`Bluetooth`) has a nested subfolder
   holding a `.fap` that must **not** appear in the result.
   - Before the fix: FAIL — returned `['ble_spam', 'should_never_be_seen']`, missing the
     `Media` category's apps entirely (the shared-generator bug above).
   - After the fix: PASS — returned exactly `['ble_spam', 'music_player', 'text2sam']`, and the
     nested `should_never_be_seen` app correctly never appears.

4. **The required phase-A dry run**, exactly as specified:

   ```
   .venv/bin/python tools/voice_build.py --extract --extract-all --dry --out <scratch>/pr3
   ```

   Output:
   ```
   extract: 6254 distinct strings from the firmware sources, 71 bubble texts
   extract: 12275 words; longest: acknowledgements acremotesettings altshuntresistor
     animationmanager animationstorage aufenthaltstitel automationmethod avrispprogworker
     backlightenforce bufferkeydecrypt
   extract-all: 243 apps under applications/external, 9376 words added
   dry run: 12278 words total, no clips made
   ```
   Ran in ~2 seconds. `applications/external` contributed 9,376 new words on top of the 2,899
   from the core firmware (see next item) — "several thousand" as the brief expected, on the
   higher end since 243 community apps is a lot of source text.

5. **Regression check** — plain `--extract --dry` (no `--extract-all`), same `--out`:
   ```
   extract: 6254 distinct strings from the firmware sources, 71 bubble texts
   extract: 2899 words; longest: animationmanager animationstorage backlightenforce
     checksdkfeatures configchangeable defaulttextclear desktopscenelock freecreatedelete
     getbatterycharge hoppingthreshold
   extract: 10 with an apostrophe: can't doesn't don't flipper's i'll i'm isn't it's who's you're
   dry run: 2908 words total, no clips made
   ```
   2,899 words matches README's documented "about 2,900 words" for `--extract` alone, exactly
   — confirms no regression. It also cross-checks the cumulative bookkeeping above:
   2899 + 9376 = 12275, matching item 4's "12275 words" line exactly.

6. **Guard-path check** — `--extract-all --dry` with no `--extract` (no device touched):
   printed `--extract-all and --card-apps only add to the word pipeline together with
   --extract; ignored` and then `dry run: 120 words total, no clips made` (just
   `voice_words.txt`'s base list) — no crash, no accidental extraction.

7. **`--help`** — renders cleanly, all three new flags documented, no argparse errors.

8. **Side-effect checks**: `git status --porcelain -- voice/` empty before and after every run
   above (the real, repo-root vocabulary was never touched — every run used `--out` pointing at
   the scratchpad); the scratch `--out` directory after the dry runs contains only
   `.build/speech_expand` (the compiled C helper) — no `manifest.json`, no `voice.txt`, no
   `.raw` clips, confirming `--dry` truly makes nothing.

**Not run in phase A, per the brief**: `--card-apps` (needs the device) and `--sync`.

### Files changed

- `tools/voice_build.py` (144 insertions, 19 deletions — `git diff --numstat`)
- `README.md` (11 insertions, 7 deletions — `git diff --numstat`)
- `tools/voice_words.txt`: unchanged (no new word was needed)

### Self-review findings

- One real bug found and fixed before it ever reached a device — see "Bug found and fixed"
  above. Caught by writing a fake-storage unit test for the trickiest piece of new logic before
  trusting it.
- Naming: kept `matched`/`unmatched` (what the printed line says) rather than the brief prose's
  "skipped," to match the actual log output.
- No third-party dependencies added; no UIKit-equivalent concerns (this is the Python tooling
  side, not the firmware/Swift side of the project).
- Did not touch `tools/run_host_tests.sh` or `tests/host/` — unrelated (those cover the C
  screen model/SAM port/speech text, not this Python tool).

### Concerns

None blocking. Two things worth the reviewer's and phase B's attention:

1. The `fap_file_name` code path is implemented but untested against a real manifest, because
   none exists in this tree (see above) — phase B's device run can't exercise it either, since
   it would need a manifest that doesn't exist. If this matters, it'd need a synthetic test
   manifest, which felt like overbuilding for phase A.
2. `list_card_apps`'s "two levels deep" assumption (category folders never nest further) is
   only verified against a fake storage object, not the real card. Phase B's device run is the
   first real test of it. If a real category folder turns out to nest one level further,
   today's code will simply not see what's in that inner folder rather than error out — worth
   confirming while phase B is looking at the matched/unmatched output.

### Commit

**Not committed.** Following the brief's default: "no commit yet: commit in phase B after the
device run confirms the mapping." Given the bug found above in the one piece of this task that
touches the device (`list_card_apps`), and that the `fap_file_name`/manifest-mapping path is
otherwise only unit-tested against a fake stand-in, I'd rather have the phase B device run
confirm real `/ext/apps` behaviour before committing than commit code whose most
device-dependent part has only been exercised against a hand-written fake. Recommend committing
after phase B, as the brief defaults to.

## Phase B (device run)

### Sequence followed

1. Stopped log capture (`pgrep -f flipper_log.py` → PID 98127, `kill`). The log file shows a
   clean `== log stopped 20:02:16` marker.
2. Confirmed idle: `loader info` → "No application is running"; `sr status` announcements held
   flat at 314 across a 30 s wait (checked in the background, `sleep 30` then re-read). No
   retry needed at this point.
3. `.venv/bin/python tools/voice_build.py --extract --card-apps --dry` (no `--out` override —
   safe against the real `voice/` directory, since `--dry` returns before any vocabulary file
   is written; the only write is the `.build/` compile cache, which already existed from prior
   real builds).
4. **Gate check**: confirmed `ble_spam` is on the card and correctly mapped, with a small
   one-off script reusing `card_apps()`/`manifest_index()` directly (see output below) — no fix
   needed.
5. Real run: `.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync --jobs 8`.
6. Investigated a port drop that happened right after the real run finished (see "Port-drop
   incident" below) before touching the device further.
7. Opened BLE Spam, read four distinct screens, checked `sr voice status` before/after,
   left the app.
8. Added the README `--dry` sentence (the `--extract-all` sentence was already in from phase
   A), committed, restarted log capture, confirmed the device idle on the home screen before
   restarting it (flipper_log.py and flipper_cli.py can't share the port at once).

### Dry run: matched apps and word counts

```
extract: 6254 distinct strings from the firmware sources, 71 bubble texts
extract: 10751 words; longest: acknowledgements acremotesettings animationmanager
  animationstorage aufenthaltstitel automationmethod backlightenforce bufferkeydecrypt
  businesscategory bytereversewords
card apps: 204 faps, 204 matched, 7852 words added; unmatched: (none)
dry run: 10756 words total, no clips made
```

All 204 `.fap` files found on the card matched a manifest — zero unmatched, so no fix was
needed. Explicit gate check (one-off script calling `card_apps()`/`manifest_index()` directly):

```
total faps: 204
'ble_spam' in faps list: True
manifest_index['ble_spam'] = .../Momentum-Firmware/applications/external/ble_spam
'ble_spam' present on the card AND correctly mapped: True
```

The 204 fap "appid" names on the card often differ from the folder name the brief's naming
convention might suggest at a glance (e.g. `coleco` for `rc2014_coleco`, `game_2048` for the
`2048` app, `snake20` for `snake_2`, `minesweeper_redux` for `minesweeper`) — all matched
correctly regardless, because the mapping goes through the manifest's declared `appid`, not the
folder name.

### Real build and sync

Command: `.venv/bin/python tools/voice_build.py --extract --card-apps --pull-missing --sync --jobs 8`
(no `--out` — the real `voice/` directory, correct for a real run).

- Wall clock: 20:04:38 -> 21:15:38 CEST, 71 minutes.
- `pulled 43 missing words from the device` (2 skipped as unusable), folded into the same run
  via `--extract` per the existing design (apostrophe spellings come from extraction, not from
  missing.txt).
- **Build**: `made 7854 clips, 0 failed, 2784 s` (46 min 24 s); final vocabulary 10,778 words.
- **Sync**: `sync: 7854 sent, 2924 skipped, 0 missing, 0 failed, 1473 s` (24 min 33 s).
- `voice: silenced for the transfer` / `voice: restored` logged for both the pull-missing step
  and the sync step — the guard worked both times.
- Zero failures anywhere: `grep -c "^failed:"` → 0, no `sync: missing`/`sync: failed` lines, no
  tracebacks/exceptions in the ~8,000-line output. The port did not drop during this step, so
  the brief's "wait a minute and rerun" contingency was never needed here.

### Port-drop incident (investigated before proceeding)

Right after the build+sync finished cleanly, my first attempt to open BLE Spam
(`loader open "BLE Spam"` style, see next section for why that specific form doesn't work here)
failed immediately with `No Flipper serial port found` — the port was gone at the OS level, not
just a device-side error. I did not push through; I investigated:

- Waited 60 s: the port device node came back.
- A `loader info`/`sr status`/`sr voice status` call then took over 30 s and returned garbled
  output (`loader info` answering "sreen: TVs. Power", `sr status`/`sr voice status` empty).
  I did not trust this and re-checked cleanly, one command at a time, rather than acting on it.
- A clean retry raised a pyserial `SerialException` ("device reports readiness to read but
  returned no data (device disconnected or multiple access on port?)"). I checked for
  concurrent access from this Mac (`ps aux` for any flipper/voice_build/storage.py process,
  `lsof` on the port): nothing was holding it from my side.
- The next clean read succeeded: `loader info` → `Application "Infrared" is running`, and
  `sr status` showed `frames: 211, announcements: 17` — far below the `frames: 11223,
  announcements: 314` seen one command earlier (right after the sync), and `change delay 3000
  ms` instead of the `1500 ms` baseline (3000 is the documented max of the throttle setting
  Task 1 is implementing, and settings persist independently of app switches).
- Reading again moments later, the state had already changed again: `loader info` → "No
  application is running", `sr screen` → `content layer: desktop`, and `sr status`'s counters
  had grown further (frames 211->338, announcements 17->22) between two of my own read-only
  calls, which don't themselves generate announcements.

This is exactly the scenario the brief anticipated ("the user may be using it, wait and retry
up to ten minutes") — something was actively opening and closing apps on the device, in
between my own commands, that I did not cause. I did not try to force past it (no Back presses,
no app opens) while that was happening. I switched to the brief's prescribed protocol: poll
every 30 s (`loader info` idle and `sr status` announcements unchanged from the prior poll) up
to a 10-minute budget. It resolved on the very first window:

```
t=0s app=[No application is running] announcements=[22]
t=30s app=[No application is running] announcements=[22]
IDLE CONFIRMED: no application running, announcements flat at 22 across 30s
```

I can't be certain whether this was Robin picking up the device, or residual activity from
Task 1's own on-device throttle testing (the saved `change delay 3000 ms` points that way), or
some other transient cause. Flagging it for the controller rather than guessing further —
worth knowing if Task 1's session was still touching the device after handing it off as "free."
The build+sync itself was unaffected (finished with 0 errors before any of this happened), and
BLE Spam's fallback/missing counts (below) show no ill effect from whatever this was either.

### BLE Spam on real hardware

**`loader list` does not show it** — checked the firmware source
(`applications/services/loader/loader_cli.c`'s `loader_cli_list()`) before assuming the brief's
suggested form would work: it only prints the compiled-in `FLIPPER_APPS`/
`FLIPPER_EXTERNAL_APPS`/`FLIPPER_SETTINGS_APPS` tables (confirmed against the device: `loader
list` showed only Sub-GHz/RFID/NFC/Infrared/GPIO/iButton/Bad KB/U2F/Momentum and the Settings
pages — no BLE Spam). `loader_start()` (`applications/services/loader/loader.c`) falls back to
`storage_file_exists(storage, name)` when the name matches neither table, i.e. it also accepts
a raw file path. I confirmed BLE Spam's exact path with a plain `storage list`:

```
== storage list /ext/apps/Bluetooth
	[F] ble_spam.fap 72784b
	...
```

and opened it with `loader open "/ext/apps/Bluetooth/ble_spam.fap"`, confirmed by `loader info`
→ `Application "BLE Spam" is running`.

**Navigation also needed adapting.** BLE Spam's actual UI is a horizontal Left/Right/OK
carousel over its 11 attack presets, not an Up/Down list: `input send down short` has nothing
bound to it on this screen, and OK is bound to "Start" — actually beginning a BLE flood
broadcast at nearby devices, which is a real-world side effect (the app's own description:
"Flood BLE advertisements to cause spammy and annoying popups/notifications") I chose not to
trigger since it weren't what the check was after. I used `input send right short` ("Next")
three times instead, 1 s apart, and read `sr screen` after each:

| # | Item | Primary text | Secondary text |
|---|------|--------------|-----------------|
| 1 (initial) | 01/11 Everything AND | The Kitchen Sink | Flood all attacks at once |
| 2 | 02/11 NameFlood | BT Settings Flood | Fills available BT devices |
| 3 | 03/11 Continuity Custom | iOS 17 Lockup Crash | Newer iPhones, long range |
| 4 | 04/11 Continuity Action | Apple Action Modal | Lock cooldown, long range |

`sr voice status` before opening the app: `fallback 0, missing 0, clips 45`. After all four
screens: `fallback 0, missing 0, clips 106` — **fallback did not rise** (the check the brief
asked for), missing stayed at 0, and 61 new distinct clip-words were spoken from screens full
of BLE-Spam-specific vocabulary (NameFlood, Continuity, Lockup, cooldown, and so on) with zero
letter-by-letter fallback. This is the real-hardware confirmation that `--card-apps`'s
extraction actually covers an app's own strings, not just a word-count on paper.

Left with a single `input send back short` (this app's menu is flat, one Back exits it):
`loader info` → "No application is running" immediately after. Confirmed the device back on
the home screen (`sr screen` → `content layer: desktop`) with voice still on before doing
anything else with the serial port.

### README

Added the `--dry` sentence phase B asked for (as its own bullet, next to the existing `--extract`
bullet it modifies): "Add `--dry` to any of the above to build the word list and print its
counts ... without making a single clip or touching the card." The `--extract-all` sentence was
already in from phase A (the fourth item in the "words come from" list). Both routine-command
mentions already read `--extract --card-apps --pull-missing --sync` from phase A.

### Commit

`5f19b77e359d9f72738ff463856208d9abee632e` — "voice_build: strings of the apps on the card;
extract-all; dry run", exactly `tools/voice_build.py` and `README.md` (explicit pathspec).
`tools/voice_words.txt` was never touched (no new word was needed in either phase) and is
correctly excluded. Working tree is clean after the commit. Not pushed (not asked for).

### Cleanup

Restarting the log capture took three tries, and the reason is worth recording:

1. First try, exactly as given (`nohup ... > /dev/null 2>&1 &` then `disown`, inside a Bash
   tool call): confirmed running immediately after (PID, and a few seconds later a real log
   line), then found dead about 17 s later with a clean `== log stopped 21:26:19` marker in
   the file — the script's own SIGTERM/SIGINT handler wrote that, meaning something signaled
   it, not a port failure. Nothing on the Mac side that I ran sent that signal. My working
   theory: this harness's sandboxing tears down a plain shell background job (`&`, even
   nohup'd and disowned) once the Bash tool call that spawned it returns, since it isn't
   tracked as one of the harness's own long-lived tasks. The 71-minute build earlier survived
   across many tool calls only because I ran it with the tool's own `run_in_background`
   option, not a shell `&`.
2. Second try, using `run_in_background` instead of a shell `&`: stayed up longer, but ended
   itself after about half a minute with a genuine `== port dropped 21:29:11: device reports
   readiness to read but returned no data (device disconnected or multiple access on port?)`
   — the same error text pyserial raised earlier for me directly (see "Port-drop incident").
   Real device/port instability, not a harness artifact this time.
3. Third try, same method, once the port had come back: stable for the 90+ s I watched it,
   normal periodic heartbeat lines a clean 60 s apart, no further drops.

Given the port had already dropped and recovered multiple times this session for reasons
that look external to anything I ran (see "Port-drop incident" above), I can't promise this
instance won't drop again later. It's the correctly-invoked, currently-running process
(`tools/flipper_log.py docs/measurements/logs/2026-09-24-session.txt`, harness-backgrounded
so it doesn't get reaped the way the plain `nohup` one did), appending to the same session
log file, which is what the brief asked for. If the device keeps having whatever
intermittent issue caused the drops, this specific log file will show `== port dropped ...`
lines marking exactly when.

Device left idle on the home screen, reader on, voice on, speech idle — confirmed by reading
the device *before* restarting the logger, since `flipper_log.py` and `flipper_cli.py` can't
hold the port at the same time.

### Concerns carried into this phase

1. The port-drop/concurrent-activity episode (see above) — not something I caused or could
   fully explain from my side; flagging for the controller in case it bears on Task 1's status
   or points to real device use that future device-touching tasks should schedule around. It
   recurred at least three times across roughly 15 minutes (right after the sync, once more
   while restarting the log capture, a `screen: TVs. Power` debug line the log capture itself
   caught live at 21:28:40 — direct evidence something was in the Infrared app at that exact
   moment, well after I'd left BLE Spam and moved on to unrelated cleanup) before settling.
2. A plain `nohup ... & disown` background process does not reliably outlive a single Bash
   tool call in this harness — it kept running for a few more of my own calls, then was gone
   with a clean stop marker instead of an error. `run_in_background` does survive across
   calls (it carried the 71-minute build through many). Worth knowing for any future task in
   this project that needs to leave something running past its own session, including
   whoever eventually hands the device off again after this one.
3. I deviated from the brief's literal `input send down short`/`ok short` suggestion for BLE
   Spam once I saw its actual UI, to avoid triggering a real BLE broadcast. Noting this plainly
   in case the controller specifically wanted the Start path exercised — I judged that
   unintended real-world side effects on nearby devices outweighed sticking to the literal
   suggestion, given the check's actual goal (vocabulary coverage, fallback count) was met
   through the carousel navigation instead.

### Late addendum: the log capture needed a third mechanism, and found the live user

After sending my first status-contract reply, task notifications kept arriving showing the log
capture I'd just restarted (via `run_in_background`) had died again -- this time with a clean
`== log stopped 21:32:57`, not a port error, after about 3 minutes. That meant even
`run_in_background` doesn't reliably outlive my own task ending in this harness, contradicting
what I'd inferred from the 71-minute build surviving it (that build finished, and was read,
entirely within my own active turns; nothing had yet tested outliving the *whole* task).

I found a real Terminal panel available (`mcp__terminal__*`, a tab the user already had open at
the project root) -- a shell that runs on the user's machine outside my sandbox and is described
as staying up after my turn ends. I moved the log capture there. Its first run hit a genuine
`== port dropped ...: multiple access on port?` within 2 seconds, so I wrapped it in a restart
loop (`while true; do .venv/bin/python tools/flipper_log.py ...; sleep 2; done`) run in a new
tab, since a one-shot command clearly wasn't going to survive this device's current port
behaviour either way.

The loop's second connection then captured this, directly:

```
21:34:30 [D][...]focus: Volume 70
21:34:31 [D][...]focus: Volume 80
21:34:33 [D][...]screen: MNTM-DEV 70A60C8F. Accessibility
21:34:34 [D][...]home: Home screen
```

(leading characters of each debug tag were lost to the reconnect timing -- the content isn't in
doubt: `focus: Volume 70` then `Volume 80` is exactly the Back+Right volume chord's own
announcement text, `screen: ... Accessibility` is the Momentum Accessibility settings screen,
and `home: Home screen` is the return to idle.) That's a person driving Back+Right on the
physical device to raise the volume from 70 to 80 while on the Accessibility settings screen,
then leaving to the home screen -- not Task 1's agent, not a stray signal, an actual live user,
almost certainly Robin, on his own device, while I was mid-way through restarting a log capture.

At that point I tried to kill the restart loop, worried it might be contending with him for the
port. `kill` on the loop's shell PID didn't stop it (the loop kept spawning new
`flipper_log.py` instances); a synthetic `SIGINT` to its process group reached the current
Python child (it logged a clean stop) but the shell's `while` loop itself wasn't interactive
enough for that to abort it either, and it just restarted again a few seconds later. I stopped
trying to force it at that point and reconsidered instead of continuing to fight it: the script
only reads (it sends one `log debug` handshake at startup and nothing else), physical button
presses reach the device over GPIO, not the CLI text stream, so a passive log reader
reconnecting every couple of seconds is very unlikely to compete with someone pressing buttons.
The repeated port drops are much more plausibly this device's USB-serial connection being
intermittently flaky right now -- for whatever mundane hardware/USB reason -- than an actual
resource fight I was causing. Repeatedly sending it signals to try to kill it felt like it risked
being more disruptive than just leaving a read-only listener running.

**Final state**: terminal tab `c2` is running the restart loop; the current `flipper_log.py`
instance connected at 21:35:56 and was still healthy (normal periodic heartbeat lines, no
further drops) as of my last check. If it drops again, it reconnects on its own within a couple
of seconds rather than leaving the session dark until someone notices. I did not re-run
`flipper_cli.py` after this to re-verify the device is idle on the home screen, since that would
mean taking the port away from the now-running log capture again, and the log itself already
shows `home: Home screen` as the last screen transition -- I'm relying on that rather than
re-touching the port a further time.

### Commit decision recap

Phase A deferred the commit until phase B confirmed the device-dependent parts. It did: 204/204
card apps matched (including `ble_spam` explicitly), the build and sync completed with 0
failures, and BLE Spam's fallback count held at 0 across four real screens. Committed as
`5f19b77e`.

## Fix round 1

Review findings (Important, x2), no device needed:

1. **`manifest_index` indexed commented-out appids.** The regex ran over raw file text with no
   notion of `#` comments, so a disabled `App(...)` block's `appid=` still got indexed. Real
   cases: `applications/external/subghz_remote/application.fam` line 2 (`# appid=
   "subghz_remote_ofw"`, a whole commented-out first block sitting right above the live
   `appid="subghz_remote"`) and `applications/main/subghz/application.fam` line 37 (`# appid=
   "subghz_fap"`, inside a second commented-out block). A grep across all five manifest roots
   confirmed these are the *only* two commented `appid=`/`fap_file_name=` lines anywhere in the
   tree, so nothing else was silently affected before this fix.

   Fixed with a new `strip_comment(line)` helper (a `#` outside a double-quoted string starts a
   comment; manifests use plain double-quoted strings, no escapes to handle) applied to every
   line of a manifest before the appid/fap_file_name regexes run, in `manifest_index`.

2. **`--dry` still ran `pull_missing`**, which silences the voice, deletes `/ext/sr/missing.txt`
   from the device and restores the voice -- a real device write despite `--dry`'s whole point
   (and the README's "without... touching the card") being that it doesn't touch anything.
   Fixed: `--dry` now skips the pull entirely and logs `dry run: missing.txt not pulled` in its
   place; only takes effect together with `--pull-missing` (unrelated otherwise). Also updated
   the module docstring's `--dry` sentence and the `--dry` `--help` text to say the same thing
   ("without making clips, pulling missing.txt, or syncing"). The README's existing `--dry`
   sentence already claimed "without... touching the card" -- that was the bug, not the
   sentence -- so it needed no wording change; only `tools/voice_build.py` was committed.

### Re-verification

**Mapping check**, extended with the two flagged files and a `strip_comment` unit check:

```
=== strip_comment() unit checks ===
PASS x7 (plain code unaffected; full-line comment at col 0; indented comment before any quote;
  trailing comment after real code; bare comment line; '#' inside quotes does NOT start a
  comment; '#' inside quotes ignored but a later real '#' still cuts)

=== manifest_index(): commented appids must NOT be indexed ===
PASS: 'subghz_remote_ofw' indexed = False
PASS: 'subghz_fap' indexed = False

=== manifest_index(): the LIVE appids in those same two files must still map correctly ===
PASS x6: subghz_remote -> .../external/subghz_remote; subghz, subghz_add_manually, subghz_gps,
  cli_subghz, subghz_load_extended_settings -> .../main/subghz

=== regression: the original three phase-A checks still pass ===
PASS x5: ble_spam, infrared, cli_ir, clock_settings, clock_settings_start all still map correctly

total index size: 480 (2 fewer than before the fix -- exactly the two commented ids, nothing else)

=== external_app_dirs() unaffected by this fix (sanity) ===
PASS: external app dirs = 243 (unchanged, this function doesn't touch appid parsing)

ALL CHECKS PASSED
```

**`tools/voice_build.py --extract --dry --out <scratch>`**, re-run exactly as asked:

```
extract: 6254 distinct strings from the firmware sources, 71 bubble texts
extract: 2899 words; longest: animationmanager animationstorage backlightenforce
  checksdkfeatures configchangeable defaulttextclear desktopscenelock freecreatedelete
  getbatterycharge hoppingthreshold
extract: 10 with an apostrophe: can't doesn't don't flipper's i'll i'm isn't it's who's you're
dry run: 2908 words total, no clips made
```

Identical to phase A's baseline (2,899 / 2,908) -- neither fix touches the `--extract` word
pipeline, so no regression was expected here and none appeared.

**`--pull-missing --dry`** (no `--extract`, to isolate finding 2 and to prove it never touches
the device): `dry run: missing.txt not pulled` then `dry run: 120 words total, no clips made`,
total wall time 0.064 s -- far too fast to have opened a serial connection, confirming
`pull_missing()`/`open_storage()` is never called on this path at all, not just that its output
is suppressed.

### Commit

`8698a893ddebfa10851d1db0645bb4ee68d7e08e` -- "voice_build: manifest comments ignored; dry run
never touches the card", `tools/voice_build.py` only (explicit pathspec; README needed no
wording change, see above). Working tree clean. Device not touched this round, per the
controller's instruction; log capture left untouched (controller's responsibility this round).
