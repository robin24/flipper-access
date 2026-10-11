# Documentation index

What this folder holds, for a reader who wants more than the project's README.

- `2026-09-14-investigation.md`: the background research that started the project, on whether a
  Flipper Zero running Momentum can be made usable without sight, checked against the firmware's
  source.
- `roadmap.md`: why Sonar is a separate firmware, the memory plan, what is done so far, and the
  release mechanics.
- `device-notes.md`: the working notes for the one device Sonar is developed on, and the
  developer's routine: flashing, the console commands, crash diagnosis and rolling back.
- `install-protocol.md`: what the install script says to the Flipper's USB console, command by
  command, and how it reads the replies, for a desktop app that does the same install.
- `measurements/`: what the device and the tools reported in each round, as plain text: the RAM
  probes, the image sizes, the speech timings and the checks run on the device.

## Specs

The designs, in `superpowers/specs/`:

- `2026-09-22-flipper-screen-reader-design.md`: the screen reader's design, with what was built in
  phases 1 to 3 and in the bounded changes after them.
- `2026-09-24-clip-voice-design.md`: the recorded voice: word clips on the card in hashed folders,
  the generator, and the larger speech ring.
- `2026-09-25-firmware-stripdown-design.md`: steps 2 to 4 of the memory plan: animations off by
  default, the JavaScript engine out, Sub-GHz back into flash, and the games and SAM out.
- `2026-09-26-github-release-design.md`: publishing: the two repositories, the first release, the
  voice sets made with Kokoro and eSpeak-NG, the install script, the continuous builds and the
  upstream merges.

## Plans

The implementation plans, task by task, in `superpowers/plans/`:

- `2026-09-22-screen-reader-phase-1.md`: phase 1, text capture, the screen model and the console
  mirror, without audio.
- `2026-09-23-screen-reader-phase-2-speech.md`: phase 2, speech through the device's own speaker
  in the SAM voice.
- `2026-09-24-clip-voice.md`: the recorded voice and its generator.
- `2026-09-24-phase-3-on-device-control.md`: phase 3, the Back chords, the Accessibility settings
  and spoken names for screens that draw only icons.
- `2026-09-24-polish-round.md`: the change delay, the Rate row shown only for SAM, and the
  generator reading the apps on the card.
- `2026-09-25-firmware-stripdown.md`: the stripdown that made Sub-GHz work with the reader on.
- `2026-09-26-publishing-plan-a.md`: publishing plan A, the repositories, the cleanup, the
  continuous build and the upstream tooling.
- `2026-09-26-publishing-plan-b.md`: publishing plan B, the voice sets on the card, the Kokoro
  and eSpeak voices, and the pack tool.

## Build logs

`superpowers/build-logs/` has one folder per round, with the ledger and its rulings, the briefs
and the reports.
