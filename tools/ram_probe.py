#!/usr/bin/env python3
"""Measure heap headroom on the Flipper while core apps run.

Reboots once, then for each app: records free heap, launches it, presses keys to put it
into its busy state, samples free heap ~7 times a second while it runs, closes it, and
records free heap again. Also reads the firmware's own low-water mark, which is exact.
Prints a plain-text summary. Usage: .venv/bin/python tools/ram_probe.py
"""
import glob, os, re, sys, time
import serial
sys.stdout.reconfigure(line_buffering=True)

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PORT = os.environ.get("FLIPPER_PORT") or (sorted(glob.glob("/dev/cu.usbmodemflip_*")) + [None])[0]

# name, loader argument, key presses after launch, seconds to dwell
APPS = [
    ("Desktop idle", None, [], 4),
    ("Sub-GHz: Read", "Sub-GHz", ["ok"], 6),
    ("Sub-GHz: Frequency Analyzer", "Sub-GHz", ["down"] * 5 + ["ok"], 6),
    ("NFC: Read", "NFC", ["ok"], 6),
    ("125 kHz RFID: Read", "125 kHz RFID", ["ok"], 6),
    ("Infrared: Learn New Remote", "Infrared", ["down", "ok"], 6),
    ("Infrared: Universal Remotes, first category", "Infrared", ["ok", "ok"], 6),
    ("iButton: Read", "iButton", ["ok"], 6),
    ("GPIO: Manual Control", "GPIO", ["down", "ok"], 4),
    ("Bad KB (file browser)", "Bad KB", [], 5),
    ("Momentum settings, first section", "Momentum", ["ok"], 4),
    ("Text to SAM (keyboard screen)", "/ext/apps/Media/text2sam.fap", [], 3),
    ("TOTP (large app)", "/ext/apps/Tools/totp.fap", [], 4),
    ("uPython (largest app, expected to fail to load)", "/ext/apps/Tools/upython.fap", [], 4),
]

def run(ser, cmd, timeout=15.0):
    ser.reset_input_buffer(); ser.write(cmd.encode() + b"\r"); buf = b""; t0 = time.time()
    while time.time() - t0 < timeout:
        c = ser.read(ser.in_waiting or 1)
        if c:
            buf += c
            if buf.endswith(b">: "): break
        else:
            time.sleep(0.01)
    return ANSI.sub("", buf.decode(errors="replace"))

class ConsoleDead(Exception):
    pass

def free(ser):
    out = run(ser, "free", 5)
    if ">: " not in out:
        out = run(ser, "free", 5)
        if ">: " not in out:
            raise ConsoleDead()
    m = {k: int(v) for k, v in re.findall(r"(Free heap size|Total heap size|Minimum heap size|Maximum heap block): (\d+)", out)}
    return m.get("Free heap size"), m.get("Minimum heap size"), m.get("Maximum heap block"), m.get("Total heap size")

def wait_port(path, gone_first=True, limit=90):
    t0 = time.time(); gone = not gone_first
    while time.time() - t0 < limit:
        exists = os.path.exists(path)
        if not exists: gone = True
        elif gone: return True
        time.sleep(0.5)
    return False

def connect():
    ser = serial.Serial(PORT, 230400, timeout=0.1)
    ser.write(b"\r"); time.sleep(0.5); ser.read(ser.in_waiting)
    return ser

class Rebooted(Exception):
    pass

class Conn:
    """Serial connection that detects a device reboot and reconnects."""
    def __init__(self):
        self.ser = connect()
    def run(self, cmd, timeout=15.0):
        try:
            return run(self.ser, cmd, timeout)
        except (serial.SerialException, OSError):
            try: self.ser.close()
            except Exception: pass
            wait_port(PORT, gone_first=False, limit=120)
            time.sleep(8)
            self.ser = connect()
            run(self.ser, "input send back short", 5)  # dismiss the fault screen if shown
            raise Rebooted()
    def close(self):
        self.ser.close()

def exit_app(conn):
    """Leave the current app the way a person would: Back presses only. The loader's exit
    signal (loader close) crashes NFC in read mode and cannot close uPython, so it is never sent;
    an app that survives twelve Back presses is reported and left alone."""
    for _ in range(12):
        if "No application" in conn.run("loader info", 5): return True
        conn.run("input send back short", 5); time.sleep(0.35)
    print("  warning: the app did not leave after twelve Back presses; not sending loader close")
    return False

def main():
    if not PORT: sys.exit("no Flipper port")
    print(f"port {PORT}")
    ser = connect()
    print("rebooting for a clean baseline")
    run(ser, "power reboot", 2); ser.close()
    if not wait_port(PORT): sys.exit("device did not come back")
    time.sleep(8)  # let the desktop settle
    conn = Conn()
    results = []
    for name, app, keys, dwell in APPS:
        try:
            exit_app(conn); time.sleep(0.6)
            f_before, min_before, _, total = free(conn.ser)
            if app:
                out = conn.run(f'loader open "{app}"', 10)
                time.sleep(1.2)
                err = [l for l in out.splitlines()[1:] if l.strip() and not l.startswith(">")]
                if err: print(f"  note: loader said: {' / '.join(err)}")
            for k in keys:
                conn.run(f"input send {k} short", 5); time.sleep(0.45)
            samples = []
            t0 = time.time()
            while time.time() - t0 < dwell:
                f, mn, mb, _ = free(conn.ser)
                if f is not None: samples.append((f, mn, mb))
                time.sleep(0.05)
            running = "No application" not in conn.run("loader info", 5)
            exited = exit_app(conn)
            if not exited: print("  note: app did not exit, continuing")
            f_after, min_after, _, _ = free(conn.ser)
        except Rebooted:
            print(f"{name}: DEVICE REBOOTED (crash) during this step; reconnected and continuing")
            results.append((name, None, None, None, None, None, None, 0, None))
            continue
        except ConsoleDead:
            print(f"{name}: CONSOLE STOPPED ANSWERING during this step. Stopping here; reboot the device with Left+Back held for 5 seconds.")
            break
        if samples:
            f_min = min(s[0] for s in samples); mn_end = min(s[1] for s in samples); mb_min = min(s[2] for s in samples)
        else:
            f_min = mn_end = mb_min = None
        results.append((name, f_before, f_min, min_before, mn_end, f_after, running, len(samples), mb_min))
        print(f"{name}: free before {f_before}, lowest sampled {f_min}, low-water mark {min_before} -> {mn_end}, after exit {f_after}, samples {len(samples)}, app was running: {running}")
    _, min_final, _, total = free(conn.ser)
    print()
    print(f"Total heap {total} bytes. Global low-water mark after all apps: {min_final} bytes free.")
    worst = min((r for r in results if r[2] is not None), key=lambda r: r[2])
    print(f"Lowest sampled free heap: {worst[2]} bytes during '{worst[0]}'.")
    conn.close()

if __name__ == "__main__":
    main()
