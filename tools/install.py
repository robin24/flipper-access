#!/usr/bin/env python3
"""Install Sonar, the Flipper Zero firmware with a screen reader, and its voice, over USB.

    python3 install.py --package flipper-z-f7-update-sonar-X.Y.Z.tgz --voice voice-heart-sonar-X.Y.Z.tar --release release.json

It needs Python 3.10 or newer and pyserial (python3 -m pip install pyserial), and the three files
that come with it: flipper_cli.py, flipper_storage.py and card_prune.py. Plug the Flipper in with
a USB cable, unlock it, and close qFlipper. The script says each step on its own line, for the
computer's screen reader; the Flipper itself says nothing until Sonar runs with its voice on the
card.

It uses only console commands that every firmware it starts from has built in, the official
firmware, Momentum and Sonar, so a blank card works too. The steps:

1. Read `info device`, and say which Flipper, firmware and version it found.
2. Back up the Flipper's internal storage with `update backup` to /ext/backup-<date>.tar on the
   card. A backup already there is kept: the new one is then named backup-<date>-2.tar, and so on.
3. For each --voice pack: send it to /ext as one file, unpack it into /ext with `storage extract`,
   and remove it. When Sonar runs, its voice is off during the unpacking (`sr voice off <seconds>`
   before, `sr voice on` after), so that it opens no clip that the unpacking replaces; if the
   script stops, the voice comes back by itself.
4. Send the --package to /ext/update/<name>/ and start it with `update install`.
5. Wait, up to 15 minutes, while the Flipper restarts, updates itself and restarts again. Then
   read `info device` again and compare the firmware with --release (the release's release.json)
   or, without it, with the package's folder name.
6. With --restore, put the internal storage back from a backup with `update restore`.
7. Remove the older update packages of Sonar from the card, as card_prune.py does.

Running it again is safe: the unpacking overwrites the clips and keeps the folders, and the
package's files are replaced. Without --yes it asks once before it changes anything. The exit code
is 0 when everything was done, and 1 when something was not, after one sentence that names the
step and the reason the Flipper gave.
"""
import argparse
import contextlib
import datetime
import glob
import json
import math
import os
import re
import sys
import tarfile
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import flipper_cli  # noqa: E402  exits with one sentence when pyserial is missing
import card_prune  # noqa: E402
from flipper_storage import EXTRACT_SECONDS_PER_MB, IDLE_SECONDS, PORT_ERRORS, Storage, StorageError  # noqa: E402

MB = 1048576  # a megabyte, as EXTRACT_SECONDS_PER_MB counts it
UPDATE_DIR = "/ext/update"
VOICE_DEST = "/ext"  # a voice pack holds sr/voices/<set>/..., so it is unpacked into /ext
# The seconds the wait for the updated Flipper allows. The updater restarts the Flipper twice, and
# a radio stack update, coming from another firmware, adds restarts and minutes (review R13)
WAIT_SECONDS = 15 * 60
# The seconds before the wait first looks for the port: the Flipper restarts 0.1 seconds after its
# "Restarting to apply update" line, and its old port must not be taken for the new one
RESTART_SECONDS = 5
POLL_SECONDS = 2  # between two looks for the port during the wait
PROBE_IDLE_SECONDS = 5  # a console that has just come back may say nothing at first; it is tried again
PROGRESS_SECONDS = 60  # at most one progress line in this many seconds of a long step
COMMAND_SECONDS = 120  # update backup, update install, update restore
MUTE_MAX_SECONDS = 3600  # the longest timed mute sr voice off takes
EXTRACT_TIMEOUT_MIN = 600  # the least time an unpacking is given before it counts as stuck
# Rates measured on 2026-10-11 (docs/measurements/2026-10-11-transfer-spike.txt), for the "this
# takes about" lines only: 111.3 MB sent in 653 seconds, and EXTRACT_SECONDS_PER_MB has half again
# on top of the measured unpacking
SEND_SECONDS_PER_MB = 5.9
UNPACK_SECONDS_PER_MB = EXTRACT_SECONDS_PER_MB / 1.5
NORMAL_BOOT = "0"  # system.boot in info device once the updater is done (FuriHalRtcBootModeNormal)
TAR_FILTERS = hasattr(tarfile, "data_filter")  # Python 3.10.12 and newer: tarfile's extraction filters
LOST = "the connection was lost"  # how flipper_storage's sentence for a port that is gone begins
TIMED_OUT = "the Flipper had not finished"  # and its sentence for a command that took too long


