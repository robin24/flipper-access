#!/usr/bin/env python3
"""Install Sonar, the Flipper Zero firmware with a screen reader, and its voice, over USB.

    python3 install.py --package flipper-z-f7-update-sonar-X.Y.Z.tgz --voice voice-heart-sonar-X.Y.Z.tar --release release.json

It needs Python 3.10 or newer and pyserial (python3 -m pip install pyserial), and the three files
that come with it: flipper_cli.py, flipper_storage.py and card_prune.py. Plug the Flipper in with
a USB cable, unlock it, leave it on its home screen, since the update commands refuse to run while
an application is open, and close qFlipper. The script says each step on its own line, for the
computer's screen reader; the Flipper itself says nothing until Sonar runs with its voice on the
card.

It uses only console commands that every firmware it starts from has built in, the official
firmware, Momentum and Sonar, so a blank card works too. The steps:

1. Read `info device`, and say which Flipper, firmware and version it found.
2. Back up the Flipper's internal storage with `update backup` to /ext/backup-<date>.tar on the
   card. A backup already there is kept: the new one is then named backup-<date>-2.tar, and so on.
3. For each --voice pack, the voice goes onto the card one of two ways. Without --yes the script
   asks which; the card reader is the default, and --yes means USB.
   - Through a card reader: the script writes a marker file to the card; you take the microSD card
     out of the Flipper, put it into the computer's card reader and press Enter; the script finds it
     by the marker, and says which card it found, with its name, where it is mounted, its size and
     its free space, and asks whether to copy the voice onto it. Enter alone, y or yes means yes: the
     script unpacks the packs onto the card, removes the marker, any marker an earlier run left, and
     the `._` files that macOS puts beside everything it writes, and ejects the card. n or no, or no
     answer, means that nothing is written to the card: the script ejects it and ends the install
     with a sentence that says to put the card back into the Flipper and run the script again.
     After the copy you put the card back and press Enter, and the script waits until the Flipper
     sees the voice again and removes any `._` file that is left.
     A card that does not turn up ends the install with a sentence that says what to do; the voice
     never goes over USB instead by itself.
   - Over USB: send the pack to /ext as one file, unpack it into /ext with `storage extract`, and
     remove it. When Sonar runs, its voice is off during the unpacking (`sr voice off <seconds>`
     before, `sr voice on` after), so that it opens no clip that the unpacking replaces; if the
     script stops, the voice comes back by itself.
4. Send the --package to /ext/update/<name>/ and start it with `update install`.
5. Wait, up to 15 minutes, while the Flipper restarts, updates itself and restarts again. A
   Flipper with a PIN asks for it again when it restarts, and the wait goes on until it is
   entered. Then read `info device` again and compare the firmware with --release (the
   release's release.json) or, without it, with the package's folder name.
6. With --restore, put the internal storage back from a backup with `update restore`.
7. Remove the older update packages of Sonar from the card, as card_prune.py does.

Running it again is safe: the unpacking, either way, overwrites the clips and keeps the folders,
and the package's files are replaced. Without --yes it asks before it changes anything, whether to
go ahead and, when there is a voice pack, which way the voice goes. The exit code is 0 when
everything was done, and 1 when something was not, after one sentence that names the step and the
reason the Flipper gave.
"""
import argparse
import contextlib
import datetime
import errno
import getpass
import glob
import json
import math
import os
import re
import secrets
import shutil
import subprocess
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
GB = 1_000_000_000  # a gigabyte, as a card's label and the Finder count it: a card sold as 64 reads about 64
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
# Rates measured on 2026-10-11, for the "this takes about" lines only: 111.3 MB sent in 653 seconds, and EXTRACT_SECONDS_PER_MB has half again
# on top of the measured unpacking
SEND_SECONDS_PER_MB = 5.9
UNPACK_SECONDS_PER_MB = EXTRACT_SECONDS_PER_MB / 1.5
NORMAL_BOOT = "0"  # system.boot in info device once the updater is done (FuriHalRtcBootModeNormal)
TAR_FILTERS = hasattr(tarfile, "data_filter")  # Python 3.10.12 and newer: tarfile's extraction filters
# The card reader way
PLATFORM = sys.platform  # darwin, linux or win32
# The seconds the script looks for the card with the marker among the volumes, once the user has
# pressed Enter to say it is in the card reader; a Mac mounts a card within a few seconds. No clock
# runs while the user moves the card.
CARD_LOOK_SECONDS = 30
# The end of the question about the card found, and all of it that is asked again
COPY_QUESTION = "Copy the voice onto it? [Y/n]"
LABEL_CHARS = 261  # the room a Windows drive's label is read into; the longest label has 32 characters
# The seconds the script waits for the Flipper to see the card with the voice on it, once the user
# has pressed Enter to say it is back in the Flipper: as long as the wait for the update. On
# 2026-10-11 the Flipper's USB port vanished within two seconds of the card going in, and stayed
# away for about ten minutes without a restart.
CARD_BACK_SECONDS = 15 * 60
# The seconds the Flipper's port must stay listed before it is opened, after the card is back
PORT_STEADY_SECONDS = 5
EJECT_SECONDS = 120  # the most `diskutil eject` is given
MARKER_PREFIX = ".sonar-install-"  # the marker on the card is this and 8 hex digits
# `storage remove` took 37 to 39 milliseconds a file on 2026-10-11, for the "this takes about"
# line only
REMOVE_SECONDS_EACH = 0.04
LOST = "the connection was lost"  # how flipper_storage's sentence for a port that is gone begins
TIMED_OUT = "the Flipper had not finished"  # and its sentence for a command that took too long
# The shell's refusal of a command that needs the loader, such as update backup, while an
# application is open on the Flipper (cli_shell.c)
APP_OPEN = "this command cannot be run while an application is open"
# What to do about a console that gives its prompt when it is opened and then finishes no
# command, as one that a run stopped with Ctrl-C left in the middle of a storage write_chunk or
# a storage extract: flipper_cli's advice for a console that gives no prompt
STUCK = f"{flipper_cli.RESTART_ADVICE}, then run this script again"
# What to check when the first command on the card, the stat in the backup step, fails with one of
# these device sentences: a Flipper without a card, or with one it cannot read, says internal error
# or filesystem not ready. A stat never fails because a card is full: its access denied, which the
# device also gives for removing a folder that is not empty, gets no advice.
NO_CARD = "check that a microSD card, formatted on the Flipper, is in the Flipper"
CARD_ADVICE = {"internal error": NO_CARD, "filesystem not ready": NO_CARD}
# A full card fails at update backup, which answers Result: FAIL, the reason _device_reason gives
DEVICE_FAILED = "the Flipper said that it failed"
FULL_CARD_ADVICE = "a full card can cause this, so check the card's free space"


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


