# Changelog

The changes in each release of Sonar, the newest first. A release's version is its tag without the
prefix: version 0.1.0 is the tag `sonar-0.1.0`. How to install a release is under Install in the
README.

## 0.1.0, 2026-10-16

The first release. Sonar is a firmware for the Flipper Zero that a blind person can use without
sight. It is built on Momentum, at Momentum's commit d3f89dfe2, and its screen reader speaks every
screen through the device's own speaker, from recorded word clips on the SD card.

This release holds:

- The firmware. The screen reader is on from the first boot, with the Back chords, the Accessibility
  settings, spoken names for the screens that draw only icons, the dolphin's level and mood in
  words, and an address on the crash popup that locates the crash. The games and the JavaScript
  engine are left out, and the home screen's animations are off by default, so that Sub-GHz is built
  into the firmware again and works with the reader on. Momentum's first boot tutorial is left out
  too, since the reader cannot read its pictures.
- The voice, heart, made with Kokoro's voice af_heart: 10,535 clips, one for each word, letter
  and digit.
- The install script, which installs Sonar from the official firmware, Momentum or an earlier
  Sonar, backs up the Flipper's internal storage first, and sends the voice over USB or writes it
  through a card reader. The same script goes back to other firmware and puts the backup back.
- For crash reports and developers: the firmware's elf and map, the SDK, and the source of every
  binary.
