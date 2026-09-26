# Plan A fix wave: every item, in the order to do them

Work from /Users/robin/Downloads/flipper-access. The firmware is the submodule `Momentum-Firmware`
(branch `screen-reader`; remotes `origin` = our fork, `upstream` = Momentum with push URL `no_push`,
never pushed). Commit with explicit pathspecs, plain-sentence messages ending with your own
Co-Authored-By line, no `--amend`, no force push; push firmware commits with
`git push origin screen-reader` from inside the submodule, then bump the pointer in the project
(`git add Momentum-Firmware`, pathspec `-- Momentum-Firmware`). Group the changes into a few
commits by theme (firmware; tools and tests; workflow; docs), not one commit per line.

Documentation rules: prose and short lists, no tables, commands in their own code blocks,
sentences of about twenty words, no em-dashes, nothing personal in the public README.

## A. Firmware (two commits on screen-reader, each pushed and pointer-bumped)

A1. `lib/momentum/settings.c`, `momentum_settings_save()`: return at once when
`furi_hal_is_normal_boot()` is false, with a `FURI_LOG_I("Momentum", "settings not saved: not a normal boot")`
before the return and this comment above the check: "In the update boots the internal storage is
formatted and restored by the updater, and the settings in RAM are the compiled defaults, so a save
there (a volume chord pressed during the update) would overwrite the restored file. The flag is
set once at power-on and stays false for the whole update boot, including after the updater
resets the boot mode." Include `<furi_hal.h>` if the file does not already see the declaration.
The build must warn about nothing.

A2. `targets/f18/target.json`: put the `"mjs",` line back exactly where it was (revert that one
file to its state at c0ba0af07^; `git checkout c0ba0af07^ -- targets/f18/target.json`). The
fork builds only the f7 target; the f18 table still lists the engine, so the earlier removal
only widened the merge footprint. Message: "f18's link list as upstream has it: the fork builds
only the Flipper Zero target".

## B. Tools and tests (project)

