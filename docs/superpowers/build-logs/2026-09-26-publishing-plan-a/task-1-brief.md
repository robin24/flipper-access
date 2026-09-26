### Task 1: The fork and the project repository on GitHub

**Files:**
- Modify: `.gitignore` (drop the `Momentum-Firmware/` line)
- Create: `.gitmodules` (written by `git submodule add`)

**Interfaces:**
- Produces: the remotes `upstream` (Next-Flip, fetch only) and `origin` (the fork) in the firmware clone; `Momentum-Firmware` as a submodule of the project; the GitHub repositories `robin24/Momentum-Firmware` (public fork, default branch `screen-reader`, Actions disabled) and `robin24/flipper-access` (private). Every later task relies on the remote names `upstream` and `origin`.

- [ ] **Step 1: Preconditions**

Run from the project root `/Users/robin/Downloads/flipper-access`:

```bash
gh auth status
git status --short
git -C Momentum-Firmware status --short
git -C Momentum-Firmware branch --show-current
git -C Momentum-Firmware remote -v
```

Expected: logged in as `robin24`; the project tree clean; the firmware tree shows only ` m applications/external` (the Text to SAM patch, which Task 2 restores); branch `screen-reader`; one remote `origin` pointing at `https://github.com/Next-Flip/Momentum-Firmware.git`. Stop and report if anything differs.

- [ ] **Step 2: Create the fork**

```bash
gh repo fork Next-Flip/Momentum-Firmware --clone=false --default-branch-only
gh repo view robin24/Momentum-Firmware --json isFork,parent,visibility --jq '"fork=\(.isFork) parent=\(.parent.nameWithOwner) \(.visibility)"'
```

Expected: `fork=true parent=Next-Flip/Momentum-Firmware PUBLIC`. If the view fails right after the fork, the fork is still being created: run the view again a moment later.

- [ ] **Step 3: Point the clone at the fork, keep Momentum fetch-only**

```bash
cd Momentum-Firmware
git remote rename origin upstream
git remote set-url --push upstream no_push
git remote add origin https://github.com/robin24/Momentum-Firmware.git
git push -u origin screen-reader
git remote -v
git config branch.screen-reader.remote
cd ..
```

Expected: `upstream` shows the Next-Flip URL for fetch and `no_push` for push; `origin` shows the fork for both; the push reports the branch set up to track `origin/screen-reader`; the config prints `origin`. The push is fast: the fork already holds every commit below ours.

- [ ] **Step 4: The fork's default branch, description and Actions**

```bash
gh repo edit robin24/Momentum-Firmware --default-branch screen-reader --description "Momentum firmware with a built-in screen reader for blind users: the Sonar firmware. Documentation, releases and tools: https://github.com/robin24/flipper-access"
gh api -X PUT repos/robin24/Momentum-Firmware/actions/permissions -F enabled=false
gh api repos/robin24/Momentum-Firmware/actions/permissions --jq .enabled
gh repo view robin24/Momentum-Firmware --json defaultBranchRef --jq .defaultBranchRef.name
```

Expected: `false` and `screen-reader`.

- [ ] **Step 5: Check nothing in the tools names the old remote**

```bash
grep -rn "origin/dev" tools tests docs/*.md README.md || echo "no references"
```

Expected: `no references` (or only references inside build logs and measurement files, which are history and stay as they are).

- [ ] **Step 6: The submodule**

```bash
sed -i '' '/^Momentum-Firmware\/$/d' .gitignore
cat .gitignore
git submodule add -b screen-reader https://github.com/robin24/Momentum-Firmware.git Momentum-Firmware
cat .gitmodules
git submodule status
git status --short
```

Expected: the ignore file without the firmware line; git says it is adding the existing repository at `Momentum-Firmware` to the index; `.gitmodules` has `path = Momentum-Firmware`, the fork's URL and `branch = screen-reader`; the status line shows the current firmware commit with `(heads/screen-reader)`; the staged changes are `.gitignore`, `.gitmodules` and `Momentum-Firmware`.

- [ ] **Step 7: Commit**

```bash
git commit -m "The firmware clone becomes a submodule: the Sonar fork of Momentum on GitHub

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- .gitignore .gitmodules Momentum-Firmware
```

- [ ] **Step 8: Create the project repository and push**

```bash
gh repo create robin24/flipper-access --private --source=. --remote=origin --push --description "Sonar: a talking Flipper Zero. Momentum firmware with a built-in screen reader for blind users, a recorded voice, install tools and documentation."
git remote -v
gh repo view robin24/flipper-access --json visibility,defaultBranchRef --jq '"\(.visibility) \(.defaultBranchRef.name)"'
gh api repos/robin24/flipper-access/contents/.gitmodules --jq .name
git log --oneline -1 origin/main
```

Expected: `PRIVATE main`, `.gitmodules`, and the last commit of `main` on GitHub is the submodule commit.

- [ ] **Step 9: Report**

The report names both URLs, the remote layout of the firmware clone, and confirms that `git push upstream` fails (`git -C Momentum-Firmware push upstream screen-reader --dry-run` must print an error about `no_push`).

---

