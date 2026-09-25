#!/usr/bin/env python3
"""Drive the Flipper through the screen reader console stream.

  tools/sr_drive.py               run the scripted checks and report mismatches
  tools/sr_drive.py --chords      run only the third session, the Back chords
  tools/sr_drive.py --interactive open sr watch and pass this terminal's keys through
                                  (arrows, Enter, Backspace, Tab, letters; Ctrl-C ends)

The scripted checks are three sessions: the menus and an app's keyboard, driven through sr watch,
then the Back chords, sent with the console's input send on the home screen and in the main menu.
Start on the home screen. Needs the screen reader firmware. The port is auto-detected; override
with FLIPPER_PORT.
"""
import glob, os, re, sys, time, termios, tty, select
import serial

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flipper_cli import run as cli  # noqa: E402  (one console command, its reply without the prompt)

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

# Third session: the Back chords of phase 3. They are sent with the console's input send, which
# passes the input filter as the device's own keys do (sr watch's keys and remote control do not).
# input send ok short and ok long publish OK's Press, Short or Long and Release themselves; the
# ok press before and ok release after them are the plan's sequence, and show that stray OK events
# around a chord do not navigate either. Down, like OK, names its chord on its Short (the status
# bar) or its Long (the reader off, which is left out here: the session needs the reader on). A
# chord must speak (the utterance counter rises) and must never navigate (the screen reads the
# same before and after).
CHORDS = [
    ("back + up", ["back press", "up press", "up release", "back release"]),
    ("back + down", ["back press", "down press", "down short", "down release", "back release"]),
    ("back + ok", ["back press", "ok press", "ok short", "ok release", "back release"]),
    ("back + ok long", ["back press", "ok press", "ok long", "ok release", "back release"]),
]
SPEECH_RE = re.compile(r"speech: (\w+), queued (\d+), speaker held: \w+, utterances (\d+), aborted (\d+), dropped (\d+)")
FRAMES_RE = re.compile(r"announcements: (\d+), suppressed: (\d+)")
LAST_RE = re.compile(r"last utterance: (\d+) ms played, (\d+) subsamples")


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


def status(ser):
    """The speech counters of sr status, or None when the reply does not parse."""
    out = cli(ser, "sr status")
    speech, frames, last = SPEECH_RE.search(out), FRAMES_RE.search(out), LAST_RE.search(out)
    if not (speech and frames and last):
        return None
    return {
        "speaking": speech.group(1) != "idle",
        "queued": int(speech.group(2)),
        "utterances": int(speech.group(3)),
        "aborted": int(speech.group(4)),
        "dropped": int(speech.group(5)),
        "announcements": int(frames.group(1)),
        "played_ms": int(last.group(1)),
        "subsamples": int(last.group(2)),
    }


def screen(ser):
    """What a chord must leave alone, from sr screen: the content layer, the focus records and,
    away from the home screen, how the screen reads. The home screen's reading is left out: the
    dolphin draws and removes its speech bubbles by itself, and a chord's Back press may start one."""
    lines = cli(ser, "sr screen").split("\n")
    layer = next((l.split("content layer: ", 1)[1].strip() for l in lines if "content layer: " in l), "?")
    focus = tuple(l[l.index(" FOCUS") + 1:].strip() for l in lines if " FOCUS" in l)
    reads = next((l[len("reads as:"):].strip() for l in lines if l.startswith("reads as:")), "")
    return layer, focus, (None if layer == "desktop" else reads)


def at_home(shown):
    return shown[0] == "desktop" and not shown[1]


def described(shown):
    layer, focus, reads = shown
    text = layer + (", " + "; ".join(focus) if focus else ", no focus")
    return text + (f", reads as: {reads}" if reads else "")


def wait_quiet(ser, before=None, rise_s=5.0, quiet_s=60.0):
    """Poll sr status until speech is idle with nothing queued. With before, the utterance counter
    must also pass before's within rise_s seconds: a key's or a chord's speech has started. Returns
    the last status (None if sr status never answered) and whether that happened in time."""
    t0 = time.time()
    s = None
    while True:
        s = status(ser) or s
        waited = time.time() - t0
        rose = before is None or (s is not None and s["utterances"] > before["utterances"])
        if s is not None and rose and not s["speaking"] and s["queued"] == 0:
            return s, True
        if (not rose and waited > rise_s) or waited > rise_s + quiet_s:
            return s, False
        time.sleep(0.25)


def press(ser, key):
    """A plain key press that changes screens, then the silence after its announcement."""
    before = status(ser)
    cli(ser, f"input send {key} short")
    wait_quiet(ser, before)


def chord(ser, where, name, keys):
    """Send one chord and check that it spoke and stayed on the screen. Returns 1 on a mismatch."""
    before, _ = wait_quiet(ser)
    shown = screen(ser)
    if before is None:
        print(f"FAIL {where:5s} {name:15s} sr status did not answer")
        return 1
    for key in keys:
        cli(ser, "input send " + key)
    after, spoke = wait_quiet(ser, before)
    now = screen(ser)
    after = after or before
    same = now == shown
    got = (
        f"utterances +{after['utterances'] - before['utterances']}, aborted +{after['aborted'] - before['aborted']}, "
        f"dropped +{after['dropped'] - before['dropped']}, announcements +{after['announcements'] - before['announcements']}; "
        f"last {after['played_ms']} ms played, {after['subsamples']} subsamples"
    )
    if not spoke:
        got += "; no speech, or it did not end"
    if not same:
        got += f"; screen was: {described(shown)}; now: {described(now)}"
    print(f"{'ok  ' if spoke and same else 'FAIL'} {where:5s} {name:15s} {got}")
    return 0 if spoke and same else 1


def chords(ser):
    """Session three: every chord on the home screen, then in the main menu. Returns the number of
    mismatches and leaves the device on the home screen."""
    failures = 0
    before, _ = wait_quiet(ser)
    cli(ser, "sr on")  # as the watch sessions do: without the reader a chord is plain keys
    wait_quiet(ser, before, rise_s=3.0)  # sr on reads the screen again, "Home screen"
    shown = screen(ser)
    if not at_home(shown):
        print(f"FAIL start expected the home screen, got: {described(shown)}")
        return 1
    print(f"     home  {described(shown)}")
    for name, keys in CHORDS:
        failures += chord(ser, "home", name, keys)
    press(ser, "ok")  # desktop -> main menu
    shown = screen(ser)
    if shown[0] == "desktop":
        print(f"FAIL menu  OK did not open the main menu: {described(shown)}")
        failures += 1
    else:
        print(f"     menu  {described(shown)}")
        for name, keys in CHORDS:
            failures += chord(ser, "menu", name, keys)
    for _ in range(3):  # back to the home screen, also after a chord that navigated by mistake
        if at_home(screen(ser)):
            break
        press(ser, "back")
    shown = screen(ser)
    ok = at_home(shown)
    print(f"{'ok  ' if ok else 'FAIL'} end   home screen expected, got: {described(shown)}")
    return failures + (0 if ok else 1)


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

    # Session three: the Back chords, through the console's input send rather than sr watch.
    failures += chords(ser)

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
        if "--chords" in sys.argv:
            ser.write(b"\r"); time.sleep(0.4); ser.read(ser.in_waiting)  # past the welcome banner
            failures = chords(ser)
            print(f"{failures} failures")
            return 1 if failures else 0
        return scripted(ser)


if __name__ == "__main__":
    sys.exit(main())
