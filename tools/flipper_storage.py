"""The install script's own file transfer to the Flipper Zero's card, over the USB console.

    from flipper_cli import find_port, open_cli
    from flipper_storage import Storage

    storage = Storage(open_cli(find_port()))
    storage.send_file("voice-heart.tar", "/ext/voice-heart.tar", progress)
    storage.extract("/ext/voice-heart.tar", "/ext", timeout=300)

Storage takes the console that flipper_cli.open_cli opened. It sends a file in chunks with the
console's `storage write_chunk`, a folder as its files and folders, unpacks a tar archive on the
device with `storage extract`, and runs the few other storage commands the install needs. What
the device says becomes one sentence: a StorageError holds the device's own error sentence and
the path it was about, or says that the connection was lost. The module imports only the
standard library, pyserial through flipper_cli, and flipper_cli.

Adapted from scripts/flipper/storage.py of the Momentum firmware (GPL-3): the same
`storage write_chunk` protocol, a Ready from the device and then the bytes, and the same error
sentences. What differs: the console is the one flipper_cli opens, there is no colorlog and no
progress bar of its own (the caller gets the progress), a read that gets nothing for 30 seconds
is a lost connection instead of a wait without end, and `storage extract` is added.
"""
import os
import posixpath
import re
import time

from flipper_cli import ANSI, PROMPT  # exits with one sentence when pyserial is missing

# The bytes of one `storage write_chunk`. The device takes a chunk of any size and appends it to
# the file, so this only sets how often the host waits for the device's prompt.
DEFAULT_CHUNK = 8192
# Seconds without a byte from the device in the middle of a reply before the connection is lost
IDLE_SECONDS = 30
# Two of the sentences after "Storage error: " (storage_error_get_desc in the firmware): a path
# that is not there says the first, and the second when a folder on the way is a file or the
# name is bad
NOT_EXIST = "file/dir not exist"
INVALID_NAME = "invalid name/path"

ERROR_LINE = re.compile(r"^Storage error: (.*)$", re.MULTILINE)
ENTRY_LINE = re.compile(r"^[DF] .+$")
# A path goes between double quotes, which have no escape, and the console's line editor acts on
# control characters (a line end ends the command, a tab completes it), so none can be in a path
UNSAFE_IN_PATH = re.compile(r'["\x00-\x1f\x7f]')


class StorageError(Exception):
    """What went wrong, as one sentence: the device's own error sentence and the path, or that
    the connection was lost."""


def _lost(why):
    """The StorageError for a console that is gone."""
    return StorageError(f"the connection was lost: {why}. Is the Flipper still plugged in?")


def _quoted(path):
    """The path as the console takes it, in double quotes; a StorageError for one it cannot take."""
    if UNSAFE_IN_PATH.search(path):
        raise StorageError(f"the console cannot take a quote or a control character in a path: {path!r}")
    return f'"{path}"'


def _error_sentence(text):
    """The sentence of the first "Storage error: ..." line in a reply, else None."""
    found = ERROR_LINE.search(text)
    return found.group(1).strip() if found else None


def _raise_error(text, path):
    """Raise a StorageError with the device's sentence and path if the reply has an error line."""
    sentence = _error_sentence(text)
    if sentence is not None:
        raise StorageError(f"{sentence}: {path}")


