#!/usr/bin/env python3
"""tools/install.py, the install over USB, against a stand-in for the Flipper: its console, its
card, and its port, which goes away while the Flipper updates and comes back. The stand-in answers
as the device's shell does (the echo of the command and a line end, the output, then a line end and
the prompt), unpacks a tar with storage extract as the firmware does, entry line by entry line, and
restarts on update install after its "Restarting to apply update" line; its console session begins
when DTR rises, and every open is checked to drop DTR and raise it again before its first command.
The checks: describe names Sonar, Momentum and the official firmware; a whole run sends info device,
update backup, the voice pack, storage extract, the update package and update install in that order,
then info device after the wait, and never loader, power, input, sysctl or sr voice use; from Sonar
the extract is wrapped in sr voice off and sr voice on, from any other firmware no sr command is
sent; verify against a release.json; the wait for the port, which names the PIN that a Flipper asks
for again when it restarts; an update command refused while an application is open, whose sentence
says to press Back until the Flipper says Home screen; a card that is missing or unreadable at the
backup's first card command, and a backup that fails, which a full card can cause, whose sentences
say what to check; a console that gives its prompt
and then answers nothing, and a run stopped with Ctrl-C, whose sentences say to restart the Flipper;
and every failure, a storage error in an upload among them, ends in one sentence that names the
step, exit code 1, and no traceback, and the last check is that every failure message the checks
made has one sentence-ending full stop. The voice through a card reader is checked with temporary
folders as the volumes, a stand-in user who moves the card when asked and presses Enter, and a
stand-in card that leaves the stand-in Flipper, whose storage commands then say internal error,
comes back after the eject, and gets a ._ file beside everything unpacked onto it, as macOS does:
find_card and the volumes, unpack_to_card in the pack's order and refusing an entry that leaves the
volume (Windows names too), remove_appledouble, eject, the marker and the markers of earlier runs,
the look for the card that starts only after Enter and ends in one sentence without USB, a card
mounted read-only, the console closed while the card is out, the wait after the card is back for a
port that stays listed, with internal error taken for not yet, a port that vanishes after the first
answer and comes back, a console that stops answering, and the time-out with the Flipper's last
reason, the ._ files removed over the console, and the questions of a run without --yes. The card
that was found is asked about, in one line, before anything is written to it: its name (the last part
of the mount path, or a Windows drive's label), its path, its size and free space in gigabytes, left
out when the system does not give them, and the marker; Enter, y and yes copy, n and no write
nothing, eject the card and end the install in one sentence, an answer that is neither is asked
again, no answer ends like no, and a card that is read-only is refused before any question.
Needs pyserial. Run from the project root: python3 tests/fbt/test_install.py"""
import contextlib
import importlib.util
import io
import errno
import json
import ntpath
import os
import posixpath
import re
import shlex
import subprocess
import sys
import tarfile
import tempfile
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


if importlib.util.find_spec("serial") is None:
    print("skipped the install checks: no pyserial")
    print("install: 0 of 0 checks passed")
    sys.exit(0)

import serial

import flipper_cli as fc
import flipper_storage as fs
import install

# Every InstallError message the checks below make install.py say, for the last check: each failure
# is one sentence, with one sentence-ending full stop
made_errors = []
made_error = install.InstallError.__init__


def recorded(self, *args):
    made_errors.append(str(args[0]) if args else "")
    made_error(self, *args)


install.InstallError.__init__ = recorded

# info device, as furi_hal_info.c prints it with "%-30s: %s". The hardware, radio and system lines
# are the device's of 2026-09-24 (docs/superpowers/build-logs/2026-09-24-clip-voice-spelling/
# task-1-report.md) with the unique id and the MAC address made up.
HARDWARE = [
    ("format.major", "3"), ("format.minor", "3"), ("hardware.model", "Flipper Zero"),
    ("hardware.uid", "0123456789ABCDEF"), ("hardware.otp.ver", "2"), ("hardware.timestamp", "1720072856"),
    ("hardware.ver", "12"), ("hardware.target", "7"), ("hardware.body", "9"), ("hardware.connect", "6"),
    ("hardware.display", "2"), ("hardware.color", "2"), ("hardware.region.builtin", "4"),
    ("hardware.region.provisioned", "DE"), ("hardware.name", "R0skie"),
]
RADIO = [
    ("radio.alive", "true"), ("radio.mode", "Stack"), ("radio.fus.major", "1"), ("radio.fus.minor", "2"),
    ("radio.fus.sub", "0"), ("radio.fus.sram2b", "16K"), ("radio.fus.sram2a", "0K"), ("radio.fus.flash", "24K"),
    ("radio.stack.type", "3"), ("radio.stack.major", "1"), ("radio.stack.minor", "20"), ("radio.stack.sub", "0"),
    ("radio.stack.branch", "0"), ("radio.stack.release", "2"), ("radio.stack.sram2b", "19K"),
    ("radio.stack.sram2a", "14K"), ("radio.stack.sram1", "0K"), ("radio.stack.flash", "116K"),
    ("radio.ble.mac", "0123456789AB"), ("enclave.keys.valid", "10"), ("enclave.valid", "true"),
]


def info_reply(commit, dirty, branch, version, date, api, origin, git, boot=0):
    """The reply to info device of a firmware: the firmware lines given, the rest as above."""
    major, minor = api.split(".")
    firmware = [
        ("firmware.commit.hash", commit), ("firmware.commit.dirty", dirty), ("firmware.branch.name", branch),
        ("firmware.branch.num", "0"), ("firmware.version", version), ("firmware.build.date", date),
        ("firmware.target", "7"), ("firmware.api.major", major), ("firmware.api.minor", minor),
        ("firmware.origin.fork", origin), ("firmware.origin.git", git),
    ]
    system = [
        ("system.debug", "0"), ("system.lock", "0"), ("system.orient", "0"), ("system.sleep.legacy", "0"),
        ("system.stealth", "1"), ("system.heap.track", "0"), ("system.boot", str(boot)),
        ("system.locale.time", "0"), ("system.locale.date", "0"), ("system.locale.unit", "0"),
        ("system.log.level", "1"), ("protobuf.version.major", "0"), ("protobuf.version.minor", "25"),
    ]
    return "".join(f"{key:<30}: {value}\r\n" for key, value in HARDWARE + firmware + RADIO + system)


SONAR_GIT = "https://github.com/robin24/Momentum-Firmware.git"
# Sonar 9149fe493 as the device reported it on 2026-10-11 (docs/measurements/2026-10-11-transfer-
# spike.txt) and on 2026-10-09 (docs/device-notes.md: API 87.3, the origin's git address)
SONAR_DEV = info_reply("9149fe49", "false", "claude/device-checks-2026-10-09", "mntm-dev", "09-10-2026", "87.3",
                       "Sonar", SONAR_GIT)
# The same commit built as the release sonar-0.1.0, which is what the release's package installs
SONAR_RELEASE = info_reply("9149fe49", "false", "screen-reader", "sonar-0.1.0", "11-10-2026", "87.3", "Sonar", SONAR_GIT)
# The keys are those of furi_hal_info.c, which official firmware and Momentum share with Sonar.
# OFFICIAL was checked against a real official 1.4.3 on 2026-10-13 (docs/measurements/2026-10-13-
# release-rehearsal.txt): the commit 8622f1a2, the dirty flag, the version, the build date
# 05-12-2025, the origin Official and the branch name 1.4.3. Its git address is the string in the
# firmware.dfu of the rollback package f7-update-1.4.3 in firmware-packages/, not read from the
# device, and its API version is still a guess, since the full reply was not kept. MOMENTUM is
# provisional: its commit, version, build date, origin and git address are the strings in the
# firmware.dfu of f7-update-mntm-012, and its API version and its branch name, release, are guesses
OFFICIAL = info_reply("8622f1a2", "false", "1.4.3", "1.4.3", "05-12-2025", "86.0", "Official",
                      "https://github.com/flipperdevices/flipperzero-firmware")
MOMENTUM = info_reply("e1784e74", "false", "release", "mntm-012", "31-12-2025", "87.1", "Momentum",
                      "https://github.com/Next-Flip/Momentum-Firmware")

RELEASE = {
    "version": "sonar-0.1.0",
    "firmware_version": "sonar-0.1.0",
    "firmware_commit": "9149fe493",
    "momentum_base": "mntm-012",
    "api_version": "87.3",
    "default_voice": "heart",
    "voices": [{"set": "heart", "backend": "kokoro", "voice": "af_heart", "file": "voice-heart-sonar-0.1.0.tar"}],
    "assets": [],
}

NOT_EXIST = "Storage error: file/dir not exist\r\n"
EXISTS = "Storage error: file/dir already exist\r\n"
FULL = "Storage error: internal error\r\n"
DENIED = "Storage error: access denied\r\n"
# What the device says of a storage command while the card is out of its slot: internal error, as
# Robin's Flipper said on 2026-10-11, and FSE_NOT_READY's sentence in filesystem_api.c, which the
# firmware's source suggests
CARD_OUT = "Storage error: internal error\r\n"
NOT_READY = "Storage error: filesystem not ready\r\n"
NOT_FOUND = "\x1b[31mcould not find command `{}`, try `help`\x1b[0m\r\n"
# What the shell says, in red and without a line end, to a command that needs the loader while an
# application is open (cli_shell.c); of the install's commands only update is such a command
APP_OPEN = "\x1b[31mthis command cannot be run while an application is open\x1b[0m"
UPDATE_OK = "Verifying update package at '{}'\r\nOK.\r\nRestarting to apply update. BRB\r\n"
UPDATE_REFUSED = "Verifying update package at '{}'\r\nError: Invalid manifest data. Stopping update.\r\n"
PORT = "/dev/cu.usbmodemflip_R0skie1"
OLD_PACKAGES = ("f7-update-1.4.3", "f7-update-mntm-012", "f7-update-mntm-screen-reader-11111111")


class Flipper:
    """The device: its card, the firmware it runs, and its port, which a restart takes away."""

    def __init__(self, info, after=None):
        self.info = info  # the reply to info device
        self.after = after if after is not None else info  # the reply once an update has run
        self.booting = []  # replies to info device after the update before it is ready, one each
        self.files = {}
        self.dirs = {"/ext", "/ext/update"}
        for name in OLD_PACKAGES:
            self.dirs.add(f"/ext/update/{name}")
            self.files[f"/ext/update/{name}/update.fuf"] = bytearray(b"Filetype: Flipper firmware upgrade configuration\n")
        self.sent = []  # every command, over every connection, in order
        self.updated = False
        self.absent_after_update = 3  # the port list does not show the port this many times
        self.absent = 0
        self.never_back = False  # after the update the port never comes back
        self.update_reply = UPDATE_OK
        self.full_under = None  # a write to a path that starts with this fails after its data
        self.extract_fails = False
        self.backup_result = "OK"
        self.restore_result = None  # what update restore answers; None: OK for a backup that is on the card
        self.connections = []
        self.app_open = None  # the update command whose word follows update is refused: an app is open
        self.card_out = False  # the card is in the user's hand or a card reader, not in the slot
        self.out_reply = CARD_OUT  # what a storage command gets while there is no card to use
        self.mounting = 0  # storage commands that still get out_reply after the card is put back
        # The USB connection drops after the card goes back, as on 2026-10-11: once the Flipper has
        # said that it sees a voice.txt, the port vanishes for this many looks at the port list
        self.drop_after_seen = None
        self.dropped = False
        self.port_script = []  # whether the port list shows the port, one look each, before the rest
        self.silent_opens = 0  # this many opens give a console that answers no command
        self.looks = 0  # the looks at the port list
        self.opened_at = []  # the looks at the port list before each open
        self.aliases = set()  # other names that open the port, such as a /dev/serial/by-id link
        self.taken = 0  # this many opens find the port held by another tool, as qFlipper holds it

    def running(self):
        """The reply to info device now."""
        if not self.updated:
            return self.info
        return self.booting.pop(0) if self.booting else self.after

    def sonar(self):
        return "Sonar" in self.info if not self.updated else "Sonar" in self.after

    def ports(self, ports=None):
        """flipper_cli.flipper_ports, as this computer would list the port."""
        self.looks += 1
        if self.port_script:
            return [PORT] if self.port_script.pop(0) else []
        if self.updated and self.never_back:
            return []
        if self.absent:
            self.absent -= 1
            return []
        return [PORT]

    def open_port(self, port, timeout=0.1):
        """flipper_cli.open_port: the port, or its one sentence and exit when it is not there."""
        if self.taken:
            self.taken -= 1
            sys.exit(f"Could not open {port}: Resource temporarily unavailable; close qFlipper or any other tool that uses it.")
        if port not in {PORT, *self.aliases} or (self.updated and self.never_back) or self.absent:
            self.absent = max(0, self.absent - 1)
            sys.exit(f"Could not open {port}: No such file or directory; close qFlipper or any other tool that uses it.")
        connection = Connection(self)
        if self.silent_opens:
            self.silent_opens -= 1
            connection.silent = True
        self.connections.append(connection)
        self.opened_at.append(self.looks)
        return connection


BANNER = b"\r\nWelcome to the stand-in\r\n\r\n>: "


