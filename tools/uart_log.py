#!/usr/bin/env python3
"""Capture the Flipper's debug console through the Wi-Fi dev board's UART bridge.

The board runs the Black Magic Probe firmware and shows up on the Mac as two serial ports; the
second one (/dev/cu.usbmodemblackmagic3) bridges the Flipper's pins 13 and 14, where the
firmware writes its log when the Debug flag is on (sysctl debug 1) at the level set with
sysctl log_level. The crash handler prints its registers, thread and stack there before the
reboot, which the USB console never sees. Lines are written with the Mac's time in front; the
port is reopened when it disappears (the board re-enumerates when the Flipper reboots).
Usage: nohup .venv/bin/python tools/uart_log.py docs/measurements/logs/<file>.txt &
"""
import glob, sys, time
import serial

PATTERN = "/dev/cu.usbmodemblackmagic3"
BAUD = 230400


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: uart_log.py <log file>")
    path = sys.argv[1]
    with open(path, "a", buffering=1) as out:
        out.write(f"== uart capture started {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        buf = b""
        while True:
            ports = glob.glob(PATTERN)
            if not ports:
                time.sleep(1)
                continue
            try:
                ser = serial.Serial(ports[0], BAUD, timeout=0.5)
            except (serial.SerialException, OSError) as e:
                out.write(f"== open failed {time.strftime('%H:%M:%S')}: {e}\n")
                time.sleep(2)
                continue
            out.write(f"== port open {time.strftime('%H:%M:%S')}\n")
            try:
                while True:
                    chunk = ser.read(4096)
                    if not chunk:
                        continue
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        out.write(time.strftime("%H:%M:%S ") + line.decode(errors="replace").rstrip("\r") + "\n")
            except (serial.SerialException, OSError) as e:
                out.write(f"== port dropped {time.strftime('%H:%M:%S')}: {e}\n")
                if buf:
                    out.write(time.strftime("%H:%M:%S ") + buf.decode(errors="replace") + "\n")
                    buf = b""
                try:
                    ser.close()
                except Exception:
                    pass
                time.sleep(2)


if __name__ == "__main__":
    main()
