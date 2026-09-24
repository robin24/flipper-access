# Roadmap: shipping the accessible Flipper firmware

Date: 2026-09-24. Decision taken with Robin: ship a separate accessibility-focused firmware built on Momentum, rather than a pull request to Momentum.

Status on 2026-09-24: the recorded voice (step 1 of the memory plan), phase 3 on-device control, and the polish round (change delay, Rate shown only for SAM) are done. Next: the memory plan, from step 2.

## Why a fork

- Momentum's repository does not accept AI-written contributions; almost all of this code was written by agents under Robin's direction.
- Momentum is at its flash limit (Sub-GHz was moved out of flash for headroom); the reader's 27 KB of RAM and 14 KB of flash would end up behind a build flag, which means custom builds for blind users anyway.
- A fork can drop what serves no blind user and costs memory: the home animations (up to 26 KB of idle heap), the JavaScript engine (on the order of 100 KB of flash), games and screensavers. That returns Sub-GHz to flash and gives the reader room.
- A fork can ship what a blind user needs: reader on, List menus, sensible defaults, the recorded voice on the card, and one accessible install script.

## Keeping the delta small

- Intrusive hooks stay tiny and isolated: the canvas text tap in gui, the speaker mutex in the signal reader. Everything else is a service under `applications/services/screen_reader`.
- Removals happen through build configuration and app manifests, not by deleting code, so rebases onto Momentum stay mechanical.
- A CI build (GitHub Actions, Linux fbt) with the host tests runs on every rebase; the flash boundary check (`tools/flash_headroom.sh`) is part of it.
- If Momentum ever wants the canvas hook behind a flag, that small change can be Robin's own contribution and shrinks the delta.

## Memory plan, in order

Where phase 3 and the polish round leave it: firmware.bin is 877,036 bytes, 3,604 spare below the BLE stack; idle free heap is about 110 KB; opening Sub-GHz with the reader on runs out of memory and restarts the device. The next steps make room, in this order.

1. Recorded voice on the card: done 2026-09-24.
   - Size: 2,892 words, in 64 hashed folders, with 0 underruns in the verification.
   - Flash: firmware.bin grew from 869,756 bytes (the spec's baseline at 54794522b, 10,884 spare) to 871,872 bytes (+2,116). That leaves 8,768 bytes spare.
   - Heap: the 8192-byte speech ring cost 4,032 bytes of idle heap (114,552 to 110,520 free). The voice state costs about 700 bytes more; that is an estimate from the Task 2 comparison of idle heap.
   - Measurements: `docs/measurements/2026-09-24-voice-rollout.txt`.
2. Animations off by default (asset pack or desktop setting; measure the idle heap with and without).
3. JavaScript engine out of the build (API major bump, all faps rebuilt by the release pipeline); Sub-GHz back into flash with the freed space; re-measure with `tools/ram_probe.py`.
4. Reader trims if still needed: worker stack 3072 to 2048 (high water 812), SAM optional once the voice covers everything. The speech ring is not trimmed: the recorded voice needs its 8192 bytes, two halves of 82 ms, because a clip open takes up to 39 ms.

## Features after the voice

- Phase 3 from the design spec: done 2026-09-24. Back chords (read the screen and the status bar, repeat and spell the focus, volume), the Accessibility settings screen with the reader toggle, spoken names for the lock menu, the lock screen, the PIN entry and the infrared universal remotes, the lock and the auto-lock announced, and the NFC-V emulation announced before it takes the speaker. As built: section 17 of the design spec. For the user: "Using it on the device" in the README.
- Pronunciation by ear: ordinals, thousands, remaining acronyms.
- Phase 4 option: a companion iOS app over BLE that speaks announcements with the phone's voices; the piezo stays the fallback.

## Release mechanics

- Repository with Momentum as upstream remote; branch `screen-reader` becomes the main branch of the fork; tags per release.
- Release artefacts: the update package (.tgz for qFlipper or the update CLI), the card payload (voice vocabulary made with a freely licensed voice, screen reader files), and an install script that flashes and copies with spoken progress on the host.
- Licensing: the firmware is GPL-3 like Momentum and the official firmware; SAM is reverse engineered 1982 software already shipped by the Text to SAM app (state its status in the README); the shipped vocabulary must come from a redistributable voice (Piper models with permissive licences), Apple voices are for personal vocabularies only.
- Documentation for blind users first: install, first boot, the console commands, the voice generator, known limits (Sub-GHz memory until step 3, NFC-V silence).