class Connection:
    """One open of the port: the serial port as install.py sees it, and the shell behind it. The
    open raises DTR, and a rising DTR starts a console session, which prints the banner and the
    prompt; DTR dropping ends the session. Typed lines are answered only in a session."""

    def __init__(self, flipper):
        self.flipper = flipper
        self.out = bytearray()
        self.typed = bytearray()
        self.target = None
        self.need = 0
        self.gone = False  # the Flipper restarted: the port is dead
        self.is_open = True
        self.silent = False  # the console takes commands and answers none
        self.session = False
        self.events = []  # the DTR changes and the first command, in order
        self._dtr = False
        self.dtr = True  # the open

    @property
    def dtr(self):
        return self._dtr

    @dtr.setter
    def dtr(self, value):
        if self.gone:
            raise serial.SerialException("could not set DTR: [Errno 6] Device not configured")
        self.events.append(("dtr", value))
        if value and not self._dtr:
            self.session = True
            self.out += BANNER
        elif not value:
            self.session = False
        self._dtr = value

    @property
    def in_waiting(self):
        return len(self.out)

    def read(self, size):
        if not self.out:
            if self.gone:
                raise serial.SerialException("device reports readiness to read but returned no data")
            return b""
        data = bytes(self.out[:size])
        del self.out[:size]
        return data

    def reset_input_buffer(self):
        if self.gone:
            raise serial.SerialException("could not clear the input buffer: [Errno 6] Device not configured")
        self.out.clear()

    def close(self):
        self.is_open = False

    def write(self, data):
        if self.gone:
            raise serial.SerialException("write failed: [Errno 6] Device not configured")
        self.typed += data
        while self.typed:
            if self.need:
                take = bytes(self.typed[: self.need])
                del self.typed[: len(take)]
                self.flipper.files[self.target] += take
                self.need -= len(take)
                if not self.need:
                    self.finish_chunk()
            elif b"\r" in self.typed:
                end = self.typed.index(b"\r")
                command = self.typed[:end].decode()
                del self.typed[: end + 1]
                self.handle(command)
            else:
                break

    def say(self, command, output):
        self.out += f"{command}\r\n{output}\r\n>: ".encode()

    def finish_chunk(self):
        full = self.flipper.full_under and self.target.startswith(self.flipper.full_under)
        self.out += (FULL if full else "").encode() + b"\r\n>: "

    def handle(self, command):
        f = self.flipper
        if not self.session:
            return  # no console session: no echo, no prompt
        if not command.strip():
            self.out += b"\r\n>: "
            return
        if not any(e[0] == "command" for e in self.events):
            self.events.append(("command", len(self.out)))  # with the bytes not yet read
        f.sent.append(command)
        if self.silent:
            return
        words = shlex.split(command)
        if words[0] == "storage" and (f.card_out or f.mounting):
            if not f.card_out:
                f.mounting -= 1
            self.say(command, f.out_reply)
            return
        if command == "info device":
            self.say(command, f.running())
        elif words[0] == "update" and words[1:2] == [f.app_open]:
            self.say(command, APP_OPEN)
        elif words[:2] == ["update", "backup"]:
            f.files[words[2]] = bytearray(b"a backup of /int")
            self.say(command, f"Backup /int to '{words[2]}'\r\nResult: {f.backup_result}\r\n")
        elif words[:2] == ["update", "restore"]:
            result = f.restore_result or ("OK" if words[2] in f.files else "FAIL")
            self.say(command, f"Restore /int from '{words[2]}'\r\nResult: {result}\r\n")
        elif words[:2] == ["update", "install"]:
            if f.update_reply == UPDATE_OK and words[2] in f.files:
                self.out += f"{command}\r\n{UPDATE_OK.format(words[2])}".encode()
                self.gone = True
                f.updated = True
                f.absent = f.absent_after_update
            else:
                self.say(command, UPDATE_REFUSED.format(words[2]))
        elif words[:2] == ["sr", "voice"] and f.sonar():
            if words[2] == "off":
                self.say(command, f"voice off for {words[3]} s, then on again by itself\r\n")
            else:
                self.say(command, "voice on\r\n")
        elif words[:2] == ["storage", "write_chunk"]:
            path, size = words[2], int(words[3])
            if posixpath.dirname(path) not in f.dirs:
                self.say(command, NOT_EXIST)
                return
            f.files.setdefault(path, bytearray())
            self.target, self.need = path, size
            self.out += f"{command}\r\nReady\r\n".encode()
            if not size:
                self.finish_chunk()
        elif words[:2] == ["storage", "stat"]:
            path = words[2]
            if path == "/ext":
                self.say(command, "Storage, 62496768KiB total, 58080768KiB free\r\n")
            elif path in f.files:
                self.say(command, f"File, size: {len(f.files[path])}b\r\n")
                if path.endswith("/voice.txt") and f.drop_after_seen is not None and not f.dropped:
                    f.dropped = True
                    f.absent = f.drop_after_seen
                    self.gone = True  # its answer is read, and then the port is gone
            elif path in f.dirs:
                self.say(command, "Directory\r\n")
            else:
                self.say(command, NOT_EXIST)
        elif words[:2] == ["storage", "mkdir"]:
            path = words[2]
            if path in f.dirs or path in f.files:
                self.say(command, EXISTS)
            elif posixpath.dirname(path) not in f.dirs:
                self.say(command, NOT_EXIST)
            else:
                f.dirs.add(path)
                self.say(command, "")
        elif words[:2] == ["storage", "remove"]:
            path = words[2]
            if path in f.files:
                del f.files[path]
                self.say(command, "")
            elif path in f.dirs:
                inside = [p for p in list(f.files) + list(f.dirs) if posixpath.dirname(p) == path]
                if inside:
                    self.say(command, DENIED)
                else:
                    f.dirs.discard(path)
                    self.say(command, "")
            else:
                self.say(command, NOT_EXIST)
        elif words[:2] == ["storage", "list"]:
            path = words[2]
            if path not in f.dirs:
                self.say(command, NOT_EXIST)
                return
            folders = sorted(posixpath.basename(d) for d in f.dirs if posixpath.dirname(d) == path)
            files = sorted((posixpath.basename(p), len(b)) for p, b in f.files.items() if posixpath.dirname(p) == path)
            lines = [f"\t[D] {name}\r\n" for name in folders] + [f"\t[F] {name} {size}b\r\n" for name, size in files]
            self.say(command, "".join(lines) or "\tEmpty\r\n")
        elif words[:2] == ["storage", "extract"]:
            self.extract(command, words[2], words[3])
        else:
            self.say(command, NOT_FOUND.format(words[0]))

    def extract(self, command, archive, dest):
        """storage extract as the firmware does it: an entry line for each folder and file."""
        f = self.flipper
        if archive not in f.files:
            self.say(command, "Failed to open archive\r\n")
            return
        lines = [f"Unpacking to {dest}\r\n"]
        with tarfile.open(fileobj=io.BytesIO(bytes(f.files[archive])), mode="r:") as tar:
            for member in tar.getmembers():
                if f.extract_fails and len(lines) > 2:
                    lines.append("Decompression failed in 12 ticks \r\n")
                    self.say(command, "".join(lines))
                    return
                path = posixpath.join(dest, member.name)
                if member.isdir():
                    f.dirs.add(path)
                    lines.append(f"\tD {member.name}\r\n")
                else:
                    f.files[path] = bytearray(tar.extractfile(member).read())
                    lines.append(f"\tF {member.name}\r\n")
        lines.append("Decompression success in 4321 ticks \r\n")
        self.say(command, "".join(lines))


# The stand-ins in place of the computer's port list and port, and no waiting
fc.time = SimpleNamespace(sleep=lambda seconds: None, time=time.time, monotonic=time.monotonic)  # open_cli's pauses
fc.glob.glob = lambda pattern: []
os.environ.pop("FLIPPER_PORT", None)
install.RESTART_SECONDS = 0
install.POLL_SECONDS = 0
install.today = lambda: "2026-10-11"
answers = []
asked = []


def stub_ask(question):
    """The user's next answer in answers, or None when no one can answer; the questions are kept."""
    asked.append(question)
    return answers.pop(0) if answers else None


install.ask = stub_ask
install._serial_devices = lambda: []  # this computer's own serial ports are never looked at
STEADY_DEFAULT = getattr(install, "PORT_STEADY_SECONDS", None)
install.PORT_STEADY_SECONDS = 0


def plug(flipper):
    """Make flipper the Flipper this computer sees."""
    fc.flipper_ports = flipper.ports
    fc.open_port = flipper.open_port


def run(flipper, argv, progress=60, wait=900):
    """install.main(argv) with flipper plugged in: (exit code, the lines it printed, stderr)."""
    plug(flipper)
    install.PROGRESS_SECONDS = progress
    install.WAIT_SECONDS = wait
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = install.main(argv)
    return code, out.getvalue().splitlines(), err.getvalue()


def main_commands(sent):
    """The commands of a run without those of the uploads, each stat, mkdir and write_chunk."""
    return [c for c in sent if not c.startswith(("storage stat ", "storage mkdir ", "storage write_chunk "))]


def forbidden(sent):
    """The commands among sent that the install must never send."""
    return [c for c in sent if c.split()[0] in ("loader", "power", "input", "sysctl") or c.startswith("sr voice use")]


def no_traceback(lines, err):
    return not any("Traceback" in line for line in lines) and "Traceback" not in err


def write(path, data):
    with open(path, "wb") as f:
        f.write(data)


def folder_entry(name):
    entry = tarfile.TarInfo(name)
    entry.type = tarfile.DIRTYPE
    entry.mode = 0o755
    return entry


def make_pack(path, extra=None, set_name="heart"):
    """A voice pack as tools/voice_pack.py writes it: USTAR, every folder before its files."""
    prefix = f"sr/voices/{set_name}"
    clips = {
        f"{prefix}/voice.txt": b"backend kokoro voice af_heart\n",
        f"{prefix}/3f/hello.raw": bytes(range(256)) * 40,
        f"{prefix}/a0/world.raw": bytes(range(255, -1, -1)) * 30,
    }
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as tar:
        for name in ("sr", "sr/voices", prefix, f"{prefix}/3f", f"{prefix}/a0"):
            tar.addfile(folder_entry(name))
        for name, data in clips.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
        for name, data in (extra or {}).items():
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            tar.addfile(entry, io.BytesIO(data))
    return clips


def make_package(root, name="f7-update-sonar-0.1.0", fuf=True):
    """An update package folder and its .tgz, as fbt's updater_package makes them."""
    folder = os.path.join(root, name)
    os.makedirs(folder)
    files = {"firmware.dfu": bytes(i % 253 for i in range(70000)), "resources.tar.gz": bytes(range(256)) * 20}
    if fuf:
        files["update.fuf"] = f"Filetype: Flipper firmware upgrade configuration\nVersion: 2\nInfo: {name[10:]}\n".encode()
    for file_name, data in files.items():
        write(os.path.join(folder, file_name), data)
    tgz = os.path.join(root, f"flipper-z-{name}.tgz")
    with tarfile.open(tgz, "w:gz") as tar:
        tar.add(folder, arcname=name)
    return folder, tgz, files


real_unpack = install.unpack_to_card


def card_path(root, path):
    """The place on a volume of a path on the card, /ext/sr/a.raw: root/sr/a.raw."""
    return os.path.join(root, *path[len("/ext/"):].split("/"))


def volume_tree(volume):
    """Every folder and file on a volume, relative to it, with the size of each file, sorted."""
    found = []
    for here, folders, names in os.walk(volume):
        relative = os.path.relpath(here, volume)
        found += [(os.path.join(relative, name), None) for name in folders]
        found += [(os.path.join(relative, name), os.path.getsize(os.path.join(here, name))) for name in names]
    return sorted(found)


# The two things the card reader way asks the user to do, each answered with Enter
TAKE_OUT = "Take the microSD card out of the Flipper and put it into this computer's card reader, then press Enter."
PUT_BACK = "Put the card back into the Flipper, then press Enter."
# The sizes the stand-in card has, 64 gigabytes with 60.1 free, as bytes the way a card's makers count
CARD_BYTES = 64_000_000_000
CARD_FREE_BYTES = 60_100_000_000
CARD_SIZES = "64.0 gigabytes with 60.1 gigabytes free"


ASK_AGAIN = "Copy the voice onto it? [Y/n]"  # what is asked after an answer that is neither yes nor no


def is_confirm(question):
    """Whether question is the one about the card that was found, which ends in [Y/n], or the short
    one that is asked again."""
    return (question.startswith("Found the card") and question.endswith("[Y/n]")) or question == ASK_AGAIN


class Reader:
    """The computer's card reader and the drives mounted beside it, round a stand-in Flipper, and
    the user who moves the card when asked to. Asked to take the card out, the user does: it leaves
    the Flipper, whose storage commands then get the Flipper's out_reply, and it appears among the
    volumes as FLIPPER, holding what the card held, on the script's mount_looks-th look. Like macOS,
    the stand-in puts a 4 KB ._ file beside everything unpacked onto it. Asked to put the card back,
    the user does, and the Flipper's storage commands get out_reply for mounting more commands
    while it mounts the card. The question about the card that was found gets the next of confirm,
    and no answer once they are used up; without confirm, it gets Enter. The other questions get
    the next of answers. recreate: the eject makes a ._ file beside every file again, as a Mac that
    removed them may do. stays: the card stays in the Flipper. never_back: the card stays out. usage:
    what the computer says of the card's size, (size, free) in bytes, or an OSError to raise."""

    def __init__(self, root, flipper, mount_looks=1, mounting=3, recreate=False, stays=False, never_back=False,
                 confirm=None, usage=(CARD_BYTES, CARD_FREE_BYTES)):
        self.flipper = flipper
        self.confirm = None if confirm is None else list(confirm)
        self.usage = usage
        self.confirmations = []  # for each question about the card found: the question and what had happened by then
        self.drives = []
        for name in ("Backup", "Camera"):
            drive = os.path.join(root, name)
            os.makedirs(os.path.join(drive, "photos"))
            write(os.path.join(drive, "photos", "a.jpg"), b"x")
            self.drives.append(drive)
        self.volume = os.path.join(root, "FLIPPER")
        self.mount_looks = mount_looks
        self.mounting = mounting
        self.recreate = recreate
        self.stays = stays
        self.never_back = never_back
        self.looks = 0  # how often the script has looked at the volumes
        self.looks_before_enter = None  # and how often before the user pressed Enter to say the card was moved
        self.out = False  # the card has left the Flipper
        self.out_looks = 0  # the looks since then
        self.mounted = False
        self.ejected = []
        self.unpacked = 0
        self.made = []  # the ._ files made beside what was unpacked, relative to the volume
        self.recreated = []  # the ._ files the eject made again
        self.put_back = None  # the commands the Flipper had had when the user was asked to put the card back
        self.open_when_asked = []  # for each move of the card, whether each connection was open when it was asked

    def ask(self, question):
        """The user: Enter after moving the card as asked, else the next of answers."""
        asked.append(question)
        if question in (TAKE_OUT, PUT_BACK):
            self.open_when_asked.append([c.is_open for c in self.flipper.connections])
        if question == TAKE_OUT:
            self.looks_before_enter = self.looks
            if not self.stays:
                self.move_out()
            return ""
        if question == PUT_BACK:
            self.put_back = len(self.flipper.sent)
            if not self.never_back:
                self.move_back()
            return ""
        if is_confirm(question):
            self.confirmations.append(SimpleNamespace(
                question=question, unpacked=self.unpacked, ejected=len(self.ejected),
                marker_there=[n for n in os.listdir(self.volume) if n.startswith(".sonar-install-")],
                tree=volume_tree(self.volume),
            ))
            if len(self.confirmations) > 10:  # a script that never takes the answer is not asked for ever
                return None
            if self.confirm is None:
                return ""
            return self.confirm.pop(0) if self.confirm else None
        return answers.pop(0) if answers else None

    def disk_usage(self, volume):
        if isinstance(self.usage, Exception):
            raise self.usage
        size, free = self.usage
        return SimpleNamespace(total=size, used=size - free, free=free)

    def card_volumes(self):
        self.looks += 1
        if self.out and not self.mounted and not self.ejected:
            self.out_looks += 1
            self.mounted = self.out_looks >= self.mount_looks
        return self.drives + ([self.volume] if self.mounted else [])

    def move_out(self):
        f = self.flipper
        os.makedirs(self.volume)
        for path in sorted(f.dirs):
            if path.startswith("/ext/"):
                os.makedirs(card_path(self.volume, path), exist_ok=True)
        for path, data in f.files.items():
            if path.startswith("/ext/"):
                os.makedirs(os.path.dirname(card_path(self.volume, path)), exist_ok=True)
                write(card_path(self.volume, path), bytes(data))
        f.card_out = True
        self.out = True

    def unpack(self, pack, volume, progress=None):
        written = real_unpack(pack, volume, progress)
        self.unpacked += 1
        with tarfile.open(pack) as tar:
            for name in tar.getnames():
                folder, _, base = name.rpartition("/")
                relative = posixpath.join(folder, "._" + base)
                write(os.path.join(volume, *relative.split("/")), bytes(4096))
                self.made.append(relative)
        return written

    def eject(self, volume, say, ask):
        self.ejected.append(volume)
        if self.recreate:
            for here, _, names in os.walk(os.path.join(volume, "sr", "voices")):
                for name in sorted(names):
                    if not name.startswith("._"):
                        apple = os.path.join(here, "._" + name)
                        write(apple, bytes(4096))
                        self.recreated.append(os.path.relpath(apple, volume).replace(os.sep, "/"))
        self.mounted = False

    def move_back(self):
        f = self.flipper
        f.card_out = False
        f.mounting = self.mounting
        if not self.out:
            return
        f.files.clear()
        f.dirs.clear()
        f.dirs.add("/ext")
        for here, folders, names in os.walk(self.volume):
            relative = os.path.relpath(here, self.volume)
            base = "/ext" if relative == "." else "/ext/" + relative.replace(os.sep, "/")
            f.dirs.update(f"{base}/{folder}" for folder in folders)
            for name in names:
                with open(os.path.join(here, name), "rb") as file:
                    f.files[f"{base}/{name}"] = bytearray(file.read())
        self.out = False