class InstallError(Exception):
    """A step that could not be done. Its message is the one sentence to show: the step and the
    reason, in the Flipper's own words where it gave any."""


def print_line(line):
    """Show one line at once, for the computer's screen reader."""
    print(line, flush=True)


def ask(question):
    """The user's answer to question, or None when no one can answer (the input has ended)."""
    try:
        return input(f"{question} ")
    except EOFError:
        return None


def today():
    """Today's date as the backup's name has it, such as 2026-10-11."""
    return datetime.date.today().isoformat()


# Sentences


def _sentence(what, reason):
    """The sentence for a step that failed: "Could not <what>: <reason>." """
    text = f"Could not {what}: {str(reason).strip()}"
    return text if text.endswith((".", "?", "!")) else text + "."


def _os_reason(error):
    """An OSError of a file on this computer, in words."""
    if error.strerror and error.filename:
        return f"{error.strerror}: {error.filename}"
    return error.strerror or str(error)


def _in_step(error):
    """Whether the console is still in step after the StorageError error: not after a lost
    connection, and not after a command that took too long, whose reply may still come."""
    return not str(error).startswith((LOST, TIMED_OUT))


@contextlib.contextmanager
def _step(what):
    """Turn whatever goes wrong inside into an InstallError that names the step what."""
    try:
        yield
    except InstallError:
        raise
    except StorageError as e:
        raise InstallError(_sentence(what, e)) from None
    except OSError as e:
        raise InstallError(_sentence(what, _os_reason(e))) from None
    except Exception as e:  # noqa: BLE001  no traceback ever reaches the user
        raise InstallError(_sentence(what, f"{type(e).__name__}: {e}")) from None


def _device_reason(reply):
    """What the Flipper said when a command did not end in "Result: OK"."""
    if "Result: FAIL" in reply:
        return "the Flipper said that it failed"
    lines = [line.strip() for line in reply.splitlines() if line.strip()]
    return f"the Flipper said: {lines[-1]}" if lines else "the Flipper gave no answer"


def _count(number, word):
    return f"{number:,} {word}" + ("" if number == 1 else "s")


def _size(size):
    """A size in megabytes, or in kilobytes when it is less than one."""
    if size >= MB:
        return f"{size / MB:,.1f} megabytes"
    return _count(max(1, round(size / 1024)), "kilobyte")


def _about(seconds):
    """How long a step takes, roughly."""
    if seconds < 45:
        return "less than a minute"
    minutes = round(seconds / 60)
    return "about a minute" if minutes <= 1 else f"about {minutes:,} minutes"


def _duration(seconds):
    """How long something took."""
    if seconds < 90:
        return _count(round(seconds), "second")
    return _count(round(seconds / 60), "minute")