def _and(sentence, more):
    """The sentence, one that ends in a full stop, with more added after a semicolon: still one
    sentence."""
    return f"{sentence.rstrip().removesuffix('.')}; {more}."


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


@contextlib.contextmanager
def _device_step(what):
    """As _step for the console alone, except that a lost or stuck connection goes on as the
    StorageError it is, for a caller that closes the console and waits for the Flipper again."""
    try:
        yield
    except StorageError as e:
        if not _in_step(e):
            raise
        raise InstallError(_sentence(what, e)) from None


def _device_reason(reply, sonar=False):
    """What the Flipper said when a command did not end in "Result: OK". A command that needs the
    loader, as the update commands do, is refused while an application is open on the Flipper; the
    reason then says what to do. sonar: Sonar runs, whose reader says Home screen on the home
    screen, while other firmware says nothing."""
    if APP_OPEN in reply:
        back = "until it says Home screen" if sonar else "a few times to reach the home screen"
        return f"the Flipper said that {APP_OPEN}; press Back on the Flipper {back}, then run this script again"
    if "Result: FAIL" in reply:
        return DEVICE_FAILED
    lines = [line.strip() for line in reply.splitlines() if line.strip()]
    return f"the Flipper said: {lines[-1]}" if lines else "the Flipper gave no answer"


def _count(number, word):
    return f"{number:,} {word}" + ("" if number == 1 else "s")


def _size(size):
    """A size in megabytes, or in kilobytes when it is less than one."""
    if size >= MB:
        return f"{size / MB:,.1f} megabytes"
    return _count(max(1, round(size / 1024)), "kilobyte")


def _card_size(size):
    """A card's size or free space, said so that the user can tell the card by it: from one gigabyte
    up in gigabytes with one decimal, counted as the card's label and the Finder count them, so that
    a card sold as 64 gigabytes reads about 64, and below that as _size says it."""
    if size >= GB:
        return f"{size / GB:,.1f} gigabytes"
    return _size(size)


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


def read_first_info(storage):
    """read_info for the first command after the console was opened. A console can give its
    prompt on the open and then finish no command; when this first one takes too long or the
    connection is lost, the InstallError's sentence ends by saying to restart the Flipper and run
    this script again."""
    what = "read the Flipper's device information"
    with _step(what):
        try:
            return read_info(storage)
        except StorageError as e:
            if _in_step(e):
                raise
            raise InstallError(_and(_sentence(what, e), STUCK)) from None


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


