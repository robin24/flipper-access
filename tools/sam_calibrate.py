#!/usr/bin/env python3
"""Calibrate the speech engine's per value overhead against the Text to SAM demo.

For each reference sentence: the demo app speaks it and records its duration; then the
firmware's engine speaks it and reports its value count and nominal time. The overhead per
value is (demo_ms - nominal_ms) / subsamples. With --verify the tool reports how far the
engine's played time is from the demo instead.

  tools/sam_calibrate.py            print the overhead estimate per sentence and the mean
  tools/sam_calibrate.py --verify   compare played time with the demo, expect within 3 percent

The engine's played time includes the rendering of the first ring half before the DMA starts
and the silence that pads the last half: 22 to 62 ms more than the nominal time at overhead 0
(measured in Task 4). --verify prints the raw difference and the difference with PADDING_MS
taken off; the corrected one is the acceptance criterion.
"""
import glob, os, re, sys, time
import serial

ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
PORT = os.environ.get("FLIPPER_PORT") or (sorted(glob.glob("/dev/cu.usbmodemflip_*")) + [None])[0]
DEMO = "/ext/apps/Media/text2sam.fap"
TIMING = "/ext/apps_data/text2sam/timing.txt"
PADDING_MS = 40
SENTENCES = [
    "Hello Robin. This is your Flipper Zero speaking through the built in piezo.",
    "The quick brown fox jumps over the lazy dog, again and again, until evening.",
]
SPEECH_LINE = re.compile(
    r"speech: (\w+), queued (\d+), speaker held: (\w+), utterances (\d+), aborted (\d+), "
    r"dropped (\d+), underruns (\d+), queue dropped (\d+)")
UTTERANCE_LINE = re.compile(
    r"last utterance: (\d+) ms played, (\d+) subsamples, (\d+) ms nominal, worker stack free (\d+)")


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


def speech_counters(out):
    m = SPEECH_LINE.search(out)
    if not m: raise SystemExit("no speech line in sr status; is the speech firmware flashed?\n" + out)
    return {"state": m.group(1), "queued": int(m.group(2)), "utterances": int(m.group(4)),
            "aborted": int(m.group(5)), "dropped": int(m.group(6))}


def engine(ser, sentence):
    before = speech_counters(run(ser, "sr status", 5))
    run(ser, "sr say " + sentence, 5)
    t0 = time.time()
    out = ""
    while time.time() - t0 < 40:
        out = run(ser, "sr status", 5)
        now = speech_counters(out)
        if now["state"] == "idle" and now["queued"] == 0:
            if now["dropped"] > before["dropped"] or now["aborted"] > before["aborted"]:
                raise SystemExit("the engine dropped or aborted the sentence:\n" + out)
            m = UTTERANCE_LINE.search(out)
            if now["utterances"] > before["utterances"] and m:
                return int(m.group(1)), int(m.group(2)), int(m.group(3))
        time.sleep(0.2)
    raise SystemExit("the engine did not finish speaking:\n" + out)


def main():
    if not PORT: sys.exit("no Flipper port found")
    verify = "--verify" in sys.argv
    with serial.Serial(PORT, 230400, timeout=0.1) as ser:
        ser.write(b"\r"); time.sleep(0.4); ser.read(ser.in_waiting)
        was_on = "enabled: yes" in run(ser, "sr status", 5)
        run(ser, "sr off", 5)
        estimates = []
        raws = []
        for sentence in SENTENCES:
            d = demo_ms(ser, sentence)
            played, subsamples, nominal = engine(ser, sentence)
            if verify:
                raw = 100.0 * (played - d) / d
                corrected = 100.0 * (played - PADDING_MS - d) / d
                print(f"demo {d} ms, engine {played} ms played, {played - PADDING_MS} ms without padding, "
                      f"difference {raw:+.1f} percent raw, {corrected:+.1f} percent corrected: {sentence[:40]}...")
                raws.append(abs(raw))
                estimates.append(abs(corrected))
            else:
                overhead_ns = (d - nominal) * 1_000_000 / subsamples
                print(f"demo {d} ms, nominal {nominal} ms, subsamples {subsamples}, overhead {overhead_ns:.0f} ns per value: {sentence[:40]}...")
                estimates.append(overhead_ns)
        if was_on: run(ser, "sr on", 5)
        if verify:
            worst = max(estimates)
            worst_raw = max(raws)
            print(f"worst corrected difference {worst:.1f} percent, {'ok' if worst <= 3.0 else 'TOO FAR'}; "
                  f"worst raw difference {worst_raw:.1f} percent, {'ok' if worst_raw <= 3.0 else 'too far'}")
            return 0 if worst <= 3.0 else 1
        mean = sum(estimates) / len(estimates)
        spread = 100.0 * (max(estimates) - min(estimates)) / mean if mean else 0
        print(f"mean overhead {mean:.0f} ns per value, spread {spread:.1f} percent between sentences")
        if mean < 0:
            print("the demo is faster than the engine's nominal time; SPEECH_OVERHEAD_NS is unsigned and cannot go below 0")
            return 1
        print(f"set SPEECH_OVERHEAD_NS to {int(round(mean, -2))}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
