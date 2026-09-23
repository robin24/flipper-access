# Roadmap: shipping the accessible Flipper firmware

Date: 2026-09-24. Decision taken with Robin: ship a separate accessibility-focused firmware built on Momentum, rather than a pull request to Momentum.

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

1. Recorded voice on the card (in progress): no new RAM, a few KB of flash.
2. Animations off by default (asset pack or desktop setting; measure the idle heap with and without).
3. JavaScript engine out of the build (API major bump, all faps rebuilt by the release pipeline); Sub-GHz back into flash with the freed space; re-measure with `tools/ram_probe.py`.
4. Reader trims if still needed: ring 4096 to 3072, worker stack 3072 to 2048 (high water 812), SAM optional once the voice covers everything.

## Features after the voice

- Phase 3 from the design spec: Back chords (repeat, spell, stop), a settings screen, a device side reader toggle, lock screen and PIN handling, the NFC-V emulation announcement, auto-lock text.
- Pronunciation by ear: ordinals, thousands, remaining acronyms.
- Phase 4 option: a companion iOS app over BLE that speaks announcements with the phone's voices; the piezo stays the fallback.

## Release mechanics

- Repository with Momentum as upstream remote; branch `screen-reader` becomes the main branch of the fork; tags per release.
- Release artefacts: the update package (.tgz for qFlipper or the update CLI), the card payload (voice vocabulary made with a freely licensed voice, screen reader files), and an install script that flashes and copies with spoken progress on the host.
- Licensing: the firmware is GPL-3 like Momentum and the official firmware; SAM is reverse engineered 1982 software already shipped by the Text to SAM app (state its status in the README); the shipped vocabulary must come from a redistributable voice (Piper models with permissive licences), Apple voices are for personal vocabularies only.
- Documentation for blind users first: install, first boot, the console commands, the voice generator, known limits (Sub-GHz memory until step 3, NFC-V silence).
