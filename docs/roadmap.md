# Roadmap: shipping the accessible Flipper firmware

Date: 2026-09-24. Decision taken with Robin: ship a separate accessibility-focused firmware built on Momentum, rather than a pull request to Momentum.

Status on 2026-09-25: the recorded voice, phase 3 on-device control, the polish round, and the memory plan (steps 2 to 4: animations off by default, the JavaScript engine out, Sub-GHz back into flash, SAM out) are done. Next: the fork and release mechanics.

Status on 2026-09-26: the publishing spec, `docs/superpowers/specs/2026-09-26-github-release-design.md`, is written, and its plan A, `docs/superpowers/plans/2026-09-26-publishing-plan-a.md`, is done: the repositories, the cleanup, the continuous build and the upstream tooling. Its tools: `tools/card_prune.py` removes old update packages from the card; `tools/strip_js_symbols.py` and `tools/subghz_manifest.py` redo the fork's two mechanical changes after a Momentum merge, in the API table and in the built-in Sub-GHz app's source list; `tools/upstream_check.sh` shows from a dry run what a merge would meet; and the Build workflow, `.github/workflows/build.yml`, runs the host tests, the release build and the headroom check on every push. The device runs the clean Sonar build with plan A's fix wave, commit a5c2ed7d9, flashed complete on 2026-09-26. Plan B's code is in: the voice sets, the Kokoro and eSpeak voices and the pack tool. Plan C, the
install path and the first release, follows. The names are decided: the repository is `flipper-access`, and the firmware is Sonar.

Status on 2026-10-08: the review of 2026-09-28 is worked through. Its fixes, their checks on the device and what those checks found were merged in five pull requests on each repository from 2026-09-29 to 2026-10-03, as listed in `docs/2026-09-28-review-fixes.md`. The device runs 59878faeb, the tip of `screen-reader`, since 2026-10-03: firmware.bin 870,084 bytes, 10,556 spare. The first weekly build of that tip passed on 2026-10-05. Plan C, not yet begun, is next: steps 4 to 8 of section 11 of the publishing spec, that is the install script, the release workflow and its rehearsal, the documentation reviewed by Robin, the round-trip install test, and the tag `sonar-0.1.0` with the GitHub Release and this repository made public. The review's release findings wait for it, as listed under Not done in the fixes record, and so do the two decisions left to Robin in section 12 of the spec: the voice, and the voice pack's terms.

Status on 2026-10-11: plan C, `docs/superpowers/plans/2026-10-09-publishing-plan-c.md`, is under way on the branches `claude/plan-c-2026-10-11` of both repositories. Robin decided the two open questions: a release ships one voice, heart, made with Kokoro's voice af_heart, and what the project adds to a voice pack is CC0 1.0, beside the Apache 2.0 of Kokoro's model. Done so far: `tools/install.py`, which installs a release over USB from the official firmware, Momentum or Sonar, or puts the voice on the card through a card reader, and goes back to other firmware with `--restore`; its whole conversation with the Flipper in `docs/install-protocol.md`; the transfer spike, after which a whole install over USB took 32 minutes; the voice packs' licences in full; `.github/workflows/release.yml`, which builds a pushed tag into a draft release with the elf, the map, the SDK and the source bundle; `tools/release_finalise.py`, which adds `SHA256SUMS` and `release.json` once the pack is uploaded; and the public documents, the README's Install and Going back, `CHANGELOG.md`, `CONTRIBUTING.md`, the bug report form and the release notes template, which wait for Robin's reading. The review's report is now in `docs/2026-09-28-review.md`, and of its release findings only R7 and the protection of the release tags, part of R3, are open in `docs/2026-09-28-review-fixes.md`, until the rehearsal and the release. Next: the rehearsal `sonar-0.1.0-rc1`, the round trip from the official firmware 1.4.3, and the release `sonar-0.1.0` with this repository made public.

## Done so far

