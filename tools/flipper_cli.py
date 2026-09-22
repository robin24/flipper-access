#!/usr/bin/env python3
"""Send one or more commands to the Flipper Zero command line over USB serial and print the replies.

Usage:
  tools/flipper_cli.py "info device" "loader list"
  tools/flipper_cli.py --timeout 120 "update backup /ext/backup.tar"

The serial port is found automatically (/dev/cu.usbmodemflip_*). Override with --port
or the FLIPPER_PORT environment variable. ANSI colour codes are stripped from the output
so it reads cleanly in a terminal with a screen reader.
"""
import argparse
import glob
import os
import re
import sys
import time

try:
    import serial
except ImportError:
    sys.exit("pyserial is missing. Run: .venv/bin/pip install pyserial  (or use .venv/bin/python)")

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
PROMPT = b">: "


def find_port(explicit=None):
    if explicit:
        return explicit
    env = os.environ.get("FLIPPER_PORT")
    if env:
        return env
    ports = sorted(glob.glob("/dev/cu.usbmodemflip_*"))
    if not ports:
        sys.exit("No Flipper serial port found. Is the device plugged in and not in the updater?")
    return ports[0]


def open_cli(port):
    ser = serial.Serial(port, 230400, timeout=0.1)
    ser.write(b"\r")
    time.sleep(0.4)
    ser.read(ser.in_waiting)  # discard the welcome banner
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
