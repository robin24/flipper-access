#!/usr/bin/env python3
"""Make 8-bit speech clips for the Flipper's speaker from a macOS voice.

    tools/clip_make.py OUT.raw "text" [--voice Samantha] [--rate 175] [--hz 16000]
                       [--highpass 500] [--gain 1.0] [--soft]

Output: raw unsigned 8-bit PCM, mono, HZ samples per second, 128 is silence. The device
plays it with `sr play OUT.raw HZ`. --highpass removes what the piezo cannot reproduce so
the headroom goes to the formants; --gain with --soft pushes loudness through a tanh limiter.
"""
import argparse, array, math, os, subprocess, sys, tempfile, wave


def synth(text, voice, rate, hz, path):
    subprocess.run(["say", "-v", voice, "-r", str(rate), "-o", path, "--file-format=WAVE",
                    "--data-format=LEI16@%d" % hz, text], check=True)


def read_wav(path):
    with wave.open(path, "rb") as w:
        assert w.getnchannels() == 1 and w.getsampwidth() == 2
        data = array.array("h"); data.frombytes(w.readframes(w.getnframes()))
        return [s / 32768.0 for s in data], w.getframerate()


def highpass(x, hz, fc):
    if not fc: return x
    rc = 1.0 / (2 * math.pi * fc); dt = 1.0 / hz; a = rc / (rc + dt)
    y = [0.0] * len(x)
    for i in range(1, len(x)):
        y[i] = a * (y[i - 1] + x[i] - x[i - 1])
    return y


def trim(x, hz, threshold=0.02):
    """Return the content span only: from the first sample past threshold to the last, no pad."""
    first = next((i for i, v in enumerate(x) if abs(v) > threshold), None)
    if first is None:
        return []
    last = next(i for i in range(len(x) - 1, -1, -1) if abs(x[i]) > threshold)
    return x[first : last + 1]


def pad(x, hz, ms=15):
    """Prepend and append ms of true silence (zeros)."""
    n = int(hz * ms / 1000)
    return [0.0] * n + x + [0.0] * n


def finish(x, gain=1.0, soft=False):
    """Peak normalise to 0.95, apply the gain and, with soft, the tanh limiter."""
    peak = max((abs(v) for v in x), default=0.0) or 1.0
    x = [v / peak * 0.95 * gain for v in x]
    if soft:
        x = [math.tanh(v * 1.5) / math.tanh(1.5) for v in x]
    return x


def to_u8(x):
    return bytes(max(0, min(255, int(round(v * 127 + 128)))) for v in x)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out"); ap.add_argument("text")
    ap.add_argument("--voice", default="Samantha"); ap.add_argument("--rate", type=int, default=175)
    ap.add_argument("--hz", type=int, default=16000); ap.add_argument("--highpass", type=float, default=0)
    ap.add_argument("--gain", type=float, default=1.0); ap.add_argument("--soft", action="store_true")
    ap.add_argument("--trim", action="store_true", help="cut leading/trailing silence, keeping 15 ms of pad")
    a = ap.parse_args()
    with tempfile.TemporaryDirectory() as d:
        wav = os.path.join(d, "clip.wav")
        synth(a.text, a.voice, a.rate, a.hz, wav)
        x, hz = read_wav(wav)
    x = highpass(x, hz, a.highpass)
    x = finish(x, a.gain, a.soft)
    if a.trim:
        x = trim(x, hz)
        x = pad(x, hz)
    out = to_u8(x)
    with open(a.out, "wb") as f: f.write(out)
    print(f"{a.out}: {len(out)} bytes, {len(out) / hz:.2f} s at {hz} Hz, voice {a.voice} rate {a.rate}, "
          f"highpass {a.highpass:g} Hz, gain {a.gain:g}{' soft' if a.soft else ''}")


if __name__ == "__main__":
    sys.exit(main())