def backup(storage, date, sonar=False):
    """Back up the Flipper's internal storage to the card with `update backup` and return the
    backup's path, /ext/backup-<date>.tar, or backup-<date>-2.tar and so on when that name is
    taken: an earlier backup, perhaps the one from before Sonar, is never overwritten. sonar: Sonar
    runs, for the advice when an application is open. The stat of the name is the install's first
    command on the card, so its sentence says what to check when the card is missing or cannot be
    read (CARD_ADVICE). A full card fails at update backup, so when that answers Result: FAIL the
    sentence adds to check the card's free space."""
    what = "back up the Flipper's internal storage"
    with _step(what):
        path = f"/ext/backup-{date}.tar"
        number = 2
        try:
            while storage.exists(path):
                path = f"/ext/backup-{date}-{number}.tar"
                number += 1
        except StorageError as e:
            advice = next((more for said, more in CARD_ADVICE.items() if str(e).startswith(f"{said}: ")), None)
            if advice is None:
                raise
            raise InstallError(_and(_sentence(what, e), advice)) from None
        reply = storage.command(f"update backup {path}", timeout=COMMAND_SECONDS)
    if "Result: OK" not in reply:
        reason = _device_reason(reply, sonar)
        sentence = _sentence(f"{what} to {path}", reason)
        raise InstallError(_and(sentence, FULL_CARD_ADVICE) if reason == DEVICE_FAILED else sentence)
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
    # Not "on the card": the voice is in place only after the unpacking, whose line is the one after
    # which a run again may leave out --voice
    say("The voice pack is sent; the Flipper unpacks it next.")
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


# The voice through a card reader


def volume_patterns(platform, user):
    """The glob patterns of the places where this system mounts a card: /Volumes/* on macOS,
    /media/<user>/* and /run/media/<user>/* on Linux, the drive letters D to Z on Windows."""
    if platform == "darwin":
        return ["/Volumes/*"]
    if platform == "win32":
        return [f"{letter}:\\" for letter in "DEFGHIJKLMNOPQRSTUVWXYZ"]
    return [f"/media/{glob.escape(user)}/*", f"/run/media/{glob.escape(user)}/*"]


def card_volumes():
    """The volumes mounted on this computer now, as folders."""
    try:
        user = getpass.getuser()
    except (KeyError, OSError, ImportError):  # a user the system does not know, as in some containers
        user = ""
    found = []
    for pattern in volume_patterns(PLATFORM, user):
        found += sorted(volume for volume in glob.glob(pattern) if os.path.isdir(volume))
    return found


def find_card(marker, volumes):
    """The first of volumes that holds the file named marker, else None: the card that the marker
    was written to over USB."""
    for volume in volumes:
        if os.path.isfile(os.path.join(volume, marker)):
            return volume
    return None


def volume_read_only(volume, statvfs=getattr(os, "statvfs", None), flag=getattr(os, "ST_RDONLY", None)):
    """Whether this computer mounted the volume read-only, as macOS mounts a card whose microSD
    adapter has its lock slider down: True or False, or None when it cannot tell. Windows has no
    statvfs, so there it cannot tell, and a write that fails says so in one sentence instead."""
    if statvfs is None or flag is None:
        return None
    try:
        return bool(statvfs(volume).f_flag & flag)
    except OSError:
        return None


disk_usage = shutil.disk_usage  # the computer's word on a volume's size and free space; the tests replace it


def _windows_label(drive):
    """The label of the Windows drive, such as D:\\, or "" when it has none or cannot be read. The
    standard library's ctypes calls GetVolumeInformationW, and is imported only here, where no other
    system needs it."""
    try:
        import ctypes

        label = ctypes.create_unicode_buffer(LABEL_CHARS)
        if ctypes.windll.kernel32.GetVolumeInformationW(drive, label, LABEL_CHARS, None, None, None, None, 0):
            return label.value.strip()
    except (AttributeError, OSError):  # no windll off Windows; and a drive that does not answer
        pass
    return ""


def volume_name(volume):
    """The name the system gives the volume: the last part of its mount path on macOS and Linux, the
    drive's label on Windows. "" when it has none."""
    if PLATFORM == "win32":
        return _windows_label(volume)
    return os.path.basename(volume.rstrip("/"))


def card_question(volume):
    """The one line that says which card was found at volume and asks whether to copy the voice onto
    it: its name, where it is mounted, its size and free space, and that it holds the marker that this
    run wrote through the Flipper. The sizes are left out when the computer does not say them; the
    name is left out when the volume has none."""
    name = volume_name(volume)
    called = f' "{name}"' if name else ""
    try:
        usage = disk_usage(volume)
    except OSError:
        sizes = ""
    else:
        sizes = f", {_card_size(usage.total)} with {_card_size(usage.free)} free"
    return (f"Found the card{called} at {volume}{sizes}, holding the marker this run wrote through the Flipper. "
            f"{COPY_QUESTION}")


