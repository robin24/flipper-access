#!/usr/bin/env python3
"""Send one or more commands to the Flipper Zero command line over USB serial and print the replies.

Usage:
  tools/flipper_cli.py "info device" "loader list"
  tools/flipper_cli.py --timeout 120 "update backup /ext/backup.tar"

The serial port is found automatically, by the Flipper's USB id on a Mac, Linux or Windows.
Override with --port or the FLIPPER_PORT environment variable. The port is opened for this tool
alone: when qFlipper or another tool has it, this one says so and stops. Every open starts a fresh
console session by dropping and raising DTR, and reads its banner to the prompt before the first
command. ANSI colour codes are stripped from the output so it reads cleanly in a terminal with a
screen reader.
"""
import argparse
import contextlib
import glob
import os
import re
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial is missing. Run: .venv/bin/pip install pyserial  (or use .venv/bin/python)")

# What a port that is gone raises. pyserial's SerialException is an OSError, but on a Mac or Linux
# the call that clears the input buffer is a bare termios call, whose termios.error is not one.
try:
    import termios

    PORT_ERRORS = (OSError, termios.error)
except ImportError:  # Windows has no termios
    PORT_ERRORS = (OSError,)

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PROMPT = b">: "
# The Flipper's USB serial port has STMicroelectronics' virtual COM port id, which other boards
# with ST's USB code share, so a port that names Flipper comes first
FLIPPER_USB_ID = (0x0483, 0x5740)
# The open of the console: DTR is low this long before it is raised again, which the Flipper
# takes for a terminal that went away and came back (cli_vcp.c ends the console session when DTR
# drops and starts a new one, with the banner and a prompt, when it rises). On 2026-10-11, after
# about ten idle hours, a fresh open got no echo and no prompt until DTR was dropped for half a
# second and raised again.
DTR_LOW_SECONDS = 0.5
BANNER_SECONDS = 5  # the most the banner and its prompt may take once DTR is up
NUDGE_SECONDS = 2  # and the prompt after one carriage return, when the banner gave none


def flipper_ports(ports=None):
    """The devices of the serial ports with the Flipper's USB id, those that name Flipper first,
    then by device name. ports: list_ports.comports() entries, by default this computer's."""
    if ports is None:
        from serial.tools import list_ports

        ports = list_ports.comports()

    def named(p):
        return "flipper" in " ".join(str(x or "") for x in (p.manufacturer, p.product, p.description, p.device)).lower()

    found = [p for p in ports if (p.vid, p.pid) == FLIPPER_USB_ID]
    return [p.device for p in sorted(found, key=lambda p: (not named(p), p.device))]


def find_port(explicit=None):
    """The port to use: explicit, else FLIPPER_PORT, else the first with the Flipper's USB id,
    else the first /dev/cu.usbmodemflip_* (a Mac whose listing lacks the id). Exits with one
    sentence when there is none, which names each state the Flipper may be in: unplugged,
    PIN-locked (the lock turns the console's USB off), in the updater, or held by qFlipper."""
    if explicit:
        return explicit
    env = os.environ.get("FLIPPER_PORT")
    if env:
        return env
    ports = flipper_ports() or sorted(glob.glob("/dev/cu.usbmodemflip_*"))
    if not ports:
        sys.exit(
            "No Flipper serial port found. Is it plugged in, unlocked, not in the updater, and not used by qFlipper? "
            "Or name it with --port."
        )
    return ports[0]


def open_port(port, timeout=0.1):
    """The port, opened for this tool alone, so that qFlipper or a second tool on it is noticed at
    once instead of a wait without a word; one sentence and exit when it cannot be opened."""
    try:
        return serial.Serial(port, 230400, timeout=timeout, exclusive=True)
    except serial.SerialException as e:
        sys.exit(f"cannot open {port}: {e}. Is qFlipper or another tool using it?")


def _read_to_prompt(ser, seconds):
    """Read from ser, and throw away, what comes until it ends in the prompt, for at most seconds;
    whether the prompt came."""
    deadline = time.monotonic() + seconds
    tail = b""
    while time.monotonic() < deadline:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            tail = (tail + chunk)[-len(PROMPT):]
            if tail == PROMPT:
                return True
        else:
            time.sleep(0.02)
    return False


def wake(ser):
    """Start a fresh console session on the open port ser and read it to its first prompt, and
    whether the prompt came. DTR is dropped for DTR_LOW_SECONDS, what came meanwhile is thrown
    away, and DTR is raised: the Flipper starts a new session, which prints the banner and the
    prompt, and a console that had stopped answering answers again. The banner is read to its
    prompt, so that none of it is taken for the reply to the first command. When no prompt comes
    within BANNER_SECONDS, one carriage return is sent, which a session that DTR did not restart
    answers with a prompt."""
    ser.dtr = False
    time.sleep(DTR_LOW_SECONDS)
    ser.reset_input_buffer()
    ser.dtr = True
    if _read_to_prompt(ser, BANNER_SECONDS):
        return True
    ser.write(b"\r")
    return _read_to_prompt(ser, NUDGE_SECONDS)


def open_cli(port):
    """The Flipper's console at port, opened for this tool alone with a fresh session that has
    said its first prompt (wake), so the first command's reply is its own. One sentence and exit
    when the port cannot be opened, goes away meanwhile, or gives no prompt; the port is closed
    then."""
    ser = open_port(port)
    try:
        answered = wake(ser)
    except PORT_ERRORS as e:
        with contextlib.suppress(*PORT_ERRORS):
            ser.close()
        sys.exit(f"Could not use {port}: {e}. Is the Flipper still plugged in?")
    if not answered:
        with contextlib.suppress(*PORT_ERRORS):
            ser.close()
        sys.exit(
            f"The Flipper's console at {port} did not answer; restart the Flipper by holding Left and Back together "
            "for five seconds, then try again."
        )
    return ser


def run(ser, cmd, timeout=15.0):
    """Send one command, return its output without the echo, the prompt, or colour codes."""
    ser.reset_input_buffer()
    ser.write(cmd.encode() + b"\r")
    buf = b""
    t0 = time.time()
    while time.time() - t0 < timeout:
        chunk = ser.read(ser.in_waiting or 1)
        if chunk:
            buf += chunk
            if buf.endswith(PROMPT):
                break
        else:
            time.sleep(0.02)
    text = ANSI.sub("", buf.decode(errors="replace")).replace("\r\n", "\n")
    if text.endswith(">: "):
        text = text[:-3]
    lines = text.split("\n")
    if lines and lines[0].strip() == cmd.strip():
        lines = lines[1:]
    return "\n".join(lines).strip("\n")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="serial port, default: auto-detect")
    ap.add_argument("--timeout", type=float, default=15.0, help="seconds to wait per command (default 15)")
    ap.add_argument("--quiet", action="store_true", help="do not print the command headers")
    ap.add_argument("commands", nargs="+", help="commands to send, one argument each")
    args = ap.parse_args()
    port = find_port(args.port)
    with open_cli(port) as ser:
        for cmd in args.commands:
            out = run(ser, cmd, args.timeout)
            if not args.quiet:
                print(f"== {cmd}")
            if out:
                print(out)


if __name__ == "__main__":
    main()
