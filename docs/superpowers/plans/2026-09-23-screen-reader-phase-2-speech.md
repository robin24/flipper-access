# Screen Reader Phase 2: On-Device Speech Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Speak every screen reader announcement through the Flipper's own speaker, in the SAM voice Robin approved, so the device can be used with no computer attached.

**Architecture:** The SAM synthesizer from the Text to SAM app is ported to plain C and renders into a callback instead of busy waiting on the CPU. A PCM stage holds each rendered value for the same time the approved demo did and converts it to one PWM duty byte per 20 microsecond slot; a DMA channel paced by TIM16's update event streams those bytes to the speaker timer while the CPU is free. A worker thread owns SAM, the ring buffer and the speaker, and is fed by a small queue with interrupt and replace semantics. The screen reader service routes announcements into that queue, and any button press silences speech.

**Tech Stack:** Momentum firmware (C, FreeRTOS, fbt), STM32 LL timer and DMA drivers, clang on macOS for host tests (the original C++ synthesizer is compiled on the Mac as a reference), pyserial tools in the project folder.

**Spec:** `/Users/robin/Downloads/flipper-access/docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md`, section 8 (speech output) and section 16 (phase 1 as built). Section 9 (hotkeys) is phase 3 and not part of this plan.

## Global Constraints

- Firmware repo: `/Users/robin/Downloads/flipper-access/Momentum-Firmware`, branch `screen-reader` (phase 1 lives there, head c661ceced at the start of this plan). Project repo: `/Users/robin/Downloads/flipper-access`, branch main. Never add or reset the submodule `applications/external`; Task 5 edits one file inside it deliberately.
- Build: `cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt`. Warnings are errors. The build must print `API version 87.1 is up to date`; nothing goes into public SDK headers and `./fbt api_sync` is never run. Every new C file under `applications/services/screen_reader/` is compiled into the firmware automatically (sources are globbed recursively), so every task that adds firmware code builds the firmware even when its tests run on the Mac.
- Flash: `./fbt flash_usb` (firmware only; the card already holds matching resources). Wait loop after flashing: `P=/dev/cu.usbmodemflip_R0skie1; gone=0; t0=$(date +%s); while [ $(( $(date +%s) - t0 )) -lt 300 ]; do if [ -e $P ]; then [ $gone -eq 1 ] && break; else gone=1; fi; sleep 2; done; sleep 6`. Right after a flash run `sr screen` once before pressing anything; a "Flipper crashed" popup means the previous image crashed, which must be reported.
- Console helper: `/Users/robin/Downloads/flipper-access/.venv/bin/python /Users/robin/Downloads/flipper-access/tools/flipper_cli.py "<command>" [...]` with `--timeout N`. One serial user at a time. Never send `loader close`; leave apps with `input send back short`. `power reboot` is allowed.
- Host tests: `/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh` builds and runs every host test; it must stay green after each task. Host code is compiled with `clang -std=c11 -Wall -Wextra -Werror` (the C++ reference synthesizer with `-w`).
- Voice: SAM defaults pitch 64, speed 72, mouth 128, throat 128. Speed comes from `momentum_settings.sr_rate` (40 to 120), volume from `momentum_settings.sr_volume` (0 to 100), both already exist.
- Timing: TIM16 as PWM carrier with prescaler 4 (divide by 5) and autoreload 255, which is 50 kHz; one duty byte per carrier period; `SPEECH_SLOT_NS` is 20000. A rendered value is held for `(delta / 8)` microseconds (integer division, as the demo) plus `SPEECH_OVERHEAD_NS`, which Task 5 calibrates so that the played duration of a sentence matches the Text to SAM demo within 3 percent.
- DMA: DMA2 channel 4, DMAMUX request `LL_DMAMUX_REQ_TIM16_UP`, circular, memory byte to peripheral half word into `TIM16->CCR1`, half and complete interrupts, `FuriHalInterruptIdDma2Ch4` registered only while playing. Ring buffer 4096 bytes in two halves of 2048 (41 ms each).
- Speaker: acquired only by the speech worker thread, never while `furi_hal_bus_is_enabled(FuriHalBusTIM16)` reports the timer in use elsewhere (the NFC tag emulation path borrows TIM16), released after 200 ms without speech. Utterances that cannot get the speaker are dropped and counted.
- Memory: everything allocated once at service start; the phase 2 additions may use at most 13 KB of heap plus the synthesizer's static tables. Speech worker: 3 KB stack, `FuriThreadPriorityHigh`.
- Pronunciation output is ASCII, SAM receives chunks of at most 80 characters, upper cased. The reciter inside SAM drops everything after a word boundary once its phoneme string passes 120 characters (ordinary English expands about 1.25 times, spelled letters about twice); `sam_speak` reports how many input characters it used, and the worker speaks the rest with further calls, so no words are lost.
- Commit messages end with a blank line and `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`. Do not push.

---

## File structure

Firmware, all under `applications/services/screen_reader/`:

- `sam/sam.h`, `sam/sam.c`: the synthesizer, plain C, no firmware includes (Task 1).
- `speech_text.h`, `speech_text.c`: pronunciation rewriting and chunking, pure C (Task 2).
- `speech_queue.h`, `speech_queue.c`: utterance queue policy, pure C (Task 3).
- `speech_pcm.h`, `speech_pcm.c`: value hold times, 50 kHz slots, loudness curve, pure C (Task 3).
- `speech_hw.h`, `speech_hw.c`: TIM16 and DMA2 channel 4 (Task 4).
- `speech.h`, `speech.c`: worker thread, ring buffer, speaker ownership (Task 4).
- `screen_reader.h`, `screen_reader.c`, `screen_reader_cli.c`: create the speech engine, console commands (Task 4), route announcements and silence on key press (Task 6).

Firmware, elsewhere: `applications/external/text2sam/sam_app.cpp` gains a timing record for calibration (Task 5).

Project repo:

- `tests/host/sam_ref/furi.h`, `tests/host/sam_ref/stm32wbxx_ll_tim.h`, `tests/host/sam_ref/sam_reference.cpp`, `tests/host/sam_cases.h`, `tests/host/test_sam_port.c` (Task 1).
- `tests/host/test_speech_text.c` (Task 2); `tests/host/test_speech_queue.c`, `tests/host/test_speech_pcm.c` (Task 3).
- `tools/run_host_tests.sh` grows with each host test (Tasks 1 to 3).
- `tools/sam_calibrate.py`, `patches/text2sam-cli-mode.patch` regenerated (Task 5).
- `README.md`, the spec, `docs/measurements/` (Task 6).

---

### Task 1: SAM in plain C, checked sample for sample against the original

**Files:**
- Create: `Momentum-Firmware/applications/services/screen_reader/sam/sam.h`
- Create: `Momentum-Firmware/applications/services/screen_reader/sam/sam.c` (ported from `Momentum-Firmware/applications/external/text2sam/stm32_sam.cpp`, which stays untouched)
- Create: `tests/host/sam_ref/furi.h`, `tests/host/sam_ref/stm32wbxx_ll_tim.h`, `tests/host/sam_ref/sam_reference.cpp`
- Create: `tests/host/sam_cases.h`, `tests/host/test_sam_port.c`
- Modify: `tools/run_host_tests.sh`

**Interfaces:**
- Produces: `sam.h` below. `sam_speak` renders one text through `SamOutputCallback`; five values per call with their duration `delta` in SAM units. Later tasks rely on exactly these names.

- [ ] **Step 1: Write the header**

Create `applications/services/screen_reader/sam/sam.h`:

```c
/**
 * @file sam.h
 * SAM (Software Automatic Mouth) speech synthesizer: plain C port of the Text to SAM app's
 * STM32SAM class. Renders text into 8 bit values handed to a callback five at a time, each
 * group with its duration in SAM time units. No hardware access, no heap. Not reentrant:
 * one caller at a time.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Longest text sam_speak accepts, in characters. */
#define SAM_MAX_INPUT 250

typedef struct {
    uint8_t pitch; /**< 64 by default; smaller values give a higher voice */
    uint8_t speed; /**< 72 by default; bigger values speak slower */
    uint8_t mouth; /**< 128 by default */
    uint8_t throat; /**< 128 by default */
} SamVoice;

#define SAM_VOICE_DEFAULT \
    ((SamVoice){.pitch = 64, .speed = 72, .mouth = 128, .throat = 128})

/**
 * Receives five consecutive output values (0..255, 128 is the mid level) that together last
 * `delta` SAM time units. The Text to SAM app held each of the five values for delta / 8
 * microseconds. Return false to abort rendering.
 */
typedef bool (*SamOutputCallback)(const uint8_t values[5], uint16_t delta, void* context);

/**
 * Render text. Returns true when the text was rendered; false when the text was empty,
 * longer than SAM_MAX_INPUT, could not be converted to phonemes, or the callback aborted.
 * `consumed` (may be NULL) receives the number of characters of `text` that were rendered:
 * the whole length normally, less when the reciter ran out of room at a word boundary
 * (its phoneme string holds 120 characters); call again with `text + consumed` for the rest.
 * The port carries guards, marked "port guard", against the original's endless loops and
 * table over-reads; all other arithmetic is the original's.
 */
bool sam_speak(
    const char* text,
    const SamVoice* voice,
    SamOutputCallback callback,
    void* context,
    size_t* consumed);

#ifdef __cplusplus
}
#endif
```

- [ ] **Step 2: Write the reference harness and the case list (the failing test)**

Create `tests/host/sam_cases.h`, shared by the reference and the port so both run identical inputs:

```c
#pragma once

typedef struct {
    const char* text;
    unsigned char pitch;
    unsigned char speed;
    unsigned char mouth;
    unsigned char throat;
} SamCase;

static const SamCase sam_cases[] = {
    {"Hello Robin. This is your Flipper Zero speaking.", 64, 72, 128, 128},
    {"The quick brown fox jumps over the lazy dog.", 64, 72, 128, 128},
    {"Settings. Bluetooth, one of eleven.", 64, 72, 128, 128},
    {"N F C. Read. Saved. Extra actions.", 64, 72, 128, 128},
    {"Point the remote at I R port and press the button.", 64, 72, 128, 128},
    {"Hello Robin. This is your Flipper Zero speaking.", 64, 100, 128, 128},
    {"Hello Robin. This is your Flipper Zero speaking.", 48, 72, 128, 128},
    {"Hello Robin. This is your Flipper Zero speaking.", 64, 50, 150, 200},
    {"W", 64, 72, 128, 128},
    {"w", 64, 72, 128, 128},
    {"", 64, 72, 128, 128},
};

#define SAM_CASE_COUNT (sizeof(sam_cases) / sizeof(sam_cases[0]))
```

Create `tests/host/sam_ref/furi.h` (the only firmware header the original synthesizer includes):

```c
#pragma once
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef __cplusplus
extern "C" {
#endif
void furi_delay_us(uint32_t us);
#ifdef __cplusplus
}
#endif
```

