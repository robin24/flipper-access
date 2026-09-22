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
    ("ok", "screen:"),          # desktop -> main menu
    ("up", "focus: Settings"),  # the menu wraps from the first item to the last
    ("ok", "Bluetooth"),        # the Settings list opens with Bluetooth focused
    ("back", "screen:"),        # back to the main menu
    ("back", "home: Home screen"),
    ("ok", "screen:"),          # desktop -> main menu
    ("down", "focus:"),
    ("down", "focus:"),
    ("back", "home: Home screen"),
    ("ok", "screen:"),
    ("ok", "screen:"),          # open the selected app
    ("down", "focus:"),
    ("back", "screen:"),        # back to the main menu
    ("back", "home: Home screen"),
]

# Second session: an app with a text input, to check that one keyboard key is announced.
KEYBOARD_APP = "/ext/apps/Media/text2sam.fap"


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


def stop_watch(ser):
    ser.write(b"\x03"); read_for(ser, 0.5)


def report(label, expect, out, ok):
    print(f"{'ok  ' if ok else 'FAIL'} {label:5s} expected '{expect}' got: {out.replace(chr(10), ' | ')}")
    return 0 if ok else 1


def step(ser, key, expect, check=None):
    """Send one key and check the announcements it produced. Returns 1 on a mismatch."""
    ser.write(KEYS[key])
    out = read_for(ser, 1.5).strip()
    return report(key, expect, out, check(out) if check else expect in out)


def single_key_focus(out):
    """A keyboard row must announce the selected key alone: 'focus: ' plus one character."""
    return any(
        line.strip().startswith("focus: ") and len(line.strip()) == len("focus: ") + 1
        for line in out.split("\n")
    )


def scripted(ser):
    failures = 0

    # Session one: the menus. Everything here is driven by key presses.
    print(start_watch(ser))
    for key, expect in SCRIPT:
        failures += step(ser, key, expect)
    stop_watch(ser)

    # Session two: the on screen keyboard. Opening the app needs the console, which sr watch
    # owns, so it runs as its own watch session.
    ser.write(f"loader open {KEYBOARD_APP}\r".encode())
    read_for(ser, 1.5)
    out = start_watch(ser).strip()
    first = next((l for l in out.split("\n") if l.strip().startswith("screen:")), "")
    failures += report("watch", "screen: ... Input ...", out, "Input" in first)
    failures += step(ser, "right", "focus: <one character>", single_key_focus)
    failures += step(ser, "back", "home: Home screen")
    stop_watch(ser)

    print(f"{failures} failures")
    return 1 if failures else 0


def interactive(ser):
    if not sys.stdin.isatty():
        print("--interactive needs a terminal: run it from a shell, not from a pipe or a script")
        return 1
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
        try:
            ser.write(b"\x03")
            print(read_for(ser, 0.5))
        except Exception as err:  # the port may already be gone; never hide the real error
            print(f"could not stop sr watch: {err}")
    return 0


def main():
    if not PORT:
        sys.exit("no Flipper port found")
    with serial.Serial(PORT, 230400, timeout=0.1) as ser:
        if "--interactive" in sys.argv:
            return interactive(ser)
        return scripted(ser)


if __name__ == "__main__":
    sys.exit(main())
