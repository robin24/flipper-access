#!/usr/bin/env python3
"""tools/flipper_cli.py's port: found by the Flipper's USB id, a port that names Flipper before
another board with ST's id, others left out; an explicit port, then FLIPPER_PORT, then the id,
then the Mac's device name; one sentence and exit without any, which names the PIN lock, the
updater and qFlipper; and opened for one tool alone, so a
second open of the same port stops with one sentence instead of sharing it. The console's open,
against a stand-in port with the Flipper's console behind it: DTR is dropped for half a second
and raised, the banner that the new session prints is read to its prompt and is never part of the
first command's reply, a console that answered nothing until then answers, a console that gives
no prompt to DTR gets one carriage return, and one that gives none at all, or whose port goes
away, ends in one sentence with the port closed. Needs pyserial. Run from the project root:
python3 tests/fbt/test_flipper_cli.py"""
import importlib.util
import os
import sys
import time
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
        check(said == "No Flipper serial port found; check that the Flipper is plugged in, unlocked, not in the "
                      "updater and not used by qFlipper, or name its port with --port.",
              f"none: the one sentence that names every reason: {said}")
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

    # The console's open, against a stand-in port
    import serial

    import flipper_storage as fs

    # The banner as cli_main_motd prints it, shortened, then the shell's prompt; it arrives in pieces
    BANNER = [
        b"\x1b[38;2;255;130;0m\r\n              _.-------.._                    -,\r\n",
        b"\r\n\x1b[1;37mWelcome to Flipper Zero Command Line Interface!\r\n",
        b"Run `help` or `?` to list available commands\r\n\r\n\x1b[0m",
        b"Firmware version: screen-reader mntm-dev (9149fe49 built on 09-10-2026)\r\n",
        b"\r\n>: ",
    ]
    INFO = "hardware.name                 : R0skie\r\nfirmware.version              : mntm-dev\r\n"
    events = []  # what was done to the stand-in port and when the tool slept, in order

    class Console:
        """A serial port as pyserial gives it, with the Flipper's console behind it. DTR rising
        starts a session, which sends the banner and its prompt as bytes that take a moment to
        arrive: one piece each time the port is read, and a command typed meanwhile is answered
        after the rest of the banner. Opening the port raises DTR. asleep: the console answers
        nothing until DTR has been dropped and raised again, as it did after ten idle hours on
        2026-10-11. deaf: DTR changes nothing, and the session from before answers a carriage
        return with a prompt. mute: nothing ever answers. gone: the port is gone at the first
        change of DTR."""

        def __init__(self, asleep=False, deaf=False, mute=False, gone=False):
            self.asleep, self.deaf, self.mute, self.gone = asleep, deaf, mute, gone
            self.out = bytearray()  # arrived, not yet read
            self.coming = []  # sent by the device, not yet arrived
            self.session = deaf
            self.is_open = True
            self._dtr = False
            self.opening = True
            self.dtr = True  # the open raises DTR
            self.opening = False

        @property
        def dtr(self):
            return self._dtr

        @dtr.setter
        def dtr(self, value):
            if not self.opening:
                if self.gone:
                    raise serial.SerialException("could not set DTR: [Errno 6] Device not configured")
                events.append(("dtr", value))
            rising = value and not self._dtr
            self._dtr = value
            if self.deaf or self.mute:
                return
            if not value:
                self.asleep = False  # the old session ends
                self.session = False
                self.coming.clear()
            elif rising and not self.asleep:
                self.session = True
                self.coming = list(BANNER)

        @property
        def in_waiting(self):
            return len(self.out)

        def read(self, size=1):
            if self.coming:
                self.out += self.coming.pop(0)
            data = bytes(self.out[:size])
            del self.out[:size]
            return data

        def reset_input_buffer(self):
            events.append(("reset",))
            self.out.clear()

        def write(self, data):
            events.append(("write", bytes(data)))
            if not self.session:
                return len(data)
            for piece in self.coming:  # the rest of the banner comes before any answer
                self.out += piece
            self.coming.clear()
            for line in bytes(data).split(b"\r")[:-1]:
                command = line.decode()
                reply = INFO if command == "info device" else ""
                self.out += (f"{command}\r\n{reply}" if command else "").encode() + b"\r\n>: "
            return len(data)

        def close(self):
            self.is_open = False

    def opened(console):
        """open_cli on a port that is console: (the port it gave or None, its exit sentence or None)."""
        events.clear()
        saved = fc.open_port, fc.time
        fc.open_port = lambda port, timeout=0.1: console
        fc.time = SimpleNamespace(sleep=lambda seconds: events.append(("sleep", seconds)), monotonic=time.monotonic,
                                  time=time.time)
        try:
            return fc.open_cli("/dev/cu.usbmodemflip_R0skie1"), None
        except SystemExit as e:
            return None, str(e.code)
        finally:
            fc.open_port, fc.time = saved

    fc.BANNER_SECONDS, fc.NUDGE_SECONDS = 0.2, 0.2  # a stand-in answers at once or never
    console = Console()
    ser, said = opened(console)
    check(ser is console and said is None, f"open_cli gives the port: {said}")
    check(events[:4] == [("dtr", False), ("sleep", 0.5), ("reset",), ("dtr", True)],
          f"DTR is dropped, half a second passes, what came is thrown away, and DTR is raised: {events[:4]}")
    check(not [e for e in events if e[0] == "write"] and not console.coming and not console.out,
          f"the banner is read to its prompt, and nothing is typed: {events}")
    reply = fc.run(ser, "info device", timeout=1)
    check(reply == INFO.replace("\r\n", "\n").strip("\n"), f"the first command's reply is its own, without the banner: {reply!r}")
    console = Console()
    ser, said = opened(console)
    reply = fs.Storage(ser).command("info device")
    check(reply.startswith("hardware.name") and "Welcome" not in reply and "Firmware version" not in reply,
          f"and so is the first reply that a Storage reads: {reply!r}")
    # A console that answered nothing to a fresh open, as after ten idle hours
    console = Console(asleep=True)
    ser, said = opened(console)
    reply = fc.run(ser, "info device", timeout=1) if ser else None
    check(said is None and reply == INFO.replace("\r\n", "\n").strip("\n"),
          f"a console that answered nothing answers after DTR was dropped and raised: {said}, {reply!r}")
    # DTR that starts no session: one carriage return, as before
    console = Console(deaf=True)
    ser, said = opened(console)
    check(said is None and ("write", b"\r") in events, f"a console that DTR does not restart gets a carriage return: {said}, {events}")
    reply = fc.run(ser, "info device", timeout=1) if ser else None
    check(reply == INFO.replace("\r\n", "\n").strip("\n"), f"and then answers: {reply!r}")
    # No prompt at all: one sentence, and the port is closed
    console = Console(mute=True)
    started = time.monotonic()
    ser, said = opened(console)
    check(ser is None and said is not None and "did not answer" in said and "R0skie" in said and not console.is_open,
          f"a console that gives no prompt: {said}")
    check(said is not None and said.count(". ") == 0 and said.endswith(".") and "\n" not in said, f"in one sentence: {said}")
    check(time.monotonic() - started < 2, "after the banner's time and the carriage return's")
    # The port goes away while it is woken
    console = Console(gone=True)
    ser, said = opened(console)
    check(ser is None and said is not None and "R0skie" in said and "Device not configured" in said and not console.is_open,
          f"a port that goes away while it is woken: {said}")

print(f"flipper cli: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
