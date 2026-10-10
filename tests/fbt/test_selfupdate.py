#!/usr/bin/env python3
"""The firmware's scripts/selfupdate.py, the last step of ./fbt flash_usb_full, against a stand-in
for the device's console. The script sends the update package to the card, closes the running app
with loader close, then starts the update with update install. The console's loader command is a
plugin on the card, so on a blank card the device answers that it cannot find the command; there
is then no app from the card to close either, and the script must go on to the update. With an app
open, it is closed first; with none, the update starts at once; any other answer to loader close
still stops the script with exit 4, before the update. The stand-in replies as the device's shell
does: the echo of the command and a line end, the command's output, then a line end and the prompt.
Run from the project root: python3 tests/fbt/test_selfupdate.py"""
import logging
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "Momentum-Firmware", "scripts")
failures = 0
checks = 0


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


NOT_FOUND = "\x1b[31mcould not find command `loader`, try `help`\x1b[0m"
NO_APP = "No application is running\r\n"
CLOSED = 'Application "NFC" was closed\r\n'
UPDATE_OK = "Verifying update package at '{}'\r\nOK.\r\nRestarting to apply update. BRB\r\n"


class Stream:
    """The serial port's receiving side: what the device has sent and the script not yet read."""

    def __init__(self):
        self.data = bytearray()

    @property
    def in_waiting(self):
        return len(self.data)

    def read(self, n):
        if not self.data:
            # The device would wait for more; a check must not hang on it
            raise RuntimeError("read past the device's last reply")
        out = bytes(self.data[:n])
        del self.data[:n]
        return out


class Console:
    """The device's shell: loader close answers from a list, update install verifies the path."""

    def __init__(self, loader_replies):
        self.loader_replies = list(loader_replies)
        self.sent = []
        self.stream = Stream()

    def handle(self, line):
        command = line.rstrip("\r")
        self.sent.append(command)
        if command == "loader close":
            output = self.loader_replies.pop(0)
        elif command.startswith("update install "):
            output = UPDATE_OK.format(command[len("update install "):])
        else:
            output = f"\x1b[31mcould not find command `{command.split()[0]}`, try `help`\x1b[0m"
        self.stream.data += f"{command}\r\n{output}\r\n>: ".encode()


def run(loader_replies):
    """selfupdate.py's install with the console answering loader close from loader_replies:
    (exit code, commands sent)."""
    console = Console(loader_replies)

    class Storage:
        CLI_EOL = "\r\n"

        def __init__(self, port):
            self.read = selfupdate_storage.BufferedRead(console.stream)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def send(self, line):
            console.handle(line)

        def send_and_wait_eol(self, line):
            self.send(line)
            return self.read.until(self.CLI_EOL)

    class Operations:
        def __init__(self, storage):
            pass

        def mkpath(self, path):
            pass

        def recursive_send(self, to, source):
            pass

    selfupdate.FlipperStorage = Storage
    selfupdate.FlipperStorageOperations = Operations
    selfupdate.resolve_port = lambda logger, port: "stand-in"
    with tempfile.TemporaryDirectory() as tmp:
        package = os.path.join(tmp, "f7-update-test")
        os.mkdir(package)
        manifest = os.path.join(package, "update.fuf")
        with open(manifest, "w") as f:
            f.write("stand-in\n")
        code = selfupdate.Main(no_exit=True)([manifest])
    return code, console.sent


sys.path.insert(0, SCRIPTS)
try:
    import selfupdate
    import flipper.storage as selfupdate_storage
except ImportError as e:
    print(f"skipped the flash script checks: {e.name} is missing")
    print(f"selfupdate: {checks - failures} of {checks} checks passed")
    sys.exit(0)

selfupdate.Main.APP_POST_CLOSE_DELAY_SEC = 0
# A handler of our own, so the script adds none and its log lines stay out of the output
logging.getLogger().addHandler(logging.NullHandler())
INSTALL = "update install /ext/update/f7-update-test/update.fuf"

code, sent = run([NOT_FOUND])
check(code == 0, f"a blank card, without the loader command: the update starts, exit {code}")
check(sent == ["loader close", INSTALL], f"and loader close is asked once, then the update: {sent}")

code, sent = run([NO_APP])
check(code == 0, f"no app running: exit {code}")
check(sent == ["loader close", INSTALL], f"the update follows at once: {sent}")

code, sent = run([CLOSED, NO_APP])
check(code == 0, f"an app open: exit {code}")
check(sent == ["loader close", "loader close", INSTALL], f"it is closed, then the update: {sent}")

code, sent = run(['Application "NFC" has to be closed manually\r\n'])
check(code == 4, f"an app that must be closed by hand stops the script: exit {code}")
check(INSTALL not in sent, f"before the update: {sent}")

print(f"selfupdate: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
