### Task 2: Retire Text to SAM, the stock backup out of git, the licence, ignore rules, the local word list

**Files:**
- Delete: `patches/text2sam-cli-mode.patch`, `tools/say.sh`
- Create: `LICENSE` (the GPL-3.0 text, copied from `Momentum-Firmware/LICENSE`), `tools/voice_words.local.txt` (ignored, holds `delphi`)
- Modify: `.gitignore`, `README.md` (small fixes only; Task 5 rewrites it), `tools/voice_build.py`, `tools/voice_words.txt`
- Move: `flipper-zero-accessibility-investigation.md` to `docs/2026-09-14-investigation.md`
- Restore in the firmware's apps submodule: `Momentum-Firmware/applications/external/text2sam/sam_app.cpp`

**Interfaces:**
- Produces: `tools/voice_build.py` loads `tools/voice_words.local.txt` beside `tools/voice_words.txt` when it exists; the firmware clone reports itself clean (`git diff HEAD --quiet` exits 0), so builds are no longer "dirty".

- [ ] **Step 1: Restore the patched app in the firmware's apps submodule**

```bash
git -C Momentum-Firmware/applications/external checkout -- text2sam/sam_app.cpp
git -C Momentum-Firmware status --short
git -C Momentum-Firmware diff HEAD --quiet && echo clean
```

Expected: an empty status and `clean`.

- [ ] **Step 2: Remove the patch and the helper, take the backup out of git, move the investigation**

```bash
git rm -q patches/text2sam-cli-mode.patch tools/say.sh
git rm -q --cached backups/backup-stock-1.4.3.tar
git mv flipper-zero-accessibility-investigation.md docs/2026-09-14-investigation.md
ls backups patches 2>&1
```

Expected: `backups/backup-stock-1.4.3.tar` still on disk; `patches` no longer exists (git removes the empty folder; if it remains, `rmdir patches`).

- [ ] **Step 3: Ignore rules**

Append to `.gitignore` these lines:

```
backups/
voice-models/
tools/voice_words.local.txt
```

- [ ] **Step 4: The licence**

```bash
cp Momentum-Firmware/LICENSE LICENSE
head -3 LICENSE
grep -c "" LICENSE
```

Expected: the GNU General Public License version 3 header, and a file of several hundred lines (the full text).

- [ ] **Step 5: The generator's local word list, and its wording**

In `tools/voice_build.py`:

Replace the docstring sentence `Defaults are the settings Robin chose by ear on 2026-09-24.` with `Defaults are the settings chosen by ear on 2026-09-24 for the Samantha voice.`

Replace the docstring sentence that begins `Words come from tools/voice_words.txt, from every string literal` so that it begins `Words come from tools/voice_words.txt and, when it exists, tools/voice_words.local.txt (personal words such as a device name, not in git), from every string literal` (keep the rest of the sentence).

In `main()`, the line

```python
    words = load_list(os.path.join(HERE, "voice_words.txt"))
```

becomes

```python
    words = load_list(os.path.join(HERE, "voice_words.txt"))
    words |= load_list(os.path.join(HERE, "voice_words.local.txt"))
```

(`load_list` returns an empty set for a missing file, so nothing else changes.)

Then move the device name:

```bash
grep -n "^delphi$" tools/voice_words.txt
sed -i '' '/^delphi$/d' tools/voice_words.txt
printf '# Personal words for this device, not in git: one per line.\ndelphi\n' > tools/voice_words.local.txt
grep -c "delphi" tools/voice_words.txt; git check-ignore tools/voice_words.local.txt
```

Expected: `0` and the local file's path (ignored).

- [ ] **Step 6: Check the generator still counts the word**

```bash
.venv/bin/python tools/voice_build.py --dry 2>&1 | tail -3
mv tools/voice_words.local.txt /tmp/vwl.txt && .venv/bin/python tools/voice_build.py --dry 2>&1 | tail -3; mv /tmp/vwl.txt tools/voice_words.local.txt
```

Expected: the first run's word count is one higher than the second's (the local list adds `delphi`); no error either way.

- [ ] **Step 7: Small README fixes so the tree is consistent until Task 5**

In `README.md`: replace `` `flipper-zero-accessibility-investigation.md` `` with `` `docs/2026-09-14-investigation.md` ``; remove the two "Folder contents" bullets for `tools/say.sh` and `patches/text2sam-cli-mode.patch`; remove the "Build the patched app and copy it to the card" command block under "Useful commands" together with its introductory sentence and the parenthetical note that follows it; in "Device state" replace the bullet about the Text to SAM app with: `- The Text to SAM app on the card is Momentum's stock build again since 2026-09-26; the patched build and tools/say.sh were retired, since the reader speaks from its own engine.`

- [ ] **Step 8: Run the tests and commit**

```bash
tools/run_host_tests.sh
git add .gitignore LICENSE tools/voice_build.py tools/voice_words.txt README.md docs/2026-09-14-investigation.md
git commit -m "Text to SAM retired, the stock backup out of git, the GPL-3 licence, a local word list for personal words

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- .gitignore LICENSE tools/voice_build.py tools/voice_words.txt tools/say.sh patches/text2sam-cli-mode.patch backups/backup-stock-1.4.3.tar README.md flipper-zero-accessibility-investigation.md docs/2026-09-14-investigation.md
git status --short
git push
```

Expected: the runner green, the status clean except the submodule (unchanged pointer, clean tree), the push accepted.

---

