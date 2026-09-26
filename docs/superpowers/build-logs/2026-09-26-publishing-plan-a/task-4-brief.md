### Task 4: Firmware defaults: origin Sonar, reader on

**Files:**
- Modify: `Momentum-Firmware/fbt_options.py:7`, `Momentum-Firmware/lib/momentum/settings.c:50`

**Interfaces:**
- Produces: `info device` reports `firmware.origin.fork : Sonar`; a device with no saved Momentum settings starts with the screen reader on. Task 10 verifies the first on the device; the second is a default that only a fresh device sees (Robin's saved settings are untouched).

- [ ] **Step 1: The two lines**

In `Momentum-Firmware/fbt_options.py` change

```python
FIRMWARE_ORIGIN = "Momentum"
```

to

```python
# The fork's name: `info device` shows it as firmware.origin.fork, the About screen speaks it
FIRMWARE_ORIGIN = "Sonar"
```

In `Momentum-Firmware/lib/momentum/settings.c` change

```c
    .screen_reader = false, // OFF
```

to

```c
    .screen_reader = true, // ON: a device with no saved settings speaks from its first boot
```

- [ ] **Step 2: Check the build system accepts the option and the unit tests still pass**

```bash
cd Momentum-Firmware && ./fbt -h > /dev/null && echo "fbt ok" && cd ..
tools/run_host_tests.sh
```

Expected: `fbt ok`, the runner green. (`./fbt -h` evaluates `fbt_options.py`; a full build comes in Task 10.)

- [ ] **Step 3: Commit in the firmware, push, bump the pointer**

```bash
cd Momentum-Firmware
git commit -m "The firmware calls itself Sonar, and a fresh device starts with the screen reader on

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- fbt_options.py lib/momentum/settings.c
git push origin screen-reader
cd ..
git add Momentum-Firmware
git commit -m "Firmware at the Sonar defaults commit

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" -- Momentum-Firmware
git push
```

---

