# Task 1 Report: The fork and the project repository on GitHub

Status: **DONE_WITH_CONCERNS** (two minor, non-blocking deviations from the brief's exact expected output text — see "Deviations" below; no git/GitHub state is wrong).

## Step-by-step, with verification output

### Step 1: Preconditions

Ran from `/Users/robin/Downloads/flipper-access`:

```
$ gh auth status
github.com
  ✓ Logged in to github.com account robin24 (keyring)
  - Active account: true
  - Git operations protocol: https
  - Token scopes: 'gist', 'read:org', 'repo', 'workflow'

$ git status --short
(empty)

$ git -C Momentum-Firmware status --short
 m applications/external

$ git -C Momentum-Firmware branch --show-current
screen-reader

$ git -C Momentum-Firmware remote -v
origin	https://github.com/Next-Flip/Momentum-Firmware.git (fetch)
origin	https://github.com/Next-Flip/Momentum-Firmware.git (push)
```

Matches the brief exactly: logged in as `robin24`, project tree clean, firmware tree dirty only in the expected nested submodule, branch `screen-reader`, single `origin` remote at Next-Flip.

### Step 2: Create the fork

```
$ gh repo fork Next-Flip/Momentum-Firmware --clone=false --default-branch-only
https://github.com/robin24/Momentum-Firmware
```

Verification (see "Deviations" — the brief's exact jq expression doesn't resolve `parent.nameWithOwner`):

```
$ gh repo view robin24/Momentum-Firmware --json isFork,parent,visibility --jq '"fork=\(.isFork) parent=\(.parent.owner.login)/\(.parent.name) \(.visibility)"'
fork=true parent=Next-Flip/Momentum-Firmware PUBLIC
```

Confirmed correct: `fork=true`, parent `Next-Flip/Momentum-Firmware`, visibility `PUBLIC`.

### Step 3: Point the clone at the fork, keep Momentum fetch-only

```
$ cd Momentum-Firmware
$ git remote rename origin upstream
$ git remote set-url --push upstream no_push
$ git remote add origin https://github.com/robin24/Momentum-Firmware.git
$ git push -u origin screen-reader
To https://github.com/robin24/Momentum-Firmware.git
 * [new branch]          screen-reader -> screen-reader
branch 'screen-reader' set up to track 'origin/screen-reader'.

$ git remote -v
origin	https://github.com/robin24/Momentum-Firmware.git (fetch)
origin	https://github.com/robin24/Momentum-Firmware.git (push)
upstream	https://github.com/Next-Flip/Momentum-Firmware.git (fetch)
upstream	no_push (push)

$ git config branch.screen-reader.remote
origin
```

Matches the brief exactly.

### Step 4: The fork's default branch, description and Actions

```
$ gh repo edit robin24/Momentum-Firmware --default-branch screen-reader --description "Momentum firmware with a built-in screen reader for blind users: the Sonar firmware. Documentation, releases and tools: https://github.com/robin24/flipper-access"
(no output; verified separately, see below)

$ gh api -X PUT repos/robin24/Momentum-Firmware/actions/permissions -F enabled=false
(no output)

$ gh api repos/robin24/Momentum-Firmware/actions/permissions --jq .enabled
false

$ gh repo view robin24/Momentum-Firmware --json defaultBranchRef --jq .defaultBranchRef.name
screen-reader
```

Matches the brief (`false` and `screen-reader`). Also independently confirmed the description was actually set:

```
$ gh repo view robin24/Momentum-Firmware --json description --jq .description
Momentum firmware with a built-in screen reader for blind users: the Sonar firmware. Documentation, releases and tools: https://github.com/robin24/flipper-access
```

### Step 5: Check nothing in the tools names the old remote

`tools`, `tests`, `docs`, `README.md` are project-root directories/files (not inside `Momentum-Firmware`), so this ran at the project root as steps 1/2/8 do:

```
$ grep -rn "origin/dev" tools tests docs/*.md README.md || echo "no references"
no references
```

Matches the brief.

### Step 6: The submodule

```
$ sed -i '' '/^Momentum-Firmware\/$/d' .gitignore
$ cat .gitignore
.DS_Store
.superpowers/
.venv/
__pycache__/
firmware-packages/
logs/
voice/
```

The `Momentum-Firmware/` line is gone, matching the brief.

```
$ git submodule add -b screen-reader https://github.com/robin24/Momentum-Firmware.git Momentum-Firmware
Adding existing repo at 'Momentum-Firmware' to the index
```

Matches the brief's expected message exactly.

```
$ cat .gitmodules
[submodule "Momentum-Firmware"]
	path = Momentum-Firmware
	url = https://github.com/robin24/Momentum-Firmware.git
	branch = screen-reader
```

Matches the brief.

```
$ git submodule status
 6451e86e8c8788b62c8c5d7d48baed9cee04437e Momentum-Firmware (mntm-012-390-g6451e86e8)
```

The commit SHA is right, but the parenthetical differs from the brief's expected `(heads/screen-reader)` — see "Deviations" below; verified benign.

```
$ git status --short
 M .gitignore
A  .gitmodules
Am Momentum-Firmware
```

`.gitmodules` and `Momentum-Firmware` are staged (`A`); `.gitignore` is modified but not staged (` M`, not `M `) — see "Deviations" below; verified this doesn't affect step 7.

### Step 7: Commit

```
$ git commit -m "The firmware clone becomes a submodule: the Sonar fork of Momentum on GitHub

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- .gitignore .gitmodules Momentum-Firmware
[main 4dbe36e] The firmware clone becomes a submodule: the Sonar fork of Momentum on GitHub
 3 files changed, 5 insertions(+), 1 deletion(-)
 create mode 100644 .gitmodules
 create mode 160000 Momentum-Firmware
```

Verified message and diff:

```
$ git log -1 --format='%H%n%s%n%n%b'
4dbe36ed52685dfbba53fa89e5f419da980b0ec7
The firmware clone becomes a submodule: the Sonar fork of Momentum on GitHub

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>

$ git show --stat HEAD
 .gitignore        | 1 -
 .gitmodules       | 4 ++++
 Momentum-Firmware | 1 +
 3 files changed, 5 insertions(+), 1 deletion(-)
```

Message is exactly as specified (including the required `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` line, per this task's explicit binding rule, which takes precedence over the session's generic attribution default for this particular commit). Exactly the three expected files changed.

### Step 8: Create the project repository and push

```
$ gh repo create robin24/flipper-access --private --source=. --remote=origin --push --description "Sonar: a talking Flipper Zero. Momentum firmware with a built-in screen reader for blind users, a recorded voice, install tools and documentation."
https://github.com/robin24/flipper-access
To https://github.com/robin24/flipper-access.git
 * [new branch]      HEAD -> main
branch 'main' set up to track 'origin/main'.

$ git remote -v
origin	https://github.com/robin24/flipper-access.git (fetch)
origin	https://github.com/robin24/flipper-access.git (push)

$ gh repo view robin24/flipper-access --json visibility,defaultBranchRef --jq '"\(.visibility) \(.defaultBranchRef.name)"'
PRIVATE main

$ gh api repos/robin24/flipper-access/contents/.gitmodules --jq .name
.gitmodules

$ git log --oneline -1 origin/main
4dbe36e The firmware clone becomes a submodule: the Sonar fork of Momentum on GitHub
```

Matches the brief exactly: `PRIVATE main`, `.gitmodules` present on GitHub, and `main`'s last commit on GitHub is the submodule commit.

### Step 9: Verify push to upstream is impossible

```
$ git -C Momentum-Firmware push upstream screen-reader --dry-run
fatal: 'no_push' does not appear to be a git repository
fatal: Could not read from remote repository.

Please make sure you have the correct access rights
and the repository exists.
(exit code 128)
```

Confirmed: pushing to `upstream` (Next-Flip) is impossible — git refuses because the push URL is literally the string `no_push`, which is not a valid remote.

### Self-review (done twice: once before finishing, once as the explicit final check)

```
$ git -C /Users/robin/Downloads/flipper-access log -1 -p --stat -- .gitignore .gitmodules
commit 4dbe36ed52685dfbba53fa89e5f419da980b0ec7
Author: Robin Kipp <robin@robin-kipp.net>
Date:   Sat Sep 26 03:41:36 2026 +0200

    The firmware clone becomes a submodule: the Sonar fork of Momentum on GitHub

    Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
---
 .gitignore  | 1 -
 .gitmodules | 4 ++++
 2 files changed, 4 insertions(+), 1 deletion(-)

diff --git a/.gitignore b/.gitignore
index 65e6115..340ead7 100644
--- a/.gitignore
+++ b/.gitignore
@@ -1,7 +1,6 @@
 .DS_Store
 .superpowers/
 .venv/
-Momentum-Firmware/
 __pycache__/
 firmware-packages/
 logs/
diff --git a/.gitmodules b/.gitmodules
new file mode 100644
index 0000000..b26c673
--- /dev/null
+++ b/.gitmodules
@@ -0,0 +1,4 @@
+[submodule "Momentum-Firmware"]
+	path = Momentum-Firmware
+	url = https://github.com/robin24/Momentum-Firmware.git
+	branch = screen-reader

$ git -C /Users/robin/Downloads/flipper-access/Momentum-Firmware remote -v
origin	https://github.com/robin24/Momentum-Firmware.git (fetch)
origin	https://github.com/robin24/Momentum-Firmware.git (push)
upstream	https://github.com/Next-Flip/Momentum-Firmware.git (fetch)
upstream	no_push (push)
```

Both exactly as expected.

Additional sanity checks performed (not required by the brief, done out of caution since this task creates public/private state on GitHub):
- `git -C Momentum-Firmware log -1` still shows `6451e86e...` "FreeRTOS: stack overflow checking..." — unchanged, confirming no commit was made inside the firmware clone.
- `git -C Momentum-Firmware status --short` still shows only ` m applications/external` — unchanged, confirming that submodule was not touched.
- `git ls-tree HEAD Momentum-Firmware` in the project repo shows gitlink `160000 commit 6451e86e8c8788b62c8c5d7d48baed9cee04437e` — matches the firmware's actual HEAD exactly.
- Final `git status --short` in the project repo shows only ` m Momentum-Firmware` (the residual dirty flag propagating up from the nested `applications/external`, expected and out of scope per the binding rules; Task 2 handles it).

## Files changed and commit created

Commit `4dbe36ed52685dfbba53fa89e5f419da980b0ec7` on branch `main` ("The firmware clone becomes a submodule: the Sonar fork of Momentum on GitHub"):
- `.gitignore` — removed the `Momentum-Firmware/` line (1 deletion).
- `.gitmodules` — created (4 lines: submodule name, path, url, branch).
- `Momentum-Firmware` — added as a gitlink (submodule) at commit `6451e86e8c8788b62c8c5d7d48baed9cee04437e`.

Pushed to `https://github.com/robin24/flipper-access` (private, default branch `main`) as the initial and only commit on that branch.

## Repository URLs

- Fork (public): `https://github.com/robin24/Momentum-Firmware` — `isFork=true`, parent `Next-Flip/Momentum-Firmware`, visibility `PUBLIC`, default branch `screen-reader`, Actions disabled (`enabled=false`), description set.
- Project (private): `https://github.com/robin24/flipper-access` — visibility `PRIVATE`, default branch `main`, contains `.gitmodules`, last commit on `main` is `4dbe36e`.

## Deviations from the brief's exact expected text (both verified benign; no git/GitHub state is wrong)

1. **Step 2 verification command's jq path doesn't resolve.** The brief's exact command `gh repo view robin24/Momentum-Firmware --json isFork,parent,visibility --jq '"fork=\(.isFork) parent=\(.parent.nameWithOwner) \(.visibility)"'` printed `fork=true parent=null PUBLIC` instead of `fork=true parent=Next-Flip/Momentum-Firmware PUBLIC`. Root cause: `gh repo view --json parent` returns a fixed shape `{id, name, owner:{id, login}}` with no `nameWithOwner` key, so `.parent.nameWithOwner` is always `null` regardless of whether the fork relationship is correct — this looks like a bug in the brief's jq expression, not a symptom of anything wrong with the fork. I confirmed the real state two ways: raw JSON dump (`parent` was fully populated with `Next-Flip`/`Momentum-Firmware`), and a corrected jq path (`.parent.owner.login`/`.parent.name`) which printed exactly the expected line. I waited ~8s and retried once before investigating, per the brief's own guidance about the view possibly needing a moment; the retry gave the same `null`, which is what led me to check the raw JSON rather than just waiting longer.

2. **Step 6 `git submodule status` annotation differs, and `.gitignore` is "modified" rather than "staged."**
   - The brief expected the parenthetical to read `(heads/screen-reader)`; the actual output is `(mntm-012-390-g6451e86e8)`. `git submodule status` annotates with `git describe` (tag-preferring) for the submodule's HEAD; Momentum's history has reachable release tags (e.g. `mntm-012`), so `describe` resolves to a tag-based description instead of falling back to the branch-name form that `describe --all` would give (I confirmed `git -C Momentum-Firmware describe --all` does print `heads/screen-reader`, and `describe --tags` prints the observed string). The SHA itself (`6451e86e8c8788b62c8c5d7d48baed9cee04437e`) matches `git -C Momentum-Firmware rev-parse HEAD` exactly, so the submodule points at the correct, current commit — only the human-readable annotation differs from what the brief predicted.
   - The brief's expected status line calls `.gitignore` "staged" alongside `.gitmodules` and `Momentum-Firmware`, but none of step 6's commands (`sed`, `git submodule add`) stage `.gitignore` — only `git add` would, and it isn't run. `git status --short` correctly shows it as ` M` (modified, unstaged). This didn't cause a problem: step 7's commit uses an explicit pathspec (`git commit -- .gitignore .gitmodules Momentum-Firmware`), and per `git commit`'s documented behavior, naming a path explicitly picks up that path's current working-tree content for the commit regardless of prior staging state. I verified the resulting commit's diff includes the `.gitignore` change correctly (confirmed above), so the end state is exactly right; only the brief's intermediate description was imprecise.

Neither deviation involved a git mutation behaving unexpectedly (no failed fork, no rejected push, no refused submodule add), so per the task's own rule ("stop and report BLOCKED" applies to those specific failure modes) I treated both as verification-wording issues to double-check and document, not blockers, and continued.

## Concerns

- The two deviations above are cosmetic/verification-wording issues in the brief, not defects in the resulting git/GitHub state; I've verified the actual state matches the brief's intent in both cases. Flagging them so the plan's author can correct the brief's example commands/expected-output text for anyone re-running this task later (the `nameWithOwner` jq path and the `heads/screen-reader` / "staged" wording).
- No concerns about the binding rules: `upstream` never received a push (dry-run confirmed impossible), no history was rewritten, no commit was made inside `Momentum-Firmware`, `applications/external` was left untouched, the commit used an explicit pathspec with the exact required message and attribution line, and `gh repo fork`/`gh repo create` were the only outward actions taken, both run from the project root with the flags the brief specified.
