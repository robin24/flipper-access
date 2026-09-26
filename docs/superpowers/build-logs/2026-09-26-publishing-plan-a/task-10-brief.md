### Task 10: Build, flash, verify, prune, and the notes

**Files:**
- Modify: `docs/device-notes.md` (the firmware line and the headroom figure), `docs/roadmap.md` (status)
- Create: `docs/measurements/2026-09-26-plan-a.txt`

**Interfaces:**
- Consumes: `tools/card_prune.py`, `tools/flash_headroom.sh`, `tools/flipper_cli.py`.
- Produces: the device on the current `screen-reader` commit, reporting itself clean and as Sonar.

- [ ] **Step 1: A clean release build**

```bash
cd Momentum-Firmware
git status --short
rm -rf build/f7-firmware-C/resources build/f7-firmware-C/.extapps
./fbt COMPACT=1 DEBUG=0 updater_package 2>&1 | tail -5
cd ..
tools/flash_headroom.sh
ls Momentum-Firmware/dist/f7-C/
```

Expected: an empty status (the tree is clean, so the build is not "dirty"); the build ends without a warning about the API table; the headroom line with a spare below 880,640; the dist folder holds `flipper-z-f7-update-mntm-screen-reader-<hash>.tgz` and the update folder with `resources.tar.gz` in it.

- [ ] **Step 2: Flash with the resources**

```bash
cd Momentum-Firmware && ./fbt COMPACT=1 DEBUG=0 flash_usb_full 2>&1 | tail -5; cd ..
```

This takes about six minutes; the serial port disappears during the update and returns after the reboot. Then, before any key press:

```bash
.venv/bin/python tools/flipper_cli.py "sr screen" "info device" "sr status"
```

Expected: the home screen, not a crash popup; `firmware.commit.hash` equal to the submodule's HEAD (first eight characters), `firmware.commit.dirty : false`, `firmware.origin.fork : Sonar`, `firmware.origin.git : https://github.com/robin24/Momentum-Firmware.git`, `firmware.api.major : 87` and `minor : 3`; `sr status` with `enabled: yes`, the voice on and the Samantha settings line.

- [ ] **Step 3: The card after the flash**

```bash
.venv/bin/python tools/flipper_cli.py "storage list /ext/apps/Media" "storage list /ext/apps/assets"
.venv/bin/python tools/card_prune.py
.venv/bin/python tools/flipper_cli.py "storage list /ext/update"
```

Expected: `text2sam.fap` present with a size different from the patched build's 30,200 bytes (the stock build was deployed); `passport.fap` present; the prune removes the previous build's folder, and the listing shows the two rollback packages and the new build's folder only.

- [ ] **Step 4: A short workout**

```bash
.venv/bin/python tools/sr_drive.py --chords
.venv/bin/python tools/flipper_cli.py "sr status" "free"
```

Expected: the chord session reports no failures; `sr status` shows no dropped frames and the free heap in the usual range (about 110 to 117 KB idle).

- [ ] **Step 5: Notes and measurements**

Write `docs/measurements/2026-09-26-plan-a.txt`: the headroom line, the `info device` block, the `sr status` block, the `storage list /ext/update` listing before and after the prune (the counts from Task 3 and this task), the free heap, and the time the flash took. Prose lines between the blocks, no tables.

Update `docs/device-notes.md`: the firmware line in "Device state" now says the device runs commit `<hash>` of 2026-09-26, flashed complete with `./fbt flash_usb_full`, reporting itself as Sonar and clean, with the image size and the spare; add the size to the history in "Useful commands". Update `docs/roadmap.md`'s status paragraph: plan A done, listing the tools by name.

- [ ] **Step 6: Commit and push**

```bash
tools/run_host_tests.sh
git add docs/measurements/2026-09-26-plan-a.txt docs/device-notes.md docs/roadmap.md
git commit -m "Plan A on the device: Sonar flashed clean, the card pruned, the notes and measurements

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- docs/measurements/2026-09-26-plan-a.txt docs/device-notes.md docs/roadmap.md
git push
git status --short
git -C Momentum-Firmware status --short
gh run list --limit 1
```

Expected: both trees clean, the push accepted, and the continuous build starting on the new commit.
