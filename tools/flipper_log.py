#!/usr/bin/env python3
"""Capture the Flipper's log stream to a file until the port drops (a crash reboots the device
and closes the port) or until the process is stopped.

    tools/flipper_log.py [--port PORT] [--level debug|info|warn|error] OUT.txt

The crash handler prints "[CRASH]", the thread name, the check message and the registers
(PC, LR) to the log before rebooting, so the file's tail names the crash site:
arm-none-eabi-addr2line -e Momentum-Firmware/build/f7-firmware-C/firmware.elf <PC> <LR>.
Only one console session can run at a time: stop this before using tools/flipper_cli.py.
"""
import argparse, glob, signal, sys, time
import serial

ap = argparse.ArgumentParser()
ap.add_argument("out")
ap.add_argument("--port", default=(glob.glob("/dev/cu.usbmodemflip_*") or [""])[0])
ap.add_argument("--level", default="debug")
a = ap.parse_args()
if not a.port:
    sys.exit("no Flipper port")

stop = False
def on_signal(signum, frame):
    global stop
    stop = True
signal.signal(signal.SIGTERM, on_signal)
signal.signal(signal.SIGINT, on_signal)

with open(a.out, "ab", buffering=0) as out, serial.Serial(a.port, 230400, timeout=0.2) as ser:
    ser.write(b"\r"); time.sleep(0.3); ser.read(ser.in_waiting)
    ser.write(("log %s\r" % a.level).encode())
    out.write(("== log started %s on %s\n" % (time.strftime("%H:%M:%S"), a.port)).encode())
    line = b""
    while not stop:
        try:
            chunk = ser.read(4096)
        except (serial.SerialException, OSError) as e:
            out.write(("== port dropped %s: %s\n" % (time.strftime("%H:%M:%S"), e)).encode())
            break
        if not chunk:
            continue
        for b in chunk:
            line += bytes([b])
            if b == 10:
                out.write(time.strftime("%H:%M:%S ").encode() + line)
                line = b""
    if stop:
        try:
            ser.write(b"\x03")  # any key ends the log command
        except Exception:
            pass
        out.write(("== log stopped %s\n" % time.strftime("%H:%M:%S")).encode())