- Terminal access, the backup of internal storage, and the Momentum install, 2026-09-22.
- The command line explored, and the helper tools written.
- The source build environment set up, with a first app built and running.
- A speech demo, in which SAM's default voice was judged intelligible.
- Phase 1 of the screen reader, 2026-09-22: text capture, the screen model and the console mirror.
- Phase 2, 2026-09-23: speech on the device with SAM and DMA playback.
- The recorded voice, 2026-09-24: word clips from the card, made on the Mac.
- Phase 3, on-device control, 2026-09-24: the Back chords, the Accessibility settings screen, and spoken names for screens that draw only icons.
- The polish round, 2026-09-24: the change delay, and the generator reading the apps on the card.
- The firmware stripdown, 2026-09-25, so that Sub-GHz works with the reader on. The games, the JavaScript engine and SAM left the build and the card. Sub-GHz was built back into the firmware. Animations are off by default, with an Animations row to turn them back on. Flash 862,612 bytes, 18,028 spare; idle heap 116,672 to 116,752 bytes free, animations off.
- The dolphin in words, the crash address, the reader toggle, and the Archive's menus naming their selection, 2026-09-25.
- Publishing plan A, 2026-09-26: the repositories, the cleanup, the continuous build and the upstream tooling.
- Publishing plan B's code, 2026-09-26: the voice sets, the Kokoro and eSpeak voices and the pack tool.
- The review of 2026-09-28 and its fixes, merged from 2026-09-29 to 2026-10-03 and checked on the device, and the first weekly build, 2026-10-05: `docs/2026-09-28-review-fixes.md`.
- Publishing plan C's install script, release workflow and public documents, 2026-10-11, with the review's report moved into `docs/`.

## Why a fork

- Momentum's repository does not accept AI-written contributions; almost all of this code was written by agents under Robin's direction.
- Momentum is at its flash limit (Sub-GHz was moved out of flash for headroom); the reader's 27 KB of RAM and 14 KB of flash would end up behind a build flag, which means custom builds for blind users anyway.
- A fork can drop what serves no blind user and costs memory: the home animations (up to 26 KB of idle heap), the JavaScript engine (41 KB of flash, measured), games and screensavers. That returns Sub-GHz to flash and gives the reader room.
- A fork can ship what a blind user needs: reader on, List menus, sensible defaults, the recorded voice on the card, and one accessible install script.

## Keeping the delta small

- Intrusive hooks stay tiny and isolated: the canvas text tap in gui, the speaker mutex in the signal reader. Everything else is a service under `applications/services/screen_reader`.
- Removals happen through build configuration and app manifests, not by deleting code, so merges from Momentum stay mechanical.
- A CI build (GitHub Actions, Linux fbt) with the host tests runs on every push, so also on the submodule bump that follows each merge from Momentum. Part of it are the flash boundary check (`tools/flash_headroom.sh`), against the radio stack's address in the build's update package; Momentum's lint; a check that the build changed no tracked file; and the golden checks against the Momentum commit pinned in `tools/momentum-base.txt`. Since pushes to the fork build nothing, it also builds the fork's `screen-reader` tip every Monday.
- If Momentum ever wants the canvas hook behind a flag, that small change can be Robin's own contribution and shrinks the delta.

## Memory plan, in order

Where phase 3 and the polish round left it, before this plan: firmware.bin was 877,036 bytes, 3,604 spare below the BLE stack; idle free heap was about 110 KB; opening Sub-GHz with the reader on ran out of memory and restarted the device. The steps below made room, in this order, and are now done; step 4 has the final figures.