def _confirm_card(volume, say, ask):
    """Ask, with card_question, whether to copy the voice onto the card at volume, and return when
    the answer is Enter alone, y or yes, in any case. An answer that is neither yes nor no is asked
    again, with the answers said, and only with the short question COPY_QUESTION, since the
    computer's screen reader would read the whole line aloud again. For n or no, and when no one can
    answer (ask gives None), nothing is written to the card: it is ejected, which writes no file,
    and an InstallError in one sentence says that nothing was copied and to put the card back and
    run the script again. The marker stays on the card, and the next run through a card reader
    removes it."""
    question = card_question(volume)
    while True:
        answer = ask(question)
        if answer is None:
            why = "No answer came"
            break
        reply = answer.strip().lower()
        if reply in ("", "y", "yes"):
            return
        if reply in ("n", "no"):
            why = "You answered no"
            break
        say("Answer Y for yes or N for no.")
        question = COPY_QUESTION
    eject(volume, say, ask)
    raise InstallError(f"{why}, so nothing was copied to the card; put the card back into the Flipper and run this "
                       "script again.")


def pack_sets(pack):
    """The voice sets that the voice pack holds, in the pack's order: the folders under
    sr/voices. An InstallError for a pack that holds none."""
    what = f"use the voice pack {pack}"
    sets = []
    try:
        with tarfile.open(pack, "r:") as tar:
            for member in tar.getmembers():
                parts = member.name.split("/")
                if len(parts) >= 3 and parts[:2] == ["sr", "voices"] and parts[2] not in sets:
                    sets.append(parts[2])
    except OSError as e:
        raise InstallError(_sentence(what, _os_reason(e))) from None
    except tarfile.TarError:
        raise InstallError(_sentence(what, "it is not a plain tar file, as a voice pack is")) from None
    if not sets:
        raise InstallError(_sentence(what, "it holds no voice set, a folder in sr/voices"))
    return sets


def _card_reason(error):
    """An OSError of the card in the reader, in words; for a card that refuses writes, also what
    to check."""
    reason = _os_reason(error)
    if error.errno in (errno.EROFS, errno.EACCES, errno.EPERM):
        reason += "; the card may be locked, so on a microSD adapter push the lock slider up, towards the contacts"
    return reason


def unpack_to_card(pack, volume, progress=None):
    """Write the voice pack onto the card mounted at volume with Python's own tar reader: the
    entries in the pack's order, which is the clip order, the folders from the pack's folder entries,
    and a file that is there replaced. No metadata is copied. Every entry is checked first to be a
    plain file or folder that lands inside the volume by its real path, so a pack with an entry that
    does not leaves the card as it was. progress(done, total) is called after each entry. The number
    of files written; an InstallError for a pack or card that cannot be used."""
    what = f"copy the voice pack {os.path.basename(pack)} onto the card"
    written = 0
    try:
        with tarfile.open(pack, "r:") as tar:
            members = _checked_members(tar, volume, "the card")
            for done, member in enumerate(members, 1):
                target = os.path.join(volume, *member.name.split("/"))
                if member.isdir():
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as clip:
                        shutil.copyfileobj(tar.extractfile(member), clip)
                    written += 1
                if progress:
                    progress(done, len(members))
    except tarfile.ReadError:
        raise InstallError(_sentence(what, "it cannot be read as a plain tar file, as a voice pack is")) from None
    except tarfile.TarError as e:
        raise InstallError(_sentence(what, e)) from None
    except OSError as e:
        raise InstallError(_sentence(what, _card_reason(e))) from None
    return written


def remove_appledouble(volume, set_name):
    """Remove every `._` file under sr/voices/<set_name>/ on the mounted card and nothing else, and
    return how many were removed. macOS puts a 4 KB `._<name>` file beside every file and folder a
    process writes to an exFAT card. One that cannot be removed is left, without an error: the
    console removes what is left once the card is back in the Flipper."""
    removed = 0
    for here, _, names in os.walk(os.path.join(volume, "sr", "voices", set_name)):
        for name in names:
            if name.startswith("._"):
                try:
                    os.remove(os.path.join(here, name))
                except OSError:
                    continue
                removed += 1
    return removed


def _find_appledouble(storage, path, found):
    """Add to found the `._` files in the folder path on the card and below it."""
    folders, files = _list_dir(storage, path)
    found += [f"{path}/{name}" for name in files if name.startswith("._")]
    for name in folders:
        _find_appledouble(storage, f"{path}/{name}", found)


