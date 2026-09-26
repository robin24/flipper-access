### Task 9: The test runner in bash, a portable headroom check, the continuous build

**Files:**
- Modify: `tools/run_host_tests.sh` (bash), `tools/flash_headroom.sh` (portable)
- Create: `.github/workflows/build.yml`

**Interfaces:**
- Produces: a green Build workflow on `main`, which uploads the update package as an artifact; `tools/flash_headroom.sh [BIN]` usable on Linux.

- [ ] **Step 1: The runner in bash**

In `tools/run_host_tests.sh` change the first lines

```zsh
#!/bin/zsh
# Build and run the host tests for the screen reader: ...
set -e
ROOT="${0:A:h:h}"
```

to

```bash
#!/bin/bash
# Build and run the host tests for the screen reader: ... (keep the comment lines)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
```

Everything else stays (the array `CFLAGS=(...)` and `"${CFLAGS[@]}"` are valid bash). Run `bash tools/run_host_tests.sh` and `tools/run_host_tests.sh`: both green.

- [ ] **Step 2: The headroom check without BSD stat**

Replace `tools/flash_headroom.sh` with:

```bash
#!/bin/bash
# Firmware image size against the flash the BLE stack leaves free: the updater refuses any page
# at or above SFSA (0xD7 for ble_light 1.20.0, 880,640 bytes); fbt's .free_flash ignores this.
#   tools/flash_headroom.sh [BIN]   (default: the submodule's build/f7-firmware-C/firmware.bin)
ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
BIN="${1:-$ROOT/Momentum-Firmware/build/f7-firmware-C/firmware.bin}"
LIMIT=880640
if [ ! -f "$BIN" ]; then echo "no firmware image at $BIN" >&2; exit 1; fi
SIZE=$(wc -c < "$BIN" | tr -d ' ')
echo "firmware.bin $SIZE bytes, limit $LIMIT, spare $((LIMIT - SIZE)) bytes"
[ "$SIZE" -le "$LIMIT" ]
```

Run `tools/flash_headroom.sh`: expected `firmware.bin 864564 bytes, limit 880640, spare 16076 bytes` (the image from 2026-09-25 still in the build folder; another size is fine as long as it is below the limit).

- [ ] **Step 3: The workflow**

Create `.github/workflows/build.yml`:

```yaml
name: Build

on:
  push:
  pull_request:

concurrency:
  group: build-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    env:
      FBT_GIT_SUBMODULE_SHALLOW: "1"
      WORKFLOW_BRANCH_OR_TAG: ${{ github.ref_name }}
    steps:
      - name: Check out the project
        uses: actions/checkout@v4

      - name: Check out the firmware submodule
        run: git submodule update --init --depth 1 Momentum-Firmware

      - name: Name the build after the firmware commit
        run: echo "DIST_SUFFIX=sonar-ci-$(git -C Momentum-Firmware rev-parse --short=8 HEAD)" >> "$GITHUB_ENV"

      - name: Cache the toolchain
        uses: actions/cache@v4
        with:
          path: Momentum-Firmware/toolchain
          key: toolchain-${{ hashFiles('Momentum-Firmware/scripts/fbtenv.sh') }}

      - name: Host tests
        run: tools/run_host_tests.sh

      - name: Build the firmware and its update package
        run: cd Momentum-Firmware && ./fbt COMPACT=1 DEBUG=0 updater_package

      - name: Flash headroom
        run: tools/flash_headroom.sh

      - name: Upload the package
        uses: actions/upload-artifact@v4
        with:
          name: ${{ env.DIST_SUFFIX }}
          path: Momentum-Firmware/dist/f7-C/flipper-z-f7-update-*.tgz
          if-no-files-found: error
```

- [ ] **Step 4: Commit, push, watch the run**

```bash
git add .github/workflows/build.yml tools/run_host_tests.sh tools/flash_headroom.sh
git commit -m "A continuous build: host tests, the firmware package on Linux, the headroom check

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- .github/workflows/build.yml tools/run_host_tests.sh tools/flash_headroom.sh
git push
gh run list --limit 1
gh run watch --exit-status $(gh run list --limit 1 --json databaseId --jq '.[0].databaseId')
```

Expected: the run completes green within about twenty minutes and lists the artifact. If a step fails, read `gh run view --log-failed`, fix the cause (a missing package on the runner, a path, a shallow-clone limitation), commit with a plain message and push again; up to three rounds. Report the run URL, its duration, the toolchain download time and whether the cache hit on a second run (`gh run rerun` is not needed; a second push in a later task will show it).

---