@contextlib.contextmanager
def card_reader(root, flipper, **settings):
    """A Reader in place of this computer's volumes, its eject, the unpacking onto the card and the
    user who answers the questions."""
    reader = Reader(root, flipper, **settings)
    names = ("card_volumes", "eject", "unpack_to_card", "ask", "disk_usage")
    saved = [getattr(install, name) for name in names]
    for name, stand_in in zip(names, (reader.card_volumes, reader.eject, reader.unpack, reader.ask, reader.disk_usage)):
        setattr(install, name, stand_in)
    try:
        yield reader
    finally:
        for name, value in zip(names, saved):
            setattr(install, name, value)


@contextlib.contextmanager
def waiting(**seconds):
    """install's constants named in seconds, such as CARD_LOOK_SECONDS=0.2, for a with block."""
    saved = {name: getattr(install, name) for name in seconds}
    for name, value in seconds.items():
        setattr(install, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(install, name, value)


def collector(flipper):
    """say and the lines it was given, each with the number of commands the Flipper had had by then."""
    lines = []

    def say(line):
        lines.append((len(flipper.sent), line))

    return lines, say


def console_of(flipper):
    """A Storage on the stand-in's console."""
    plug(flipper)
    return fs.Storage(fc.open_cli(PORT))


def apple_files(flipper, under="/ext/sr/voices/heart/"):
    """The ._ files on the stand-in's card under a folder."""
    return sorted(p for p in flipper.files if p.startswith(under) and posixpath.basename(p).startswith("._"))


def line_with(lines, *words):
    """The first line, with the number of commands before it, that holds every one of words."""
    for mark, line in lines:
        if all(word.lower() in line.lower() for word in words):
            return mark, line
    return None


# describe: the Flipper's name, the firmware and its version
def parsed(reply):
    return install.read_info(SimpleNamespace(command=lambda line: reply.replace("\r\n", "\n").strip("\n")))


sonar_info = parsed(SONAR_DEV)
check(sonar_info["firmware.origin.fork"] == "Sonar" and sonar_info["firmware.commit.hash"] == "9149fe49",
      f"read_info gives the keys and values: {sorted(sonar_info)[:3]}")
check(sonar_info["firmware.origin.git"] == SONAR_GIT, f"a value with a colon in it is whole: {sonar_info['firmware.origin.git']}")
said = install.describe(sonar_info)
check("R0skie" in said and "Sonar" in said and "mntm-dev" in said and "9149fe49" in said and said.endswith("."),
      f"describe names Sonar, its version and, for a build not on a tag, its commit: {said}")
said = install.describe(parsed(SONAR_RELEASE))
check("Sonar" in said and "sonar-0.1.0" in said, f"describe names a Sonar release: {said}")
said = install.describe(parsed(MOMENTUM))
check("Momentum" in said and "mntm-012" in said and "Sonar" not in said, f"describe names Momentum: {said}")
said = install.describe(parsed(OFFICIAL))
check("official firmware" in said and "1.4.3" in said, f"describe names the official firmware: {said}")
said = install.describe({})
check(said.endswith(".") and "\n" not in said, f"describe of a reply without the keys is still a sentence: {said}")

# verify against a release.json of sonar-0.1.0, commit 9149fe493, API 87.3
release_info = parsed(SONAR_RELEASE)
check(install.verify(release_info, RELEASE) == [], f"a matching reply: {install.verify(release_info, RELEASE)}")


def differs(**changes):
    info = dict(release_info)
    info.update(changes)
    return install.verify(info, RELEASE)


found = differs(**{"firmware.version": "sonar-0.0.9"})
check(len(found) == 1 and "sonar-0.0.9" in found[0] and "sonar-0.1.0" in found[0], f"another version: {found}")
found = differs(**{"firmware.commit.hash": "86820a7d"})
check(len(found) == 1 and "86820a7d" in found[0] and "9149fe493" in found[0], f"another commit: {found}")
found = differs(**{"firmware.commit.dirty": "true"})
check(len(found) == 1 and "changes" in found[0], f"dirty: true: {found}")
found = differs(**{"firmware.origin.fork": "Momentum"})
check(len(found) == 1 and "Momentum" in found[0] and "Sonar" in found[0], f"another origin: {found}")
found = differs(**{"firmware.api.minor": "1"})
check(len(found) == 1 and "87.1" in found[0] and "87.3" in found[0], f"another API version: {found}")
check(all(line.endswith(".") and "\n" not in line for line in differs(**{"firmware.version": "x", "firmware.origin.fork": "y"})),
      "each difference is one sentence")
# The commits as prefixes: release.json carries 9 characters, the device prints 8
check(differs(**{"firmware.commit.hash": "9149FE49"}) == [], "the commit's case does not matter")
check(install.verify(release_info, dict(RELEASE, firmware_commit="9149fe49")) == [], "8 characters against 8")
check(install.verify(release_info, dict(RELEASE, firmware_commit="9149fe4")) == [], "7 characters are enough")
check(len(install.verify(release_info, dict(RELEASE, firmware_commit="9149fe"))) == 1, "6 are not")
check(install.verify(release_info, dict(RELEASE, firmware_commit="9149fe490")) == [],
      "a 9th character the device does not print cannot tell two commits apart")
check(len(install.verify(release_info, dict(RELEASE, firmware_commit="9149fe593"))) == 1, "a difference in the 8 it prints")
# Without release.json, the package's folder name: its commit, or its version
check(install.verify_package(sonar_info, "f7-update-mntm-claude-device-checks-2026-10-09-9149fe49") == [],
      "a build's package and the build it installed")
found = install.verify_package(sonar_info, "f7-update-mntm-screen-reader-86820a7d")
check(len(found) == 1 and "86820a7d" in found[0], f"a build's package and another build: {found}")
check(install.verify_package(parsed(OFFICIAL), "f7-update-1.4.3") == [], "the official package by its version")
found = install.verify_package(parsed(OFFICIAL), "f7-update-mntm-012")
check(len(found) == 1 and "mntm-012" in found[0], f"Momentum's package, and the official firmware still runs: {found}")

# The mute around the unpacking: the pack's megabytes times EXTRACT_SECONDS_PER_MB, rounded up
check(install.mute_seconds(116705280) == 1447, f"the heart pack of the spike: {install.mute_seconds(116705280)}")
check(install.mute_seconds(1048576) == fs.EXTRACT_SECONDS_PER_MB, "a megabyte")
check(install.mute_seconds(10000) == 1, f"a pack of a few kilobytes: {install.mute_seconds(10000)}")
check(install.mute_seconds(400 * 1048576) == 3600, "never more than the hour sr voice off takes")

with tempfile.TemporaryDirectory() as tmp:
    pack = os.path.join(tmp, "voice-heart-sonar-0.1.0.tar")
    clips = make_pack(pack)
    entries = 5 + len(clips)
    check(install.pack_entries(pack) == entries, f"the pack's entries: {install.pack_entries(pack)}")
    package_dir, tgz, package_files = make_package(tmp)
    release_json = os.path.join(tmp, "release.json")
    with open(release_json, "w") as f:
        json.dump(RELEASE, f)
    full_run = ["--package", tgz, "--voice", pack, "--release", release_json, "--yes"]
    mute = f"sr voice off {install.mute_seconds(os.path.getsize(pack))}"
    extract = 'storage extract "/ext/voice-heart-sonar-0.1.0.tar" "/ext"'
    remove_pack = 'storage remove "/ext/voice-heart-sonar-0.1.0.tar"'
    update = "update install /ext/update/f7-update-sonar-0.1.0/update.fuf"
    old = "/ext/update/f7-update-mntm-screen-reader-11111111"
    prune = ['storage list "/ext/update"', f'storage list "{old}"', f'storage remove "{old}/update.fuf"',
             f'storage remove "{old}"']

    # A whole run from Sonar
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    code, lines, err = run(flipper, full_run)
    check(code == 0, f"a whole run from Sonar ends with 0: {code}, {lines[-3:]}")
    expected = ["info device", "update backup /ext/backup-2026-10-11.tar", mute, extract, "sr voice on", remove_pack,
                update, "info device", "info device"] + prune
    check(main_commands(flipper.sent) == expected, f"the run's commands in order: {main_commands(flipper.sent)}")
    check(not forbidden(flipper.sent), f"no loader, power, input, sysctl or sr voice use: {forbidden(flipper.sent)}")
    order = flipper.sent
    pack_writes = [i for i, c in enumerate(order) if c.startswith('storage write_chunk "/ext/voice-heart')]
    package_writes = [i for i, c in enumerate(order) if c.startswith('storage write_chunk "/ext/update/f7-update-sonar')]
    check(pack_writes and order.index("update backup /ext/backup-2026-10-11.tar") < pack_writes[0]
          and pack_writes[-1] < order.index(mute), "the pack is sent after the backup and before the mute")
    check(package_writes and order.index(remove_pack) < package_writes[0] and package_writes[-1] < order.index(update),
          "the package is sent after the voice and before update install")
    check(all(bytes(flipper.files[f"/ext/{name}"]) == data for name, data in clips.items()),
          "the voice is on the card, unpacked from the pack's bytes")
    check("/ext/voice-heart-sonar-0.1.0.tar" not in flipper.files, "and the pack's file is gone")
    check(all(bytes(flipper.files[f"/ext/update/f7-update-sonar-0.1.0/{n}"]) == d for n, d in package_files.items()),
          "the package's files are on the card")
    check(old not in flipper.dirs and all(f"/ext/update/{n}" in flipper.dirs for n in OLD_PACKAGES[:2])
          and "/ext/update/f7-update-sonar-0.1.0" in flipper.dirs,
          "the older Sonar package went; the official and Momentum packages and the new one stay")
    check(no_traceback(lines, err) and not err, f"nothing on stderr: {err!r}")
    check(any("Sonar" in line and "mntm-dev" in line for line in lines[:4]), f"the first lines say what was found: {lines[:4]}")
    check(any("sonar-0.1.0" in line and "Sonar" in line for line in lines), "and what runs after the update")
    check(lines[-1].startswith("Done"), f"the last line says it is done: {lines[-1]}")
    # The line after the send says that the pack is not unpacked yet, so that it is not taken for
    # the line after which a run again may leave out --voice, which comes after the unpacking
    sent_line = "The voice pack is sent; the Flipper unpacks it next."
    unpacked = [i for i, line in enumerate(lines) if line.startswith("The voice pack is unpacked")]
    check(sent_line in lines and unpacked and lines.index(sent_line) < unpacked[0]
          and not [line for line in lines if "voice pack is on the card" in line],
          f"the send ends with a line that says the unpacking comes next: {[l for l in lines if 'voice pack' in l]}")
    check(all("\r" not in line and line.strip() for line in lines), "plain lines, no carriage returns, none empty")
    check(all(c.is_open is False for c in flipper.connections), "every connection was closed")
    check(all(c.events[:3] == [("dtr", True), ("dtr", False), ("dtr", True)] for c in flipper.connections),
          f"every open dropped DTR and raised it again before its first command: {[c.events[:4] for c in flipper.connections]}")

    # From the official firmware and from Momentum: the same, without any sr command
    for name, reply in (("official 1.4.3", OFFICIAL), ("Momentum mntm-012", MOMENTUM)):
        flipper = Flipper(reply, after=SONAR_RELEASE)
        code, lines, err = run(flipper, full_run)
        check(code == 0, f"a whole run from {name}: {code}, {lines[-2:]}")
        check(not [c for c in flipper.sent if c.startswith("sr ")], f"no sr command from {name}: {flipper.sent}")
        check(main_commands(flipper.sent) == [c for c in expected if not c.startswith("sr ")],
              f"the run's commands from {name}: {main_commands(flipper.sent)}")
        check(not forbidden(flipper.sent) and no_traceback(lines, err), f"nothing forbidden from {name}")

    # Progress lines on a long step: plain lines, at most one a PROGRESS_SECONDS
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    code, lines, err = run(flipper, full_run, progress=0)
    check(code == 0 and any("percent" in line for line in lines), f"progress lines: {[x for x in lines if 'percent' in x][:3]}")
    check(all("\r" not in line for line in lines), "no carriage returns in them")

    # A package folder instead of the .tgz, and no release.json: the commit from the package's name
    dev_root = os.path.join(tmp, "dev")
    dev_dir, _, _ = make_package(dev_root, name="f7-update-mntm-claude-device-checks-2026-10-09-9149fe49")
    flipper = Flipper(SONAR_DEV)
    code, lines, err = run(flipper, ["--package", dev_dir, "--yes"])
    check(code == 0, f"a package folder, no release.json, no voice: {code}, {lines[-2:]}")
    check("update install /ext/update/f7-update-mntm-claude-device-checks-2026-10-09-9149fe49/update.fuf" in flipper.sent,
          "the folder's name is the package's name on the card")

    # The Flipper comes back first in the updater's last boot, then in a normal one
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.booting = [SONAR_RELEASE.replace("system.boot                   : 0", "system.boot                   : 4")]
    code, lines, err = run(flipper, full_run)
    check(code == 0 and main_commands(flipper.sent).count("info device") == 4,
          f"a console in the post-update boot is not taken for the end of the update: {code}, {main_commands(flipper.sent)}")

    # A backup of the day is never overwritten
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.files["/ext/backup-2026-10-11.tar"] = bytearray(b"the backup from before Sonar")
    code, lines, err = run(flipper, full_run)
    check(code == 0 and "update backup /ext/backup-2026-10-11-2.tar" in flipper.sent,
          f"the second backup of a day gets -2: {main_commands(flipper.sent)[:2]}")
    check(bytes(flipper.files["/ext/backup-2026-10-11.tar"]) == b"the backup from before Sonar", "the first is kept")

    # --restore with a backup on this computer: sent, then update restore after the update
    local_backup = os.path.join(tmp, "backup-stock-1.4.3.tar")
    write(local_backup, b"a backup of official /int")
    flipper = Flipper(SONAR_DEV, after=OFFICIAL)
    official_root = os.path.join(tmp, "official")
    official_dir, _, _ = make_package(official_root, name="f7-update-1.4.3")
    code, lines, err = run(flipper, ["--package", official_dir, "--restore", local_backup, "--yes"])
    check(code == 0, f"back to the official firmware with its backup: {code}, {lines[-3:]}")
    commands = main_commands(flipper.sent)
    check("update restore /ext/backup-stock-1.4.3.tar" in commands
          and commands.index("update restore /ext/backup-stock-1.4.3.tar") > commands.index("update install /ext/update/f7-update-1.4.3/update.fuf"),
          f"update restore after the update: {commands}")
    check(any("Left and Back" in line for line in lines), "and the user is told to restart the Flipper")
    # --restore with a backup on the card
    flipper = Flipper(OFFICIAL)
    flipper.files["/ext/backup-2026-10-01.tar"] = bytearray(b"an older backup")
    code, lines, err = run(flipper, ["--restore", "/ext/backup-2026-10-01.tar", "--yes"])
    check(code == 0 and main_commands(flipper.sent) == ["info device", "update backup /ext/backup-2026-10-11.tar",
                                                         "update restore /ext/backup-2026-10-01.tar"],
          f"a restore alone: {code}, {main_commands(flipper.sent)}")
    flipper = Flipper(OFFICIAL)
    code, lines, err = run(flipper, ["--restore", "/ext/no-such-backup.tar", "--yes"])
    check(code == 1 and "/ext/no-such-backup.tar" in lines[-1] and not [c for c in flipper.sent if "restore" in c],
          f"a backup that is not on the card: {lines[-1:]}")

    # Without --yes, one question before anything changes
    for answer in ("n", None):
        answers[:] = [answer]
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        code, lines, err = run(flipper, full_run[:-1])
        check(code == 1 and flipper.sent == ["info device"], f"the answer {answer!r} changes nothing: {code}, {flipper.sent}")
        check(lines and "nothing was changed" in lines[-1].lower(), f"and says so: {lines[-1:]}")
    answers[:] = [""]
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    code, lines, err = run(flipper, full_run[:-1])
    check(code == 0 and update in flipper.sent, f"Enter alone means yes: {code}")

    # The wait for the port, by itself
    flipper = Flipper(SONAR_RELEASE)
    flipper.absent = 5
    plug(flipper)
    install.PROGRESS_SECONDS = 0
    said = []
    console = install.wait_for_device(5, said.append)
    check(isinstance(console, fs.Storage) and flipper.absent == 0, "the wait returns once the port is back")
    check(console.command("info device").startswith("format.major"), "with a console in step")
    check(any("back" in line.lower() for line in said), f"and says the Flipper is back: {said}")
    console.ser.close()
    flipper = Flipper(SONAR_RELEASE)
    flipper.updated = flipper.never_back = True
    plug(flipper)
    said = []
    started = time.monotonic()
    try:
        install.wait_for_device(0.3, said.append)
        error = None
    except install.InstallError as e:
        error = e
    check(error is not None and time.monotonic() - started >= 0.3, f"a port that never comes back: {error!r}")
    check(error is not None and "\n" not in str(error) and str(error).endswith("."), f"one sentence: {error}")
    check(any("Still waiting" in line for line in said), f"it says it is still waiting meanwhile: {said[-2:]}")
    # A Flipper with a PIN locks itself again when it restarts, which turns its console off: the
    # first line says so, and the sentence at the limit names the lock beside an update that is
    # still running, and does not send the user through the whole install again
    check(said and "Flipper with a PIN asks for it again when it restarts" in said[0] and "waits until it is entered" in said[0],
          f"the wait's first line says that a PIN is asked for again and waited for: {said[:1]}")
    said = str(error)
    check(error is not None and "still updating" in said and "locked with its PIN, enter the PIN" in said
          and "may be installed already" in said and "run this script again" in said and "--voice" not in said,
          f"the sentence at the limit names the PIN lock and says the firmware may be installed already: {error}")
    try:
        install.wait_for_device(0.1, [].append, voice=True)
        error = None
    except install.InstallError as e:
        error = e
    said = str(error)
    check(error is not None and "leave out --voice, since the voice is on the card already" in said
          and len(re.findall(r"[.?!](?=\s|$)", said)) == 1,
          f"after a voice pack, a run again may leave out --voice, in the same one sentence: {error}")
    # A port named with --port is waited for by its name, without the port list
    flipper = Flipper(SONAR_RELEASE)
    plug(flipper)
    fc.flipper_ports = lambda ports=None: [][0]  # the list must not be asked
    console = install.wait_for_device(5, [].append, port=PORT)
    check(isinstance(console, fs.Storage), "a named port is waited for by its name")
    console.ser.close()
    flipper.updated = flipper.never_back = True
    try:
        install.wait_for_device(0.1, [].append, port=PORT)
        error = None
    except install.InstallError as e:
        error = e
    check(error is not None and "did not come back" in str(error), f"and one that cannot be opened is waited for: {error}")
    # And in a whole run: one sentence after the time-out, and exit 1
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.never_back = True
    code, lines, err = run(flipper, full_run, wait=0.2)
    check(code == 1 and "did not come back" in lines[-1] and no_traceback(lines, err),
          f"a whole run whose Flipper never comes back: {code}, {lines[-1:]}")
    check("PIN" in lines[-1] and "leave out --voice" in lines[-1], f"after its voice pack, the PIN and --voice are named: {lines[-1:]}")
    check(main_commands(flipper.sent)[-1] == update, f"nothing after update install: {main_commands(flipper.sent)[-2:]}")

    # A storage error in an upload: the step and the device's sentence, exit 1, no traceback
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.full_under = "/ext/update/f7-update-sonar-0.1.0/"
    code, lines, err = run(flipper, full_run)
    check(code == 1, f"a full card in the package's upload ends with 1: {code}")
    check("update package" in lines[-1] and "internal error" in lines[-1], f"the step and the device's sentence: {lines[-1]}")
    check(no_traceback(lines, err) and not err, f"no traceback: {err!r}")
    check(update not in flipper.sent, "and no update was started")
    flipper = Flipper(OFFICIAL, after=SONAR_RELEASE)
    flipper.full_under = "/ext/voice-heart"
    code, lines, err = run(flipper, full_run)
    check(code == 1 and "voice pack" in lines[-1] and "internal error" in lines[-1] and no_traceback(lines, err),
          f"a full card in the pack's upload: {lines[-1:]}")
    check(not [c for c in flipper.sent if c.startswith("storage extract")], "and nothing was unpacked")

    # An unpacking that fails: from Sonar the voice is turned on again before the run ends
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.extract_fails = True
    code, lines, err = run(flipper, full_run)
    check(code == 1 and "unpack" in lines[-1] and no_traceback(lines, err), f"a failed unpacking: {lines[-1:]}")
    commands = main_commands(flipper.sent)
    check(commands[-2:] == [extract, "sr voice on"], f"sr voice on after it: {commands[-3:]}")

    # The Flipper refuses the package
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.update_reply = UPDATE_REFUSED
    code, lines, err = run(flipper, full_run)
    check(code == 1 and "update" in lines[-1] and "Invalid manifest data" in lines[-1] and no_traceback(lines, err),
          f"a refused package: {lines[-1:]}")

    # The update ran, but the Flipper runs another firmware: the differences, exit 1, no prune
    flipper = Flipper(SONAR_DEV, after=SONAR_DEV)
    code, lines, err = run(flipper, full_run)
    check(code == 1 and any("mntm-dev" in line and "sonar-0.1.0" in line for line in lines), f"another version: {lines[-3:]}")
    check(not [c for c in flipper.sent if c.startswith("storage list")] and old in flipper.dirs,
          "and the older packages stay, since the new one may be needed again")

    # The backup fails
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.backup_result = "FAIL"
    code, lines, err = run(flipper, full_run)
    check(code == 1 and "back up" in lines[-1] and main_commands(flipper.sent)[-1].startswith("update backup"),
          f"a failed backup stops the run: {lines[-1:]}")
    # A full card fails at update backup, which answers Result: FAIL: the one sentence adds to check
    # the card's free space, and only for this step
    said = lines[-1] if lines else ""
    check(said == "Could not back up the Flipper's internal storage to /ext/backup-2026-10-11.tar: the Flipper said "
                  "that it failed; a full card can cause this, so check the card's free space."
          and len(re.findall(r"[.?!](?=\s|$)", said)) == 1 and no_traceback(lines, err),
          f"a failed backup adds that a full card can cause it: {said}")
    flipper = Flipper(OFFICIAL)
    flipper.files["/ext/backup-2026-10-01.tar"] = bytearray(b"an older backup")
    flipper.restore_result = "FAIL"
    code, lines, err = run(flipper, ["--restore", "/ext/backup-2026-10-01.tar", "--yes"])
    said = lines[-1] if lines else ""
    check(code == 1 and said.startswith("Could not restore the internal storage from /ext/backup-2026-10-01.tar: ")
          and said.endswith("the Flipper said that it failed.") and "full" not in said and "free space" not in said,
          f"a failed restore does not add the full card: {said}")
    # No card in the Flipper or one it cannot read: the first card command, the stat in the backup
    # step, gets the device's bare words, and the sentence adds what to check. A stat never fails
    # because a card is full: access denied, which the device also gives for removing a folder that
    # is not empty, gets no advice, as any other answer
    no_card = "check that a microSD card, formatted on the Flipper, is in the Flipper"
    for reply, advice in ((CARD_OUT, no_card), (NOT_READY, no_card), (DENIED, None),
                          ("Storage error: invalid parameter\r\n", None)):
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        flipper.card_out = True
        flipper.out_reply = reply
        code, lines, err = run(flipper, full_run)
        said = lines[-1] if lines else ""
        device = reply.strip().removeprefix("Storage error: ")
        check(code == 1 and said.startswith(f"Could not back up the Flipper's internal storage: {device}: /ext/backup-")
              and (said.endswith(f"; {advice}.") if advice else "microSD" not in said and "full" not in said
                   and "free space" not in said)
              and len(re.findall(r"[.?!](?=\s|$)", said)) == 1 and main_commands(flipper.sent) == ["info device"]
              and no_traceback(lines, err),
              f"the first card command's {device!r}: the sentence adds {advice!r}: {said}")

    # An application is open on the Flipper: the update commands are refused, and the sentence says
    # to press Back to the home screen and then to run the script again: until it says Home screen
    # when Sonar runs, a few times from other firmware, which says nothing
    def home_screen_advice(line, sonar):
        said = ("press Back on the Flipper until it says Home screen" if sonar
                else "press Back on the Flipper a few times to reach the home screen")
        return ("application is open" in line and said in line and ("Home screen" in line) == sonar
                and "run this script again" in line and "free space" not in line
                and len(re.findall(r"[.?!](?=\s|$)", line)) == 1)

    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.app_open = "backup"
    code, lines, err = run(flipper, full_run)
    check(code == 1 and "back up" in lines[-1] and home_screen_advice(lines[-1], True) and no_traceback(lines, err),
          f"update backup refused while an app is open on Sonar: {lines[-1:]}")
    check(not [c for c in flipper.sent if c.startswith("storage write_chunk")], "and nothing was sent")
    flipper = Flipper(MOMENTUM, after=SONAR_RELEASE)
    flipper.app_open = "backup"
    code, lines, err = run(flipper, full_run)
    check(code == 1 and "back up" in lines[-1] and home_screen_advice(lines[-1], False),
          f"update backup refused while an app is open on Momentum, which says nothing: {lines[-1:]}")
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.app_open = "install"
    code, lines, err = run(flipper, full_run)
    check(code == 1 and "start the update" in lines[-1] and home_screen_advice(lines[-1], True),
          f"update install refused while an app is open on Sonar: {lines[-1:]}")
    flipper = Flipper(OFFICIAL, after=SONAR_RELEASE)
    flipper.app_open = "install"
    code, lines, err = run(flipper, full_run)
    check(code == 1 and "start the update" in lines[-1] and home_screen_advice(lines[-1], False),
          f"update install refused while an app is open on the official firmware: {lines[-1:]}")
    flipper = Flipper(OFFICIAL)
    flipper.files["/ext/backup-2026-10-01.tar"] = bytearray(b"an older backup")
    flipper.app_open = "restore"
    code, lines, err = run(flipper, ["--restore", "/ext/backup-2026-10-01.tar", "--yes"])
    check(code == 1 and "restore" in lines[-1] and home_screen_advice(lines[-1], False),
          f"update restore refused while an app is open on the official firmware: {lines[-1:]}")
    flipper = Flipper(OFFICIAL, after=SONAR_RELEASE)
    flipper.files["/ext/backup-2026-10-01.tar"] = bytearray(b"an older backup")
    flipper.app_open = "restore"
    code, lines, err = run(flipper, ["--package", tgz, "--restore", "/ext/backup-2026-10-01.tar", "--yes"])
    check(code == 1 and "restore" in lines[-1] and update in flipper.sent and home_screen_advice(lines[-1], True),
          f"update restore after the update to Sonar goes by the firmware that runs then: {lines[-1:]}")

    # Files that are not what they should be: refused before the Flipper is touched
    no_fuf_root = os.path.join(tmp, "nofuf")
    no_fuf_dir, no_fuf_tgz, _ = make_package(no_fuf_root, fuf=False)
    flipper = Flipper(SONAR_DEV)
    code, lines, err = run(flipper, ["--package", no_fuf_tgz, "--yes"])
    check(code == 1 and "update.fuf" in lines[-1] and not flipper.sent, f"a package without update.fuf: {lines[-1:]}")
    evil = os.path.join(tmp, "evil.tgz")
    with tarfile.open(evil, "w:gz") as tar:
        entry = tarfile.TarInfo("../outside.txt")
        entry.size = 1
        tar.addfile(entry, io.BytesIO(b"x"))
    code, lines, err = run(flipper, ["--package", evil, "--yes"])
    check(code == 1 and "evil.tgz" in lines[-1] and "outside.txt" in lines[-1] and not flipper.sent,
          f"a package with a path out of its folder: {lines[-1:]}")
    # Python 3.10 before 3.10.12 has no tar filters: the script's own check stands in for them
    check(install.TAR_FILTERS, "this Python has the filters")
    install.TAR_FILTERS = False
    try:
        with tempfile.TemporaryDirectory() as work:
            unpacked = install.package_folder(tgz, work)
            check(sorted(os.listdir(unpacked)) == sorted(package_files), f"a .tgz without the filters: {os.listdir(unpacked)}")
        with tempfile.TemporaryDirectory() as work:
            try:
                install.package_folder(evil, work)
                error = None
            except install.InstallError as e:
                error = e
            check(error is not None and "../outside.txt" in str(error), f"and the path out of its folder without them: {error}")
    finally:
        install.TAR_FILTERS = True
    code, lines, err = run(flipper, ["--package", os.path.join(tmp, "no-such.tgz"), "--yes"])
    check(code == 1 and "no-such.tgz" in lines[-1] and not flipper.sent, f"a package that is not there: {lines[-1:]}")
    stray = os.path.join(tmp, "voice-stray.tar")
    make_pack(stray, extra={"apps/evil.fap": b"x"})
    code, lines, err = run(flipper, ["--voice", stray, "--yes"])
    check(code == 1 and "apps/evil.fap" in lines[-1] and not flipper.sent, f"a pack with a file outside sr: {lines[-1:]}")
    code, lines, err = run(flipper, ["--voice", tgz, "--yes"])
    check(code == 1 and "flipper-z-f7-update-sonar-0.1.0.tgz" in lines[-1] and not flipper.sent,
          f"an update package given as a voice pack: {lines[-1:]}")
    other = os.path.join(tmp, "release-other.json")
    with open(other, "w") as f:
        json.dump(dict(RELEASE, firmware_version="sonar-0.2.0"), f)
    code, lines, err = run(flipper, ["--package", tgz, "--release", other, "--yes"])
    check(code == 1 and "sonar-0.2.0" in lines[-1] and not flipper.sent, f"a release.json of another release: {lines[-1:]}")
    broken = os.path.join(tmp, "broken.json")
    write(broken, b"{ not json")
    code, lines, err = run(flipper, ["--package", tgz, "--release", broken, "--yes"])
    check(code == 1 and "broken.json" in lines[-1] and not flipper.sent and no_traceback(lines, err),
          f"a release.json that is not JSON: {lines[-1:]}")
    code, lines, err = run(flipper, ["--yes"])
    check(code == 1 and "--package" in lines[-1] and not flipper.sent, f"nothing to do: {lines[-1:]}")

    # No Flipper at all: flipper_cli's sentence, which names the PIN lock
    flipper = Flipper(SONAR_DEV)
    flipper.updated = flipper.never_back = True
    code, lines, err = run(flipper, full_run)
    check(code == 1 and lines and lines[-1] == "No Flipper serial port found; check that the Flipper is plugged in, "
          "unlocked, not in the updater and not used by qFlipper, or name its port with --port.", f"no port: {lines[-1:]}")
    check(no_traceback(lines, err) and not err, f"on stdout, without a traceback: {err!r}")

    # A cable pulled in the middle of a step: the connection was lost, in one sentence
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    original = Connection.handle

    def pulled(self, command):
        if command.startswith("storage extract"):
            self.flipper.sent.append(command)
            self.gone = True
            self.out += f"{command}\r\nUnpacking to /ext\r\n".encode()
            return
        original(self, command)

    Connection.handle = pulled
    try:
        code, lines, err = run(flipper, full_run)
    finally:
        Connection.handle = original
    check(code == 1 and "unpack" in lines[-1] and "connection was lost" in lines[-1] and no_traceback(lines, err),
          f"a cable pulled during the unpacking: {lines[-1:]}")
    check(main_commands(flipper.sent)[-1] == extract, "and nothing is sent after it")

    # A console that gives its prompt on the open and then finishes no command, as one that a run
    # stopped with Ctrl-C left in the middle of a write_chunk: the first command's sentence ends
    # with open_cli's advice, to restart the Flipper, and to run the script again
    restart = "restart the Flipper by holding Left and Back together for five seconds, then run this script again"
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    flipper.silent_opens = 1
    saved_idle = fs.IDLE_SECONDS
    fs.IDLE_SECONDS = 0.2  # the quiet that counts as a lost connection, 30 seconds on the device
    try:
        code, lines, err = run(flipper, full_run)
    finally:
        fs.IDLE_SECONDS = saved_idle
    check(code == 1 and flipper.sent == ["info device"] and lines[-1].startswith("Could not read the Flipper's device information")
          and "connection was lost" in lines[-1] and lines[-1].endswith(f"; {restart}.") and no_traceback(lines, err),
          f"a console that answers nothing after its prompt: the sentence says to restart the Flipper: {code}, {lines[-1:]}")
    check(flipper.connections and flipper.connections[0].events[:3] == [("dtr", True), ("dtr", False), ("dtr", True)]
          and not flipper.connections[0].is_open, "the console was opened with DTR dropped and raised, and is closed")
    # The first command takes longer than its limit, or the Flipper's own error, read by read_first_info
    for raised, advised in (("the Flipper had not finished info device after 30 seconds", True),
                            ("the connection was lost: [Errno 6] Device not configured; check that the Flipper is still "
                             "plugged in", True),
                            ("the console cannot take a quote or a control character in a path: 'x'", False)):
        def stuck(line, timeout=30, raised=raised):
            raise fs.StorageError(raised)

        try:
            install.read_first_info(SimpleNamespace(command=stuck))
            error = None
        except install.InstallError as e:
            error = e
        said = str(error)
        check(error is not None and said.startswith("Could not read the Flipper's device information: " + raised)
              and (f"; {restart}." in said) == advised and len(re.findall(r"[.?!](?=\s|$)", said)) == 1,
              f"the first command's {raised[:30]!r}: the advice to restart only for a lost or stuck console: {error}")

    # Stopped with Ctrl-C: one sentence that says a run again starts over, and to restart the
    # Flipper the same way if it does not answer then
    flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
    saved_ask = install.ask
    install.ask = lambda question: (_ for _ in ()).throw(KeyboardInterrupt())
    try:
        code, lines, err = run(flipper, full_run[:-1])
    finally:
        install.ask = saved_ask
    said = lines[-1] if lines else ""
    check(code == 1 and said.startswith("Stopped before the install was done") and "starts it over" in said
          and "if the Flipper does not answer" in said and restart in said
          and len(re.findall(r"[.?!](?=\s|$)", said)) == 1 and no_traceback(lines, err),
          f"Ctrl-C: one sentence that says to restart the Flipper if it does not answer on the next run: {code}, {said}")

    # The card reader way: the volumes, and the card among them by its marker
    marker_a, marker_b = ".sonar-install-11111111", ".sonar-install-22222222"
    with tempfile.TemporaryDirectory() as drives:
        backup_drive, card_drive, camera_drive = (os.path.join(drives, n) for n in ("Backup", "FLIPPER", "Camera"))
        for drive in (backup_drive, card_drive, camera_drive):
            os.mkdir(drive)
        write(os.path.join(backup_drive, marker_a), b"")  # the marker of another install
        write(os.path.join(card_drive, marker_b), b"")
        os.mkdir(os.path.join(camera_drive, marker_b))  # a folder of that name is not a marker
        check(install.find_card(marker_b, [backup_drive, card_drive, camera_drive]) == card_drive,
              "find_card finds the volume that holds the marker and ignores the others")
        check(install.find_card(".sonar-install-33333333", [backup_drive, card_drive, camera_drive]) is None,
              "and gives None when no volume holds it")
        check(install.find_card(marker_b, [backup_drive, os.path.join(drives, "gone"), camera_drive]) is None,
              "a volume that is not there is skipped")
        check(install.find_card(marker_b, []) is None, "no volumes at all")
    check(install.volume_patterns("darwin", "robin") == ["/Volumes/*"], f"macOS: {install.volume_patterns('darwin', 'robin')}")
    check(install.volume_patterns("linux", "robin") == ["/media/robin/*", "/run/media/robin/*"],
          f"Linux: {install.volume_patterns('linux', 'robin')}")
    letters = install.volume_patterns("win32", "robin")
    check(len(letters) == 23 and letters[0] == "D:\\" and letters[-1] == "Z:\\", f"Windows: the drive letters D to Z: {letters[:2]}")
    volumes = install.card_volumes()
    check(isinstance(volumes, list) and all(os.path.isdir(v) for v in volumes), f"card_volumes of this computer: {volumes}")

    # Real paths decide whether an entry lands inside the volume, Windows names included
    check(install.lands_inside("C:\\card", "sr\\voices\\a.raw", ntpath) and install.lands_inside("C:\\card", "sr/voices/a.raw", ntpath),
          "on Windows both slashes name a path inside")
    for name in ("..\\outside.raw", "sr\\..\\..\\x", "C:\\other\\x.raw", "D:\\x.raw", "\\\\server\\share\\x", "\\x"):
        check(not install.lands_inside("C:\\card", name, ntpath), f"on Windows {name} leaves the volume")

    # unpack_to_card: the pack's entries in the pack's order, folders from the folder entries
    written_order = []
    with tempfile.TemporaryDirectory() as parent, tempfile.TemporaryDirectory() as elsewhere:
        card = os.path.join(parent, "card")  # a folder of its own, so that a name that leaves it lands in parent
        os.makedirs(os.path.join(card, "sr", "voices", "heart", "3f"))
        write(os.path.join(card, "sr", "voices", "heart", "3f", "hello.raw"), b"an older clip")
        write(os.path.join(card, "sr", "voices", "heart", "keep.raw"), b"kept")
        install.open = lambda path, mode="r", *a, **k: (written_order.append(path), open(path, mode, *a, **k))[1]
        try:
            written = install.unpack_to_card(pack, card)
        finally:
            del install.open
        check(written == len(clips), f"unpack_to_card returns the files written: {written}")
        check(written_order == [os.path.join(card, *name.split("/")) for name in clips],
              f"the files are written in the pack's order, which is not the sorted order: {written_order}")
        check(all(open(os.path.join(card, *name.split("/")), "rb").read() == data for name, data in clips.items()),
              "with the pack's bytes, over a clip that was there")
        check(open(os.path.join(card, "sr", "voices", "heart", "keep.raw"), "rb").read() == b"kept", "and a file that was there stays")
        empty_folder = os.path.join(tmp, "voice-empty-folder.tar")
        with tarfile.open(empty_folder, "w", format=tarfile.USTAR_FORMAT) as tar:
            for name in ("sr", "sr/voices", "sr/voices/heart", "sr/voices/heart/ff"):
                tar.addfile(folder_entry(name))
        with tempfile.TemporaryDirectory() as bare:
            check(install.unpack_to_card(empty_folder, bare) == 0 and os.path.isdir(os.path.join(bare, "sr", "voices", "heart", "ff")),
                  "a folder entry makes the folder")
        # An entry that leaves the volume is refused, and then nothing at all is written
        outside = os.path.join(elsewhere, "absolute.raw")
        for name in ("../outside.raw", outside, "sr/../../outside.raw", "sr/voices/../../../x.raw"):
            bad = os.path.join(tmp, "voice-bad.tar")
            with tarfile.open(bad, "w", format=tarfile.GNU_FORMAT) as tar:
                for good in ("sr", "sr/ok.raw"):
                    entry = tarfile.TarInfo(good)
                    if good == "sr":
                        entry.type = tarfile.DIRTYPE
                    else:
                        entry.size = 1
                    tar.addfile(entry, io.BytesIO(b"x") if entry.size else None)
                entry = tarfile.TarInfo(name)
                entry.size = 1
                tar.addfile(entry, io.BytesIO(b"x"))
            before = sorted(os.listdir(card))
            try:
                install.unpack_to_card(bad, card)
                error = None
            except install.InstallError as e:
                error = e
            check(error is not None and name in str(error) and "\n" not in str(error), f"{name} leaves the volume: {error}")
            check(sorted(os.listdir(card)) == before and not os.path.exists(os.path.join(card, "sr", "ok.raw"))
                  and os.listdir(parent) == ["card"] and not os.path.exists(outside),
                  f"and nothing was written for {name}")
        link = os.path.join(tmp, "voice-link.tar")
        with tarfile.open(link, "w", format=tarfile.USTAR_FORMAT) as tar:
            entry = tarfile.TarInfo("sr/link")
            entry.type = tarfile.SYMTYPE
            entry.linkname = "/etc"
            tar.addfile(entry)
        try:
            install.unpack_to_card(link, card)
            error = None
        except install.InstallError as e:
            error = e
        check(error is not None and "sr/link" in str(error), f"a link is refused: {error}")
        try:
            os.symlink(elsewhere, os.path.join(card, "slip"))
        except (OSError, NotImplementedError):
            pass  # no symbolic links here
        else:
            through = os.path.join(tmp, "voice-through.tar")
            with tarfile.open(through, "w", format=tarfile.USTAR_FORMAT) as tar:
                entry = tarfile.TarInfo("slip/escape.raw")
                entry.size = 1
                tar.addfile(entry, io.BytesIO(b"x"))
            try:
                install.unpack_to_card(through, card)
                error = None
            except install.InstallError as e:
                error = e
            check(error is not None and "slip/escape.raw" in str(error) and not os.listdir(elsewhere),
                  f"a path through a link that leaves the volume is refused: {error}")
        # A card that refuses the write: the sentence names the lock of the adapter
        install.open = lambda path, mode="r", *a, **k: (_ for _ in ()).throw(OSError(errno.EROFS, "Read-only file system", path))
        try:
            install.unpack_to_card(pack, card)
            error = None
        except install.InstallError as e:
            error = e
        finally:
            del install.open
        check(error is not None and "Read-only" in str(error) and "lock" in str(error) and "\n" not in str(error),
              f"a card mounted read-only: {error}")
        not_a_pack = os.path.join(tmp, "not-a-pack.tar")
        write(not_a_pack, b"this is not a tar file" * 100)
        try:
            install.unpack_to_card(not_a_pack, card)
            error = None
        except install.InstallError as e:
            error = e
        check(error is not None and "not-a-pack.tar" in str(error), f"a file that is not a tar: {error}")

    # remove_appledouble: every ._ file under sr/voices/<set>/ and nothing else
    with tempfile.TemporaryDirectory() as card:
        inside = ["sr/voices/heart/._voice.txt", "sr/voices/heart/3f/._hello.raw", "sr/voices/heart/a0/._world.raw",
                  "sr/voices/heart/._3f", "sr/voices/heart/3f/deeper/._x.raw"]
        outside_set = ["._sr", "sr/._voices", "sr/voices/._heart", "sr/voices/samantha/3f/._x.raw",
                       "sr/voices/heart/3f/.hidden", "sr/voices/heart/3f/hello._raw", "sr/voices/heart/3f/hello.raw",
                       "sr/voices/heart/voice.txt", "sr/voices/hearts/._x.raw"]
        for name in inside + outside_set:
            os.makedirs(os.path.dirname(os.path.join(card, *name.split("/"))), exist_ok=True)
            write(os.path.join(card, *name.split("/")), b"x")
        removed = install.remove_appledouble(card, "heart")
        check(removed == len(inside), f"remove_appledouble counts the files it removed: {removed}")
        check(not any(os.path.exists(os.path.join(card, *n.split("/"))) for n in inside), "every ._ file under the set is gone")
        check(all(os.path.exists(os.path.join(card, *n.split("/"))) for n in outside_set),
              "and nothing else: not the ones beside the set's folder, in other sets, nor files like them")
        check(install.remove_appledouble(card, "heart") == 0, "again: none")
        check(install.remove_appledouble(card, "no-such-set") == 0, "a set that is not on the card: none")
        if hasattr(os, "geteuid") and os.geteuid() != 0:
            locked = os.path.join(card, "sr", "voices", "heart", "a0")
            write(os.path.join(locked, "._stuck"), b"x")
            os.chmod(locked, 0o555)
            try:
                check(install.remove_appledouble(card, "heart") == 0, "a ._ file that cannot be removed is not counted, and is no error")
            finally:
                os.chmod(locked, 0o755)

    # eject: diskutil on a Mac, the user elsewhere or when diskutil fails
    saved_run, saved_platform = subprocess.run, install.PLATFORM
    calls, spoken, questions = [], [], []

    def eject_with(platform, outcome):
        calls.clear()
        spoken.clear()
        questions.clear()
        install.PLATFORM = platform

        def fake_run(argv, **kwargs):
            calls.append(argv)
            if isinstance(outcome, Exception):
                raise outcome
            return subprocess.CompletedProcess(argv, outcome[0], outcome[1], outcome[2])

        subprocess.run = fake_run
        try:
            install.eject("/Volumes/FLIPPER", spoken.append, lambda q: questions.append(q))
        finally:
            subprocess.run, install.PLATFORM = saved_run, saved_platform

    eject_with("darwin", (0, "Disk /dev/disk4 ejected\n", ""))
    check(calls == [["diskutil", "eject", "/Volumes/FLIPPER"]] and not questions and any("ejected" in line for line in spoken),
          f"on a Mac the card is ejected with diskutil: {calls}, {spoken}")
    eject_with("darwin", (1, "", "Volume FLIPPER on disk4 failed to eject: busy\n"))
    check(len(calls) == 1 and len(questions) == 1 and "by hand" in questions[0]
          and any("diskutil" in line and "busy" in line and line.endswith(".") for line in spoken),
          f"when diskutil fails: one sentence, then the user is asked: {spoken}, {questions}")
    eject_with("darwin", FileNotFoundError(errno.ENOENT, "No such file or directory", "diskutil"))
    check(len(questions) == 1 and "by hand" in questions[0] and any("diskutil" in line for line in spoken),
          f"when diskutil is not there: {spoken}, {questions}")
    eject_with("linux", (0, "", ""))
    check(not calls and len(questions) == 1 and "eject" in questions[0].lower() and "Enter" in questions[0],
          f"elsewhere the user is asked to eject safely and press Enter: {questions}")

    # voice_through_reader, the whole way: marker, Enter, card found, copy, eject, Enter, card back, ._ files
    install.PROGRESS_SECONDS = 60
    marker_write = re.compile(r'^storage write_chunk "/ext/\.sonar-install-[0-9a-f]{8}" 0$')
    poll = 'storage stat "/ext/sr/voices/heart/voice.txt"'
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        asked.clear()
        lines, say = collector(flipper)
        with card_reader(root, flipper) as reader:
            console = install.voice_through_reader(storage, [pack], say, reader.ask)
        check(isinstance(console, fs.Storage), f"voice_through_reader gives the console to go on with: {console!r}")
        markers = [c for c in flipper.sent if marker_write.match(c)]
        check(len(markers) == 1, f"the marker is written over the console, an empty file: {markers}")
        marker = re.search(r"\.sonar-install-[0-9a-f]{8}", markers[0]).group(0)
        first = flipper.sent.index(markers[0])
        check(len(asked) == 3 and asked[0] == TAKE_OUT and is_confirm(asked[1]) and asked[2] == PUT_BACK,
              f"the user is asked to move the card and press Enter, out and back, with the question about the card between: {asked}")
        leave = line_with(lines, "plugged in and unlocked")
        check(leave is not None and leave[0] > first, f"after the marker the user is told to leave the Flipper plugged in: {leave}")
        looking = line_with(lines, "Looking for the card on this computer")
        check(looking is not None and reader.looks_before_enter == 0,
              f"the volumes are looked at only after Enter: {reader.looks_before_enter} looks before")
        before_enter = [line for _, line in lines[:lines.index(looking)]] if looking else []
        check(not [line for line in before_enter if re.search(r"\bminutes?\b|\bseconds?\b", line)],
              f"and no clock runs while the user moves the card: {before_enter}")
        check(len(reader.confirmations) == 1 and reader.volume in reader.confirmations[0].question
              and line_with(lines, "Found the card") is None,
              f"and the card is found among the volumes; the question names it and takes the place of a line that says so: {asked[1:2]}")
        check(not os.path.exists(os.path.join(reader.volume, marker)) and f"/ext/{marker}" not in flipper.files,
              "the marker is gone from the volume and so from the card")
        check(reader.ejected == [reader.volume] and reader.unpacked == 1, f"the card is ejected once, after one unpacking: {reader.ejected}")
        polls = [i for i, c in enumerate(flipper.sent) if c == poll]
        check(reader.put_back is not None and polls and reader.put_back <= polls[0],
              f"it asks to put the card back, then asks the Flipper for voice.txt: {reader.put_back}, {polls}")
        check(len(polls) == reader.mounting + 1,
              f"and asks again while the Flipper says internal error, until it sees the file: {len(polls)} polls")
        check(reader.open_when_asked == [[False], [False]],
              f"the console is closed before the card leaves the Flipper and stays closed until it is back: {reader.open_when_asked}")
        check(len(flipper.connections) == 2 and console.ser is flipper.connections[1] and console.ser.is_open
              and console.ser.events[:3] == [("dtr", True), ("dtr", False), ("dtr", True)],
              f"after Enter one console is opened, with DTR dropped and raised, and it is the one to go on with: {len(flipper.connections)}")
        check(line_with(lines, "Waiting for the Flipper", "15 minutes") is not None,
              f"the wait says its limit: {[l for _, l in lines if 'Waiting' in l]}")
        check(all(bytes(flipper.files[f"/ext/{name}"]) == data for name, data in clips.items()),
              "the voice is on the Flipper's card with the pack's bytes")
        check("/ext/update/f7-update-1.4.3/update.fuf" in flipper.files and f"/ext/voice-heart-sonar-0.1.0.tar" not in flipper.files,
              "the rest of the card is as it was")
        check(not apple_files(flipper) and "/ext/sr/voices/._heart" in flipper.files and "/ext/._sr" in flipper.files,
              "no ._ file under the set is left; the ones beside the set's folder stay")
        inside_set = [m for m in reader.made if m.startswith("sr/voices/heart/")]
        check(line_with(lines, f"{len(inside_set)} macOS helper files", "this computer") is not None,
              f"the step says how many ._ files it removed from this computer: {[l for _, l in lines if 'helper' in l]}")
        check(line_with(lines, "no helper files", "Flipper") is not None, "and that the console found none")
        check(not [c for c in flipper.sent if c.startswith("storage remove") and "/._" in c], "so it removes none over the console")
        check(all(line.strip() and "\r" not in line for _, line in lines), "plain lines")
        check(not [c for c in flipper.sent if c.startswith(("sr ", "storage extract"))], "no extract and no sr command")
        console.ser.close()

    # The Mac could not remove them for good: the eject made them again, and the console removes the rest
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        lines, say = collector(flipper)
        with card_reader(root, flipper, recreate=True) as reader:
            console = install.voice_through_reader(storage, [pack], say, reader.ask)
        again = sorted("/ext/" + p for p in reader.recreated)
        removed_over_console = sorted(shlex.split(c)[2] for c in flipper.sent if c.startswith("storage remove") and "/._" in c)
        check(again and removed_over_console == again,
              f"the ._ files that came back are removed over the console, and only those: {removed_over_console}")
        check(not apple_files(flipper) and "/ext/sr/voices/._heart" in flipper.files, "none is left under the set, the others stay")
        inside_set = [m for m in reader.made if m.startswith("sr/voices/heart/")]
        check(line_with(lines, f"{len(inside_set)} macOS helper files", "this computer") is not None
              and line_with(lines, f"{len(again)} helper files", "console") is not None,
              f"and both counts are said: {[l for _, l in lines if 'helper' in l]}")
        console.ser.close()

    # A card that this computer mounted read-only, as a microSD adapter with its lock slider down
    # makes it: one sentence that names the slider, before anything is written
    def statvfs_with(flags):
        return lambda path: SimpleNamespace(f_flag=flags)

    check(install.volume_read_only("/Volumes/FLIPPER", statvfs=statvfs_with(1 | 4), flag=1) is True, "a volume mounted read-only")
    check(install.volume_read_only("/Volumes/FLIPPER", statvfs=statvfs_with(4), flag=1) is False, "a volume that takes writes")
    check(install.volume_read_only("E:\\", statvfs=None, flag=None) is None, "no statvfs, as on Windows: cannot tell")

    def statvfs_fails(path):
        raise OSError(errno.ENOENT, "No such file or directory", path)

    check(install.volume_read_only("/Volumes/gone", statvfs=statvfs_fails, flag=1) is None, "a volume that cannot be asked: cannot tell")
    if hasattr(os, "statvfs"):
        check(install.volume_read_only(tmp) is False, f"this computer's temporary folder takes writes: {install.volume_read_only(tmp)}")
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        lines, say = collector(flipper)
        asked.clear()
        saved_read_only = install.volume_read_only
        with card_reader(root, flipper) as reader:
            install.volume_read_only = lambda volume: volume == reader.volume
            try:
                install.voice_through_reader(storage, [pack], say, reader.ask)
                error = None
            except install.InstallError as e:
                error = e
            finally:
                install.volume_read_only = saved_read_only
        said = str(error)
        check(error is not None and "read-only" in said and "lock slider" in said and "towards the contacts" in said
              and "put the card back into the Flipper" in said and "run this script again" in said and "\n" not in said,
              f"a read-only card: {error}")
        check(reader.unpacked == 0 and not reader.made and not reader.ejected and asked == [TAKE_OUT]
              and not reader.confirmations and [n for n in os.listdir(reader.volume) if n.startswith(".sonar-install-")],
              "nothing is written to it, the marker included, and nothing more is asked, the question about the card least")
        storage.ser.close()

    # The card that was found: its name, its sizes in gigabytes, and the one question that is asked
    # before anything is written to it (Robin, 2026-10-13)
    for size, said in ((CARD_BYTES, "64.0 gigabytes"), (CARD_FREE_BYTES, "60.1 gigabytes"), (1_000_000_000, "1.0 gigabytes"),
                       (1_500_000_000_000, "1,500.0 gigabytes")):
        check(install._card_size(size) == said, f"{size:,} bytes of a card are said as {said}: {install._card_size(size)}")
    check(install._card_size(999_999_999) == install._size(999_999_999) and "megabytes" in install._card_size(999_999_999),
          f"less than a gigabyte is said as before, in megabytes: {install._card_size(999_999_999)}")
    check(install._size(12_400_000) == "11.8 megabytes" and install._size(300) == "1 kilobyte",
          f"and the update package's size stays as it was: {install._size(12_400_000)}")

    def usage_of(total, free):
        return lambda volume: SimpleNamespace(total=total, used=total - free, free=free)

    def failing_usage(volume):
        raise OSError(errno.EIO, "Input/output error", volume)

    def question_for(volume, platform="darwin", usage=usage_of(CARD_BYTES, CARD_FREE_BYTES), label=""):
        """install.card_question(volume) as platform would have it, with the sizes from usage and, on
        Windows, the drive's label."""
        saved = install.PLATFORM, install.disk_usage, getattr(install, "_windows_label", None)
        install.PLATFORM, install.disk_usage, install._windows_label = platform, usage, lambda drive: label
        try:
            return install.card_question(volume)
        finally:
            install.PLATFORM, install.disk_usage, install._windows_label = saved

    tail = "holding the marker this run wrote through the Flipper. Copy the voice onto it? [Y/n]"
    said = question_for("/Volumes/Flipper SD")
    check(said == f'Found the card "Flipper SD" at /Volumes/Flipper SD, {CARD_SIZES}, {tail}',
          f"the question names the card, its path, its size and free space, the marker, and ends in [Y/n]: {said}")
    check("\n" not in said, "and it is one line")
    for volume in ("/media/robin/FLIPPER", "/run/media/robin/SONAR CARD/"):
        said = question_for(volume, "linux")
        name = volume.rstrip("/").rpartition("/")[2]
        check(said.startswith(f'Found the card "{name}" at {volume}, {CARD_SIZES}, {tail.split(".")[0]}.'),
              f"on Linux the name is the last part of the mount path: {said}")
    said = question_for("D:\\", "win32", label="SONAR")
    check(said == f'Found the card "SONAR" at D:\\, {CARD_SIZES}, {tail}', f"on Windows the name is the drive's label: {said}")
    said = question_for("D:\\", "win32", label="")
    check(said == f"Found the card at D:\\, {CARD_SIZES}, {tail}", f"and without one the drive alone is said: {said}")
    said = question_for("/Volumes/Flipper SD", usage=failing_usage)
    check(said == f'Found the card "Flipper SD" at /Volumes/Flipper SD, {tail}',
          f"when the computer does not say the sizes they are left out: {said}")
    said = question_for("/Volumes/Flipper SD", usage=usage_of(500_000_000, 400_000_000))
    check("476.8 megabytes with 381.5 megabytes free" in said, f"a card of less than a gigabyte is said in megabytes: {said}")

    # The name of a Windows drive: GetVolumeInformationW, through ctypes, which is not loaded elsewhere
    calls_made = []

    def get_volume_information(drive, buffer, size, *rest):
        calls_made.append((drive, size, rest))
        buffer.value = "SONAR"
        return 1

    def fake_ctypes(call):
        return SimpleNamespace(
            create_unicode_buffer=lambda size: SimpleNamespace(value=""),
            windll=SimpleNamespace(kernel32=SimpleNamespace(GetVolumeInformationW=call)),
        )

    saved_ctypes = sys.modules.get("ctypes")
    try:
        sys.modules["ctypes"] = fake_ctypes(get_volume_information)
        got = install._windows_label("D:\\")
        sys.modules["ctypes"] = fake_ctypes(lambda *args: 0)
        refused = install._windows_label("D:\\")
        sys.modules["ctypes"] = fake_ctypes(lambda *args: (_ for _ in ()).throw(OSError(errno.EIO, "Input/output error")))
        broken = install._windows_label("D:\\")
        sys.modules["ctypes"] = SimpleNamespace()  # no windll, as on a Mac
        elsewhere = install._windows_label("D:\\")
    finally:
        if saved_ctypes is None:
            del sys.modules["ctypes"]
        else:
            sys.modules["ctypes"] = saved_ctypes
    check(got == "SONAR" and calls_made and calls_made[0][0] == "D:\\" and calls_made[0][1] > 32 and calls_made[0][2] == (None, None, None, None, 0),
          f"the label is what GetVolumeInformationW gives for the drive: {got!r}, {calls_made}")
    check(refused == "" and broken == "" and elsewhere == "",
          f"and none when it refuses, fails, or is not there: {refused!r}, {broken!r}, {elsewhere!r}")

    # In the way: the question comes after the card is found and found writable, before anything is
    # written, and the answers decide
    def reader_way(confirm=None, packs=None, **settings):
        """(the error or None, the Reader, the lines said, the questions asked, the commands the Flipper got,
        the tree of the volume at the end) of voice_through_reader with the answers confirm to the question
        about the card found."""
        with tempfile.TemporaryDirectory() as root:
            flipper = Flipper(SONAR_DEV)
            storage = console_of(flipper)
            lines, say = collector(flipper)
            asked.clear()
            with card_reader(root, flipper, confirm=confirm, **settings) as reader:
                try:
                    console = install.voice_through_reader(storage, packs or [pack], say, reader.ask)
                    error = None
                except install.InstallError as e:
                    console, error = None, e
            tree = volume_tree(reader.volume)
            if console is not None:
                console.ser.close()
            else:
                storage.ser.close()
            return error, reader, [line for _, line in lines], list(asked), list(flipper.sent), tree, flipper

    # Enter, y and yes, in any case with spaces round it, copy
    for given in ("", "y", "Y", "yes", " YES ", "Yes\t", "  "):
        error, reader, lines, questions, sent, tree, flipper = reader_way(confirm=[given])
        asked_once = reader.confirmations[0] if reader.confirmations else None
        check(error is None and reader.unpacked == 1 and len(reader.confirmations) == 1 and len(reader.ejected) == 1,
              f"the answer {given!r} copies the voice, after one question: {error}, {len(reader.confirmations)}")
        check(asked_once is not None and asked_once.unpacked == 0 and asked_once.ejected == 0 and asked_once.marker_there
              and not [name for name, _ in asked_once.tree if name.startswith("sr")],
              f"and the question is asked with nothing yet written to the card but the marker: {asked_once}")
        if given == "":
            question = asked_once.question
            check(question == f'Found the card "FLIPPER" at {reader.volume}, {CARD_SIZES}, {tail}' and "\n" not in question,
                  f"the question names the card, its path, both sizes and the marker, in one line: {question}")
            check(questions == [TAKE_OUT, question, PUT_BACK], f"between the two moves of the card: {questions}")

    # n and no copy nothing, eject, and end the install in one sentence
    for given in ("n", "N", "no", " No ", "NO"):
        error, reader, lines, questions, sent, tree, flipper = reader_way(confirm=[given])
        said = str(error)
        check(error is not None and "nothing was copied to the card" in said and "put the card back into the Flipper" in said
              and "run this script again" in said and "\n" not in said and len(re.findall(r"[.?!](?=\s|$)", said)) == 1,
              f"the answer {given!r} ends the install in one sentence that says what to do: {error}")
        check(reader.unpacked == 0 and not reader.made and reader.ejected == [reader.volume]
              and tree == reader.confirmations[0].tree and len(reader.confirmations[0].marker_there) == 1,
              f"nothing is written to the card, not even a removal, and it is ejected: {reader.ejected}")
        check(questions == [TAKE_OUT, reader.confirmations[0].question] and PUT_BACK not in questions,
              f"and the user is not asked to put the card back: {questions}")
        check(not [c for c in sent if c.startswith(("sr ", "storage extract"))] and len(flipper.connections) == 1
              and not any(c.is_open for c in flipper.connections),
              "the console stays closed, and the Flipper is sent nothing more")

    # An answer that is neither is asked again, with the answers said, and only the short question
    # is asked again: the screen reader reads the long line aloud once
    error, reader, lines, questions, sent, tree, flipper = reader_way(confirm=["maybe", "yep", ""])
    again = [q for q in questions if is_confirm(q)]
    check(error is None and reader.unpacked == 1 and len(again) == 3 and again[0].startswith("Found the card")
          and again[1:] == [ASK_AGAIN, ASK_AGAIN] and lines.count("Answer Y for yes or N for no.") == 2,
          f"an unknown answer is asked again, each time with the answers said, until Enter: {error}, {again}, {lines[-8:]}")
    check(questions[:2] == [TAKE_OUT, again[0]] and questions[-1] == PUT_BACK and len(reader.confirmations) == 3,
          f"the whole line is asked once, and the short question after it: {questions}")
    error, reader, lines, questions, sent, tree, flipper = reader_way(confirm=["x", "n"])
    again = [q for q in questions if is_confirm(q)]
    check(error is not None and "nothing was copied" in str(error) and len(again) == 2 and again[1] == ASK_AGAIN
          and reader.unpacked == 0 and reader.ejected == [reader.volume],
          f"an unknown answer and then no: {error}, {again}")

    # No answer, the input has ended: as no, with a sentence that says so
    for given in ([], ["x"]):
        error, reader, lines, questions, sent, tree, flipper = reader_way(confirm=given)
        said = str(error)
        check(error is not None and said.startswith("No answer came") and "nothing was copied to the card" in said
              and "put the card back into the Flipper" in said and "run this script again" in said
              and "\n" not in said and len(re.findall(r"[.?!](?=\s|$)", said)) == 1,
              f"no answer after {given}: one sentence that says no answer came: {error}")
        check(reader.unpacked == 0 and reader.ejected == [reader.volume] and tree == reader.confirmations[0].tree
              and PUT_BACK not in questions, "and nothing is written, the card is ejected, as for no")

    # The computer does not say the card's sizes: they are left out, and the question is still asked
    error, reader, lines, questions, sent, tree, flipper = reader_way(usage=OSError(errno.EIO, "Input/output error"))
    question = reader.confirmations[0].question if reader.confirmations else ""
    check(error is None and reader.unpacked == 1 and "gigabytes" not in question and "free" not in question
          and f'Found the card "FLIPPER" at {reader.volume}, {tail}' == question,
          f"sizes that cannot be read are left out, not an error: {error}, {question}")

    # In a whole run: no to the question ends the run before the update, in one sentence, with no traceback
    for confirm in (["n"], []):
        with tempfile.TemporaryDirectory() as root:
            flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
            answers[:] = ["y", "r"]
            asked.clear()
            with card_reader(root, flipper, confirm=confirm) as reader:
                code, lines, err = run(flipper, full_run[:-1])
            commands = main_commands(flipper.sent)
            check(code == 1 and "nothing was copied to the card" in lines[-1] and "run this script again" in lines[-1]
                  and "\n" not in lines[-1] and no_traceback(lines, err) and update not in commands
                  and not any("Done" in line for line in lines),
                  f"{confirm} to the question in a whole run: the exit code is 1, one sentence, no update: {code}, {lines[-2:]}")
            check(reader.unpacked == 0 and reader.ejected == [reader.volume] and PUT_BACK not in asked
                  and extract not in commands and not [c for c in flipper.sent if c.startswith("sr voice")],
                  "and nothing was copied to the card, nor sent over USB instead")
            check(not any(c.is_open for c in flipper.connections), "and no console is left open")

    # Markers that earlier runs left at the card's top go too, before the eject; a folder of that name stays
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        flipper.files["/ext/.sonar-install-deadbeef"] = bytearray()
        flipper.files["/ext/.sonar-install-0badcafe"] = bytearray()
        flipper.dirs.add("/ext/.sonar-install-f01dab1e")
        flipper.files["/ext/sr/.sonar-install-12345678"] = bytearray()  # not at the top: not a marker
        storage = console_of(flipper)
        lines, say = collector(flipper)
        with card_reader(root, flipper) as reader:
            console = install.voice_through_reader(storage, [pack], say, reader.ask)
        left = sorted(p for p in flipper.files if posixpath.basename(p).startswith(".sonar-install-"))
        check(left == ["/ext/sr/.sonar-install-12345678"] and "/ext/.sonar-install-f01dab1e" in flipper.dirs,
              f"every marker file at the card's top is gone, this run's and the older ones: {left}")
        check(line_with(lines, "2 marker files", "earlier") is not None, f"and the older ones are counted: {[l for _, l in lines][6:12]}")
        console.ser.close()
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        flipper.files["/ext/.sonar-install-deadbeef"] = bytearray()
        storage = console_of(flipper)
        lines, say = collector(flipper)

        def card_full(pack, volume, progress=None):
            raise install.InstallError("Could not copy the voice pack: the card is full.")

        with card_reader(root, flipper) as reader:
            install.unpack_to_card = card_full
            with contextlib.suppress(install.InstallError):
                install.voice_through_reader(storage, [pack], say, reader.ask)
        check(not [n for n in os.listdir(reader.volume) if n.startswith(".sonar-install-")],
              "after a failed copy every marker is removed from the volume as far as it can be")
        storage.ser.close()

    # The card turns up a few looks after Enter, as a Mac mounts it within a few seconds
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        lines, say = collector(flipper)
        with card_reader(root, flipper, mount_looks=4) as reader:
            console = install.voice_through_reader(storage, [pack], say, reader.ask)
        check(reader.looks >= 4 and reader.unpacked == 1, f"a card that mounts a few looks after Enter is found: {reader.looks}")
        console.ser.close()

    # No card turns up within CARD_LOOK_SECONDS after Enter: one sentence that says what to do, and
    # the voice goes no other way by itself
    for settings in ({"stays": True}, {"mount_looks": 10 ** 9}):
        with tempfile.TemporaryDirectory() as root:
            flipper = Flipper(SONAR_DEV)
            storage = console_of(flipper)
            lines, say = collector(flipper)
            asked.clear()
            with card_reader(root, flipper, **settings) as reader, waiting(CARD_LOOK_SECONDS=0.3):
                started = time.monotonic()
                try:
                    install.voice_through_reader(storage, [pack], say, reader.ask)
                    error = None
                except install.InstallError as e:
                    error = e
            check(error is not None and time.monotonic() - started >= 0.3, f"no card with {settings}: an error after the look: {error}")
            check(error is not None and "card" in str(error) and "put the card back into the Flipper" in str(error)
                  and "run this script again" in str(error) and "USB" in str(error) and "\n" not in str(error),
                  f"in one sentence that says to put the card back and run the script again: {error}")
            check(asked == [TAKE_OUT], f"no question but the one to move the card, USB is not offered: {asked}")
            check(reader.unpacked == 0 and not reader.ejected and not [c for c in flipper.sent if c.startswith(
                  ("storage extract", "sr ", 'storage write_chunk "/ext/voice-heart'))],
                  "nothing is copied, through the reader or over USB")
            storage.ser.close()
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        lines, say = collector(flipper)
        install.PROGRESS_SECONDS = 0
        with card_reader(root, flipper, mount_looks=10 ** 9) as reader, waiting(CARD_LOOK_SECONDS=0.2):
            with contextlib.suppress(install.InstallError):
                install.voice_through_reader(storage, [pack], say, reader.ask)
        install.PROGRESS_SECONDS = 60
        check(line_with(lines, "Still looking for the card") is not None, f"it says meanwhile that it still looks for the card: {lines[:5]}")
        storage.ser.close()
    check(install.CARD_LOOK_SECONDS == 30, f"the card is looked for for 30 seconds after Enter: {install.CARD_LOOK_SECONDS}")

    # After Enter: the port must be listed and stay listed before it is opened, the Flipper's storage
    # errors mean not yet, and a port that vanishes or a console that stops answering is closed and
    # waited for again (findings D and E of 2026-10-11)
    check(getattr(install, "CARD_BACK_SECONDS", None) == 15 * 60 and STEADY_DEFAULT is not None and 2 <= STEADY_DEFAULT <= 10,
          f"the wait has 15 minutes, and the port must stay a few seconds: {getattr(install, 'CARD_BACK_SECONDS', None)}, "
          f"{STEADY_DEFAULT}")
    for reply in (CARD_OUT, NOT_READY):
        with tempfile.TemporaryDirectory() as root:
            flipper = Flipper(SONAR_DEV)
            flipper.out_reply = reply
            storage = console_of(flipper)
            lines, say = collector(flipper)
            with card_reader(root, flipper, mounting=5) as reader:
                console = install.voice_through_reader(storage, [pack], say, reader.ask)
            polls = [c for c in flipper.sent if c == poll]
            check(len(polls) == 6 and len(flipper.connections) == 2 and console.ser.is_open,
                  f"{reply.strip()!r} while the card mounts is not yet, on the same console: {len(polls)}, {len(flipper.connections)}")
            console.ser.close()
    # The port vanishes after the Flipper's first answer and comes back later
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        flipper.drop_after_seen = 6
        storage = console_of(flipper)
        lines, say = collector(flipper)
        with card_reader(root, flipper) as reader:
            try:
                console = install.voice_through_reader(storage, [pack], say, reader.ask)
                error = None
            except install.InstallError as e:
                console, error = None, e
        check(error is None and isinstance(console, fs.Storage), f"a port that vanishes after the first answer: {error}")
        check(len(flipper.connections) == 3 and console is not None and console.ser is flipper.connections[2] and console.ser.is_open
              and not flipper.connections[1].is_open, f"the lost console is closed and a new one opened: {len(flipper.connections)}")
        check(len(flipper.opened_at) == 3 and flipper.opened_at[2] - flipper.opened_at[1] > 6,
              f"only once the port is back: {flipper.opened_at}")
        check(line_with(lines, "connection to the Flipper was lost") is not None, f"it says so: {[l for _, l in lines][-8:]}")
        check(not apple_files(flipper) and line_with(lines, "no helper files", "Flipper") is not None,
              "and then looks for the ._ files over the new console")
        check(all(c.events[:3] == [("dtr", True), ("dtr", False), ("dtr", True)] for c in flipper.connections),
              "each open drops DTR and raises it")
        if console is not None:
            console.ser.close()
    # A port named with --port or FLIPPER_PORT counts as there when the Flipper's list or the system's
    # list of serial ports has it, or when its device file exists, as a /dev/tty. name on a Mac or a
    # /dev/serial/by-id link on Linux does, which pyserial never lists; on Windows names are compared
    # without case
    with tempfile.TemporaryDirectory() as devices:
        by_id = os.path.join(devices, "usb-Flipper_Devices_Inc._Flipper_R0skie_flip_R0skie-if00")
        write(by_id, b"")
        flipper = Flipper(SONAR_DEV)
        plug(flipper)
        check(install._port_listed(PORT) == PORT, "a named port on the Flipper's list")
        check(install._port_listed(by_id) == by_id, f"a named port that no list has but whose device file exists: {by_id}")
        check(install._port_listed(os.path.join(devices, "gone")) is None, "a named port that is nowhere")
        saved = install.PLATFORM, install._serial_devices
        install.PLATFORM, install._serial_devices = "win32", lambda: ["COM4"]
        try:
            check(install._port_listed("com4") == "com4" and install._port_listed("COM5") is None,
                  "on Windows a named port is compared without case")
        finally:
            install.PLATFORM, install._serial_devices = saved
        # And the card-back wait finds it
        flipper.aliases.add(by_id)
        storage = console_of(flipper)
        lines, say = collector(flipper)
        with card_reader(devices, flipper) as reader, waiting(CARD_BACK_SECONDS=0.5):
            try:
                console = install.voice_through_reader(storage, [pack], say, reader.ask, port=by_id)
                error = None
            except install.InstallError as e:
                console, error = None, e
        check(error is None and console is not None and len(flipper.connections) == 2,
              f"the card-back wait opens a named port that only exists as a device file: {error}")
        if console is not None:
            console.ser.close()

    # A port that is listed and then vanishes again before it stayed long enough is not opened
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        lines, say = collector(flipper)
        with card_reader(root, flipper) as reader, waiting(PORT_STEADY_SECONDS=0.2):
            flipper.looks = 0
            flipper.port_script = [True, True, False, False]
            console = install.voice_through_reader(storage, [pack], say, reader.ask)
        check(len(flipper.connections) == 2 and len(flipper.opened_at) == 2 and flipper.opened_at[1] > 4,
              f"the port is opened only after it stayed listed: opened after look {flipper.opened_at[1:]}")
        console.ser.close()
    # A console that opens and then answers nothing: closed, and the port waited for again
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        flipper.silent_opens = 1
        lines, say = collector(flipper)
        with card_reader(root, flipper) as reader, waiting(PROBE_IDLE_SECONDS=0.1):
            started = time.monotonic()
            console = install.voice_through_reader(storage, [pack], say, reader.ask)
        check(len(flipper.connections) == 3 and not flipper.connections[1].is_open and console.ser is flipper.connections[2],
              f"a console that stops answering is closed, and a new one is opened: {len(flipper.connections)}")
        check(time.monotonic() - started < 5 and line_with(lines, "connection to the Flipper was lost") is not None,
              "after a few quiet seconds, not 30")
        console.ser.close()
    # The cable is pulled while the card is waited for: closed, and waited for again
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        lines, say = collector(flipper)
        original = Connection.handle
        pulled = []

        def pulled_at_poll(self, command):
            if command == poll and not pulled:
                pulled.append(command)
                self.flipper.sent.append(command)
                self.gone = True
                self.flipper.absent = 3
                self.out += f"{command}\r\n".encode()
                return
            original(self, command)

        Connection.handle = pulled_at_poll
        try:
            with card_reader(root, flipper) as reader:
                console = install.voice_through_reader(storage, [pack], say, reader.ask)
        finally:
            Connection.handle = original
        check(pulled and len(flipper.connections) == 3 and console.ser.is_open,
              f"a cable pulled during a poll: the console is opened again once the port is back: {len(flipper.connections)}")
        console.ser.close()

    # The card is never put back: after the limit, one sentence with the Flipper's last reason
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        lines, say = collector(flipper)
        install.PROGRESS_SECONDS = 0
        with card_reader(root, flipper, never_back=True) as reader, waiting(CARD_BACK_SECONDS=0.3):
            try:
                install.voice_through_reader(storage, [pack], say, reader.ask)
                error = None
            except install.InstallError as e:
                error = e
        install.PROGRESS_SECONDS = 60
        check(line_with(lines, "Still waiting for the Flipper", "so far") is not None, "it says meanwhile that it is still waiting")
        check(error is not None and "/ext/sr/voices/heart/voice.txt" in str(error) and "within" in str(error)
              and "internal error" in str(error) and "run this script again" in str(error) and "\n" not in str(error),
              f"a card that is not put back: the sentence keeps the Flipper's last reason: {error}")
        check(len(reader.ejected) == 1 and not any(c.is_open for c in flipper.connections), "it was ejected first, and no console is left open")
    # The port is there, but another tool holds it for the whole wait: the sentence keeps what the open said
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        flipper.taken = 10 ** 9
        lines, say = collector(flipper)
        with card_reader(root, flipper) as reader, waiting(CARD_BACK_SECONDS=0.3):
            try:
                install.voice_through_reader(storage, [pack], say, reader.ask)
                error = None
            except install.InstallError as e:
                error = e
        said = str(error)
        check(error is not None and "console was not back" in said and "Resource temporarily unavailable" in said
              and "close qFlipper or any other tool that uses it" in said and "run this script again" in said
              and len(re.findall(r"[.?!](?=\s|$)", said)) == 1, f"a port that another tool holds: {error}")
    # Held for the first opens, then free while the card is out: the Flipper's own answer is the last reason
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        flipper.taken = 2
        lines, say = collector(flipper)
        with card_reader(root, flipper, never_back=True) as reader, waiting(CARD_BACK_SECONDS=0.3):
            try:
                install.voice_through_reader(storage, [pack], say, reader.ask)
                error = None
            except install.InstallError as e:
                error = e
        check(error is not None and "internal error" in str(error) and "qFlipper" not in str(error),
              f"a later answer of the Flipper takes the place of what an earlier open said: {error}")

    # The port goes and does not come back
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        flipper.drop_after_seen = 10 ** 9
        storage = console_of(flipper)
        lines, say = collector(flipper)
        with card_reader(root, flipper) as reader, waiting(CARD_BACK_SECONDS=0.3):
            try:
                install.voice_through_reader(storage, [pack], say, reader.ask)
                error = None
            except install.InstallError as e:
                error = e
        check(error is not None and "console" in str(error) and "within" in str(error) and "plugged in" in str(error)
              and "\n" not in str(error) and not any(c.is_open for c in flipper.connections),
              f"a port that never comes back: {error}")

    # The copy fails with the card in the reader: the marker goes, and the sentence says to put the card back
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        lines, say = collector(flipper)

        def failing(pack, volume, progress=None):
            raise install.InstallError("Could not copy the voice pack: the card is full.")

        with card_reader(root, flipper) as reader:
            install.unpack_to_card = failing
            try:
                install.voice_through_reader(storage, [pack], say, reader.ask)
                error = None
            except install.InstallError as e:
                error = e
        check(error is not None and "the card is full" in str(error) and "put the card back" in str(error).lower(),
              f"a failed copy: {error}")
        check(not [n for n in os.listdir(reader.volume) if n.startswith(".sonar-install-")] and not reader.ejected,
              "the marker is removed from the volume")
        storage.ser.close()

    # Two packs, two sets: one trip of the card
    with tempfile.TemporaryDirectory() as root:
        second = os.path.join(root, "voice-samantha-sonar-0.1.0.tar")
        more = make_pack(second, set_name="samantha")
        flipper = Flipper(SONAR_DEV)
        storage = console_of(flipper)
        lines, say = collector(flipper)
        with card_reader(root, flipper) as reader:
            console = install.voice_through_reader(storage, [pack, second], say, reader.ask)
        check(reader.unpacked == 2 and len(reader.ejected) == 1 and len([c for c in flipper.sent if marker_write.match(c)]) == 1,
              f"two packs go in one trip of the card: {reader.unpacked}, {len(reader.ejected)}")
        check(all(bytes(flipper.files[f"/ext/{name}"]) == data for name, data in {**clips, **more}.items()), "both sets are on the card")
        check('storage stat "/ext/sr/voices/samantha/voice.txt"' in flipper.sent and poll in flipper.sent, "and both are looked for")
        console.ser.close()

    # In a whole run: without --yes the second question is the way, and the card reader is the default
    way = "Copy the voice through a card reader (faster) or over USB? [R/u]"
    for given in (["y", ""], ["y", "r"], ["y", "R"], ["y", "reader"], ["y", "x", "r"]):
        with tempfile.TemporaryDirectory() as root:
            flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
            asked.clear()
            answers[:] = list(given)
            with card_reader(root, flipper) as reader:
                code, lines, err = run(flipper, full_run[:-1])
            check(code == 0, f"a whole run through the card reader with the answers {given}: {code}, {lines[-3:]}")
            check(asked[0].endswith("Go ahead? [Y/n]") and asked[1:-3] == [way] * (len(given) - 1)
                  and asked[-3] == TAKE_OUT and is_confirm(asked[-2]) and asked[-1] == PUT_BACK,
                  f"the questions: the go-ahead, the way, the card out, the card found, and the card back, each with Enter: {asked}")
            check(reader.unpacked == 1 and len(reader.ejected) == 1, "the voice went through the reader")
            commands = main_commands(flipper.sent)
            check(not [c for c in flipper.sent if c.startswith(("storage extract", 'storage write_chunk "/ext/voice-heart', "sr voice"))],
                  f"and not over USB: no pack sent, no extract, no mute: {commands[:4]}")
            check(commands[:2] == ["info device", "update backup /ext/backup-2026-10-11.tar"] and update in commands
                  and not flipper.card_out and all(bytes(flipper.files[f"/ext/{n}"]) == d for n, d in clips.items()),
                  f"the card is back in the Flipper before the update, with the voice on it: {commands[:4]}")
            check(any("Done" in line for line in lines[-1:]) and no_traceback(lines, err), f"and the run is done: {lines[-1:]}")
            if given == ["y", "x", "r"]:
                check(any("R" in line and "U" in line for line in lines), f"an answer that is neither is asked again: {lines[:12]}")
    for given in (["y", "u"], ["y", "USB"], ["y", None]):
        with tempfile.TemporaryDirectory() as root:
            flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
            asked.clear()
            answers[:] = list(given)
            with card_reader(root, flipper) as reader:
                code, lines, err = run(flipper, full_run[:-1])
            commands = main_commands(flipper.sent)
            check(code == 0 and mute in commands and extract in commands and reader.looks == 0 and not reader.ejected,
                  f"the answers {given}: the voice goes over USB: {code}, {commands[:5]}")
            check(not [c for c in flipper.sent if ".sonar-install-" in c] and TAKE_OUT not in asked, "and no marker is written")
            if given[1] is None:
                check(any("USB" in line and "No answer" in line for line in lines), f"with no answer it says that the voice goes over USB: {lines[:8]}")
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        asked.clear()
        with card_reader(root, flipper) as reader:
            code, lines, err = run(flipper, full_run)
        check(code == 0 and not asked and reader.looks == 0 and extract in main_commands(flipper.sent),
              f"--yes asks nothing and sends the voice over USB: {code}, {asked}")
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        asked.clear()
        answers[:] = ["y"]
        code, lines, err = run(flipper, ["--package", tgz, "--release", release_json])
        check(code == 0 and len(asked) == 1, f"without a voice pack there is no question about the way: {asked}")
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        asked.clear()
        answers[:] = ["n"]
        code, lines, err = run(flipper, full_run[:-1])
        check(code == 1 and len(asked) == 1, f"and a no to the go-ahead ends it before the way is asked: {asked}")

    # In a whole run, no card after Enter: the run ends in one sentence, and the voice goes no other way
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        answers[:] = ["y", "r"]
        asked.clear()
        with card_reader(root, flipper, stays=True), waiting(CARD_LOOK_SECONDS=0.2):
            code, lines, err = run(flipper, full_run[:-1])
        commands = main_commands(flipper.sent)
        check(code == 1 and extract not in commands and update not in commands and no_traceback(lines, err)
              and not [c for c in flipper.sent if c.startswith('storage write_chunk "/ext/voice-heart')],
              f"no card: the run ends without the voice going over USB, and without the update: {code}, {lines[-2:]}")
        check("card" in lines[-1] and "run this script again" in lines[-1] and "\n" not in lines[-1] and asked[-1] == TAKE_OUT,
              f"in one sentence, after no further question: {lines[-1]}, {asked}")

    # In a whole run, a read-only card ends the run before the update
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        answers[:] = ["y", "r"]
        saved_read_only = install.volume_read_only
        with card_reader(root, flipper) as reader:
            install.volume_read_only = lambda volume: volume == reader.volume
            try:
                code, lines, err = run(flipper, full_run[:-1])
            finally:
                install.volume_read_only = saved_read_only
        check(code == 1 and "read-only" in lines[-1] and update not in flipper.sent and no_traceback(lines, err),
              f"a read-only card in a whole run: {code}, {lines[-1:]}")

    # A card that does not come back ends the run before the update
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        answers[:] = ["y", "r"]
        with card_reader(root, flipper, never_back=True), waiting(CARD_BACK_SECONDS=0.3):
            code, lines, err = run(flipper, full_run[:-1])
        check(code == 1 and "voice.txt" in lines[-1] and update not in flipper.sent and no_traceback(lines, err),
              f"a card that is not put back: {code}, {lines[-1:]}")
    # A whole run whose port vanishes after the card is back, and comes back
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        flipper.drop_after_seen = 5
        answers[:] = ["y", "r"]
        with card_reader(root, flipper):
            code, lines, err = run(flipper, full_run[:-1])
        check(code == 0 and update in flipper.sent and no_traceback(lines, err) and not any(c.is_open for c in flipper.connections),
              f"a whole run survives the port that drops after the card goes back: {code}, {lines[-2:]}")
    # Progress lines while the voice pack is copied
    with tempfile.TemporaryDirectory() as root:
        flipper = Flipper(SONAR_DEV, after=SONAR_RELEASE)
        answers[:] = ["y", "r"]
        with card_reader(root, flipper):
            code, lines, err = run(flipper, full_run[:-1], progress=0)
        check(code == 0 and any("percent of the voice pack is copied" in line for line in lines),
              f"progress lines while the pack is copied: {[x for x in lines if 'percent' in x][:3]}")

# Each failure is one sentence: one full stop, question mark or exclamation mark that ends a
# sentence, that is one followed by a space or the end, so that the dots in paths and versions do
# not count, and a question after a full stop does
SENTENCE_END = re.compile(r"[.?!](?=\s|$)")
several = [m for m in made_errors if len(SENTENCE_END.findall(m)) != 1 or "\n" in m]
check(len(made_errors) > 30 and not several,
      f"every failure the checks made, {len(made_errors)} in all, is one sentence: {several[:3]}")
declined = [m for m in made_errors if "nothing was copied to the card" in m]
check(len(declined) >= 2 and any(m.startswith("No answer came") for m in declined) and not [m for m in declined if m in several],
      f"and the sentences for a card that the user did not agree to write to are among them: {len(declined)}")

print(f"install: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