class Storage:
    """The card of a Flipper whose console is ser, a port opened by flipper_cli.open_cli.
    chunk_size: the bytes of each `storage write_chunk`. idle_timeout: the seconds the device may
    say nothing in the middle of a reply before the connection counts as lost."""

    def __init__(self, ser, chunk_size=DEFAULT_CHUNK):
        if chunk_size < 1:
            raise ValueError("chunk_size must be at least 1 byte")
        self.ser = ser
        self.chunk_size = chunk_size
        self.idle_timeout = IDLE_SECONDS
        self._buffer = bytearray()  # read from the port and not yet taken as a line

    # The console

    def _ask(self, line, timeout=None):
        """Send one command and return an iterator over the lines of its reply, the echo first,
        up to the prompt. What the device said before is not taken for the reply. timeout: the
        seconds the whole reply may take, else no limit."""
        self._buffer.clear()
        try:
            self.ser.reset_input_buffer()
            self.ser.write(line.encode() + b"\r")
        except OSError as e:  # pyserial's SerialException is one
            raise _lost(e) from e
        return self._reply(line, timeout)

    def _reply(self, line, timeout):
        """The lines of the reply to line as they arrive, without colour codes or the prompt."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            while (end := self._buffer.find(b"\r\n")) >= 0:
                text = bytes(self._buffer[:end])
                del self._buffer[: end + 2]
                yield ANSI.sub("", text.decode(errors="replace"))
            if self._buffer.endswith(PROMPT):
                text = bytes(self._buffer[: -len(PROMPT)])
                self._buffer.clear()
                if text:
                    yield ANSI.sub("", text.decode(errors="replace"))
                return
            self._fill(line, deadline, timeout)

    def _fill(self, line, deadline, timeout):
        """Wait for more bytes from the device. A StorageError when none come for idle_timeout
        seconds, or when the deadline of the command has passed."""
        quiet_until = time.monotonic() + self.idle_timeout
        while True:
            now = time.monotonic()
            if deadline is not None and now >= deadline:
                raise StorageError(f"the Flipper had not finished {line} after {timeout:g} seconds")
            try:
                data = self.ser.read(max(1, self.ser.in_waiting))
            except OSError as e:
                raise _lost(e) from e
            if data:
                self._buffer += data
                return
            if now >= quiet_until:
                raise _lost(f"the Flipper sent nothing for {self.idle_timeout:g} seconds")

    def command(self, line, timeout=30):
        """Send one console command and return its output without the echo, the prompt or colour
        codes. The device's own words, such as a "Storage error: ..." line, are in the output;
        the storage methods below turn them into a StorageError. timeout: the seconds the command
        may take before a StorageError says so."""
        lines = list(self._ask(line, timeout))
        if lines and lines[0].strip() == line.strip():
            lines = lines[1:]
        return "\n".join(lines).strip("\n")

    # The card

    def _stat(self, path):
        """What the device says of path: "Directory", "File, size: 12b" or the like, or None when
        there is no such path. Any other error is a StorageError."""
        text = self.command(f"storage stat {_quoted(path)}")
        if _error_sentence(text) in (NOT_EXIST, INVALID_NAME):
            return None
        _raise_error(text, path)
        return text

    def _is_dir(self, path):
        """Whether a folder is at path, or the card itself, which `storage stat` calls Storage."""
        found = self._stat(path)
        return found is not None and (found == "Directory" or found.startswith("Storage"))

    def exists(self, path):
        """Whether a file or folder is at path."""
        return self._stat(path) is not None

    def mkdir(self, path):
        """Make the folder at path, whose own folder must be there."""
        _raise_error(self.command(f"storage mkdir {_quoted(path)}"), path)

    def _make_path(self, path):
        """Make the folder at path and those of its folders that are not there."""
        missing = []
        while path not in ("", "/") and not self._is_dir(path):
            missing.append(path)
            path = posixpath.dirname(path)
        for folder in reversed(missing):
            self.mkdir(folder)

    def remove(self, path):
        """Remove the file at path, or the folder if it is empty."""
        _raise_error(self.command(f"storage remove {_quoted(path)}"), path)

    # Sending

    def send_file(self, local, remote, progress=None):
        """Send the file local to the card as remote, whose folder must be there; a file already
        at remote is replaced. progress(sent_bytes, total_bytes) is called after each chunk."""
        self._upload(local, remote, progress, 0, os.path.getsize(local))

    def send_tree(self, local_dir, remote_dir, progress=None):
        """Send the folder local_dir to the card as remote_dir, with its files and folders, the
        empty folders too, each folder's files before its subfolders and both sorted by name.
        The folders remote_dir itself needs are made. progress(sent_bytes, total_bytes) is called
        after each chunk and counts the bytes of the whole folder."""
        if not os.path.isdir(local_dir):  # os.walk would find nothing and send nothing, without a word
            raise FileNotFoundError(f"no folder {local_dir}")
        remote_dir = remote_dir.rstrip("/") or "/"
        steps = []  # (remote path, local file or None for a folder, size)
        total = 0
        for here, folders, names in os.walk(local_dir):
            folders.sort()
            relative = os.path.relpath(here, local_dir)
            remote_here = remote_dir if relative == "." else posixpath.join(remote_dir, *relative.split(os.sep))
            steps.append((remote_here, None, 0))
            for name in sorted(names):
                local = os.path.join(here, name)
                size = os.path.getsize(local)
                steps.append((posixpath.join(remote_here, name), local, size))
                total += size
        for remote, _, _ in steps:
            _quoted(remote)  # a name the console cannot take stops the folder before its first byte
        done = 0
        for remote, local, size in steps:
            if local is None:
                self._make_path(remote)
            else:
                self._upload(local, remote, progress, done, total)
                done += size

    def _upload(self, local, remote, progress, before, total):
        """Send one file in chunks. progress(before + sent_bytes, total) is called after each."""
        found = self._stat(remote)
        # A chunk is appended to the file, so a file that is there would stay in front of the new one
        if found is not None and found.startswith("File"):
            self.remove(remote)
        with open(local, "rb") as f:
            sent = 0
            data = f.read(self.chunk_size)
            while True:
                # An empty file is a chunk of no bytes, which makes the file and writes nothing
                self._write_chunk(remote, data)
                sent += len(data)
                if progress:
                    progress(before + sent, total)
                data = f.read(self.chunk_size)
                if not data:
                    break

    def _write_chunk(self, remote, data):
        """Append data to the file remote with one `storage write_chunk`: the command, the
        device's Ready, the bytes, then the device's prompt."""
        command = f"storage write_chunk {_quoted(remote)} {len(data)}"
        lines = self._ask(command)
        answer = ""
        for text in lines:
            if text.strip() and text.strip() != command:  # not the echo, nor a blank line
                answer = text.strip()
                break
        if answer != "Ready":
            rest = "\n".join(lines)  # to the prompt, so that the console stays in step
            _raise_error(f"{answer}\n{rest}", remote)
            raise StorageError(f"the Flipper did not say it was ready for {remote}, it said: {answer or 'nothing'}")
        try:
            self.ser.write(data)
        except OSError as e:
            raise _lost(e) from e
        _raise_error("\n".join(lines), remote)  # what it says after the bytes, such as a full card

    # Unpacking

    def extract(self, archive, dest, on_entry=None, *, timeout):
        """Unpack the tar archive on the card to dest with `storage extract` and return the number
        of entries it printed. on_entry(line) is called for each as it comes, with the line as the
        device prints it, "F name" for a file and "D name" for a folder. timeout: the seconds the
        whole extract may take. A StorageError when the device could not open or unpack the
        archive, or did not say that it unpacked it."""
        entries = 0
        opened = True
        unpacked = None
        for text in self._ask(f"storage extract {_quoted(archive)} {_quoted(dest)}", timeout):
            text = text.strip()
            if ENTRY_LINE.match(text):
                entries += 1
                if on_entry:
                    on_entry(text)
            elif text == "Failed to open archive":
                opened = False
            elif text.startswith("Decompression "):
                unpacked = text.startswith("Decompression success")
        if not opened:
            raise StorageError(f"the device could not open the archive: {archive}")
        if unpacked is None:
            raise StorageError(f"the device did not say that it unpacked the archive: {archive}")
        if not unpacked:
            raise StorageError(f"the device could not unpack the archive {archive} to {dest}, after {entries} entries")
        return entries