Create `tests/host/sam_ref/stm32wbxx_ll_tim.h` (stubs for the timer calls in the original's `begin` and `SetAUDIO`):

```c
#pragma once
#include <stdint.h>

typedef struct {
    uint32_t Prescaler, CounterMode, Autoreload, ClockDivision, RepetitionCounter;
} LL_TIM_InitTypeDef;

typedef struct {
    uint32_t OCMode, OCState, OCNState, CompareValue, OCPolarity, OCNPolarity, OCIdleState,
        OCNIdleState;
} LL_TIM_OC_InitTypeDef;

typedef struct {
    int unused;
} TIM_TypeDef;

extern TIM_TypeDef tim16_stub;
#define TIM16 (&tim16_stub)
#define LL_TIM_CHANNEL_CH1    1u
#define LL_TIM_OCMODE_PWM1    6u
#define LL_TIM_OCSTATE_ENABLE 1u

static inline int LL_TIM_Init(TIM_TypeDef* t, LL_TIM_InitTypeDef* i) {
    (void)t;
    (void)i;
    return 0;
}
static inline int LL_TIM_OC_Init(TIM_TypeDef* t, uint32_t c, LL_TIM_OC_InitTypeDef* i) {
    (void)t;
    (void)c;
    (void)i;
    return 0;
}
static inline void LL_TIM_EnableAllOutputs(TIM_TypeDef* t) {
    (void)t;
}
static inline void LL_TIM_EnableCounter(TIM_TypeDef* t) {
    (void)t;
}
void LL_TIM_OC_SetCompareCH1(TIM_TypeDef* t, uint32_t v);
```

Create `tests/host/sam_ref/sam_reference.cpp`. It records what the original would have sent to the speaker: the delay before each value (`f`, from `furi_delay_us`) and the duty written to the timer (after the original's loudness curve), folded into a count, a sum and a hash per case:

```cpp
#include <cstdio>
#include <cstring>
#include "stm32_sam.h"
#include <stm32wbxx_ll_tim.h>
#include "../sam_cases.h"

TIM_TypeDef tim16_stub;

static unsigned long long n_values, sum_f, hash;
static uint32_t pending_f;

extern "C" void furi_delay_us(uint32_t us) {
    pending_f = us;
}

void LL_TIM_OC_SetCompareCH1(TIM_TypeDef* t, uint32_t v) {
    (void)t;
    n_values++;
    sum_f += pending_f;
    hash = (hash ^ ((unsigned long long)v * 131u + pending_f)) * 1099511628211ULL;
    pending_f = 0;
}

int main() {
    for(size_t i = 0; i < SAM_CASE_COUNT; i++) {
        const SamCase* c = &sam_cases[i];
        char buf[256];
        memset(buf, 0, sizeof(buf));
        strncpy(buf, c->text, sizeof(buf) - 1);
        n_values = 0;
        sum_f = 0;
        hash = 1469598103934665603ULL;
        STM32SAM voice; // a fresh instance per case: same resets as one sam_speak call
        voice.begin();
        voice.setVoice(c->pitch, c->speed, c->mouth, c->throat);
        voice.say(buf);
        printf("case %zu n=%llu sum_f=%llu hash=%016llx\n", i, n_values, sum_f, hash);
    }
    return 0;
}
```

Create `tests/host/test_sam_port.c`. The port's callback gets raw values and `delta`; the harness derives the same `f = delta / 8` and applies the same loudness curve the original applied inside `SetAUDIO`, so both programs print identical `case` lines when the port is exact. It also checks aborting and that state is reset between calls:

```c
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "sam.h"
#include "sam_cases.h"

static unsigned long long n_values, sum_f, hash;

// The Text to SAM app's SetAUDIO curve, reproduced operation for operation
static uint32_t demo_curve(uint8_t x) {
    float data = x;
    data /= 255.0f;
    data -= 0.5f;
    data *= 4.0f;
    data = tanhf(data);
    data += 0.5f;
    data *= 255.0f;
    if(data < 0) {
        data = 0;
    } else if(data > 255) {
        data = 255;
    }
    return (uint32_t)data;
}

static bool record(const uint8_t values[5], uint16_t delta, void* context) {
    (void)context;
    uint32_t f = delta / 8;
    for(int k = 0; k < 5; k++) {
        n_values++;
        sum_f += f;
        hash = (hash ^ ((unsigned long long)demo_curve(values[k]) * 131u + f)) *
               1099511628211ULL;
    }
    return true;
}

static unsigned abort_calls;
static bool abort_after_1000(const uint8_t values[5], uint16_t delta, void* context) {
    (void)values;
    (void)delta;
    (void)context;
    abort_calls++;
    return abort_calls < 1000;
}

static unsigned long long run_case(const SamCase* c) {
    n_values = 0;
    sum_f = 0;
    hash = 1469598103934665603ULL;
    SamVoice voice = {c->pitch, c->speed, c->mouth, c->throat};
    sam_speak(c->text, &voice, record, NULL, NULL);
    return hash;
}

int main(void) {
    int failures = 0;
    for(size_t i = 0; i < SAM_CASE_COUNT; i++) {
        run_case(&sam_cases[i]);
        printf("case %zu n=%llu sum_f=%llu hash=%016llx\n", i, n_values, sum_f, hash);
    }

    // Aborting stops rendering at the callback that said so
    SamVoice voice = SAM_VOICE_DEFAULT;
    abort_calls = 0;
    bool completed = sam_speak(sam_cases[0].text, &voice, abort_after_1000, NULL, NULL);
    if(completed || abort_calls != 1000) {
        printf("FAIL abort: completed=%d calls=%u\n", completed, abort_calls);
        failures++;
    }

    // An aborted call leaves no trace: the next call renders exactly as a fresh one
    unsigned long long fresh = run_case(&sam_cases[1]);
    abort_calls = 0;
    sam_speak(sam_cases[0].text, &voice, abort_after_1000, NULL, NULL);
    unsigned long long after_abort = run_case(&sam_cases[1]);
    if(fresh != after_abort) {
        printf("FAIL state: fresh=%016llx after_abort=%016llx\n", fresh, after_abort);
        failures++;
    }

    // Rejected inputs
    if(sam_speak("", &voice, record, NULL, NULL)) {
        printf("FAIL empty text accepted\n");
        failures++;
    }
    char too_long[SAM_MAX_INPUT + 2];
    memset(too_long, 'a', sizeof(too_long) - 1);
    too_long[sizeof(too_long) - 1] = '\0';
    if(sam_speak(too_long, &voice, record, NULL, NULL)) {
        printf("FAIL over long text accepted\n");
        failures++;
    }

    printf("port checks: %d failures\n", failures);
    return failures ? 1 : 0;
}
```

Replace `tools/run_host_tests.sh` with a runner that builds every host test and compares the port with the reference:

```bash
#!/bin/zsh
# Build and run the host tests for the screen reader: the screen model, the SAM port checked
# against the original C++ synthesizer, and the speech helpers. Uses clang from Xcode.
set -e
ROOT="${0:A:h:h}"
SRC="$ROOT/Momentum-Firmware/applications/services/screen_reader"
SAM_ORIG="$ROOT/Momentum-Firmware/applications/external/text2sam"
TESTS="$ROOT/tests/host"
OUT="${TMPDIR:-/tmp}/screen_reader_host_tests"
mkdir -p "$OUT"
CFLAGS=(-std=c11 -Wall -Wextra -Werror -O1)

clang "${CFLAGS[@]}" -I "$SRC" -o "$OUT/test_screen_model" \
  "$TESTS/test_screen_model.c" "$SRC/screen_model.c"
"$OUT/test_screen_model"

clang++ -std=c++17 -O1 -w -I "$TESTS/sam_ref" -I "$SAM_ORIG" -o "$OUT/sam_reference" \
  "$TESTS/sam_ref/sam_reference.cpp" "$SAM_ORIG/stm32_sam.cpp"
clang "${CFLAGS[@]}" -I "$SRC/sam" -I "$TESTS" -o "$OUT/test_sam_port" \
  "$TESTS/test_sam_port.c" "$SRC/sam/sam.c" -lm
"$OUT/sam_reference" > "$OUT/sam_reference.txt"
"$OUT/test_sam_port" > "$OUT/sam_port.txt"
if ! diff <(grep '^case' "$OUT/sam_reference.txt") <(grep '^case' "$OUT/sam_port.txt"); then
  echo "SAM port output differs from the original synthesizer"
  exit 1
fi
grep -v '^case' "$OUT/sam_port.txt"
echo "SAM port matches the original on $(grep -c '^case' "$OUT/sam_reference.txt") cases"
```

```bash
chmod +x /Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

- [ ] **Step 3: Run the runner to see it fail**

```bash
/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

Expected: the screen model test passes, the reference builds, and clang fails on `sam/sam.c` because it does not exist yet.

- [ ] **Step 4: Port the synthesizer**

Start from a copy: `cp applications/external/text2sam/stm32_sam.cpp applications/services/screen_reader/sam/sam.c`. Then apply these edits, keeping every table and every algorithm line unchanged:

1. Replace `#include "stm32_sam.h"` at the top with:
   ```c
   #include "sam.h"

   #include <stdbool.h>
   #include <stdint.h>
   #include <string.h>
   ```
2. Delete the hardware section at the end of the file: from the line `#include <math.h>` (just before the `FURI_HAL_SPEAKER_TIMER` defines) to the end. That removes `begin()` and `SetAUDIO()` and the Arduino `USE_ROGER_CORE` / `USE_STM32duino_CORE` blocks.
3. Delete the two constructors `STM32SAM::STM32SAM(...)`, the commented destructor, and the public wrappers: both `sam(...)` overloads, `say`, `sing`, `sayPhonetic`, `singPhonetic` (all overloads), `setVoice`, `setPitch`, `setSpeed`, `setMouth`, `setThroat`. Keep `to_upper_case`. Keep everything else, including the reciter (`TextToPhonemes` and its helpers) and the renderer.
4. Turn every remaining method into a file local function: replace `void STM32SAM::Name(` with `static void Name(`, `int STM32SAM::Name(` with `static int Name(`, `unsigned char STM32SAM::Name(` with `static unsigned char Name(`. Functions declared with empty parentheses become `(void)`.
5. Add, after the includes, the former member variables and the port's state:
   ```c
   static unsigned char speed;
   static unsigned char pitch;
   static unsigned char mouth;
   static unsigned char throat;
   static unsigned char phonetic;
   static unsigned char singmode;

   static SamOutputCallback sam_callback;
   static void* sam_context;
   static bool sam_aborted;
   ```
   and prototypes for every static function that is called before its definition (the list in the private section of `stm32_sam.h` is the complete list: `Output8BitAry`, `Output8Bit`, `Read`, `Write`, `RenderSample`, `Render`, `AddInflection`, `SetMouthThroat`, `trans`, `SetInput`, `Init`, `SAMMain`, `PrepareOutput`, `Insert`, `InsertBreath`, `CopyStress`, `Parser1`, `SetPhonemeLength`, `Code41240`, `Parser2`, `AdjustLengths`, `Code47503`, `Code37055`, `Code37066`, `GetRuleByte`, `TextToPhonemes`).
6. Replace the body of `Output8BitAry` so that it reports instead of waiting:
   ```c
   static void Output8BitAry(int index, unsigned char ary[5]) {
       int bufferposOld = bufferpos;
       bufferpos += timetable[oldtimetableindex][index];
       oldtimetableindex = index;
       int delta = bufferpos - bufferposOld;
       if(sam_aborted) return;
       if(!sam_callback(ary, (uint16_t)delta, sam_context)) sam_aborted = true;
   }
   ```
7. Make an abort stop the renderer promptly: insert `if(sam_aborted) return;` as the first statement inside the sound output loop of `Render` (the `while(1)` whose first line is `A = sampledConsonantFlag[Y];`) and as the first statement inside the `while(1)` loop of `PrepareOutput`.
8. Append the entry point at the end of the file. It performs the same resets as the original default constructor, then the same steps as the original `sam()`:
   ```c
   bool sam_speak(const char* text, const SamVoice* voice, SamOutputCallback callback, void* context, size_t* consumed) {
       if(!text || !voice || !callback) return false;
       size_t len = strlen(text);
       if(len == 0 || len > SAM_MAX_INPUT) return false;

       // Same resets as the original STM32SAM constructor, so every call starts alike
       wait1 = 7;
       wait2 = 6;
       mem59 = 0;
       oldtimetableindex = 0;

       phonetic = 0;
       singmode = 0;
       pitch = voice->pitch;
       speed = voice->speed;
       mouth = voice->mouth;
       throat = voice->throat;

       sam_callback = callback;
       sam_context = context;
       sam_aborted = false;

       memset(input, 0, sizeof(input));
       memcpy(input, text, len);
       // The original upper cases every character except the first; kept for identical output
       for(size_t i = 1; input[i] != 0; i++) {
           input[i] = to_upper_case(input[i]);
       }
       strcat(input, "[");
       if(!TextToPhonemes((unsigned char*)input)) return false;
       SetInput(input);
       if(!SAMMain()) return false;
       return !sam_aborted;
   }
   ```
9. Compile with `clang -std=c11 -Wall -Wextra -Werror -c applications/services/screen_reader/sam/sam.c -o /dev/null` and fix what C rejects: `bool` needs the include already added, functions that became unused after step 3 must be deleted, `()` parameter lists become `(void)`, and any sign comparison or unused variable warning is fixed in the least invasive way that keeps the arithmetic identical (casts, not reordering). Never change table contents or arithmetic.

- [ ] **Step 5: Run the runner to see it pass**

```bash
/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
```

Expected: `SAM port matches the original on 11 cases` and `port checks: 0 failures`. If a case differs, compare the two `case` lines: a different `n` means the loop structure changed, a different `sum_f` with equal `n` means the timetable path changed, a different hash alone means a value changed.

- [ ] **Step 6: Build the firmware**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt 2>&1 | grep -E "error|warning|API version|\.free_flash" | head
```

Expected: no errors, `API version 87.1 is up to date`, `.free_flash` about 15 to 25 KB smaller than before (the tables and renderer are now in the image). GCC may warn where clang did not; fix in the same spirit as step 4.9.

- [ ] **Step 7: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/sam && git commit -m "screen reader: SAM synthesizer as plain C with a callback output"
cd /Users/robin/Downloads/flipper-access && git add tests/host/sam_ref tests/host/sam_cases.h tests/host/test_sam_port.c tools/run_host_tests.sh && git commit -m "host tests: SAM port checked against the original synthesizer"
```

---

### Task 2: Pronunciation and chunking

**Files:**
- Create: `Momentum-Firmware/applications/services/screen_reader/speech_text.h`, `speech_text.c`
- Create: `tests/host/test_speech_text.c`
- Modify: `tools/run_host_tests.sh`

**Interfaces:**
- Produces: `size_t speech_text_expand(const char* in, char* out, size_t out_size)` and `size_t speech_text_next_chunk(const char* text, size_t* pos, char* chunk, size_t chunk_size)`, constants `SPEECH_TEXT_MAX` (800, five times an announcement: a screen of two digit pairs expands about 4.7 times) and `SPEECH_CHUNK_MAX` (80). Task 4's worker calls expand once per utterance, then next_chunk until it returns 0, upper casing each chunk before `sam_speak`.

Rules the code implements (SAM's own behaviour was measured: isolated letters are spoken by name except A, which becomes the article, so A is written as "ay"; digits are spoken one by one; words such as okay, gigahertz, percent, slash, dot come out correctly):

1. A whole announcement that is one character: a letter becomes its upper case letter, except A becomes "ay"; a digit becomes its word; punctuation becomes its name (space "space", period "dot", comma "comma", hyphen "dash", underscore "underscore", slash "slash", colon "colon", semicolon "semicolon", exclamation "exclamation mark", question "question mark", apostrophe "apostrophe", quote "quote", plus "plus", star "star", equals "equals", percent "percent", ampersand "and", hash "number", at "at", parentheses "open paren" and "close paren", brackets "open bracket" and "close bracket").
2. Otherwise the text is scanned as tokens. A token is a run of letters, digits, apostrophes between letters, periods between two alphanumerics, and hyphens between two alphanumerics.
3. Whole token replacements, exact match: Sub-GHz and SubGHz "sub gigahertz"; kHz "kilohertz"; MHz "megahertz"; GHz "gigahertz"; Hz "hertz"; dBm "dee bee em"; dB "dee bee"; iButton "eye button"; OK and Ok "okay"; PIN "pin"; Wi-Fi and WiFi "why fye"; mAh "milliamp hours"; MNTM "momentum".
4. A token with periods between alphanumerics that is not a decimal number is split at the periods with the word "dot" between the parts (key.sub reads "key dot sub"). A token with hyphens that matched nothing is split at the hyphens and each part processed.
5. A token that starts with digits, optionally a period and more digits, and continues with letters is split into the number and the letters (125kHz reads as the number then kilohertz; 433.92MHz reads "four hundred thirty three point nine two megahertz"). The letters part is looked up in the rule 3 replacements; otherwise, when it is one to five upper case letters and not in the stop list, it is spelled as in rule 7 (1A reads "one ay", 9F reads "nine F"); otherwise it is copied.
6. A token of digits, optionally followed by a period and more digits, is a number. Up to six digits without a leading zero are spoken as words (zero, one .. nineteen, twenty .. ninety, hundred, thousand, no "and"); otherwise each digit is spoken as its word. The decimal part is "point" followed by its digits one by one.
7. A token of upper case letters and digits, two or more characters long, with at least one letter, that is not in the stop list, is spelled by runs: a run of one to five letters is written character by character separated by spaces, A written as "ay", unless the run itself is in the stop list, in which case it is copied as a word; a run of more than five letters is copied as a word; a run of one to three digits is spoken as a number (rule 6); a longer digit run is spoken digit by digit. Examples: NFC "N F C"; AM650 "ay M six hundred fifty"; T5577 "T five five seven seven"; EM4100 "E M four one zero zero"; DS1990A "D S one nine nine zero ay"; NTAG215 "N T ay G two hundred fifteen"; ISO14443 "I S O one four four four three"; MIFARE "MIFARE"; MODE1 "MODE one"; A1 "ay one"; 3V3 "three V three". Stop list (upper case words that are real words): ON OFF NO YES NEW ADD ALL SET RUN SAVE SEND READ EXIT BACK MENU INFO TEST FILE EDIT OPEN LOCK DEMO HOLD PLAY STOP TIME DATE MODE AUTO EASY NONE MAX MIN RAW WARN FAIL DONE LOW HIGH FULL START RESET CLEAR ENTER EMPTY RETRY MORE FREE UP DOWN LEFT RIGHT HOME AND OR NOT THE GO BAD KEY CARD TAG APP APPS TAB SUB WAIT SCAN SKIP NEXT PREV ERROR OKAY LOAD COPY MOVE NAME TYPE SIZE PAGE LIST VIEW ZERO TEXT SAM AT IN OF TO IS AS BY IT AN BE DO IF SO WE FOR NOW END TOP BIT HEX BIN DEC.
8. Any other token is copied unchanged, except that a token longer than 20 characters is written as pieces of at most 20 characters separated by spaces (the original synthesizer loops forever on words of about 30 letters).
9. Between tokens: period, comma, question mark and exclamation mark are attached to the previous word (SAM pauses on them); a colon becomes a comma unless it sits between two digits, where it becomes a space; slash becomes the word "slash", percent "percent", ampersand "and", plus "plus", equals "equals", hash "number", at "at", star "star"; underscore, whitespace, quotes, brackets, bars, angle brackets and every byte outside printable ASCII become a single space. Runs of spaces collapse, leading and trailing spaces are dropped.
10. Chunking: from the current position, skip spaces; if the rest fits in the limit take it all; otherwise cut at the last sentence end (period, question mark or exclamation mark followed by a space) within the limit, else at the last comma followed by a space, else at the last space, else hard at the limit. Trailing spaces are trimmed; the returned length is 0 when nothing is left.
11. A hyphen directly followed by a digit, at the start of the text or after a character that is not alphanumeric, becomes the word "minus" followed by a space (-90dBm reads "minus ninety dee bee em").
12. A hyphen with a digit on at least one side: when every part of the token is a pure digit run, one hyphen becomes " to " (378-481 reads "three hundred seventy eight to four hundred eighty one") and more become " dash " (2026-09-23 reads "two thousand twenty six dash zero nine dash twenty three"); otherwise the hyphen becomes " dash " (ISO14443-3A reads "I S O one four four four three dash three ay"; Ch-3 reads "Ch dash three"). Hyphens with letters on both sides keep rule 4.
13. A token that is the single upper case letter A becomes "ay", since SAM would speak the article (NFC-A reads "N F C ay"; Type A reads "Type ay"); lower case a stays the article.

- [ ] **Step 1: Write the failing tests**

Create `tests/host/test_speech_text.c`:

```c
#include <stdio.h>
#include <string.h>
#include "speech_text.h"

static int failures = 0;
static int checks = 0;

static void expect(const char* in, const char* want) {
    char out[SPEECH_TEXT_MAX];
    speech_text_expand(in, out, sizeof(out));
    checks++;
    if(strcmp(out, want) != 0) {
        failures++;
        printf("FAIL expand(\"%s\")\n  got  \"%s\"\n  want \"%s\"\n", in, out, want);
    }
}

#define CHECK(cond)                                                            \
    do {                                                                       \
        checks++;                                                              \
        if(!(cond)) {                                                          \
            failures++;                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);            \
        }                                                                      \
    } while(0)

static void test_words_and_numbers(void) {
    expect("Settings. Bluetooth, 1 of 11", "Settings. Bluetooth, one of eleven");
    expect("125 kHz RFID", "one hundred twenty five kilohertz R F I D");
    expect("433.92 MHz", "four hundred thirty three point nine two megahertz");
    expect("Mood: Happy. Level: 1. 18/100", "Mood, Happy. Level, one. eighteen slash one hundred");
    expect("Battery: 87%", "Battery, eighty seven percent");
    expect("2026", "two thousand twenty six");
    expect("1234567", "one two three four five six seven");
    expect("04 A2 FF", "zero four ay 2 F F");
    expect("12:34", "twelve thirty four");
    expect("100", "one hundred");
    expect("105", "one hundred five");
    expect("1000", "one thousand");
    expect("0", "zero");
}

static void test_acronyms_and_terms(void) {
    expect("NFC", "N F C");
    expect("Sub-GHz", "sub gigahertz");
    expect("OK", "okay");
    expect("U2F", "U 2 F");
    expect("GPIO", "G P I O");
    expect("ON", "ON");
    expect("Read RAW", "Read RAW");
    expect("iButton", "eye button");
    expect("Wrong PIN!", "Wrong pin!");
    expect("Point the remote at IR port and press the button", "Point the remote at I R port and press the button");
    expect("125kHz", "one hundred twenty five kilohertz");
    expect("Text to SAM", "Text to SAM");
    expect("MNTM", "momentum");
    expect("A", "ay");
    expect("Supercalifragilisticexpialidocious", "Supercalifragilistic expialidocious");
}

static void test_punctuation(void) {
    expect("buttons: left Retry, right More", "buttons, left Retry, right More");
    expect("key.sub", "key dot sub");
    expect("Don't move", "Don't move");
    expect("Home screen", "Home screen");
    expect("Hold card next to Flipper's back", "Hold card next to Flipper's back");
    expect("some_file_name", "some file name");
    expect("caf\xc3\xa9 au lait", "caf au lait");
    expect("  spaced   out  ", "spaced out");
    expect("", "");
    expect("a (b) [c] <d> |e| \"f\"", "a b c d e f");
}

static void test_single_characters(void) {
    expect("w", "W");
    expect("5", "five");
    expect(".", "dot");
    expect(",", "comma");
    expect(" ", "space");
    expect("_", "underscore");
    expect("space", "space");
    expect("deleted", "deleted");
}

static void test_chunks(void) {
    char chunk[SPEECH_CHUNK_MAX + 1];
    size_t pos = 0;
    const char* one = "Hello world";
    CHECK(speech_text_next_chunk(one, &pos, chunk, sizeof(chunk)) == 11);
    CHECK(strcmp(chunk, "Hello world") == 0);
    CHECK(speech_text_next_chunk(one, &pos, chunk, sizeof(chunk)) == 0);

    const char* three =
        "Sentence number one has some words in it. "
        "Sentence number two has some more words in it. "
        "Sentence number three is the last one.";
    pos = 0;
    size_t n = speech_text_next_chunk(three, &pos, chunk, sizeof(chunk));
    CHECK(n == 41);
    CHECK(strcmp(chunk, "Sentence number one has some words in it.") == 0);
    n = speech_text_next_chunk(three, &pos, chunk, sizeof(chunk));
    CHECK(n == 46);
    CHECK(strcmp(chunk, "Sentence number two has some more words in it.") == 0);
    n = speech_text_next_chunk(three, &pos, chunk, sizeof(chunk));
    CHECK(n == 38);
    CHECK(strcmp(chunk, "Sentence number three is the last one.") == 0);
    CHECK(speech_text_next_chunk(three, &pos, chunk, sizeof(chunk)) == 0);

    char words[151];
    words[0] = '\0';
    for(int i = 0; i < 30; i++) strcat(words, i ? " word" : "word");
    pos = 0;
    n = speech_text_next_chunk(words, &pos, chunk, sizeof(chunk));
    CHECK(n == 79);
    CHECK(chunk[78] == 'd' && chunk[79] == '\0');
    n = speech_text_next_chunk(words, &pos, chunk, sizeof(chunk));
    CHECK(n == 69);
    CHECK(speech_text_next_chunk(words, &pos, chunk, sizeof(chunk)) == 0);

    char solid[121];
    memset(solid, 'x', 120);
    solid[120] = '\0';
    pos = 0;
    CHECK(speech_text_next_chunk(solid, &pos, chunk, sizeof(chunk)) == 80);
    CHECK(speech_text_next_chunk(solid, &pos, chunk, sizeof(chunk)) == 40);

    pos = 0;
    const char* commas = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu, nu xi omicron pi rho sigma tau upsilon phi chi psi omega alpha";
    n = speech_text_next_chunk(commas, &pos, chunk, sizeof(chunk));
    CHECK(chunk[n - 1] == ',');
}

int main(void) {
    test_words_and_numbers();
    test_acronyms_and_terms();
    test_punctuation();
    test_single_characters();
    test_chunks();
    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
```

Add to `tools/run_host_tests.sh` after the SAM section:

```bash
clang "${CFLAGS[@]}" -I "$SRC" -o "$OUT/test_speech_text" \
  "$TESTS/test_speech_text.c" "$SRC/speech_text.c"
"$OUT/test_speech_text"
```

- [ ] **Step 2: Run the runner to see the new test fail**

Expected: clang cannot find `speech_text.h`.

- [ ] **Step 3: Write the header and the implementation**

Create `speech_text.h`:

```c
/**
 * @file speech_text.h
 * Rewrites announcement text into words SAM pronounces well, and splits it into chunks
 * short enough for one synthesizer call. Pure C, host tested.
 */
#pragma once

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPEECH_TEXT_MAX  800
#define SPEECH_CHUNK_MAX 80

/** Rewrite `in` into `out`. Returns the length written. */
size_t speech_text_expand(const char* in, char* out, size_t out_size);

/**
 * Copy the next chunk of `text` starting at *pos into `chunk` and advance *pos.
 * Chunks are at most SPEECH_CHUNK_MAX characters and end at a sentence, a comma or a word
 * boundary when possible. Returns the chunk length, 0 when the text is exhausted.
 */
size_t speech_text_next_chunk(const char* text, size_t* pos, char* chunk, size_t chunk_size);

#ifdef __cplusplus
}
#endif
```

Create `speech_text.c`:

```c
#include "speech_text.h"

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

typedef struct {
    char* buf;
    size_t size;
    size_t len;
} Out;

static bool is_digit(char c) {
    return c >= '0' && c <= '9';
}
static bool is_upper(char c) {
    return c >= 'A' && c <= 'Z';
}
static bool is_lower(char c) {
    return c >= 'a' && c <= 'z';
}
static bool is_alpha(char c) {
    return is_upper(c) || is_lower(c);
}
static bool is_alnum(char c) {
    return is_alpha(c) || is_digit(c);
}

static void out_char(Out* o, char c) {
    if(o->len + 1 < o->size) o->buf[o->len++] = c;
    o->buf[o->len] = '\0';
}

static void out_str(Out* o, const char* s) {
    while(*s) out_char(o, *s++);
}

/** Start a new word: one space after the previous word, none at the start. */
static void out_word(Out* o, const char* s) {
    if(o->len && o->buf[o->len - 1] != ' ') out_char(o, ' ');
    out_str(o, s);
}

/** Attach punctuation to the previous word. */
static void out_punct(Out* o, char c) {
    if(o->len && o->buf[o->len - 1] == ' ') o->len--;
    out_char(o, c);
}

static const char* const ones[] = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
    "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
    "nineteen",
};
static const char* const tens[] = {
    "", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
};

static void number_words(Out* o, unsigned v) {
    if(v >= 1000) {
        number_words(o, v / 1000);
        out_word(o, "thousand");
        v %= 1000;
        if(v == 0) return;
    }
    if(v >= 100) {
        out_word(o, ones[v / 100]);
        out_word(o, "hundred");
        v %= 100;
        if(v == 0) return;
    }
    if(v >= 20) {
        out_word(o, tens[v / 10]);
        v %= 10;
        if(v == 0) return;
    }
    out_word(o, ones[v]);
}

static void digits_one_by_one(Out* o, const char* s, size_t n) {
    for(size_t i = 0; i < n; i++) out_word(o, ones[s[i] - '0']);
}

/** digits, optionally followed by a period and digits */
static void number_token(Out* o, const char* s, size_t n) {
    size_t int_len = 0;
    while(int_len < n && is_digit(s[int_len])) int_len++;
    bool leading_zero = int_len > 1 && s[0] == '0';
    if(int_len <= 6 && !leading_zero) {
        unsigned v = 0;
        for(size_t i = 0; i < int_len; i++) v = v * 10 + (unsigned)(s[i] - '0');
        number_words(o, v);
    } else {
        digits_one_by_one(o, s, int_len);
    }
    if(int_len < n && s[int_len] == '.') {
        out_word(o, "point");
        digits_one_by_one(o, s + int_len + 1, n - int_len - 1);
    }
}

typedef struct {
    const char* from;
    const char* to;
} Term;

static const Term terms[] = {
    {"Sub-GHz", "sub gigahertz"}, {"SubGHz", "sub gigahertz"}, {"kHz", "kilohertz"},
    {"MHz", "megahertz"},         {"GHz", "gigahertz"},        {"Hz", "hertz"},
    {"dBm", "dee bee em"},        {"dB", "dee bee"},           {"iButton", "eye button"},
    {"OK", "okay"},               {"Ok", "okay"},              {"PIN", "pin"},
    {"Wi-Fi", "why fye"},         {"WiFi", "why fye"},         {"mAh", "milliamp hours"},
    {"MNTM", "momentum"},
};

static const char* const stop_words[] = {
    "ON",    "OFF",   "NO",    "YES",   "NEW",   "ADD",   "ALL",   "SET",   "RUN",   "SAVE",
    "SEND",  "READ",  "EXIT",  "BACK",  "MENU",  "INFO",  "TEST",  "FILE",  "EDIT",  "OPEN",
    "LOCK",  "DEMO",  "HOLD",  "PLAY",  "STOP",  "TIME",  "DATE",  "MODE",  "AUTO",  "EASY",
    "NONE",  "MAX",   "MIN",   "RAW",   "WARN",  "FAIL",  "DONE",  "LOW",   "HIGH",  "FULL",
    "START", "RESET", "CLEAR", "ENTER", "EMPTY", "RETRY", "MORE",  "FREE",  "UP",    "DOWN",
    "LEFT",  "RIGHT", "HOME",  "AND",   "OR",    "NOT",   "THE",   "GO",    "BAD",   "KEY",
    "CARD",  "TAG",   "APP",   "APPS",  "TAB",   "SUB",   "WAIT",  "SCAN",  "SKIP",  "NEXT",
    "PREV",  "ERROR", "OKAY",  "LOAD",  "COPY",  "MOVE",  "NAME",  "TYPE",  "SIZE",  "PAGE",
    "LIST",  "VIEW",  "ZERO",  "TEXT",  "SAM",
};

static bool token_equals(const char* s, size_t n, const char* word) {
    return strlen(word) == n && strncmp(s, word, n) == 0;
}

static bool is_stop_word(const char* s, size_t n) {
    for(size_t i = 0; i < sizeof(stop_words) / sizeof(stop_words[0]); i++) {
        if(token_equals(s, n, stop_words[i])) return true;
    }
    return false;
}

static bool is_acronym(const char* s, size_t n) {
    if(n < 2 || n > 5) return false;
    bool has_letter = false;
    for(size_t i = 0; i < n; i++) {
        if(is_upper(s[i])) {
            has_letter = true;
        } else if(!is_digit(s[i])) {
            return false;
        }
    }
    return has_letter && !is_stop_word(s, n);
}

static void spell(Out* o, const char* s, size_t n) {
    for(size_t i = 0; i < n; i++) {
        char letter[2] = {s[i], '\0'};
        out_word(o, s[i] == 'A' ? "ay" : letter);
    }
}

static bool is_number_token(const char* s, size_t n) {
    size_t i = 0;
    while(i < n && is_digit(s[i])) i++;
    if(i == 0) return false;
    if(i == n) return true;
    if(s[i] != '.') return false;
    i++;
    if(i == n) return false;
    while(i < n) {
        if(!is_digit(s[i])) return false;
        i++;
    }
    return true;
}

static void process_token(Out* o, const char* s, size_t n);

static void process_plain(Out* o, const char* s, size_t n) {
    for(size_t i = 0; i < sizeof(terms) / sizeof(terms[0]); i++) {
        if(token_equals(s, n, terms[i].from)) {
            out_word(o, terms[i].to);
            return;
        }
    }
    if(is_number_token(s, n)) {
        number_token(o, s, n);
        return;
    }
    // digits followed by letters: a number and its unit
    size_t d = 0;
    while(d < n && is_digit(s[d])) d++;
    if(d > 0 && d < n && is_alpha(s[d])) {
        number_token(o, s, d);
        process_token(o, s + d, n - d);
        return;
    }
    if(is_acronym(s, n)) {
        spell(o, s, n);
        return;
    }
    // Pieces of at most 20 characters: the synthesizer never returns on very long words
    while(n > 0) {
        char word[21];
        size_t m = n < 20 ? n : 20;
        memcpy(word, s, m);
        word[m] = '\0';
        out_word(o, word);
        s += m;
        n -= m;
    }
}

static void process_token(Out* o, const char* s, size_t n) {
    for(size_t i = 0; i < sizeof(terms) / sizeof(terms[0]); i++) {
        if(token_equals(s, n, terms[i].from)) {
            out_word(o, terms[i].to);
            return;
        }
    }
    if(is_number_token(s, n)) {
        number_token(o, s, n);
        return;
    }
    // a period inside a token that is not a decimal number: "key.sub"
    for(size_t i = 0; i < n; i++) {
        if(s[i] == '.') {
            process_token(o, s, i);
            out_word(o, "dot");
            process_token(o, s + i + 1, n - i - 1);
            return;
        }
    }
    for(size_t i = 0; i < n; i++) {
        if(s[i] == '-') {
            process_token(o, s, i);
            process_token(o, s + i + 1, n - i - 1);
            return;
        }
    }
    process_plain(o, s, n);
}

typedef struct {
    char c;
    const char* name;
} CharName;

static const CharName char_names[] = {
    {' ', "space"},       {'.', "dot"},           {',', "comma"},          {'-', "dash"},
    {'_', "underscore"},  {'/', "slash"},         {'\\', "backslash"},     {':', "colon"},
    {';', "semicolon"},   {'!', "exclamation mark"}, {'?', "question mark"}, {'\'', "apostrophe"},
    {'"', "quote"},       {'+', "plus"},          {'*', "star"},           {'=', "equals"},
    {'%', "percent"},     {'&', "and"},           {'#', "number"},         {'@', "at"},
    {'(', "open paren"},  {')', "close paren"},   {'[', "open bracket"},   {']', "close bracket"},
    {'{', "open brace"},  {'}', "close brace"},   {'<', "less than"},      {'>', "greater than"},
    {'^', "caret"},       {'~', "tilde"},         {'`', "backtick"},       {'|', "bar"},
    {'$', "dollar"},
};

static bool single_character(const char* in, Out* o) {
    if(in[0] == '\0' || in[1] != '\0') return false;
    char c = in[0];
    if(is_alpha(c)) {
        if(c == 'a' || c == 'A') {
            out_str(o, "ay");
        } else {
            out_char(o, is_lower(c) ? (char)(c - 'a' + 'A') : c);
        }
        return true;
    }
    if(is_digit(c)) {
        out_str(o, ones[c - '0']);
        return true;
    }
    for(size_t i = 0; i < sizeof(char_names) / sizeof(char_names[0]); i++) {
        if(char_names[i].c == c) {
            out_str(o, char_names[i].name);
            return true;
        }
    }
    return false;
}

static bool in_token(const char* s, size_t i, size_t n) {
    char c = s[i];
    if(is_alnum(c)) return true;
    bool prev = i > 0 && is_alnum(s[i - 1]);
    bool next = i + 1 < n && is_alnum(s[i + 1]);
    if(c == '\'') return i > 0 && is_alpha(s[i - 1]) && next && is_alpha(s[i + 1]);
    if(c == '.' || c == '-') return prev && next;
    return false;
}

size_t speech_text_expand(const char* in, char* out, size_t out_size) {
    Out o = {.buf = out, .size = out_size, .len = 0};
    if(out_size == 0) return 0;
    out[0] = '\0';
    if(!in) return 0;
    if(single_character(in, &o)) return o.len;

    size_t n = strlen(in);
    size_t i = 0;
    while(i < n) {
        if(in_token(in, i, n)) {
            size_t start = i;
            while(i < n && in_token(in, i, n)) i++;
            process_token(&o, in + start, i - start);
            continue;
        }
        char c = in[i];
        unsigned char uc = (unsigned char)c;
        bool between_digits = i > 0 && i + 1 < n && is_digit(in[i - 1]) && is_digit(in[i + 1]);
        if(c == '.' || c == ',' || c == '?' || c == '!') {
            out_punct(&o, c);
        } else if(c == ':') {
            if(!between_digits) out_punct(&o, ',');
        } else if(c == '/') {
            out_word(&o, "slash");
        } else if(c == '%') {
            out_word(&o, "percent");
        } else if(c == '&') {
            out_word(&o, "and");
        } else if(c == '+') {
            out_word(&o, "plus");
        } else if(c == '=') {
            out_word(&o, "equals");
        } else if(c == '#') {
            out_word(&o, "number");
        } else if(c == '@') {
            out_word(&o, "at");
        } else if(c == '*') {
            out_word(&o, "star");
        } else if(uc < 0x20 || uc > 0x7E || c == ' ' || c == '_' || c == '"' || c == '\'' ||
                  c == '-' || c == '(' || c == ')' || c == '[' || c == ']' || c == '{' ||
                  c == '}' || c == '<' || c == '>' || c == '|' || c == '\\' || c == '~' ||
                  c == '^' || c == '`' || c == '$' || c == ';') {
            if(o.len && o.buf[o.len - 1] != ' ') out_char(&o, ' ');
        }
        i++;
    }
    while(o.len && o.buf[o.len - 1] == ' ') o.buf[--o.len] = '\0';
    return o.len;
}

size_t speech_text_next_chunk(const char* text, size_t* pos, char* chunk, size_t chunk_size) {
    if(chunk_size == 0) return 0;
    chunk[0] = '\0';
    size_t len = strlen(text);
    size_t start = *pos;
    while(start < len && text[start] == ' ') start++;
    if(start >= len) {
        *pos = len;
        return 0;
    }
    size_t max = SPEECH_CHUNK_MAX;
    if(max > chunk_size - 1) max = chunk_size - 1;
    size_t remaining = len - start;
    size_t take = remaining;
    if(remaining > max) {
        size_t best = 0;
        for(size_t i = start; i < start + max; i++) {
            char c = text[i];
            if((c == '.' || c == '?' || c == '!') && text[i + 1] == ' ') best = i + 1 - start;
        }
        if(!best) {
            for(size_t i = start; i < start + max; i++) {
                if(text[i] == ',' && text[i + 1] == ' ') best = i + 1 - start;
            }
        }
        if(!best) {
            for(size_t i = start; i < start + max; i++) {
                if(text[i] == ' ') best = i - start;
            }
        }
        take = best ? best : max;
    }
    memcpy(chunk, text + start, take);
    chunk[take] = '\0';
    *pos = start + take;
    while(take && chunk[take - 1] == ' ') chunk[--take] = '\0';
    return take;
}
```

- [ ] **Step 4: Run the runner to see it pass**

Expected: `test_speech_text` prints `0 failures` and the earlier tests still pass. If a case fails, fix the code toward the rule list above, not the expectation, unless the expectation contradicts the rule list; in that case report it.

- [ ] **Step 5: Build the firmware and commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt 2>&1 | grep -E "error|warning|API version" | head -5
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/speech_text.h applications/services/screen_reader/speech_text.c && git commit -m "screen reader: pronunciation rewriting and chunking for speech"
cd /Users/robin/Downloads/flipper-access && git add tests/host/test_speech_text.c tools/run_host_tests.sh && git commit -m "host tests: pronunciation and chunking"
```

---

### Task 3: Speech queue and PCM stage

**Files:**
- Create: `speech_queue.h`, `speech_queue.c`, `speech_pcm.h`, `speech_pcm.c` under `Momentum-Firmware/applications/services/screen_reader/`
- Create: `tests/host/test_speech_queue.c`, `tests/host/test_speech_pcm.c`
- Modify: `tools/run_host_tests.sh`

**Interfaces:**
- Produces (queue): `SpeechItem {uint32_t generation; bool replaceable; char text[160];}`, `SpeechQueue`, `speech_queue_init`, `speech_queue_push(queue, text, interrupt, replaceable)`, `speech_queue_pop(queue, out)`, `speech_queue_stop(queue)`, `speech_queue_count(queue)`. Interrupt clears the queue and starts a new generation; a replaceable item overwrites a replaceable item at the tail; a full queue drops its oldest item and counts it in `dropped`.
- Produces (pcm): `SpeechPcm`, `speech_pcm_init(pcm, volume_percent, overhead_ns)`, `speech_pcm_set_volume`, `speech_pcm_reset`, `speech_pcm_silence`, `speech_pcm_push(pcm, values, delta, emit, context)` where `emit` is `bool (*)(uint8_t duty, void* context)`. Constants `SPEECH_SLOT_NS` 20000 and `SPEECH_SILENCE_VALUE` 128.

- [ ] **Step 1: Write the failing tests**

Create `tests/host/test_speech_queue.c`:

```c
#include <stdio.h>
#include <string.h>
#include "speech_queue.h"

static int failures = 0, checks = 0;
#define CHECK(cond)                                                            \
    do {                                                                       \
        checks++;                                                              \
        if(!(cond)) {                                                          \
            failures++;                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);            \
        }                                                                      \
    } while(0)

int main(void) {
    SpeechQueue q;
    SpeechItem item;
    speech_queue_init(&q);
    CHECK(speech_queue_count(&q) == 0);
    CHECK(!speech_queue_pop(&q, &item));

    // Plain order
    speech_queue_push(&q, "one", false, false);
    speech_queue_push(&q, "two", false, false);
    CHECK(speech_queue_count(&q) == 2);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "one") == 0);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "two") == 0);
    CHECK(!speech_queue_pop(&q, &item));

    // Interrupt clears and starts a new generation
    uint32_t g0 = q.generation;
    speech_queue_push(&q, "old", false, false);
    speech_queue_push(&q, "new", true, false);
    CHECK(q.generation == g0 + 1);
    CHECK(speech_queue_count(&q) == 1);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "new") == 0);
    CHECK(item.generation == g0 + 1);

    // A replaceable item at the tail is overwritten by the next replaceable one
    speech_queue_push(&q, "focus", false, false);
    speech_queue_push(&q, "change 1", false, true);
    speech_queue_push(&q, "change 2", false, true);
    CHECK(speech_queue_count(&q) == 2);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "focus") == 0);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "change 2") == 0);

    // A replaceable item after a non replaceable tail is appended
    speech_queue_push(&q, "change 1", false, true);
    speech_queue_push(&q, "focus", false, false);
    speech_queue_push(&q, "change 2", false, true);
    CHECK(speech_queue_count(&q) == 3);
    speech_queue_stop(&q);
    CHECK(speech_queue_count(&q) == 0);

    // Full: the oldest is dropped and counted
    uint32_t dropped = q.dropped;
    speech_queue_push(&q, "a", false, false);
    speech_queue_push(&q, "b", false, false);
    speech_queue_push(&q, "c", false, false);
    speech_queue_push(&q, "d", false, false);
    speech_queue_push(&q, "e", false, false);
    CHECK(speech_queue_count(&q) == SPEECH_QUEUE_CAPACITY);
    CHECK(q.dropped == dropped + 1);
    CHECK(speech_queue_pop(&q, &item) && strcmp(item.text, "b") == 0);

    // Stop bumps the generation so a running utterance notices
    uint32_t g1 = q.generation;
    speech_queue_stop(&q);
    CHECK(q.generation == g1 + 1);

    // Long text is cut to the item size
    char longtext[300];
    memset(longtext, 'x', sizeof(longtext) - 1);
    longtext[sizeof(longtext) - 1] = '\0';
    speech_queue_push(&q, longtext, true, false);
    CHECK(speech_queue_pop(&q, &item) && strlen(item.text) == SPEECH_ITEM_TEXT_MAX - 1);

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
```

Create `tests/host/test_speech_pcm.c`:

```c
#include <math.h>
#include <stdio.h>
#include <string.h>
#include "speech_pcm.h"

static int failures = 0, checks = 0;
#define CHECK(cond)                                                            \
    do {                                                                       \
        checks++;                                                              \
        if(!(cond)) {                                                          \
            failures++;                                                        \
            printf("FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);            \
        }                                                                      \
    } while(0)

// The Text to SAM app's SetAUDIO curve
static uint8_t demo_curve(uint8_t x) {
    float data = x;
    data /= 255.0f;
    data -= 0.5f;
    data *= 4.0f;
    data = tanhf(data);
    data += 0.5f;
    data *= 255.0f;
    if(data < 0) {
        data = 0;
    } else if(data > 255) {
        data = 255;
    }
    return (uint8_t)data;
}

static uint8_t emitted[64];
static size_t emitted_count;
static size_t abort_at = 1000;

static bool collect(uint8_t duty, void* context) {
    (void)context;
    if(emitted_count >= abort_at) return false;
    if(emitted_count < sizeof(emitted)) emitted[emitted_count] = duty;
    emitted_count++;
    return true;
}

int main(void) {
    SpeechPcm pcm;

    // Full volume reproduces the demo curve exactly, zero volume is the mid level
    speech_pcm_init(&pcm, 100, 0);
    for(int x = 0; x < 256; x++) CHECK(pcm.lut[x] == demo_curve((uint8_t)x));
    CHECK(speech_pcm_silence(&pcm) == demo_curve(128));
    speech_pcm_set_volume(&pcm, 0);
    for(int x = 0; x < 256; x++) CHECK(pcm.lut[x] == 127);
    speech_pcm_set_volume(&pcm, 50);
    CHECK(pcm.lut[0] < pcm.lut[128] && pcm.lut[128] < pcm.lut[255]);
    CHECK(pcm.lut[255] < demo_curve(255));

    // Identity mapping for the timing checks: volume 100, values chosen on the flat parts
    speech_pcm_set_volume(&pcm, 100);
    const uint8_t v[5] = {100, 115, 128, 140, 155};
    uint8_t want[5];
    for(int k = 0; k < 5; k++) want[k] = pcm.lut[v[k]];

    // delta 160 and no overhead: 20 us per value, one slot each
    speech_pcm_reset(&pcm);
    emitted_count = 0;
    CHECK(speech_pcm_push(&pcm, v, 160, collect, NULL));
    CHECK(emitted_count == 5);
    for(int k = 0; k < 5; k++) CHECK(emitted[k] == want[k]);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 100 && pcm.slots == 5);

    // delta 162 rounds down to 20 us like the demo's integer division
    speech_pcm_reset(&pcm);
    emitted_count = 0;
    speech_pcm_push(&pcm, v, 162, collect, NULL);
    CHECK(emitted_count == 5);

    // a value shorter than a slot is skipped
    speech_pcm_reset(&pcm);
    emitted_count = 0;
    speech_pcm_push(&pcm, v, 4, collect, NULL);
    CHECK(emitted_count == 0);
    CHECK(pcm.subsamples == 5 && pcm.nominal_us == 0);

    // with 5 us of overhead every value lasts 25 us: slots fall on 0,20,40,60,80,100,120
    speech_pcm_init(&pcm, 100, 5000);
    emitted_count = 0;
    speech_pcm_push(&pcm, v, 160, collect, NULL);
    CHECK(emitted_count == 7);
    const uint8_t order[7] = {0, 0, 1, 2, 3, 4, 4};
    for(int k = 0; k < 7; k++) CHECK(emitted[k] == want[order[k]]);

    // time keeps running across calls: the next call continues from 125 us
    emitted_count = 0;
    speech_pcm_push(&pcm, v, 160, collect, NULL);
    CHECK(emitted_count == 6);

    // abort propagates
    speech_pcm_reset(&pcm);
    emitted_count = 0;
    abort_at = 3;
    CHECK(!speech_pcm_push(&pcm, v, 160, collect, NULL));
    CHECK(emitted_count == 3);

    printf("%d checks, %d failures\n", checks, failures);
    return failures ? 1 : 0;
}
```

Add to `tools/run_host_tests.sh` after the speech text section:

```bash
clang "${CFLAGS[@]}" -I "$SRC" -o "$OUT/test_speech_queue" \
  "$TESTS/test_speech_queue.c" "$SRC/speech_queue.c"
"$OUT/test_speech_queue"
clang "${CFLAGS[@]}" -I "$SRC" -o "$OUT/test_speech_pcm" \
  "$TESTS/test_speech_pcm.c" "$SRC/speech_pcm.c" -lm
"$OUT/test_speech_pcm"
```

- [ ] **Step 2: Run the runner to see the new tests fail** (missing headers).

- [ ] **Step 3: Write the queue**

`speech_queue.h`:

```c
/**
 * @file speech_queue.h
 * Bounded queue of utterances with interrupt and replace semantics. Pure C, host tested.
 * The caller provides locking.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define SPEECH_QUEUE_CAPACITY 4
#define SPEECH_ITEM_TEXT_MAX  160

typedef struct {
    uint32_t generation; /**< generation the item was queued in */
    bool replaceable; /**< a later replaceable item may overwrite it while it waits */
    char text[SPEECH_ITEM_TEXT_MAX];
} SpeechItem;

typedef struct {
    SpeechItem items[SPEECH_QUEUE_CAPACITY];
    uint8_t head;
    uint8_t count;
    uint32_t generation; /**< bumped by interrupt and stop; a speaking item of an older generation aborts */
    uint32_t dropped; /**< items pushed out of a full queue */
} SpeechQueue;

void speech_queue_init(SpeechQueue* queue);

/** interrupt: clear everything and start a new generation before adding. replaceable: overwrite a
 *  replaceable item at the tail instead of appending. A full queue drops its oldest item. */
void speech_queue_push(SpeechQueue* queue, const char* text, bool interrupt, bool replaceable);

bool speech_queue_pop(SpeechQueue* queue, SpeechItem* out);

/** Clear everything and start a new generation. */
void speech_queue_stop(SpeechQueue* queue);

size_t speech_queue_count(const SpeechQueue* queue);

#ifdef __cplusplus
}
#endif
```

`speech_queue.c`:

```c
#include "speech_queue.h"

#include <string.h>

void speech_queue_init(SpeechQueue* queue) {
    memset(queue, 0, sizeof(*queue));
}

static SpeechItem* tail(SpeechQueue* queue) {
    return &queue->items[(queue->head + queue->count - 1) % SPEECH_QUEUE_CAPACITY];
}

static void set_text(SpeechItem* item, const char* text) {
    size_t n = strlen(text);
    if(n > SPEECH_ITEM_TEXT_MAX - 1) n = SPEECH_ITEM_TEXT_MAX - 1;
    memcpy(item->text, text, n);
    item->text[n] = '\0';
}

void speech_queue_push(SpeechQueue* queue, const char* text, bool interrupt, bool replaceable) {
    if(interrupt) {
        queue->generation++;
        queue->count = 0;
        queue->head = 0;
    }
    SpeechItem* item;
    if(replaceable && queue->count > 0 && tail(queue)->replaceable) {
        item = tail(queue);
    } else {
        if(queue->count == SPEECH_QUEUE_CAPACITY) {
            queue->head = (queue->head + 1) % SPEECH_QUEUE_CAPACITY;
            queue->count--;
            queue->dropped++;
        }
        queue->count++;
        item = tail(queue);
    }
    item->generation = queue->generation;
    item->replaceable = replaceable;
    set_text(item, text);
}

bool speech_queue_pop(SpeechQueue* queue, SpeechItem* out) {
    if(queue->count == 0) return false;
    *out = queue->items[queue->head];
    queue->head = (queue->head + 1) % SPEECH_QUEUE_CAPACITY;
    queue->count--;
    return true;
}

void speech_queue_stop(SpeechQueue* queue) {
    queue->generation++;
    queue->count = 0;
    queue->head = 0;
}

size_t speech_queue_count(const SpeechQueue* queue) {
    return queue->count;
}
```

- [ ] **Step 4: Write the PCM stage**

`speech_pcm.h`:

```c
/**
 * @file speech_pcm.h
 * Turns SAM's five value groups into PWM duty bytes, one per 20 microsecond carrier period,
 * holding each value as long as the Text to SAM demo did. Pure C, host tested.
 */
#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** TIM16 update period: 64 MHz / 5 / 256 = 50 kHz */
#define SPEECH_SLOT_NS       20000u
#define SPEECH_SILENCE_VALUE 128u

typedef bool (*SpeechPcmEmit)(uint8_t duty, void* context);

typedef struct {
    uint8_t lut[256]; /**< loudness curve with the volume folded in */
    uint32_t overhead_ns; /**< added to every value's hold time; calibrated against the demo */
    uint64_t now_ns;
    uint64_t next_slot_ns;
    uint32_t subsamples; /**< values received since reset */
    uint32_t nominal_us; /**< sum of delta / 8 microseconds since reset, without overhead */
    uint32_t slots; /**< duty bytes emitted since reset */
} SpeechPcm;

void speech_pcm_init(SpeechPcm* pcm, uint8_t volume_percent, uint32_t overhead_ns);
void speech_pcm_set_volume(SpeechPcm* pcm, uint8_t volume_percent);

/** Start of an utterance: timers and counters back to zero. */
void speech_pcm_reset(SpeechPcm* pcm);

/** The duty byte that keeps the speaker quiet between utterances. */
uint8_t speech_pcm_silence(const SpeechPcm* pcm);

/** Feed five values held for delta / 8 microseconds each plus the overhead. Emits one duty byte
 *  per slot boundary crossed. Returns false when emit asked to stop. */
bool speech_pcm_push(
    SpeechPcm* pcm,
    const uint8_t values[5],
    uint16_t delta,
    SpeechPcmEmit emit,
    void* context);

#ifdef __cplusplus
}
#endif
```

`speech_pcm.c`:

```c
#include "speech_pcm.h"

#include <math.h>
#include <string.h>

void speech_pcm_set_volume(SpeechPcm* pcm, uint8_t volume_percent) {
    if(volume_percent > 100) volume_percent = 100;
    float volume = (float)volume_percent / 100.0f;
    for(int x = 0; x < 256; x++) {
        // The Text to SAM app's curve: tanh soft clipping around the mid level, then volume
        float data = (float)x;
        data /= 255.0f;
        data -= 0.5f;
        data *= 4.0f;
        data = tanhf(data);
        data *= volume;
        data += 0.5f;
        data *= 255.0f;
        if(data < 0) {
            data = 0;
        } else if(data > 255) {
            data = 255;
        }
        pcm->lut[x] = (uint8_t)data;
    }
}

void speech_pcm_init(SpeechPcm* pcm, uint8_t volume_percent, uint32_t overhead_ns) {
    memset(pcm, 0, sizeof(*pcm));
    pcm->overhead_ns = overhead_ns;
    speech_pcm_set_volume(pcm, volume_percent);
}

void speech_pcm_reset(SpeechPcm* pcm) {
    pcm->now_ns = 0;
    pcm->next_slot_ns = 0;
    pcm->subsamples = 0;
    pcm->nominal_us = 0;
    pcm->slots = 0;
}

uint8_t speech_pcm_silence(const SpeechPcm* pcm) {
    return pcm->lut[SPEECH_SILENCE_VALUE];
}

bool speech_pcm_push(
    SpeechPcm* pcm,
    const uint8_t values[5],
    uint16_t delta,
    SpeechPcmEmit emit,
    void* context) {
    uint32_t hold_ns = (uint32_t)(delta / 8) * 1000u + pcm->overhead_ns;
    pcm->subsamples += 5;
    pcm->nominal_us += 5u * (delta / 8);
    for(int k = 0; k < 5; k++) {
        uint64_t end_ns = pcm->now_ns + hold_ns;
        while(pcm->next_slot_ns < end_ns) {
            if(!emit(pcm->lut[values[k]], context)) return false;
            pcm->slots++;
            pcm->next_slot_ns += SPEECH_SLOT_NS;
        }
        pcm->now_ns = end_ns;
    }
    return true;
}
```

- [ ] **Step 5: Run the runner to see both pass, build the firmware, commit**

```bash
/Users/robin/Downloads/flipper-access/tools/run_host_tests.sh
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt 2>&1 | grep -E "error|warning|API version" | head -5
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/speech_queue.h applications/services/screen_reader/speech_queue.c applications/services/screen_reader/speech_pcm.h applications/services/screen_reader/speech_pcm.c && git commit -m "screen reader: speech queue and PCM stage"
cd /Users/robin/Downloads/flipper-access && git add tests/host/test_speech_queue.c tests/host/test_speech_pcm.c tools/run_host_tests.sh && git commit -m "host tests: speech queue and PCM stage"
```

---

### Task 4: Speaker playback, the worker thread, and `sr say`

**Files:**
- Create: `speech_hw.h`, `speech_hw.c`, `speech.h`, `speech.c` under `Momentum-Firmware/applications/services/screen_reader/`
- Modify: `screen_reader.h` (accessor), `screen_reader.c` (create the engine at start), `screen_reader_cli.c` (`say`, `stop`, `rate`, `volume`, status lines)

**Interfaces:**
- Consumes: Tasks 1 to 3.
- Produces: `Speech* speech_alloc(void)`, `speech_say(speech, text, interrupt, replaceable)`, `speech_stop(speech)` (any thread, never blocks), `speech_set_voice(speech, rate, volume)`, `speech_is_busy(speech)`, `speech_get_stats(speech, out)`, `SpeechStats`; `Speech* screen_reader_get_speech(ScreenReader* sr)`; console subcommands `say`, `stop`, `rate`, `volume`.

- [ ] **Step 1: The hardware layer**

`speech_hw.h`:

```c
/**
 * @file speech_hw.h
 * TIM16 as a 50 kHz PWM carrier on the speaker pin, fed by DMA2 channel 4 from a circular
 * byte buffer. The speaker must already be acquired (furi_hal_speaker_acquire) by the caller.
 */
#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

/** Called from the DMA interrupt when the first (false) or second (true) half was played. */
typedef void (*SpeechHwEvent)(bool second_half, void* context);

void speech_hw_start(uint8_t* buffer, size_t size, SpeechHwEvent callback, void* context);
void speech_hw_stop(void);
```

`speech_hw.c`:

```c
#include "speech_hw.h"

#include <furi_hal.h>
#include <stm32wbxx_ll_dma.h>
#include <stm32wbxx_ll_tim.h>

#define SPEECH_TIMER       TIM16
#define SPEECH_DMA         DMA2
#define SPEECH_DMA_CHANNEL LL_DMA_CHANNEL_4

static SpeechHwEvent speech_hw_callback;
static void* speech_hw_context;

static void speech_hw_dma_isr(void* context) {
    UNUSED(context);
    if(LL_DMA_IsActiveFlag_HT4(SPEECH_DMA)) {
        LL_DMA_ClearFlag_HT4(SPEECH_DMA);
        speech_hw_callback(false, speech_hw_context);
    }
    if(LL_DMA_IsActiveFlag_TC4(SPEECH_DMA)) {
        LL_DMA_ClearFlag_TC4(SPEECH_DMA);
        speech_hw_callback(true, speech_hw_context);
    }
}

void speech_hw_start(uint8_t* buffer, size_t size, SpeechHwEvent callback, void* context) {
    speech_hw_callback = callback;
    speech_hw_context = context;

    // 64 MHz / (4 + 1) / (255 + 1) = 50 kHz carrier, as in the Text to SAM app
    LL_TIM_InitTypeDef tim;
    memset(&tim, 0, sizeof(tim));
    tim.Prescaler = 4;
    tim.Autoreload = 255;
    tim.CounterMode = LL_TIM_COUNTERMODE_UP;
    LL_TIM_Init(SPEECH_TIMER, &tim);

    LL_TIM_OC_InitTypeDef oc;
    memset(&oc, 0, sizeof(oc));
    oc.OCMode = LL_TIM_OCMODE_PWM1;
    oc.OCState = LL_TIM_OCSTATE_ENABLE;
    oc.CompareValue = buffer[0];
    LL_TIM_OC_Init(SPEECH_TIMER, LL_TIM_CHANNEL_CH1, &oc);
    LL_TIM_OC_EnablePreload(SPEECH_TIMER, LL_TIM_CHANNEL_CH1);

    LL_DMA_ConfigAddresses(
        SPEECH_DMA,
        SPEECH_DMA_CHANNEL,
        (uint32_t)buffer,
        (uint32_t) & (SPEECH_TIMER->CCR1),
        LL_DMA_DIRECTION_MEMORY_TO_PERIPH);
    LL_DMA_SetDataLength(SPEECH_DMA, SPEECH_DMA_CHANNEL, size);
    LL_DMA_SetPeriphRequest(SPEECH_DMA, SPEECH_DMA_CHANNEL, LL_DMAMUX_REQ_TIM16_UP);
    LL_DMA_SetChannelPriorityLevel(SPEECH_DMA, SPEECH_DMA_CHANNEL, LL_DMA_PRIORITY_VERYHIGH);
    LL_DMA_SetMode(SPEECH_DMA, SPEECH_DMA_CHANNEL, LL_DMA_MODE_CIRCULAR);
    LL_DMA_SetPeriphIncMode(SPEECH_DMA, SPEECH_DMA_CHANNEL, LL_DMA_PERIPH_NOINCREMENT);
    LL_DMA_SetMemoryIncMode(SPEECH_DMA, SPEECH_DMA_CHANNEL, LL_DMA_MEMORY_INCREMENT);
    LL_DMA_SetPeriphSize(SPEECH_DMA, SPEECH_DMA_CHANNEL, LL_DMA_PDATAALIGN_HALFWORD);
    LL_DMA_SetMemorySize(SPEECH_DMA, SPEECH_DMA_CHANNEL, LL_DMA_MDATAALIGN_BYTE);
    LL_DMA_ClearFlag_HT4(SPEECH_DMA);
    LL_DMA_ClearFlag_TC4(SPEECH_DMA);
    LL_DMA_EnableIT_HT(SPEECH_DMA, SPEECH_DMA_CHANNEL);
    LL_DMA_EnableIT_TC(SPEECH_DMA, SPEECH_DMA_CHANNEL);
    furi_hal_interrupt_set_isr(FuriHalInterruptIdDma2Ch4, speech_hw_dma_isr, NULL);
    LL_DMA_EnableChannel(SPEECH_DMA, SPEECH_DMA_CHANNEL);

    LL_TIM_EnableDMAReq_UPDATE(SPEECH_TIMER);
    LL_TIM_EnableAllOutputs(SPEECH_TIMER);
    LL_TIM_EnableCounter(SPEECH_TIMER);
}

void speech_hw_stop(void) {
    LL_TIM_DisableDMAReq_UPDATE(SPEECH_TIMER);
    LL_DMA_DisableChannel(SPEECH_DMA, SPEECH_DMA_CHANNEL);
    LL_DMA_DisableIT_HT(SPEECH_DMA, SPEECH_DMA_CHANNEL);
    LL_DMA_DisableIT_TC(SPEECH_DMA, SPEECH_DMA_CHANNEL);
    furi_hal_interrupt_set_isr(FuriHalInterruptIdDma2Ch4, NULL, NULL);
    LL_TIM_DisableAllOutputs(SPEECH_TIMER);
    LL_TIM_DisableCounter(SPEECH_TIMER);
}
```

- [ ] **Step 2: The engine**

`speech.h`:

```c
/**
 * @file speech.h
 * Speech engine: a worker thread that renders queued utterances with SAM and plays them
 * through the speaker with DMA. Announcements come from the screen reader service; the console
 * command "sr say" uses it too.
 */
#pragma once

#include <furi.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct Speech Speech;

typedef struct {
    uint32_t utterances; /**< started */
    uint32_t dropped; /**< could not get the speaker */
    uint32_t aborted; /**< interrupted by a newer utterance, a stop, or a key press */
    uint32_t underruns; /**< DMA reached a half before it was filled */
    uint32_t queue_dropped; /**< pushed out of a full queue */
    uint32_t queued; /**< items waiting */
    bool speaking; /**< true from dequeue until the utterance has been played out */
    bool speaker_held;
    uint32_t last_subsamples;
    uint32_t last_nominal_ms;
    uint32_t last_played_ms;
    uint32_t stack_free; /**< worker thread stack watermark, bytes */
} SpeechStats;

/** Allocates everything once and starts the worker. */
Speech* speech_alloc(void);

/** Queue text. interrupt: stop what is being said and drop what waits. replaceable: a pending
 *  replaceable item is overwritten instead of queued behind it. */
void speech_say(Speech* speech, const char* text, bool interrupt, bool replaceable);

/** Stop speaking and drop the queue. Safe from any thread, including input callbacks. */
void speech_stop(Speech* speech);

/** rate is the SAM speed (40..120), volume 0..100. Applied from the next utterance on. */
void speech_set_voice(Speech* speech, uint8_t rate, uint8_t volume);

/** True while something is queued or being spoken. */
bool speech_is_busy(Speech* speech);

void speech_get_stats(Speech* speech, SpeechStats* out);

#ifdef __cplusplus
}
#endif
```

`speech.c`:

```c
#include "speech.h"

#include "sam/sam.h"
#include "speech_hw.h"
#include "speech_pcm.h"
#include "speech_queue.h"
#include "speech_text.h"

#include <furi_hal.h>

#define TAG "Speech"

#define SPEECH_RING_SIZE          4096
#define SPEECH_HALF               (SPEECH_RING_SIZE / 2)
#define SPEECH_OVERHEAD_NS        0 /* Task 5 calibrates this against the Text to SAM demo */
#define SPEECH_IDLE_RELEASE_MS    200
#define SPEECH_ACQUIRE_TIMEOUT_MS 500
#define SPEECH_EVENT_TIMEOUT_MS   200

#define SPEECH_FLAG_WORK  (1 << 0)
#define SPEECH_FLAG_STOP  (1 << 1)
#define SPEECH_FLAG_HALF0 (1 << 2) /* DMA finished playing the first half */
#define SPEECH_FLAG_HALF1 (1 << 3) /* DMA finished playing the second half */

struct Speech {
    FuriThread* thread;
    volatile FuriThreadId thread_id;
    FuriMutex* mutex;

    // Guarded by mutex
    SpeechQueue queue;
    SpeechStats stats;

    // Set by any thread, read by the worker
    volatile uint8_t rate;
    volatile uint8_t volume;

    // Worker thread only
    SpeechPcm pcm;
    uint8_t ring[SPEECH_RING_SIZE];
    uint8_t fill_half;
    uint16_t fill_index;
    bool running;
    bool aborted;
    bool stop_pending;
    uint32_t generation;
    uint8_t lut_volume;
    char expanded[SPEECH_TEXT_MAX];
    char chunk[SPEECH_CHUNK_MAX + 2]; /* room for an appended period */
};

static void speech_lock(Speech* speech) {
    furi_check(furi_mutex_acquire(speech->mutex, FuriWaitForever) == FuriStatusOk);
}

static void speech_unlock(Speech* speech) {
    furi_check(furi_mutex_release(speech->mutex) == FuriStatusOk);
}

// Interrupt context
static void speech_dma_event(bool second_half, void* context) {
    Speech* speech = context;
    furi_thread_flags_set(speech->thread_id, second_half ? SPEECH_FLAG_HALF1 : SPEECH_FLAG_HALF0);
}

static uint32_t half_flag(uint8_t half) {
    return half == 0 ? SPEECH_FLAG_HALF0 : SPEECH_FLAG_HALF1;
}

/** A newer utterance, a stop request or a key press makes the current one worthless. */
static bool speech_superseded(Speech* speech) {
    if(speech->stop_pending) return true;
    if(furi_thread_flags_get() & SPEECH_FLAG_STOP) {
        speech->stop_pending = true;
        return true;
    }
    return *(volatile uint32_t*)&speech->queue.generation != speech->generation;
}

/** Wait until the DMA has finished playing `half`. False when stopped or when no event came. */
static bool speech_wait_half_played(Speech* speech, uint8_t half) {
    uint32_t wanted = half_flag(half);
    uint32_t flags =
        furi_thread_flags_wait(wanted | SPEECH_FLAG_STOP, FuriFlagWaitAny, SPEECH_EVENT_TIMEOUT_MS);
    if(flags & FuriFlagError) return false;
    if(flags & SPEECH_FLAG_STOP) {
        speech->stop_pending = true;
        return false;
    }
    return (flags & wanted) != 0;
}

// Called by the PCM stage for every duty byte, on the worker thread
static bool speech_emit(uint8_t duty, void* context) {
    Speech* speech = context;
    if(speech_superseded(speech)) {
        speech->aborted = true;
        return false;
    }
    speech->ring[speech->fill_half * SPEECH_HALF + speech->fill_index++] = duty;
    if(speech->fill_index < SPEECH_HALF) return true;
    speech->fill_index = 0;

    if(!speech->running) {
        // First half complete: start playing it; the second half holds silence until filled
        furi_thread_flags_clear(SPEECH_FLAG_HALF0 | SPEECH_FLAG_HALF1);
        speech_hw_start(speech->ring, SPEECH_RING_SIZE, speech_dma_event, speech);
        speech->running = true;
        speech->fill_half = 1;
        return true;
    }

    // Continue in the other half once the DMA has finished with it. If it has already
    // finished, the DMA moved into the half just written while it was still being filled.
    uint8_t next = speech->fill_half ^ 1;
    if(furi_thread_flags_get() & half_flag(next)) {
        speech_lock(speech);
        speech->stats.underruns++;
        speech_unlock(speech);
    }
    if(!speech_wait_half_played(speech, next)) {
        speech->aborted = true;
        return false;
    }
    speech->fill_half = next;
    return true;
}

static bool speech_sam_output(const uint8_t values[5], uint16_t delta, void* context) {
    Speech* speech = context;
    return speech_pcm_push(&speech->pcm, values, delta, speech_emit, speech);
}

/** Play out what was rendered and stop the hardware cleanly. */
static void speech_flush(Speech* speech) {
    uint8_t silence = speech_pcm_silence(&speech->pcm);
    if(!speech->running) {
        if(speech->fill_index == 0) return; // nothing was rendered
        memset(&speech->ring[speech->fill_index], silence, SPEECH_HALF - speech->fill_index);
        memset(&speech->ring[SPEECH_HALF], silence, SPEECH_HALF);
        furi_thread_flags_clear(SPEECH_FLAG_HALF0 | SPEECH_FLAG_HALF1);
        speech_hw_start(speech->ring, SPEECH_RING_SIZE, speech_dma_event, speech);
        speech->running = true;
        speech_wait_half_played(speech, 0);
    } else {
        uint8_t h = speech->fill_half;
        memset(
            &speech->ring[h * SPEECH_HALF + speech->fill_index],
            silence,
            SPEECH_HALF - speech->fill_index);
        speech_wait_half_played(speech, h ^ 1);
        memset(&speech->ring[(h ^ 1) * SPEECH_HALF], silence, SPEECH_HALF);
        speech_wait_half_played(speech, h);
    }
    speech_hw_stop();
    speech->running = false;
}

static bool speech_take_speaker(Speech* speech) {
    if(furi_hal_speaker_is_mine()) return true;
    // Someone else drives TIM16 (another speaker user, or NFC tag emulation): do not touch it
    if(furi_hal_bus_is_enabled(FuriHalBusTIM16)) return false;
    if(!furi_hal_speaker_acquire(SPEECH_ACQUIRE_TIMEOUT_MS)) return false;
    speech_lock(speech);
    speech->stats.speaker_held = true;
    speech_unlock(speech);
    return true;
}

static void speech_drop_speaker(Speech* speech) {
    if(!furi_hal_speaker_is_mine()) return;
    furi_hal_speaker_release();
    speech_lock(speech);
    speech->stats.speaker_held = false;
    speech_unlock(speech);
}

static void speech_apply_stop(Speech* speech) {
    speech_lock(speech);
    speech_queue_stop(&speech->queue);
    speech_unlock(speech);
    speech->stop_pending = false;
}

static void speech_speak_item(Speech* speech, const SpeechItem* item) {
    speech->generation = item->generation;
    speech->aborted = false;
    speech->fill_half = 0;
    speech->fill_index = 0;
    speech->running = false;

    if(!speech_take_speaker(speech)) {
        speech_lock(speech);
        speech->stats.dropped++;
        speech->stats.speaking = false;
        speech_unlock(speech);
        return;
    }

    uint8_t volume = speech->volume;
    if(volume != speech->lut_volume) {
        speech_pcm_set_volume(&speech->pcm, volume);
        speech->lut_volume = volume;
    }
    speech_pcm_reset(&speech->pcm);
    memset(speech->ring, speech_pcm_silence(&speech->pcm), SPEECH_RING_SIZE);

    speech_text_expand(item->text, speech->expanded, sizeof(speech->expanded));
    SamVoice voice = SAM_VOICE_DEFAULT;
    voice.speed = speech->rate;

    speech_lock(speech);
    speech->stats.utterances++;
    speech_unlock(speech);
    uint32_t started = furi_get_tick();

    size_t pos = 0;
    while(!speech->aborted &&
          speech_text_next_chunk(speech->expanded, &pos, speech->chunk, sizeof(speech->chunk))) {
        for(char* p = speech->chunk; *p; p++) {
            if(*p >= 'a' && *p <= 'z') *p = (char)(*p - 'a' + 'A');
        }
        // A closing period gives the synthesizer a pause to shape the end of the chunk on
        size_t len = strlen(speech->chunk);
        if(len > 0 && len < sizeof(speech->chunk) - 1 && strchr(".?!,", speech->chunk[len - 1]) == NULL) {
            speech->chunk[len] = '.';
            speech->chunk[len + 1] = '\0';
            len++;
        }
        // The reciter inside SAM stops at a word boundary once its phoneme string is full and
        // reports how much text it used; speak the rest with further calls
        size_t offset = 0;
        while(offset < len && !speech->aborted) {
            size_t consumed = 0;
            sam_speak(speech->chunk + offset, &voice, speech_sam_output, speech, &consumed);
            if(consumed == 0) break;
            offset += consumed;
        }
    }

    if(speech->aborted) {
        if(speech->running) {
            speech_hw_stop();
            speech->running = false;
        }
    } else {
        speech_flush(speech);
    }

    speech_lock(speech);
    speech->stats.speaking = false;
    if(speech->aborted) speech->stats.aborted++;
    speech->stats.last_subsamples = speech->pcm.subsamples;
    speech->stats.last_nominal_ms = speech->pcm.nominal_us / 1000;
    speech->stats.last_played_ms = furi_get_tick() - started;
    speech_unlock(speech);
}

static bool speech_pop(Speech* speech, SpeechItem* item) {
    speech_lock(speech);
    bool got = speech_queue_pop(&speech->queue, item);
    if(got) speech->stats.speaking = true; // from here until played out or dropped
    speech_unlock(speech);
    return got;
}

static int32_t speech_worker(void* context) {
    Speech* speech = context;
    speech->thread_id = furi_thread_get_current_id();
    SpeechItem* item = malloc(sizeof(SpeechItem));

    while(true) {
        uint32_t timeout = furi_hal_speaker_is_mine() ? SPEECH_IDLE_RELEASE_MS : FuriWaitForever;
        uint32_t flags =
            furi_thread_flags_wait(SPEECH_FLAG_WORK | SPEECH_FLAG_STOP, FuriFlagWaitAny, timeout);
        if(flags & FuriFlagError) {
            // Quiet for a while: hand the speaker back so beeps and other apps can use it
            speech_drop_speaker(speech);
            continue;
        }
        if(flags & SPEECH_FLAG_STOP) speech->stop_pending = true;
        if(speech->stop_pending) speech_apply_stop(speech);

        while(speech_pop(speech, item)) {
            speech_speak_item(speech, item);
            if(speech->stop_pending) speech_apply_stop(speech);
        }
    }
    return 0;
}

Speech* speech_alloc(void) {
    Speech* speech = malloc(sizeof(Speech));
    memset(speech, 0, sizeof(Speech));
    speech->mutex = furi_mutex_alloc(FuriMutexTypeNormal);
    speech_queue_init(&speech->queue);
    speech->rate = 72;
    speech->volume = 100;
    speech->lut_volume = 100;
    speech_pcm_init(&speech->pcm, 100, SPEECH_OVERHEAD_NS);

    speech->thread = furi_thread_alloc_ex("SpeechWorker", 3 * 1024, speech_worker, speech);
    furi_thread_set_priority(speech->thread, FuriThreadPriorityHigh);
    furi_thread_start(speech->thread);
    while(!speech->thread_id) furi_delay_ms(1);
    return speech;
}

void speech_say(Speech* speech, const char* text, bool interrupt, bool replaceable) {
    furi_check(speech && text);
    speech_lock(speech);
    speech_queue_push(&speech->queue, text, interrupt, replaceable);
    speech->stats.queue_dropped = speech->queue.dropped;
    speech_unlock(speech);
    furi_thread_flags_set(speech->thread_id, SPEECH_FLAG_WORK);
}

void speech_stop(Speech* speech) {
    furi_check(speech);
    furi_thread_flags_set(speech->thread_id, SPEECH_FLAG_STOP);
}

void speech_set_voice(Speech* speech, uint8_t rate, uint8_t volume) {
    furi_check(speech);
    speech->rate = rate;
    speech->volume = volume;
}

bool speech_is_busy(Speech* speech) {
    furi_check(speech);
    speech_lock(speech);
    bool busy = speech->stats.speaking || speech_queue_count(&speech->queue) > 0;
    speech_unlock(speech);
    return busy;
}

void speech_get_stats(Speech* speech, SpeechStats* out) {
    furi_check(speech && out);
    speech_lock(speech);
    *out = speech->stats;
    out->queued = speech_queue_count(&speech->queue);
    speech_unlock(speech);
    out->stack_free = furi_thread_get_stack_space(speech->thread_id);
}
```

- [ ] **Step 3: Wire it into the service and the console**

In `screen_reader.h`, add `#include "speech.h"` after `#include "screen_model.h"`, and this declaration before the closing of the `extern "C"` block:

```c
/** The speech engine, for the console command. */
Speech* screen_reader_get_speech(ScreenReader* sr);
```

In `screen_reader.c`:
- add the field `Speech* speech;` to `struct ScreenReader` after `Gui* gui;`;
- in `screen_reader_srv`, right after `sr_model_init(...)` and before the input subscription, add:
  ```c
  sr->speech = speech_alloc();
  speech_set_voice(sr->speech, momentum_settings.sr_rate, momentum_settings.sr_volume);
  ```
- in `screen_reader_set_enabled`, when `enabled` is false, add `speech_stop(sr->speech);`;
- add the accessor after `screen_reader_get_stats`:
  ```c
  Speech* screen_reader_get_speech(ScreenReader* sr) {
      furi_check(sr);
      return sr->speech;
  }
  ```

In `screen_reader_cli.c`:
- extend `sr_cli_usage` with these lines after the `status` line:
  ```c
      printf("  say <text>   speak text now; sr status shows its timing when done\r\n");
      printf("  stop         stop speaking\r\n");
      printf("  rate <n>     SAM speed 40..120, bigger is slower (saved)\r\n");
      printf("  volume <n>   0..100 (saved)\r\n");
  ```
- add before `sr_cli_execute`:
  ```c
  static void sr_cli_say(ScreenReader* sr, FuriString* args) {
      const char* text = furi_string_get_cstr(args);
      if(strlen(text) == 0) {
          printf("say what?\r\n");
          return;
      }
      speech_say(screen_reader_get_speech(sr), text, true, false);
      printf("queued %u characters; sr status shows the timing when it is done\r\n", (unsigned)strlen(text));
  }

  static void sr_cli_set_number(ScreenReader* sr, FuriString* args, bool rate) {
      int value = 0;
      int lo = rate ? 40 : 0;
      int hi = rate ? 120 : 100;
      if(!args_read_int_and_trim(args, &value) || value < lo || value > hi) {
          printf("expected a number from %d to %d\r\n", lo, hi);
          return;
      }
      if(rate) {
          momentum_settings.sr_rate = (uint32_t)value;
      } else {
          momentum_settings.sr_volume = (uint32_t)value;
      }
      momentum_settings_save();
      speech_set_voice(
          screen_reader_get_speech(sr),
          (uint8_t)momentum_settings.sr_rate,
          (uint8_t)momentum_settings.sr_volume);
      printf("%s set to %d\r\n", rate ? "rate" : "volume", value);
  }
  ```
- in `sr_cli_execute`, add branches before the final `else`:
  ```c
      } else if(furi_string_cmp_str(cmd, "say") == 0) {
          sr_cli_say(sr, args);
      } else if(furi_string_cmp_str(cmd, "stop") == 0) {
          speech_stop(screen_reader_get_speech(sr));
          printf("stopped\r\n");
      } else if(furi_string_cmp_str(cmd, "rate") == 0) {
          sr_cli_set_number(sr, args, true);
      } else if(furi_string_cmp_str(cmd, "volume") == 0) {
          sr_cli_set_number(sr, args, false);
  ```
- in `sr_cli_status`, after the `frames:` printf, add:
  ```c
      SpeechStats speech;
      speech_get_stats(screen_reader_get_speech(sr), &speech);
      printf(
          "speech: %s, queued %lu, speaker held: %s, utterances %lu, aborted %lu, dropped %lu, underruns %lu, queue dropped %lu\r\n",
          speech.speaking ? "speaking" : "idle",
          (unsigned long)speech.queued,
          speech.speaker_held ? "yes" : "no",
          (unsigned long)speech.utterances,
          (unsigned long)speech.aborted,
          (unsigned long)speech.dropped,
          (unsigned long)speech.underruns,
          (unsigned long)speech.queue_dropped);
      printf(
          "last utterance: %lu ms played, %lu subsamples, %lu ms nominal, worker stack free %lu\r\n",
          (unsigned long)speech.last_played_ms,
          (unsigned long)speech.last_subsamples,
          (unsigned long)speech.last_nominal_ms,
          (unsigned long)speech.stack_free);
  ```

- [ ] **Step 4: Build, flash, and check through the counters**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt 2>&1 | grep -E "error|warning|API version|\.free_flash" | head
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt flash_usb 2>&1 | tail -3
```

Then the wait loop from the constraints. Write this helper to the scratchpad directory (any path outside both repos) as `speech_check.py`; it speaks a sentence and polls `sr status` until the engine is idle:

```python
import re, sys, time, serial
PORT = "/dev/cu.usbmodemflip_R0skie1"
ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
def run(ser, cmd, timeout=10):
    ser.reset_input_buffer(); ser.write(cmd.encode() + b"\r"); buf = b""; t0 = time.time()
    while time.time() - t0 < timeout:
        c = ser.read(ser.in_waiting or 1)
        if c:
            buf += c
            if buf.endswith(b">: "): break
        else: time.sleep(0.02)
    return ANSI.sub(b"", buf).decode(errors="replace")
def status(ser): return run(ser, "sr status")
def wait_idle(ser, limit=40):
    t0 = time.time()
    while time.time() - t0 < limit:
        out = status(ser)
        if "speech: idle, queued 0" in out: return out
        time.sleep(0.2)
    return status(ser)
with serial.Serial(PORT, 230400, timeout=0.1) as ser:
    ser.write(b"\r"); time.sleep(0.4); ser.read(ser.in_waiting)
    print(run(ser, "sr screen"))
    print(run(ser, "sr say Hello Robin. This is your Flipper Zero speaking through the built in piezo."))
    t0 = time.time(); out = wait_idle(ser); print(out); print("finished after %.1f s" % (time.time() - t0))
    time.sleep(1.2); print([l for l in status(ser).splitlines() if "speaker held" in l])
    long = "This is a much longer sentence, produced by the software automatic mouth, to check that a stop command cuts it short."
    run(ser, "sr say " + long); time.sleep(1.5); print(run(ser, "sr stop")); time.sleep(0.5); print([l for l in wait_idle(ser).splitlines() if "utterance" in l or "aborted" in l])
    run(ser, "sr say " + long); time.sleep(1.0); run(ser, "sr say Interrupted by a shorter one."); print([l for l in wait_idle(ser).splitlines() if "utterance" in l or "aborted" in l])
```

Run it with the venv Python. Expected: no crash popup in the `sr screen` output; the first sentence finishes after a few seconds with `underruns 0`, `dropped 0` and a `last utterance` line whose played time is a few thousand milliseconds; a second later `speaker held: no`; after `sr stop` the aborted counter has grown by one and the last played time is about 1500 to 1900 ms; after the interrupting sentence the aborted counter has grown by one more and the last utterance is the short one. Record the exact output. Robin will judge the sound separately; the implementer only verifies the numbers.

- [ ] **Step 5: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader && git commit -m "screen reader: speech engine with DMA playback and sr say"
```

---

### Task 5: Calibrate the timing against the Text to SAM demo

**Files:**
- Modify: `Momentum-Firmware/applications/external/text2sam/sam_app.cpp` (inside the submodule working tree; only this file)
- Create: `tools/sam_calibrate.py`
- Modify: `Momentum-Firmware/applications/services/screen_reader/speech.c` (`SPEECH_OVERHEAD_NS`)
- Modify: `patches/text2sam-cli-mode.patch` (regenerated)

**Interfaces:**
- Consumes: the `sr status` lines from Task 4 (`speech: idle, queued 0, ...` and `last utterance: N ms played, S subsamples, M ms nominal, ...`).
- Produces: the calibrated `SPEECH_OVERHEAD_NS` and the tool that re-checks it.

Why: the demo held each value for `delta / 8` microseconds plus the time its loop spent computing, so it ran faster and higher than SAM's nominal rate. Robin approved that sound. The overhead per value is `(D - M) / S` where `D` is the demo's measured duration, `M` the nominal milliseconds and `S` the value count that `sr say` reports for the same text.

- [ ] **Step 1: Make the demo record how long it spoke**

In `sam_app.cpp` add after `save_message`'s definition:

```cpp
static void save_timing(uint32_t ms) {
    Storage* storage = (Storage*)furi_record_open(RECORD_STORAGE);
    File* file = storage_file_alloc(storage);
    if(storage_file_open(file, APP_DATA_PATH("timing.txt"), FSAM_WRITE, FSOM_CREATE_ALWAYS)) {
        char line[32];
        int n = snprintf(line, sizeof(line), "ms=%lu\n", (unsigned long)ms);
        storage_file_write(file, line, n);
    }
    storage_file_close(file);
    storage_file_free(file);
    furi_record_close(RECORD_STORAGE);
}
```

and change `say_something` to:

```cpp
static void say_something(char* something) {
    if(furi_hal_speaker_is_mine() || furi_hal_speaker_acquire(1000)) {
        uint32_t started = furi_get_tick();
        voice.begin();
        voice.say(something);
        uint32_t elapsed = furi_get_tick() - started;
        furi_hal_speaker_release();
        save_timing(elapsed);
    }
}
```

`save_timing` must be defined before `say_something`; move `say_something` below `save_message` if needed. Build and upload the app:

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && ./fbt fap_text2sam 2>&1 | tail -3 && ../.venv/bin/python scripts/storage.py -p /dev/cu.usbmodemflip_R0skie1 send -f build/f7-firmware-C/.extapps/text2sam.fap /ext/apps/Media/text2sam.fap 2>&1 | tail -1
cd /Users/robin/Downloads/flipper-access && (cd Momentum-Firmware/applications/external && git diff text2sam/sam_app.cpp) > patches/text2sam-cli-mode.patch
```

- [ ] **Step 2: Write the calibration tool**

Create `tools/sam_calibrate.py`:

```python
#!/usr/bin/env python3
"""Calibrate the speech engine's per value overhead against the Text to SAM demo.

For each reference sentence: the demo app speaks it and records its duration; then the
firmware's engine speaks it and reports its value count and nominal time. The overhead per
value is (demo_ms - nominal_ms) / subsamples. With --verify the tool reports how far the
engine's played time is from the demo instead.

  tools/sam_calibrate.py            print the overhead estimate per sentence and the mean
  tools/sam_calibrate.py --verify   compare played time with the demo, expect within 3 percent
"""
import glob, os, re, sys, time
import serial

ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
PORT = os.environ.get("FLIPPER_PORT") or (sorted(glob.glob("/dev/cu.usbmodemflip_*")) + [None])[0]
DEMO = "/ext/apps/Media/text2sam.fap"
TIMING = "/ext/apps_data/text2sam/timing.txt"
SENTENCES = [
    "Hello Robin. This is your Flipper Zero speaking through the built in piezo.",
    "The quick brown fox jumps over the lazy dog, again and again, until evening.",
]


def run(ser, cmd, timeout=15.0):
    ser.reset_input_buffer(); ser.write(cmd.encode() + b"\r"); buf = b""; t0 = time.time()
    while time.time() - t0 < timeout:
        c = ser.read(ser.in_waiting or 1)
        if c:
            buf += c
            if buf.endswith(b">: "): break
        else:
            time.sleep(0.02)
    return ANSI.sub(b"", buf).decode(errors="replace")


def wait_no_app(ser, timeout=30.0):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if "No application" in run(ser, "loader info", 5): return True
        time.sleep(0.2)
    return False


def demo_ms(ser, sentence):
    run(ser, "storage remove " + TIMING, 5)
    run(ser, 'loader open ' + DEMO + ' ' + sentence, 30)
    wait_no_app(ser)
    out = run(ser, "storage read " + TIMING, 5)
    m = re.search(r"ms=(\d+)", out)
    if not m: raise SystemExit("demo timing missing; is the instrumented Text to SAM on the card?\n" + out)
    return int(m.group(1))


def engine(ser, sentence):
    run(ser, "sr say " + sentence, 5)
    t0 = time.time()
    while time.time() - t0 < 40:
        out = run(ser, "sr status", 5)
        if "speech: idle, queued 0" in out:
            m = re.search(r"last utterance: (\d+) ms played, (\d+) subsamples, (\d+) ms nominal", out)
            if m: return int(m.group(1)), int(m.group(2)), int(m.group(3))
        time.sleep(0.2)
    raise SystemExit("the engine did not finish speaking")


def main():
    if not PORT: sys.exit("no Flipper port found")
    verify = "--verify" in sys.argv
    with serial.Serial(PORT, 230400, timeout=0.1) as ser:
        ser.write(b"\r"); time.sleep(0.4); ser.read(ser.in_waiting)
        was_on = "enabled: yes" in run(ser, "sr status", 5)
        run(ser, "sr off", 5)
        estimates = []
        for sentence in SENTENCES:
            d = demo_ms(ser, sentence)
            played, subsamples, nominal = engine(ser, sentence)
            if verify:
                diff = 100.0 * (played - d) / d
                print(f"demo {d} ms, engine {played} ms, difference {diff:+.1f} percent: {sentence[:40]}...")
                estimates.append(abs(diff))
            else:
                overhead_ns = (d - nominal) * 1_000_000 / subsamples
                print(f"demo {d} ms, nominal {nominal} ms, subsamples {subsamples}, overhead {overhead_ns:.0f} ns per value: {sentence[:40]}...")
                estimates.append(overhead_ns)
        if was_on: run(ser, "sr on", 5)
        if verify:
            worst = max(estimates)
            print(f"worst difference {worst:.1f} percent, {'ok' if worst <= 3.0 else 'TOO FAR'}")
            return 0 if worst <= 3.0 else 1
        mean = sum(estimates) / len(estimates)
        spread = 100.0 * (max(estimates) - min(estimates)) / mean if mean else 0
        print(f"mean overhead {mean:.0f} ns per value, spread {spread:.1f} percent between sentences")
        print(f"set SPEECH_OVERHEAD_NS to {int(round(mean, -1))}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
```

```bash
chmod +x /Users/robin/Downloads/flipper-access/tools/sam_calibrate.py
```

- [ ] **Step 3: Measure, set the constant, rebuild, verify**

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/sam_calibrate.py
```

Record the output. The spread between the two sentences should be under 10 percent; if it is larger, run the tool once more and use the mean of both runs. Set `SPEECH_OVERHEAD_NS` in `speech.c` to the printed value, rebuild, flash, wait, then:

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/sam_calibrate.py --verify
```

Expected: `worst difference` at most 3.0 percent, `ok`. If the difference is larger, adjust the constant proportionally (a longer played time means a smaller overhead) and repeat once.

- [ ] **Step 4: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/speech.c && git commit -m "screen reader: speech timing calibrated against the Text to SAM demo"
cd /Users/robin/Downloads/flipper-access && git add tools/sam_calibrate.py patches/text2sam-cli-mode.patch && git commit -m "sam_calibrate: timing calibration tool; demo records its duration"
```

---

### Task 6: Announcements spoken, key presses silence, regression checks, docs

**Files:**
- Modify: `Momentum-Firmware/applications/services/screen_reader/screen_reader.c`
- Modify: `README.md`, `docs/superpowers/specs/2026-09-22-flipper-screen-reader-design.md` (a short "phase 2 as built" list appended to section 16), `docs/measurements/` (new probe log)

**Interfaces:**
- Consumes: `speech_say`, `speech_stop` from Task 4.

- [ ] **Step 1: Route announcements and silence on key press**

In `screen_reader.c`:

In `sr_process`, inside the `for(size_t i = 0; i < n; i++)` loop that feeds the watch queue, add before the `if(sr->watch_queue)`:

```c
            if(momentum_settings.screen_reader) {
                const SrAnnouncement* a = &sr->announcements[i];
                speech_say(sr->speech, a->text, a->interrupt, a->kind == SrAnnChange);
            }
```

In `sr_input_callback`, inside `if(event->type == InputTypePress) { ... }`, add after the tick assignment:

```c
        speech_stop(sr->speech);
```

`speech_stop` only sets a thread flag, so it is safe on the input thread. The service creates `sr->speech` before it subscribes to input events (Task 4), so the pointer is valid in the callback.

- [ ] **Step 2: Build, flash, and exercise it**

Build and flash as before, wait, `sr screen` first. Then:

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/sr_drive.py
```

Expected: both sessions still pass (the console mirror is unchanged), and during the run the device speaks each announcement. Then:

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/flipper_cli.py --timeout 8 "sr status"
```

Expected: `utterances` well above zero, `underruns 0`, `dropped 0`, and after a second `speaker held: no`.

Key press silencing:

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/flipper_cli.py --timeout 8 "sr status" | grep -o "aborted [0-9]*" && .venv/bin/python tools/flipper_cli.py --timeout 8 "sr say This sentence is long enough to be interrupted by a key press before it finishes speaking, which the aborted counter will show." && sleep 1.2 && .venv/bin/python tools/flipper_cli.py --timeout 8 "input send ok short" && sleep 0.6 && .venv/bin/python tools/flipper_cli.py --timeout 8 "sr status" | grep -E "aborted|last utterance"
```

Expected: `aborted` one higher than before, and the last utterance's played time about 1200 to 1600 ms. The OK press opened the main menu, which the reader then announces; press Back afterwards with `input send back short`.

- [ ] **Step 3: Memory and stability**

```bash
cd /Users/robin/Downloads/flipper-access && .venv/bin/python tools/ram_probe.py > docs/measurements/2026-09-23-ram-probe-speech-on.txt 2>&1; tail -4 docs/measurements/2026-09-23-ram-probe-speech-on.txt
```

Expected: the NFC read low point at 24 KB free or more; note the numbers. If it is below 20 KB, report it as a concern. Then a soak: leave the device on the home screen for four minutes and confirm with `sr status` that `frames` keeps rising, `underruns` stays 0 and no crash popup appears in `sr screen`.

- [ ] **Step 4: Documentation**

In `README.md`, under the screen reader commands, add:

```markdown
Speech: announcements are spoken by the device itself. `sr say <text>` speaks text and prints
timing; `sr stop` silences; `sr rate <40..120>` and `sr volume <0..100>` are saved settings.
Any button press silences speech. `tools/sam_calibrate.py --verify` checks the voice still
matches the Text to SAM demo's timing.
```

and change the plan list's last items to:

```markdown
6. Done: phase 2, on device speech with SAM and DMA playback.
7. Next: phase 3, hotkeys, settings screen, and screens that draw no text.
```

Append to the spec's section 16 a paragraph "Phase 2 as built" listing: the synthesizer lives under the service directory rather than lib; DMA2 channel 4 paced by TIM16's update event instead of DMA1 channel 1 and a second timer; per value hold time is the demo's delta / 8 microseconds plus a calibrated overhead (state the measured value); the queue replaces pending change announcements; any key press stops speech (moved from phase 3); speech is skipped while TIM16 is in use elsewhere; the pronunciation rules of Task 2.

- [ ] **Step 5: Commit**

```bash
cd /Users/robin/Downloads/flipper-access/Momentum-Firmware && git add applications/services/screen_reader/screen_reader.c && git commit -m "screen reader: announcements are spoken, key presses silence speech"
cd /Users/robin/Downloads/flipper-access && git add README.md docs && git commit -m "phase 2 docs and measurements"
```

---

## Self review notes

Spec coverage: section 8 (SAM in firmware as C, DMA output, ring buffer, speaker sharing, interruption, thread) is Tasks 1, 3, 4; the pronunciation table of section 5 is Task 2; settings for rate and volume (section 10) are wired in Task 4; failure handling for a busy speaker (section 12) is Task 4; testing (section 13) is the host tests of Tasks 1 to 3 plus the device checks and probe of Tasks 4 to 6. Deviations from section 8 are listed for the spec update in Task 6.

Type consistency: `SamOutputCallback` (Task 1) is what `speech_sam_output` implements (Task 4); `SpeechPcmEmit` (Task 3) is what `speech_emit` implements; `SpeechItem.text` is 160 bytes and `SrAnnouncement.text` is 160 bytes; `speech_text_expand` writes at most `SPEECH_TEXT_MAX` (800) and the chunk buffer is `SPEECH_CHUNK_MAX + 1`; `sam_calibrate.py` parses the exact `last utterance: N ms played, S subsamples, M ms nominal` order that `sr status` prints.
