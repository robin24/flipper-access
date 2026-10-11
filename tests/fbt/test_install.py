#!/usr/bin/env python3
"""tools/install.py, the install over USB, against a stand-in for the Flipper: its console, its
card, and its port, which goes away while the Flipper updates and comes back. The stand-in answers
as the device's shell does (the echo of the command and a line end, the output, then a line end
and the prompt), unpacks a tar with storage extract as the firmware does, entry line by entry line,
and restarts on update install after its "Restarting to apply update" line. The checks: describe
names Sonar, Momentum and the official firmware; a whole run sends info device, update backup, the
voice pack, storage extract, the update package and update install in that order, then info device
after the wait, and never loader, power, input, sysctl or sr voice use; from Sonar the extract is
wrapped in sr voice off and sr voice on, from any other firmware no sr command is sent; verify
against a release.json; the wait for the port; and every failure, a storage error in an upload
among them, ends in one sentence that names the step, exit code 1, and no traceback. Needs
pyserial. Run from the project root: python3 tests/fbt/test_install.py"""
import contextlib
import importlib.util
import io
import json
import os
import posixpath
import shlex
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
# Provisional until Task 11 records the real replies: the keys are those of furi_hal_info.c, which
# official firmware and Momentum share with Sonar; the commit, version, build date, origin and git
# address are the strings in the firmware.dfu of the two rollback packages in firmware-packages/
# (f7-update-1.4.3 and f7-update-mntm-012); the API versions are a guess
OFFICIAL = info_reply("8622f1a2", "false", "release", "1.4.3", "05-12-2025", "86.0", "Official",
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
NOT_FOUND = "\x1b[31mcould not find command `{}`, try `help`\x1b[0m\r\n"
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
        self.connections = []

    def running(self):
        """The reply to info device now."""
        if not self.updated:
            return self.info
        return self.booting.pop(0) if self.booting else self.after

    def sonar(self):
        return "Sonar" in self.info if not self.updated else "Sonar" in self.after

    def ports(self, ports=None):
        """flipper_cli.flipper_ports, as this computer would list the port."""
        if self.updated and self.never_back:
            return []
        if self.absent:
            self.absent -= 1
            return []
        return [PORT]

    def open_port(self, port, timeout=0.1):
        """flipper_cli.open_port: the port, or its one sentence and exit when it is not there."""
        if port != PORT or (self.updated and self.never_back):
            sys.exit(f"cannot open {port}: [Errno 2] could not open port {port}. Is qFlipper or another tool using it?")
        connection = Connection(self)
        self.connections.append(connection)
        return connection


class Connection:
    """One open of the port: the serial port as install.py sees it, and the shell behind it."""

    def __init__(self, flipper):
        self.flipper = flipper
        self.out = bytearray(b"\r\nWelcome to the stand-in\r\n>: ")  # the banner, which open_cli discards
        self.typed = bytearray()
        self.target = None
        self.need = 0
        self.gone = False  # the Flipper restarted: the port is dead
        self.is_open = True

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
        if not command.strip():
            self.out += b"\r\n>: "
            return
        f.sent.append(command)
        words = shlex.split(command)
        if command == "info device":
            self.say(command, f.running())
        elif words[:2] == ["update", "backup"]:
            f.files[words[2]] = bytearray(b"a backup of /int")
            self.say(command, f"Backup /int to '{words[2]}'\r\nResult: {f.backup_result}\r\n")
        elif words[:2] == ["update", "restore"]:
            result = "OK" if words[2] in f.files else "FAIL"
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
fc.time = SimpleNamespace(sleep=lambda seconds: None, time=time.time)  # open_cli's pause for the banner
fc.glob.glob = lambda pattern: []
os.environ.pop("FLIPPER_PORT", None)
install.RESTART_SECONDS = 0
install.POLL_SECONDS = 0
install.today = lambda: "2026-10-11"
answers = []
install.ask = lambda question: answers.pop(0) if answers else None


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


def make_pack(path, extra=None):
    """A voice pack as tools/voice_pack.py writes it: USTAR, every folder before its files."""
    clips = {
        "sr/voices/heart/voice.txt": b"backend kokoro voice af_heart\n",
        "sr/voices/heart/3f/hello.raw": bytes(range(256)) * 40,
        "sr/voices/heart/a0/world.raw": bytes(range(255, -1, -1)) * 30,
    }
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as tar:
        for name in ("sr", "sr/voices", "sr/voices/heart", "sr/voices/heart/3f", "sr/voices/heart/a0"):
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
    check(all("\r" not in line and line.strip() for line in lines), "plain lines, no carriage returns, none empty")
    check(all(c.is_open is False for c in flipper.connections), "every connection was closed")

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
    check(code == 1 and lines and lines[-1] == "No Flipper serial port found. Is it plugged in, unlocked, not in the "
          "updater, and not used by qFlipper? Or name it with --port.", f"no port: {lines[-1:]}")
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

print(f"install: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