class _Progress:
    """Says how far a long step is: a plain line at most once in PROGRESS_SECONDS, never a bar.
    template has {percent}."""

    def __init__(self, say, template):
        self.say = say
        self.template = template
        self.next = time.monotonic() + PROGRESS_SECONDS

    def __call__(self, done, total):
        now = time.monotonic()
        if total and done < total and now >= self.next:
            self.say(self.template.format(percent=done * 100 // total))
            self.next = now + PROGRESS_SECONDS


# The Flipper


def read_info(storage):
    """The keys and values of `info device`, such as firmware.version: Sonar, Momentum and the
    official firmware print the same keys, each line "<key> : <value>". A StorageError as the
    console raises it."""
    info = {}
    for line in storage.command("info device").splitlines():
        key, colon, value = line.partition(":")
        key = key.strip()
        if colon and key and " " not in key:
            info[key] = value.strip()
    return info


def is_sonar(info):
    """Whether the firmware that info describes is Sonar."""
    return info.get("firmware.origin.fork") == "Sonar"


def describe(info):
    """One sentence: the Flipper's name, its firmware and the firmware's version, and the commit of
    a build that is not on a tag, whose version says nothing."""
    name = info.get("hardware.name")
    who = f"The Flipper {name}" if name else "The Flipper"
    origin = info.get("firmware.origin.fork")
    firmware = "the official firmware" if origin == "Official" else origin or "a firmware that does not say its origin"
    text = f"{who} runs {firmware}"
    version = info.get("firmware.version")
    if version:
        text += f", version {version}"
    commit = info.get("firmware.commit.hash")
    if commit and version == card_prune.DEV_VERSION:
        text += f", commit {commit}"
    return text + "."


def _connect(port=None):
    """A Storage on the Flipper's console and the port's name: port, else the one flipper_cli
    finds. An InstallError with flipper_cli's sentence when there is none or it cannot be opened."""
    try:
        found = flipper_cli.find_port(port)
        ser = flipper_cli.open_cli(found)
    except SystemExit as e:  # flipper_cli's one sentence: no port, or a port that another tool has
        raise InstallError(str(e.code)) from None
    except PORT_ERRORS as e:
        raise InstallError(_sentence("open the Flipper's console", e)) from None
    return Storage(ser), found


def _close(storage):
    """Close the console; a port that is already gone is fine."""
    with contextlib.suppress(*PORT_ERRORS):
        storage.ser.close()


# The steps


def backup(storage, date):
    """Back up the Flipper's internal storage to the card with `update backup` and return the
    backup's path, /ext/backup-<date>.tar, or backup-<date>-2.tar and so on when that name is
    taken: an earlier backup, perhaps the one from before Sonar, is never overwritten."""
    what = "back up the Flipper's internal storage"
    with _step(what):
        path = f"/ext/backup-{date}.tar"
        number = 2
        while storage.exists(path):
            path = f"/ext/backup-{date}-{number}.tar"
            number += 1
        reply = storage.command(f"update backup {path}", timeout=COMMAND_SECONDS)
    if "Result: OK" not in reply:
        raise InstallError(_sentence(f"{what} to {path}", _device_reason(reply)))
    return path


def pack_entries(pack):
    """The number of entries in the voice pack, a plain tar that holds the folder sr and nothing
    else. An InstallError for any other file, so that a wrong file is refused before the Flipper is
    touched, rather than unpacked all over its card."""
    what = f"use the voice pack {pack}"
    try:
        with tarfile.open(pack, "r:") as tar:
            members = tar.getmembers()
    except OSError as e:
        raise InstallError(_sentence(what, _os_reason(e))) from None
    except tarfile.TarError:
        raise InstallError(_sentence(what, "it is not a plain tar file, as a voice pack is")) from None
    if not members:
        raise InstallError(_sentence(what, "it is empty"))
    for member in members:
        inside = member.name == "sr" or (member.name.startswith("sr/") and ".." not in member.name.split("/"))
        if not inside or not (member.isdir() or member.isfile()):
            raise InstallError(_sentence(what, f"it holds {member.name}, and a voice pack holds only the folder sr"))
    return len(members)


def mute_seconds(size):
    """The seconds of `sr voice off` around the unpacking of a pack of size bytes: its megabytes
    times EXTRACT_SECONDS_PER_MB, which has half again on top of the measured time, rounded up,
    and within the 1 to 3,600 seconds the command takes."""
    return min(MUTE_MAX_SECONDS, max(1, math.ceil(size / MB * EXTRACT_SECONDS_PER_MB)))


def voice_over_usb(storage, pack, sonar, say):
    """Put a voice pack on the card over the console: send it to /ext as one file, unpack it into
    /ext with `storage extract`, and remove it. sonar: Sonar runs, so its voice is off with
    `sr voice off <seconds>` during the unpacking and on again after it; the console is busy for
    the whole unpacking, so the mute is timed to last it out and ends by itself if the script
    stops. From any other firmware no sr command is sent. An InstallError that names the step."""
    name = os.path.basename(pack)
    remote = f"{VOICE_DEST}/{name}"
    entries = pack_entries(pack)
    with _step(f"use the voice pack {pack}"):
        size = os.path.getsize(pack)
    say(f"Sending the voice pack {name}, {_size(size)}, to the card. This takes {_about(size / MB * SEND_SECONDS_PER_MB)}.")
    with _step(f"send the voice pack {name} to the card"):
        storage.send_file(pack, remote, _Progress(say, "{percent} percent of the voice pack is sent."))
    say("The voice pack is on the card.")
    if sonar:
        seconds = mute_seconds(size)
        with _step("turn the Flipper's voice off for the unpacking"):
            storage.command(f"sr voice off {seconds}")
        say(f"The Flipper's voice is off while the pack is unpacked, for {_count(math.ceil(seconds / 60), 'minute')} at most.")
    say(f"Unpacking the voice pack on the Flipper. This takes {_about(size / MB * UNPACK_SECONDS_PER_MB)}.")
    progress = _Progress(say, "{percent} percent of the voice pack is unpacked.")
    unpacked = 0

    def on_entry(line):
        nonlocal unpacked
        unpacked += 1
        progress(unpacked, entries)

    timeout = max(EXTRACT_TIMEOUT_MIN, 2 * math.ceil(size / MB * EXTRACT_SECONDS_PER_MB))
    try:
        count = storage.extract(remote, VOICE_DEST, on_entry, timeout=timeout)
    except StorageError as e:
        if sonar and _in_step(e):  # the device's own error: the console can still give the voice back
            with contextlib.suppress(StorageError):
                storage.command("sr voice on")
        raise InstallError(_sentence(f"unpack the voice pack {name}", e)) from None
    if sonar:
        with _step("turn the Flipper's voice on again"):
            storage.command("sr voice on")
    say(f"The voice pack is unpacked, {count:,} files and folders in all.")
    with _step(f"remove {remote} from the card"):
        storage.remove(remote)


def package_folder(package, work):
    """The update package's folder: package itself when it is a folder, else the one folder that
    the .tgz package holds, unpacked into work with only plain files and folders inside it. An
    InstallError when it is neither or has no update.fuf."""
    what = f"use the update package {package}"
    if os.path.isdir(package):
        folder = os.path.abspath(package)
    elif os.path.isfile(package):
        dest = os.path.join(work, "package")
        os.mkdir(dest)
        try:
            with tarfile.open(package, "r:*") as tar:
                _extract_safely(tar, dest)
        except tarfile.ReadError:
            raise InstallError(_sentence(what, "it is neither a folder nor a .tgz file")) from None
        except tarfile.TarError as e:
            raise InstallError(_sentence(what, f"it cannot be unpacked safely, {e}")) from None
        except OSError as e:
            raise InstallError(_sentence(what, _os_reason(e))) from None
        tops = os.listdir(dest)
        if len(tops) != 1 or not os.path.isdir(os.path.join(dest, tops[0])):
            raise InstallError(_sentence(what, "it does not hold one folder, as an update package does"))
        folder = os.path.join(dest, tops[0])
    else:
        raise InstallError(_sentence(what, "there is no such file or folder"))
    if not os.path.isfile(os.path.join(folder, "update.fuf")):
        raise InstallError(_sentence(what, "it has no update.fuf"))
    return folder


def _extract_safely(tar, dest):
    """Unpack tar into dest with tarfile's data filter, which refuses links out of dest, absolute
    paths and device files; before Python 3.10.12, which lacks it, only plain files and folders
    whose paths stay inside dest are taken."""
    if TAR_FILTERS:
        tar.extractall(dest, filter="data")
        return
    members = tar.getmembers()
    for member in members:
        if not (member.isfile() or member.isdir()) or member.name.startswith("/") or ".." in member.name.split("/"):
            raise tarfile.TarError(f"{member.name} is not a plain file or folder inside the package")
    tar.extractall(dest, members=members)


def upload_package(storage, package_dir, say):
    """Send the update package's folder to /ext/update/<its name>/, replacing the files of a
    package of the same name, and return that folder on the card."""
    name = os.path.basename(os.path.normpath(package_dir))
    folder = f"{UPDATE_DIR}/{name}"
    with _step(f"use the update package {name}"):
        size = sum(os.path.getsize(os.path.join(here, f)) for here, _, files in os.walk(package_dir) for f in files)
    say(f"Sending the update package {name}, {_size(size)}, to the card. This takes {_about(size / MB * SEND_SECONDS_PER_MB)}.")
    with _step("send the update package to the card"):
        storage.send_tree(package_dir, folder, _Progress(say, "{percent} percent of the update package is sent."))
    say("The update package is on the card.")
    return folder


def start_update(storage, folder):
    """Start the update with `update install <folder>/update.fuf`. The Flipper checks the package,
    says "Restarting to apply update" and restarts into its updater, so the console goes away;
    it is closed here. An InstallError with the Flipper's reason when it refuses the package."""
    what = "start the update"
    try:
        reply = storage.command(f"update install {folder}/update.fuf", timeout=COMMAND_SECONDS)
    except StorageError as e:
        if str(e).startswith(LOST):  # the Flipper restarted, as it does once it took the package
            _close(storage)
            return
        raise InstallError(_sentence(what, e)) from None
    # The prompt came back, so the Flipper did not restart: it said why
    refused = re.search(r"^Error: (.*?)\.? Stopping update\.?$", reply, re.MULTILINE)
    reason = f"the Flipper said: {refused.group(1)}" if refused else _device_reason(reply)
    raise InstallError(_sentence(f"{what} from {folder}", reason))


def _list_ports():
    """The Flipper's ports this computer sees now, as flipper_cli finds them."""
    return flipper_cli.flipper_ports() or sorted(glob.glob("/dev/cu.usbmodemflip_*"))


def _probe(port):
    """A Storage on the Flipper's console when it is back from the update and done with it, else
    None: the port must be there and open, and info device must answer with a firmware version
    and the normal boot mode. In the updater's last boot the console is there while the updater
    still unpacks its resources (system.boot 4), and a restart follows."""
    ports = [port] if port else _list_ports()
    if not ports:
        return None
    try:
        ser = flipper_cli.open_cli(ports[0])
    except (SystemExit, *PORT_ERRORS):
        return None
    storage = Storage(ser)
    storage.idle_timeout = PROBE_IDLE_SECONDS
    try:
        info = read_info(storage)
    except StorageError:
        _close(storage)  # a console out of step is never used again
        return None
    if not info.get("firmware.version") or info.get("system.boot", NORMAL_BOOT) != NORMAL_BOOT:
        _close(storage)
        return None
    storage.idle_timeout = IDLE_SECONDS
    return storage


def wait_for_device(timeout, say, port=None):
    """Wait for the Flipper to come back after `update install` and return a Storage on its
    console. Its port is missing for most of the update, and comes and goes as it restarts, for
    as long as timeout seconds; port: the port to wait for, else any Flipper's. An InstallError
    with one sentence when it is not back in time."""
    say("Waiting for the Flipper. It restarts, updates itself and restarts again, silent all the while; "
        f"this takes a few minutes, and at most {_duration(timeout)}.")
    time.sleep(RESTART_SECONDS)
    started = time.monotonic()
    deadline = started + timeout
    next_note = started + PROGRESS_SECONDS
    while True:
        storage = _probe(port)
        if storage is not None:
            say("The Flipper is back.")
            return storage
        now = time.monotonic()
        if now >= deadline:
            raise InstallError(
                f"Could not finish the update: the Flipper did not come back within {_duration(timeout)}; if it is still "
                "updating, let it finish, then run this script again."
            )
        if now >= next_note:
            say(f"Still waiting for the Flipper, {_duration(now - started)} so far.")
            next_note = now + PROGRESS_SECONDS
        time.sleep(POLL_SECONDS)


def _same_commit(a, b):
    """Whether two commit hashes name the same commit: the shorter, of at least 7 characters, is
    the start of the longer. release.json carries 9 characters, info device prints 8."""
    a, b = a.strip().lower(), b.strip().lower()
    shorter, longer = sorted((a, b), key=len)
    return len(shorter) >= 7 and longer.startswith(shorter)


def _api_version(info):
    major, minor = info.get("firmware.api.major"), info.get("firmware.api.minor")
    return f"{major}.{minor}" if major and minor else ""


def verify(info, release):
    """Each way the running firmware, as info describes it, differs from the release that release
    (release.json's fields) describes, as a sentence; an empty list when it matches. The version,
    the commit and the API version are compared when release names them; a release is always
    Sonar, built from a tree without uncommitted changes."""
    differences = []
    version = info.get("firmware.version", "")
    wanted = release.get("firmware_version")
    if wanted is not None and version != wanted:
        differences.append(f"The Flipper runs version {version or 'unknown'}, but the release is {wanted}.")
    commit = info.get("firmware.commit.hash", "")
    wanted = release.get("firmware_commit")
    if wanted is not None and not _same_commit(commit, str(wanted)):
        differences.append(f"The Flipper runs commit {commit or 'unknown'}, but the release is commit {wanted}.")
    api = _api_version(info)
    wanted = release.get("api_version")
    if wanted is not None and api != str(wanted):
        differences.append(f"The Flipper's API version is {api or 'unknown'}, but the release's is {wanted}.")
    if info.get("firmware.commit.dirty") == "true":
        differences.append("The Flipper's firmware was built from a tree with uncommitted changes, which a release never is.")
    origin = info.get("firmware.origin.fork", "")
    if origin != "Sonar":
        differences.append(f"The Flipper's firmware calls itself {origin or 'nothing'}, not Sonar.")
    return differences


def verify_package(info, name):
    """Without release.json: how the running firmware differs from what the package's folder name
    says, as sentences. A build's package ends in its commit's eight hex digits
    (f7-update-mntm-screen-reader-9149fe49); any other is f7-update-<version>
    (f7-update-sonar-0.1.0, f7-update-1.4.3, f7-update-mntm-012)."""
    built = re.search(r"-([0-9a-f]{8})$", name)
    if built:
        commit = info.get("firmware.commit.hash", "")
        if _same_commit(commit, built.group(1)):
            return []
        return [f"The Flipper runs commit {commit or 'unknown'}, but the package {name} is commit {built.group(1)}."]
    if not name.startswith("f7-update-"):
        return []
    wanted = name[len("f7-update-"):]
    version = info.get("firmware.version", "")
    if version == wanted:
        return []
    return [f"The Flipper runs version {version or 'unknown'}, but the package {name} is version {wanted}."]


def _check_restore(storage, path):
    """Before anything changes: a backup to restore from the card must be there."""
    if not path.startswith("/ext/"):
        return
    with _step(f"restore the internal storage from {path}"):
        if not storage.exists(path):
            raise InstallError(_sentence(f"restore the internal storage from {path}", "there is no such file on the card"))


def restore(storage, path, say):
    """Put the Flipper's internal storage back from a backup with `update restore`. path is on the
    card (/ext/...), or a file on this computer, which is sent to /ext first. The Flipper reads the
    restored settings when it restarts, which the user does."""
    if path.startswith("/ext/"):
        card = path
    else:
        card = f"/ext/{os.path.basename(path)}"
        say(f"Sending the backup {os.path.basename(path)} to the card.")
        with _step("send the backup to the card"):
            storage.send_file(path, card)
    what = f"restore the internal storage from {card}"
    say(f"Restoring the internal storage from {card}.")
    with _step(what):
        reply = storage.command(f"update restore {card}", timeout=COMMAND_SECONDS)
    if "Result: OK" not in reply:
        raise InstallError(_sentence(what, _device_reason(reply)))
    say("The internal storage is restored. Restart the Flipper so that it reads it: hold Left and Back together for five seconds.")


def _list_dir(storage, path):
    """(folders, files) in a folder on the card, from `storage list`: lines "[D] name" and
    "[F] name 123b". Two empty lists when there is no such folder."""
    text = storage.command(f'storage list "{path}"', timeout=60)
    folders, files = [], []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Storage error: "):
            sentence = line[len("Storage error: "):]
            if sentence == "file/dir not exist":
                return [], []
            raise StorageError(f"{sentence}: {path}")
        if line.startswith("[D] "):
            folders.append(line[4:])
        elif line.startswith("[F] "):
            files.append(line[4:].rsplit(" ", 1)[0])
    return folders, files


def _remove_tree(storage, path):
    """Remove a folder on the card with everything in it: `storage remove` takes a file or an
    empty folder."""
    folders, files = _list_dir(storage, path)
    for name in folders:
        _remove_tree(storage, f"{path}/{name}")
    for name in files:
        storage.remove(f"{path}/{name}")
    storage.remove(path)


def prune(storage, say, info=None, keep=()):
    """Remove the older update packages of Sonar from /ext/update by card_prune's rule: the fork's
    own builds go, except the running build's and those named in keep; the packages of other
    firmware, such as the official and Momentum ones, stay. info: the running firmware's
    `info device`, read here when not given."""
    with _step("remove the older update packages from the card"):
        if info is None:
            info = read_info(storage)
        running = info.get("firmware.commit.hash", "").lower()
        if not running:
            say("The older update packages stay on the card, since the Flipper did not say its commit.")
            return
        folders, _ = _list_dir(storage, UPDATE_DIR)
        remove = card_prune.plan(folders, running, info.get("firmware.version", ""), set(keep))
        for name in remove:
            say(f"Removing the older update package {name}.")
            _remove_tree(storage, f"{UPDATE_DIR}/{name}")
    if remove:
        say(f"Removed {_count(len(remove), 'older update package')}.")
    else:
        say("There are no older update packages to remove.")


# The run


def _load_release(path):
    """release.json's fields, with an InstallError for a file that is not one."""
    what = f"read the release description {path}"
    try:
        with open(path, encoding="utf-8") as f:
            release = json.load(f)
    except OSError as e:
        raise InstallError(_sentence(what, _os_reason(e))) from None
    except ValueError as e:
        raise InstallError(_sentence(what, f"it is not JSON, {e}")) from None
    if not isinstance(release, dict) or not release.get("firmware_version") or not release.get("firmware_commit"):
        raise InstallError(_sentence(what, "it does not name a firmware_version and a firmware_commit"))
    return release


def _agreed(packs, name, restore_from, say):
    """Whether the user wants the install, after one question that says what will happen."""
    actions = ["back up its internal storage to the card"]
    actions += [f"put the voice pack {os.path.basename(pack)} on the card" for pack in packs]
    if name:
        actions.append(f"install {name}")
    if restore_from:
        actions.append(f"restore its internal storage from {restore_from}")
    listed = actions[0] if len(actions) == 1 else ", ".join(actions[:-1]) + " and " + actions[-1]
    answer = ask(f"This will {listed}. Go ahead? [Y/n]")
    if answer is None:
        say("No answer came, so nothing was changed. To install without questions, add --yes.")
        return False
    if answer.strip().lower() in ("", "y", "yes"):
        return True
    say("Nothing was changed.")
    return False


def _install(args, say):
    started = time.monotonic()
    if not (args.package or args.voice or args.restore):
        raise InstallError(
            "Nothing to do: name an update package with --package, a voice pack with --voice, or a backup with --restore."
        )
    # The files first, so that a wrong one is refused before the Flipper is touched
    release = _load_release(args.release) if args.release else None
    packs = [os.path.abspath(pack) for pack in args.voice]
    for pack in packs:
        pack_entries(pack)
    if args.restore and not args.restore.startswith("/ext/") and not os.path.isfile(args.restore):
        raise InstallError(_sentence(f"use the backup {args.restore}", "there is no such file"))
    with tempfile.TemporaryDirectory(prefix="sonar-install-") as work:
        package_dir = name = None
        if args.package:
            package_dir = package_folder(args.package, work)
            name = os.path.basename(package_dir)
            if release and name != f"f7-update-{release['firmware_version']}":
                raise InstallError(_sentence(
                    f"use the update package {args.package}",
                    f"it holds {name}, but the release description is for {release['firmware_version']}",
                ))
        say("Looking for the Flipper.")
        storage, port = _connect(args.port)
        try:
            say(f"Found the Flipper at {port}.")
            with _step("read the Flipper's device information"):
                info = read_info(storage)
            say(describe(info))
            sonar = is_sonar(info)
            if args.restore:
                _check_restore(storage, args.restore)
            if not args.yes and not _agreed(packs, name, args.restore, say):
                return 1
            say("Backing up the Flipper's internal storage to the card.")
            say(f"The backup is {backup(storage, today())}.")
            for pack in packs:
                voice_over_usb(storage, pack, sonar, say)
            if package_dir:
                folder = upload_package(storage, package_dir, say)
                say("Starting the update.")
                start_update(storage, folder)
                say("The Flipper is restarting to install the update.")
                storage = wait_for_device(WAIT_SECONDS, say, port=args.port or os.environ.get("FLIPPER_PORT"))
                with _step("read the Flipper's device information after the update"):
                    info = read_info(storage)
                say(describe(info))
                differences = verify(info, release) if release else verify_package(info, name)
                for line in differences:
                    say(line)
                if differences:
                    raise InstallError(_sentence(
                        "confirm the update",
                        "the Flipper does not run the package's firmware, so the older packages stay on the card",
                    ))
                say("The Flipper runs the firmware of the release." if release else "The Flipper runs the firmware of the package.")
            if args.restore:
                restore(storage, args.restore, say)
            if package_dir:
                prune(storage, say, info=info, keep={name})
            say(f"Done, after {_duration(time.monotonic() - started)}.")
            return 0
        finally:
            _close(storage)


def _parser():
    parser = argparse.ArgumentParser(
        prog="install.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--package", help="the update package: the release's .tgz, or a folder with update.fuf")
    parser.add_argument("--voice", action="append", default=[], metavar="PACK",
                        help="a voice pack, voice-<set>-<version>.tar; give it once for each set")
    parser.add_argument("--release", help="the release's release.json, to check the installed firmware against")
    parser.add_argument("--port", help="the Flipper's serial port, when it is not found by itself")
    parser.add_argument("--restore", metavar="BACKUP",
                        help="a backup of the internal storage to put back after the update: a .tar on this "
                             "computer, or a path on the card such as /ext/backup-2026-10-11.tar")
    parser.add_argument("--yes", action="store_true", help="ask nothing; the voice goes over USB")
    return parser


def main(argv=None):
    """Run the install with the command line argv and return the exit code: 0 when everything was
    done, 1 when something was not, after one sentence that says what and why."""
    try:
        args = _parser().parse_args(argv)
    except SystemExit as e:  # --help, or a mistake in the arguments, which argparse has explained
        return e.code if isinstance(e.code, int) else 1
    try:
        return _install(args, print_line)
    except InstallError as e:
        print_line(str(e))
    except KeyboardInterrupt:
        print_line("Stopped before the install was done; running this script again starts it over.")
    except Exception as e:  # noqa: BLE001  never a traceback, whatever went wrong
        print_line(f"The install stopped on an unexpected error: {type(e).__name__}: {e}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
