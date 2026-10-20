# Documentation index

What this folder holds, for a reader who wants more than the project's README. Beside the README,
at the project's root, are `CHANGELOG.md`, the changes in each release, and `CONTRIBUTING.md`, how
to report a bug and send a change.

- `2026-09-14-investigation.md`: the background research that started the project, on whether a
  Flipper Zero running Momentum can be made usable without sight, checked against the firmware's
  source.
- `roadmap.md`: why Sonar is a separate firmware, the memory plan, what is done so far, and the
  release mechanics.
- `developer-notes.md`: the developer's routine: the tools, building and flashing, merging
  Momentum, making a release, the console commands, crash diagnosis and rolling back.
- `install-protocol.md`: what the install script says to the Flipper's USB console, command by
  command, and how it reads the replies, for a desktop app that does the same install.
- `release-notes-template.md`: the notes of every release, which the release workflow fills in
  with the tag, the fork's commit, the Momentum base, the submodules' commits and the source
  bundle's name.
- `2026-09-28-review.md`: the review of the firmware, the tools and the release process before the
  first release, with its findings, marked F, S, G, R and T, and the checks for the device.
- `2026-09-28-review-fixes.md`: what was done about each finding of that review, how it was checked
  on the device, and what is left.

## Specs

The designs, in `superpowers/specs/`:

- `2026-09-22-flipper-screen-reader-design.md`: the screen reader's design, with what was built in
  phases 1 to 3 and in the bounded changes after them.
- `2026-09-24-clip-voice-design.md`: the recorded voice: word clips on the card in hashed folders,
  the generator, and the larger speech ring.
- `2026-09-25-firmware-stripdown-design.md`: steps 2 to 4 of the memory plan: animations off by
  default, the JavaScript engine out, Sub-GHz back into flash, and the games and SAM out.
- `2026-09-26-github-release-design.md`: publishing: the two repositories, the first release, the
  voice made with Kokoro, of which a release ships the one set heart, the eSpeak-NG backend for
  the sets users make, the install script, the continuous builds and the upstream merges.

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
- `2026-10-09-publishing-plan-c.md`: publishing plan C, the install script, the release workflow,
  the public documents, the rehearsal and the first release.

## Removed records

The measurement files of each round, `measurements/`, and the build logs of each round,
`superpowers/build-logs/`, recorded what was run and seen on the device the project was developed
on. They were removed on 2026-10-20, and so was that device's state from the developer notes,
which were called `device-notes.md` before. The specs, the plans and the review's fixes record
still name some of those files; they are in the git history before that day.
