# Roadmap: shipping the accessible Flipper firmware

Date: 2026-09-24. Decision taken with Robin: ship a separate accessibility-focused firmware built on Momentum, rather than a pull request to Momentum.

Status on 2026-09-25: the recorded voice, phase 3 on-device control, the polish round, and the memory plan (steps 2 to 4: animations off by default, the JavaScript engine out, Sub-GHz back into flash, SAM out) are done. Next: the fork and release mechanics.

## Why a fork

- Momentum's repository does not accept AI-written contributions; almost all of this code was written by agents under Robin's direction.
- Momentum is at its flash limit (Sub-GHz was moved out of flash for headroom); the reader's 27 KB of RAM and 14 KB of flash would end up behind a build flag, which means custom builds for blind users anyway.
- A fork can drop what serves no blind user and costs memory: the home animations (up to 26 KB of idle heap), the JavaScript engine (41 KB of flash, measured), games and screensavers. That returns Sub-GHz to flash and gives the reader room.
- A fork can ship what a blind user needs: reader on, List menus, sensible defaults, the recorded voice on the card, and one accessible install script.

## Keeping the delta small

- Intrusive hooks stay tiny and isolated: the canvas text tap in gui, the speaker mutex in the signal reader. Everything else is a service under `applications/services/screen_reader`.
- Removals happen through build configuration and app manifests, not by deleting code, so rebases onto Momentum stay mechanical.
- A CI build (GitHub Actions, Linux fbt) with the host tests runs on every rebase; the flash boundary check (`tools/flash_headroom.sh`) is part of it.
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
   - Final image after the whole memory plan: 862,588 bytes, 18,052 spare below the BLE stack.
   - Measurements: `docs/measurements/2026-09-25-stripdown.txt`.

## Features after the voice

- Phase 3 from the design spec: done 2026-09-24. Back chords (read the screen and the status bar, repeat and spell the focus, volume), the Accessibility settings screen with the reader toggle, spoken names for the lock menu, the lock screen, the PIN entry and the infrared universal remotes, the lock and the auto-lock announced, and the NFC-V emulation announced before it takes the speaker. As built: section 17 of the design spec. For the user: "Using it on the device" in the README.
- Pronunciation by ear: ordinals, thousands, remaining acronyms.
- Phase 4 option: a companion iOS app over BLE that speaks announcements with the phone's voices; the piezo stays the fallback.

## Release mechanics

- Repository with Momentum as upstream remote; branch `screen-reader` becomes the main branch of the fork; tags per release.
- Release artefacts: the update package (.tgz for qFlipper or the update CLI), the card payload (voice vocabulary made with a freely licensed voice, screen reader files), and an install script that flashes and copies with spoken progress on the host.
- Licensing: the firmware is GPL-3 like Momentum and the official firmware; the shipped vocabulary must come from a redistributable voice (Piper models with permissive licences), Apple voices are for personal vocabularies only.
- Documentation for blind users first: install, first boot, the console commands, the voice generator, known limits (NFC-V silence).