B1. `tools/subghz_manifest.py`: `rewrite()` also forces `apptype=FlipperAppType.APP,` inside the
subghz block (replace the block's `apptype=FlipperAppType.<Name>,` whatever the name), so "take
upstream's file, run the script" yields a built-in app and not a card-loaded one; anchor the
sources capture on `sources=[` at the start of a line (leading spaces allowed) so a comment
containing that text cannot match; wrap the git calls of `--verify-upstream` so a missing
`upstream/dev` gives one sentence and exit 1, not a traceback. Docstring updated.
`tests/fbt/test_subghz_manifest.py`: the synthetic block gets `apptype=FlipperAppType.MENUEXTERNAL,`
and the test checks it becomes APP; a check that the fork's current manifest has
`apptype=FlipperAppType.APP` in the subghz block (CI-safe); a golden check, skipped without
`upstream/dev`, that the merge base's manifest through the script equals the fork's file when
comment lines (stripped lines starting with `#`) are ignored on both sides. Counts stay dynamic.

B2. `tools/card_prune.py`: candidates are only folders named `f7-update-sonar-`,
`f7-update-mntm-screen-reader-` or `f7-update-mntm-HEAD-` plus anything (the fork's own
builds); a foreign package (`f7-update-1.4.3`, `f7-update-mntm-012`, `f7-update-1.5.0`, an
Unleashed one) is never a candidate, so `DEFAULT_KEEP` becomes unnecessary and goes (keep
`--keep` for explicit names); the running build is recognised by the commit hash at the end of
the name or, when `info device` reports a `firmware.version` other than `mntm-dev`, by the name
`f7-update-<firmware.version>`; `plan(folders, running_hash, running_version, keep)` is the new
signature; the `flipper_cli` import guard also catches `ImportError`. Docstring updated.
`tests/fbt/test_card_prune.py`: cases for a foreign package staying, a tagged running build
`f7-update-sonar-0.1.0` with version `sonar-0.1.0` staying while `f7-update-sonar-0.0.9` goes,
an `mntm-HEAD` build, and the previous cases adapted. Update the runner's expectations if the
summary line changes.

B3. `tools/strip_js_symbols.py` docstring: name the resolution step explicitly ("after a merge
that conflicts on this file: `git checkout --theirs targets/f7/api_symbols.csv`, then run this
script"); the "our line missing" check keys on kind and name; the synthetic test's version
expectation becomes the literal `Version,+,90.6,,`.

B4. `tools/upstream_check.sh`: fetch the upstream remote with `--tags` (so `--upstream mntm-013`
works, the main use), and derive the remote to fetch as: the part before the first slash when
the ref contains one, else `upstream`; a trailing option without a value prints one sentence
and exits 1. `tests/fbt/test_upstream_check.py`: pass `-c commit.gpgsign=false` for the
throwaway commits; if `git merge-tree --write-tree` is unsupported (git older than 2.38), print
a skip line and exit 0.

B5. `tools/run_host_tests.sh`: the header comment names the four new tests and drops "from
Xcode"; each Python block echoes the test's skip lines too (print every line that starts with
"skipped"), so CI shows what was skipped; `tests/fbt/test_strip_js_symbols.py` and
`tests/fbt/test_subghz_manifest.py` send git's stderr to DEVNULL. `tests/fbt/test_subghz_sources.py`
docstring: "rebase" becomes "merge".

B6. File modes: `chmod +x tools/card_prune.py tools/strip_js_symbols.py tools/subghz_manifest.py`
(they have shebangs and are invoked directly in their docstrings).

B7. `tools/flash_headroom.sh`: over the limit, print "too large by N bytes" as its own line.

## C. Workflow (project)

`.github/workflows/build.yml`: `permissions: contents: read` at the top level; `on: push:
branches: ["**"]` so tag pushes go to the release workflow later; pin `runs-on: ubuntu-24.04`;
for each of `actions/checkout`, `actions/cache`, `actions/upload-artifact`, check with
`gh api repos/actions/<name>/releases/latest --jq .tag_name` whether a newer major exists and
use that major if so (the run log warns that the v4 majors target Node 20), else keep v4. Push
and confirm the run goes green (`gh run watch`); the cache should hit.

## D. Documentation (project)

D1. `README.md`, all of these:
- Title area: one sentence connecting Flipper Access (the project) with Sonar (the firmware);
  link Momentum (https://github.com/Next-Flip/Momentum-Firmware) where it is first named.
- "What changed against Momentum": add the changed defaults (the reader on, the List menu
  style, which is the only style whose focus the reader can name; the other styles are read by
  inversion where possible) and the FreeRTOS stack overflow check.
- Back chords: `sr watch` gets its command (`tools/sr_drive.py --interactive`) or the sentence
  is cut to "bypass the chords"; one sentence that a volume change during a firmware update is
  heard but not kept, since settings are not saved in the update boot.
- The toggle chord: "by design also in the PIN entry, which has not been tried on a device";
  drop the remark about locking the developer out (lines 236-239 area), or make it neutral.
- The voice: "skipped" becomes "skipped and noted, like a word" (lines 286-287 area); the Piper
  caveat (line 352 area) becomes "The Piper backend has not been run yet, so its output is
  untested"; after "runs on any platform" (line 346 area): the tools' port default matches only
  a Mac, elsewhere `--port` is needed, or `FLIPPER_PORT` for the console tools.
- Inline commands into code blocks: `sr on` (line 154 area), `sr voice off` and `sr voice on`
  (310 area), `sr voice on` and `--sync-all` (379-380 area).
- The file browser's menus: the Delete prompt's words as a code span, `Delete <name>?`
  (line 273 area).
- "reads nothing from the card" becomes "loads nothing from the card" (lines 44-45 and 174-175
  areas).
- Building from source: say the clone leaves the submodule on a detached HEAD, so a source build
  is named `f7-update-mntm-HEAD-<hash>` and reports its branch as HEAD, and that
  `git -C Momentum-Firmware checkout screen-reader` before building gives the branch name; say
  the host tests need clang (Linux users install it); say only the Flipper Zero target (f7) is
  built.

D2. `docs/device-notes.md`:
- The List-style fact once (drop the second copy that promises hints in a later phase).
- The settings paragraph: say the three values were restored from the update's `backup.tar`
  and the device rebooted, and that the firmware now skips saves in update boots (A1).
- Routine step 1: a full wipe of `Momentum-Firmware/build` before a release build and after a
  merge from Momentum (the stale `libmjs.a` lesson), the narrower wipe for everyday builds.
- "Builds are reproducible, so the addresses match": qualify: shown on this Mac; CI's image of
  the same commit differs by 12 bytes, so a release's `firmware.elf` must be kept for decoding.
- A new section "Merging Momentum" with this numbered routine: fetch upstream with tags; run
  `tools/upstream_check.sh --upstream <tag>`; merge; for `targets/f7/api_symbols.csv` take
  theirs and run `tools/strip_js_symbols.py`; for the Sub-GHz manifest take theirs and run
  `tools/subghz_manifest.py`; commit, then `tools/subghz_manifest.py --verify-upstream`; run the
  host tests; wipe the whole build folder, build, run the headroom check; run the RAM probe and
  the reader's routine; tag.
- `docs/superpowers/specs/2026-09-26-github-release-design.md` section 3: the stock backup's
  blob stays in the history (it holds settings, dolphin state and region data, no keys and no
  PIN); one sentence.

D3. Privacy: `docs/superpowers/build-logs/2026-09-24-clip-voice-spelling/task-1-report.md`
(lines 187 and 228 area) and `docs/superpowers/build-logs/2026-09-24-polish-round/task-1-report.md`
(lines 264 and 1004 area) hold the device's `hardware.uid` and `radio.ble.mac` values. Replace
each value with the word `redacted` and add, on the first such line of each file, the note
"(identifier redacted before publication)". Then `git grep -n -E "redacted|redacted|hardware.uid|radio.ble.mac"` over the whole project (not the firmware)
and redact any other occurrence of those two values the same way; report what you found.

## E. Flash and verify

After A1 and A2 are pushed and the pointer bumped, and B and D are committed: wipe
`Momentum-Firmware/build` entirely, `./fbt COMPACT=1 DEBUG=0 updater_package`,
`tools/flash_headroom.sh`, then `./fbt COMPACT=1 DEBUG=0 flash_usb_full`. Before the flash,
record `/int/.momentum_settings.txt` (`storage read`) and `sr status`. Wait for the port to
return (up to ten minutes); then, before any key: `sr screen`, `info device` (hash equal to the
new firmware HEAD, dirty false, origin Sonar), `sr status` (volume 40), `storage read
/int/.momentum_settings.txt` (identical to the copy from before the flash: `lock_on_boot: false`,
`dark_mode: true`, `sr_volume: 40`). Then `sysctl debug 1` and `sysctl log_level debug` (the
flash clears them), `tools/card_prune.py` (the previous build's folder goes), and
`tools/sr_drive.py --chords`. Append the outputs to `docs/measurements/2026-09-26-plan-a.txt`
under a heading "After the fix wave", and update the firmware line and size history in
`docs/device-notes.md`. Commit and push.

Nobody but you touches the device; never send `loader close`; never touch `/ext/sr/voice`.
