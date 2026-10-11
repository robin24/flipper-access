#!/usr/bin/env python3
"""tools/flipper_cli.py's port: found by the Flipper's USB id, a port that names Flipper before
another board with ST's id, others left out; an explicit port, then FLIPPER_PORT, then the id,
then the Mac's device name; one sentence and exit without any, which names the PIN lock, the
updater and qFlipper; and opened for one tool alone, so a
second open of the same port stops with one sentence instead of sharing it. Needs pyserial. Run
from the project root: python3 tests/fbt/test_flipper_cli.py"""
import importlib.util
import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools"))
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def port(device, vid=None, pid=None, manufacturer=None, product=None, description=None):
    return SimpleNamespace(device=device, vid=vid, pid=pid, manufacturer=manufacturer, product=product, description=description)


def exits(fn, *args):
    try:
        fn(*args)
    except SystemExit as e:
        return str(e.code)
    return None


if importlib.util.find_spec("serial") is None:
    print("skipped the port checks: no pyserial")
else:
    import flipper_cli as fc

    ports = [
        port("/dev/ttyACM1", 0x0483, 0x5740, "STMicroelectronics", "STM32 Virtual ComPort"),
        port("/dev/ttyUSB0", 0x1D50, 0x6018, "Black Magic Debug"),
        port("/dev/ttyS0"),
        port("/dev/ttyACM0", 0x0483, 0x5740, "Flipper Devices Inc.", "Flipper Rover"),
    ]
    check(fc.flipper_ports(ports) == ["/dev/ttyACM0", "/dev/ttyACM1"],
          f"the Flipper's id only, the one that names Flipper first: {fc.flipper_ports(ports)}")
    check(fc.flipper_ports([port("COM4", 0x0483, 0x5740, description="Flipper Rover (COM4)")]) == ["COM4"],
          "a Windows port named in its description")
    check(fc.flipper_ports([]) == [], "none plugged in")

    saved = fc.flipper_ports, fc.glob.glob, os.environ.pop("FLIPPER_PORT", None)
    try:
        fc.flipper_ports = lambda: ["/dev/ttyACM0"]
        fc.glob.glob = lambda pattern: ["/dev/cu.usbmodemflip_Rover1"]
        check(fc.find_port("/dev/given") == "/dev/given", "a port given wins")
        os.environ["FLIPPER_PORT"] = "/dev/from-env"
        check(fc.find_port() == "/dev/from-env", "then FLIPPER_PORT")
        del os.environ["FLIPPER_PORT"]
        check(fc.find_port() == "/dev/ttyACM0", "then the USB id")
        fc.flipper_ports = lambda: []
        check(fc.find_port() == "/dev/cu.usbmodemflip_Rover1", "then the Mac's device name")
        fc.glob.glob = lambda pattern: []
        said = exits(fc.find_port)
        # A PIN-locked Flipper has no port at all, so the sentence names the lock beside the
        # updater and qFlipper
        check(said == "No Flipper serial port found. Is it plugged in, unlocked, not in the updater, and not used by "
                      "qFlipper? Or name it with --port.", f"none: the sentence that names every reason: {said}")
    finally:
        fc.flipper_ports, fc.glob.glob = saved[0], saved[1]
        if saved[2] is not None:
            os.environ["FLIPPER_PORT"] = saved[2]

    said = exits(fc.open_port, "/dev/no-such-port")
    check(said is not None and said.startswith("cannot open /dev/no-such-port"), f"a port that is not there: {said}")
    if os.name == "posix":
        # A pseudo-terminal stands in for the device: opened once, a second open is refused
        master, slave = os.openpty()
        name = os.ttyname(slave)
        first = fc.open_port(name)
        said = exits(fc.open_port, name)
        check(said is not None and "another tool" in said, f"a port another tool has is named at once: {said}")
        first.close()
        again = fc.open_port(name)
        check(again.is_open, "and free again once closed")
        again.close()
        os.close(master)
        os.close(slave)

print(f"flipper cli: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