def remove_appledouble_over_console(storage, sets, say):
    """Remove every `._` file under /ext/sr/voices/<set>/ on the card in the Flipper, for each set,
    with `storage list` and `storage remove`, and return how many were removed. An InstallError
    that names the step when the Flipper says no; a lost or stuck connection is the StorageError
    it is."""
    found = []
    with _device_step("look for the helper files in the voice folders on the card"):
        say("Looking through the voice folders on the Flipper for helper files that are left.")
        progress = _Progress(say, "{percent} percent of the voice folders are looked through.")
        for name in sets:
            root = f"{VOICE_DEST}/sr/voices/{name}"
            folders, files = _list_dir(storage, root)
            found += [f"{root}/{file}" for file in files if file.startswith("._")]
            for done, folder in enumerate(folders, 1):
                _find_appledouble(storage, f"{root}/{folder}", found)
                progress(done, len(folders))
    if not found:
        say("The Flipper lists no helper files in the voice folders.")
        return 0
    say(f"The Flipper lists {_count(len(found), 'more helper file')}. Removing them over the console. "
        f"This takes {_about(len(found) * REMOVE_SECONDS_EACH)}.")
    progress = _Progress(say, "{percent} percent of the helper files are removed.")
    with _device_step("remove the helper files from the card"):
        for done, path in enumerate(found, 1):
            storage.remove(path)
            progress(done, len(found))
    say(f"Removed {_count(len(found), 'helper file')} over the console.")
    return len(found)


def eject(volume, say, ask):
    """Eject the card's volume. On a Mac that is `diskutil eject`; when it fails, in one sentence,
    and everywhere else the user is asked to eject the card safely and press Enter. Ejecting
    writes out what the system still holds back, which is why the card must not just be pulled."""
    if PLATFORM == "darwin":
        try:
            result = subprocess.run(
                ["diskutil", "eject", volume], capture_output=True, text=True, timeout=EJECT_SECONDS
            )
        except subprocess.TimeoutExpired:
            reason = f"it did not finish within {_duration(EJECT_SECONDS)}"
        except OSError as e:
            reason = _os_reason(e)
        else:
            if result.returncode == 0:
                say("The card is ejected.")
                return
            said = [line.strip() for line in (result.stderr + result.stdout).splitlines() if line.strip()]
            reason = said[-1] if said else f"it ended with the code {result.returncode}"
        say(_sentence("eject the card with diskutil", reason))
        ask("Eject the card by hand, with the eject button next to its name in the Finder, then press Enter.")
        return
    ask("Eject the card safely from this computer, then press Enter.")


def _wait_for(look, timeout, say, still):
    """The first value look() gives that is not None, looking every POLL_SECONDS for as long as
    timeout seconds; None when the time is out. still has {time} for the seconds so far and is said
    at most once in PROGRESS_SECONDS."""
    started = time.monotonic()
    deadline = started + timeout
    next_note = started + PROGRESS_SECONDS
    while True:
        found = look()
        if found is not None:
            return found
        now = time.monotonic()
        if now >= deadline:
            return None
        if now >= next_note:
            say(still.format(time=_duration(now - started)))
            next_note = now + PROGRESS_SECONDS
        time.sleep(POLL_SECONDS)


def _write_marker(storage, marker):
    """Write an empty file named marker to the card's top folder, over the console."""
    with tempfile.TemporaryDirectory(prefix="sonar-install-") as work:
        empty = os.path.join(work, marker)
        with open(empty, "wb"):
            pass
        storage.send_file(empty, f"{VOICE_DEST}/{marker}")


def remove_markers(volume):
    """Remove every marker file at the top of the card's volume, .sonar-install-<8 hex digits>:
    this run's, and any that an earlier run left, as a run that stopped while the card was out of
    the Flipper does. A folder of that name stays. The number of files removed."""
    removed = 0
    for name in sorted(os.listdir(volume)):
        path = os.path.join(volume, name)
        if name.startswith(MARKER_PREFIX) and os.path.isfile(path):
            os.remove(path)
            removed += 1
    return removed


def _copy_to_card(packs, sets, volume, say, ask):
    """The part of the card reader way with the card in the computer: unpack the packs onto it,
    remove the marker files, this run's and older ones, and then the `._` files macOS made, and
    eject it. An InstallError that names the step, with the marker files taken off the card again
    as far as they can be."""
    try:
        written = 0
        for pack in packs:
            say(f"Copying the voice pack {os.path.basename(pack)} onto the card.")
            written += unpack_to_card(pack, volume, _Progress(say, "{percent} percent of the voice pack is copied."))
    except InstallError:
        with contextlib.suppress(OSError):
            remove_markers(volume)
        raise
    say(f"The voice is on the card, {_count(written, 'file')}.")
    with _step("remove the marker files from the card"):
        older = remove_markers(volume) - 1  # this run's own is among them
    if older > 0:
        say(f"Also removed {_count(older, 'marker file')} that an earlier run left on the card.")
    removed = sum(remove_appledouble(volume, name) for name in sets)
    if removed:
        say(f"Removed {_count(removed, 'macOS helper file')}, files whose names start with a dot and an underscore, "
            "from the card on this computer.")
    else:
        say("The card on this computer shows no macOS helper files, files whose names start with a dot and an "
            "underscore.")
    eject(volume, say, ask)


