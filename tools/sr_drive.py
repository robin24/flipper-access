#!/usr/bin/env python3
"""Drive the Flipper through the screen reader console stream.

  tools/sr_drive.py               run the scripted checks and report mismatches
  tools/sr_drive.py --interactive open sr watch and pass this terminal's keys through
                                  (arrows, Enter, Backspace, Tab, letters; Ctrl-C ends)

Needs the screen reader firmware. The port is auto-detected; override with FLIPPER_PORT.
"""
import glob, os, re, sys, time, termios, tty, select
import serial

ANSI = re.compile(rb"\x1b\[[0-9;]*[A-Za-z]")
PORT = os.environ.get("FLIPPER_PORT") or (sorted(glob.glob("/dev/cu.usbmodemflip_*")) + [None])[0]

KEYS = {"ok": b"\r", "up": b"\x1b[A", "down": b"\x1b[B", "right": b"\x1b[C", "left": b"\x1b[D", "back": b"\x7f", "tab": b"\t"}

# (key to send, substring that must appear in the reply lines within 1.5 s)
SCRIPT = [
    ("ok", "screen:"),         # desktop -> main menu
    ("down", "focus:"),
    ("down", "focus:"),
    ("back", "home: Home screen"),
    ("ok", "screen:"),
    ("ok", "screen:"),         # open the selected app
    ("down", "focus:"),
    ("back", "screen:"),       # back to the main menu
    ("back", "home: Home screen"),
]


def read_for(ser, seconds):
    t0 = time.time(); buf = b""
    while time.time() - t0 < seconds:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
        else:
            time.sleep(0.02)
    return ANSI.sub(b"", buf).decode(errors="replace").replace("\r\n", "\n")


def start_watch(ser):
    ser.write(b"\r"); time.sleep(0.4); ser.read(ser.in_waiting)
    ser.write(b"sr on\r"); read_for(ser, 0.5)
    ser.write(b"sr watch\r")
    return read_for(ser, 0.8)


def scripted(ser):
    print(start_watch(ser))
    failures = 0
    for key, expect in SCRIPT:
        ser.write(KEYS[key])
        out = read_for(ser, 1.5).strip()
        ok = expect in out
        failures += 0 if ok else 1
        print(f"{'ok  ' if ok else 'FAIL'} {key:5s} expected '{expect}' got: {out.replace(chr(10), ' | ')}")
    ser.write(b"\x03"); read_for(ser, 0.5)
    print(f"{failures} failures")
    return 1 if failures else 0


def interactive(ser):
    print(start_watch(ser), end="")
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    pending = b""
    try:
        tty.setcbreak(fd)
        while True:
            r, _, _ = select.select([fd, ser.fileno()], [], [], 0.05)
            if fd in r:
                data = os.read(fd, 8)
                if b"\x03" in data:
                    break
                ser.write(data)
            if ser.fileno() in r or ser.in_waiting:
                chunk = ser.read(ser.in_waiting or 1)
                if chunk:
                    pending += chunk
                    # Hold back an unfinished escape sequence so it is never printed half stripped.
                    cut = pending.rfind(b"\x1b")
                    if cut != -1 and not ANSI.search(pending[cut:]):
                        ready, pending = pending[:cut], pending[cut:]
                    else:
                        ready, pending = pending, b""
                    sys.stdout.write(ANSI.sub(b"", ready).decode(errors="replace"))
                    sys.stdout.flush()
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
    ser.write(b"\x03")
    print(read_for(ser, 0.5))


def main():
    if not PORT:
        sys.exit("no Flipper port found")
    with serial.Serial(PORT, 230400, timeout=0.1) as ser:
        if "--interactive" in sys.argv:
            interactive(ser)
            return 0
        return scripted(ser)


if __name__ == "__main__":
    sys.exit(main())