1. Recorded voice on the card: done 2026-09-24.
   - Size: 2,892 words, in 64 hashed folders, with 0 underruns in the verification.
   - Flash: firmware.bin grew from 869,756 bytes (the spec's baseline at 54794522b, 10,884 spare) to 871,872 bytes (+2,116). That leaves 8,768 bytes spare.
   - Heap: the 8192-byte speech ring cost 4,032 bytes of idle heap (114,552 to 110,520 free). The voice state costs about 700 bytes more; that is an estimate from the Task 2 comparison of idle heap.
   - Measurements: `docs/measurements/2026-09-24-voice-rollout.txt`.
2. Animations off by default: done 2026-09-25.
   - Setting: `desktop_anims`, off by default; changing it reboots the device.
   - Idle heap, 30 s after boot: 116,672 and 116,752 bytes free with animations off (two
     boots), 116,736 with animations on. The "on" reading caught the firmware's own built-in
     animation, not a card one, so it does not measure a card animation's cost; the earlier
     estimate of 10 to 26 KB for that still comes from the 2026-09-22 probe.
3. JavaScript engine out, Sub-GHz back into flash: done 2026-09-25.
   - JavaScript engine out: 41,288 bytes of flash (877,036 to 835,748).
   - Sub-GHz built back into the firmware: 42,028 bytes (835,748 to 877,776).
   - API: kept at 87.2. Nothing but the JavaScript modules imported the removed symbols, and a
     bump would only make the app catalog stop offering builds for this firmware.
   - Sub-GHz now works with the reader on: Read keeps 53,064 bytes free at its lowest, the
     Frequency Analyzer 51,136, where before it crashed the device out of memory.
4. SAM out of the speech engine: done 2026-09-25.
   - Flash: 15,344 bytes. Static RAM: 3,683 bytes.
   - The reader now speaks only from the recorded voice's clips, spelling a word, or a letter
     whose own clip is missing, and stays muted with the voice off or without a card.
   - Final image after the whole memory plan and the round's final fixes (08e80106f): 862,612
     bytes, 18,028 spare below the BLE stack.
   - Measurements: `docs/measurements/2026-09-25-stripdown.txt`.

## Features after the voice

- Phase 3 from the design spec: done 2026-09-24. Back chords (read the screen and the status bar, repeat and spell the focus, volume), the Accessibility settings screen with the reader toggle, spoken names for the lock menu, the lock screen, the PIN entry and the infrared universal remotes, the lock and the auto-lock announced, and the NFC-V emulation announced before it takes the speaker. As built: section 17 of the design spec. For the user: "Using it on the device" in the README.
- Pronunciation by ear: ordinals, thousands, remaining acronyms.
- Phase 4 option: a companion iOS app over BLE that speaks announcements with the phone's voices; the piezo stays the fallback.

## Release mechanics

- Repository with Momentum as upstream remote; branch `screen-reader` becomes the main branch of the fork; tags per release.
- Section 8 of the publishing spec, `docs/superpowers/specs/2026-09-26-github-release-design.md`, now defines the sync procedure for following Momentum.
- Release artefacts: the update package, the voice pack `heart`, the install zip with `install.py` and its helpers, the firmware's elf and map, the SDK, the source bundle, `SHA256SUMS` and `release.json`. `.github/workflows/release.yml` makes a draft release from a pushed tag, and the pack, the checksums and `release.json` are added on the Mac, as under Making a release in `docs/device-notes.md`. The install script says its progress in plain lines on the computer, for the computer's screen reader.
- Licensing: the firmware is GPL-3 like Momentum and the official firmware; the shipped vocabulary must come from a redistributable voice. The release's one set, heart, is made with Kokoro, under Apache 2.0, and what the project adds is CC0 1.0, as Robin decided on 2026-10-11; eSpeak-NG, GPL-3, is a backend for the sets users make. Apple voices are for personal vocabularies only.
- Documentation for blind users first: install, first boot, the console commands, the voice generator, and the known limits:
  - NFC-V emulation silences the reader.
  - Fixed after the review of 2026-09-28 (S4): the sync guard read the voice flag once per item, so an utterance already playing when `sr voice off` arrived kept opening clips and wrote the missing list at its end, while the generator had already started the transfer. Now `sr voice off` stops that utterance and answers once it has ended, and the missing list waits for an utterance with the voice on.
  - `sr play` still plays a file with the voice off, by design.