def _serial_devices():
    """Every serial port this computer lists now."""
    from serial.tools import list_ports

    return [p.device for p in list_ports.comports()]


def _port_listed(port=None):
    """The Flipper's port when this computer has it now, else None: port when one was named, else
    the first Flipper port flipper_cli finds. A named port is there when the Flipper's list or the
    system's list of serial ports has it, compared without case on Windows, or when its device file
    exists: pyserial lists only /dev/cu.* on a Mac and never a /dev/serial/by-id link on Linux, and
    those vanish with the device too."""
    listed = _list_ports()
    if not port:
        return listed[0] if listed else None
    names = listed + _serial_devices()
    if PLATFORM == "win32":
        there = port.upper() in (name.upper() for name in names)
    else:
        there = port in names
    return port if there or os.path.exists(port) else None


def _open_console(port):
    """(a Storage on the console at port, opened as flipper_cli.open_cli opens it, DTR dropped and
    raised and the banner read, None), or (None, the sentence that says why not) when it cannot be
    opened, goes away or gives no prompt."""
    try:
        return Storage(flipper_cli.open_cli(port)), None
    except SystemExit as e:  # flipper_cli's one sentence, such as a port that qFlipper holds
        return None, str(e.code or "the port could not be opened")
    except PORT_ERRORS as e:
        return None, str(e)


def wait_for_card(sets, say, port=None):
    """After the user put the card back into the Flipper and pressed Enter: wait until the Flipper
    sees each set's voice on it, remove the `._` files that are left through the console, and
    return a Storage on the console. The Flipper's USB connection can drop just after the card
    goes in and stay away for minutes, so nothing is taken for granted: the Flipper's port must be
    listed and stay listed for PORT_STEADY_SECONDS; it is opened as flipper_cli opens it, with DTR
    dropped and raised; and `storage stat /ext/sr/voices/<set>/voice.txt` is asked for each set.
    Any storage error means not yet: the Flipper says internal error while it has no card. A port
    that vanishes, a console that cannot be opened or stops answering, closes the console and goes
    back to waiting for the port. port: the port to wait for, else any Flipper's. After
    CARD_BACK_SECONDS in all, with a line about once a minute meanwhile, an InstallError in one
    sentence that keeps the last reason: what the Flipper last said instead of the voice, or why
    its port, though there, could not be opened, as when qFlipper holds it."""
    paths = [f"{VOICE_DEST}/sr/voices/{name}/voice.txt" for name in sets]
    what = paths[0] if len(paths) == 1 else "the voice sets"
    say(f"Waiting for the Flipper to see the card with the voice, at most {_duration(CARD_BACK_SECONDS)}.")
    started = time.monotonic()
    deadline = started + CARD_BACK_SECONDS
    next_note = started + PROGRESS_SECONDS
    storage = None
    listed_since = None  # since when the port has been listed without a break
    reason = None  # the last reason why there is no voice yet: the Flipper's own words, or the open's

    def lost():
        nonlocal storage
        _close(storage)  # a console out of step is never used again
        storage = None
        say("The connection to the Flipper was lost; waiting for it to come back.")

    try:
        while True:
            if storage is None:
                found = _port_listed(port)
                if found is None:
                    listed_since = None
                else:
                    listed_since = listed_since if listed_since is not None else time.monotonic()
                    if time.monotonic() - listed_since >= PORT_STEADY_SECONDS:
                        listed_since = None
                        storage, failed = _open_console(found)
                        if storage is None:
                            reason = f"the last try to open its port said {failed.rstrip().removesuffix('.')}"
                        else:
                            storage.idle_timeout = PROBE_IDLE_SECONDS  # a stat answers at once, or the console is stuck
            if storage is not None:
                try:
                    missing = [path for path in paths if not storage.exists(path)]
                except StorageError as e:
                    if _in_step(e):
                        said = str(e)
                        for path in paths:  # the device's sentence is enough, the path is named anyway
                            said = said.removesuffix(f": {path}")
                        reason = f"its last answer was {said}"
                    else:
                        lost()
                else:
                    reason = None
                    if not missing:
                        say("The Flipper sees the card with the voice on it.")
                        storage.idle_timeout = IDLE_SECONDS
                        try:
                            remove_appledouble_over_console(storage, sets, say)
                        except StorageError:  # lost or stuck, while the Flipper's own errors are an InstallError
                            lost()
                        else:
                            console, storage = storage, None  # handed over, so not closed below
                            return console
            now = time.monotonic()
            if now >= deadline:
                said = f", and {reason}" if reason else ""
                if storage is None:
                    why = f"the Flipper's console was not back within {_duration(CARD_BACK_SECONDS)}{said}"
                else:
                    why = f"the Flipper did not see {what} within {_duration(CARD_BACK_SECONDS)}{said}"
                raise InstallError(_sentence(
                    "find the voice on the card after it was put back",
                    f"{why}; check that the card sits in the Flipper and that the Flipper is plugged in and unlocked, "
                    "then run this script again",
                ))
            if now >= next_note:
                say(f"Still waiting for the Flipper, {_duration(now - started)} so far.")
                next_note = now + PROGRESS_SECONDS
            time.sleep(POLL_SECONDS)
    finally:
        if storage is not None:
            _close(storage)


def voice_through_reader(storage, packs, say, ask, port=None):
    """Put the voice packs on the card through the computer's card reader, and return a Storage on
    the console to go on with. The steps: a marker file, /ext/.sonar-install-<8 hex digits>, is
    written to the card over the console, and the console is closed for the whole trip of the
    card; the user takes the card out of the Flipper, puts it into the reader and presses Enter,
    with no clock running meanwhile; the card is looked for among the mounted volumes by the
    marker for CARD_LOOK_SECONDS; a card mounted read-only is refused before anything is written
    to it; the card is described in one line, its name, its path, its size and free space and the
    marker, and the user is asked whether to copy the voice onto it, with Enter alone meaning yes,
    before anything is written to it: n or no, or no answer, writes nothing, ejects the card and
    ends in an InstallError that says to put it back and run the script again, and an answer that
    is neither is asked again; the packs are unpacked onto it, the marker files at its top, this
    run's and any an earlier run left, and the `._` files under the sets' folders are removed, and
    it is ejected; the user puts it back and presses Enter; and wait_for_card waits, on port or any
    Flipper's, until the Flipper sees the voice, and removes the `._` files that are left through a
    new console. The voice never goes over USB instead: a card that does not turn up, like every
    other failure, is an InstallError in one sentence that says what to do."""
    sets = [name for pack in packs for name in pack_sets(pack)]
    marker = MARKER_PREFIX + secrets.token_hex(4)
    say("Writing a small marker file to the card, so that this computer can tell the card from other drives.")
    with _step("write the marker file to the card"):
        _write_marker(storage, marker)
    _close(storage)  # no console session while the card is out, nor across its return
    say("Leave the Flipper plugged in and unlocked while its card is out.")
    ask("Take the microSD card out of the Flipper and put it into this computer's card reader, then press Enter.")
    say("Looking for the card on this computer.")
    volume = _wait_for(lambda: find_card(marker, card_volumes()), CARD_LOOK_SECONDS, say,
                       "Still looking for the card, {time} so far.")
    if volume is None:
        raise InstallError(_sentence(
            "find the card on this computer",
            f"no drive with the marker file turned up within {_duration(CARD_LOOK_SECONDS)}; put the card back into "
            "the Flipper and run this script again, and answer U for USB if this computer does not show the card",
        ))
    if volume_read_only(volume):
        raise InstallError(_sentence(
            "copy the voice onto the card",
            "the card is read-only on this computer; on a microSD adapter, push the lock slider up, towards the "
            "contacts, put the card back into the Flipper, and run this script again",
        ))
    _confirm_card(volume, say, ask)
    try:
        _copy_to_card(packs, sets, volume, say, ask)
    except InstallError as e:
        raise InstallError(_and(str(e), "put the card back into the Flipper before running this script again")) from None
    ask("Put the card back into the Flipper, then press Enter.")
    return wait_for_card(sets, say, port)


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


def lands_inside(root, name, path=os.path):
    """Whether the tar member name lands inside the folder root, a real path itself: the real path
    of where the member would be written, with links and .. resolved, must stay inside root. That
    holds for names with a drive or backslashes on Windows too; path=ntpath reads them as Windows
    does."""
    try:
        return path.commonpath([root, path.realpath(path.join(root, name))]) == root
    except ValueError:  # another drive on Windows, or a name that is no path at all
        return False


def _checked_members(tar, dest, where):
    """The members of tar in the archive's order, once each is a plain file or folder that lands
    inside dest; tarfile.TarError naming the first that does not. where says what dest is."""
    root = os.path.realpath(dest)
    members = tar.getmembers()
    for member in members:
        if not (member.isfile() or member.isdir()) or not lands_inside(root, member.name):
            raise tarfile.TarError(f"{member.name} is not a plain file or folder inside {where}")
    return members


def _extract_safely(tar, dest):
    """Unpack tar into dest: only plain files and folders whose real paths stay inside dest are
    taken, and tarfile's data filter, where Python has it (3.10.12 and newer), is applied on top."""
    members = _checked_members(tar, dest, "the package")
    if TAR_FILTERS:
        tar.extractall(dest, members=members, filter="data")
    else:
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


def start_update(storage, folder, sonar=False):
    """Start the update with `update install <folder>/update.fuf`. The Flipper checks the package,
    says "Restarting to apply update" and restarts into its updater, so the console goes away;
    it is closed here. An InstallError with the Flipper's reason when it refuses the package.
    sonar: Sonar runs, for the advice when an application is open."""
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
    reason = f"the Flipper said: {refused.group(1)}" if refused else _device_reason(reply, sonar)
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


def wait_for_device(timeout, say, port=None, voice=False):
    """Wait for the Flipper to come back after `update install` and return a Storage on its
    console. Its port is missing for most of the update, and comes and goes as it restarts, for
    as long as timeout seconds; port: the port to wait for, else any Flipper's. A Flipper with a
    PIN locks itself again when it restarts, as Momentum and Sonar do by default, and its console
    is off until the PIN is entered, so the wait goes on meanwhile. An InstallError with one
    sentence when it is not back in time, which names the PIN beside an update that still runs;
    voice: the run put a voice pack on the card, so a run again may leave it out."""
    say("Waiting for the Flipper. It restarts, updates itself and restarts again, silent all the while; "
        f"this takes a few minutes, and at most {_duration(timeout)}. A Flipper with a PIN asks for it again when "
        "it restarts, and this script waits until it is entered.")
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
            again = ", and leave out --voice, since the voice is on the card already" if voice else ""
            raise InstallError(_sentence(
                "finish the update",
                f"the Flipper did not come back within {_duration(timeout)}, though the firmware may be installed "
                "already; if it is still updating, let it finish, and if it is locked with its PIN, enter the PIN, "
                f"then run this script again{again}",
            ))
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


def restore(storage, path, say, sonar=False):
    """Put the Flipper's internal storage back from a backup with `update restore`. path is on the
    card (/ext/...), or a file on this computer, which is sent to /ext first. The Flipper reads the
    restored settings when it restarts, which the user does. sonar: Sonar runs, for the advice
    when an application is open."""
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
        raise InstallError(_sentence(what, _device_reason(reply, sonar)))
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


def _voice_way(say):
    """The answer to the one question about the way: True for the card reader, the default, False
    for USB, and also False when no one can answer."""
    while True:
        answer = ask("Copy the voice through a card reader (faster) or over USB? [R/u]")
        if answer is None:
            say("No answer came, so the voice goes over USB.")
            return False
        first = answer.strip().lower()[:1]
        if first in ("", "r"):
            return True
        if first == "u":
            return False
        say("Answer R for the card reader or U for USB.")


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
            info = read_first_info(storage)
            say(describe(info))
            sonar = is_sonar(info)
            if args.restore:
                _check_restore(storage, args.restore)
            by_reader = False  # --yes asks nothing, so the voice goes over USB
            if not args.yes:
                if not _agreed(packs, name, args.restore, say):
                    return 1
                by_reader = bool(packs) and _voice_way(say)
            say("Backing up the Flipper's internal storage to the card.")
            say(f"The backup is {backup(storage, today(), sonar)}.")
            if by_reader:
                storage = voice_through_reader(storage, packs, say, ask, port=args.port or os.environ.get("FLIPPER_PORT"))
            else:
                for pack in packs:
                    voice_over_usb(storage, pack, sonar, say)
            if package_dir:
                folder = upload_package(storage, package_dir, say)
                say("Starting the update.")
                start_update(storage, folder, sonar)
                say("The Flipper is restarting to install the update.")
                storage = wait_for_device(WAIT_SECONDS, say, port=args.port or os.environ.get("FLIPPER_PORT"),
                                          voice=bool(packs))
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
                restore(storage, args.restore, say, is_sonar(info))  # the firmware that runs now
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
    # Ctrl-C lands most often inside a storage write_chunk or a storage extract, whose end the
    # Flipper's shell then still waits for
    except KeyboardInterrupt:
        print_line("Stopped before the install was done; running this script again starts it over, and if the "
                   f"Flipper does not answer on that run, {STUCK}.")
    except Exception as e:  # noqa: BLE001  never a traceback, whatever went wrong
        print_line(f"The install stopped on an unexpected error: {type(e).__name__}: {e}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
