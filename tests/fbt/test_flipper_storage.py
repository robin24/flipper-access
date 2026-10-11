#!/usr/bin/env python3
"""tools/flipper_storage.py, the install script's own file transfer, against a stand-in for the
device's console. The stand-in answers as the device's shell does: the echo of the command and a
line end, the command's output, then a line end and the prompt; storage write_chunk answers Ready
and takes the given number of bytes before the prompt. The checks: a file goes over in chunks of
the chunk size, with its progress, an empty file too, and a file already there is replaced; a
folder goes with the folders it needs; the device's error replies, before and after the data,
become a StorageError with the device's sentence and the path; exists, mkdir, remove and extract;
the paths the console cannot take; and a console that goes quiet, or whose cable is pulled, ends
in a StorageError that says the connection was lost, never in a serial exception. Needs pyserial.
Run from the project root: python3 tests/fbt/test_flipper_storage.py"""
import importlib.util
import os
import posixpath
import shlex
import sys
import tempfile

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
    print("skipped the storage checks: no pyserial")
    print("flipper storage: 0 of 0 checks passed")
    sys.exit(0)

import serial

import flipper_storage as fs

NOT_EXIST = "Storage error: file/dir not exist\r\n"
EXISTS = "Storage error: file/dir already exist\r\n"
NOT_READY = "Storage error: filesystem not ready\r\n"
FULL = "Storage error: internal error\r\n"
RED_NOT_FOUND = "\x1b[31mcould not find command `{}`, try `help`\x1b[0m\r\n"
INFO = "hardware_model         : Flipper Zero\r\nfirmware.version       : sonar-0.0.0\r\n"
EXTRACT_OK = (
    "Unpacking to /ext\r\n\tD voice\r\n\tF voice/a.wav\r\n\tF voice/b c.wav\r\n"
    "Decompression success in 4321 ticks \r\n"
)


class Device:
    """The device as the script sees it: the serial port, and the shell and card behind it."""

    def __init__(self, files=None, piece=0):
        self.out = bytearray()  # what the device has sent and the script has not read
        self.typed = bytearray()  # what the script has sent and the shell has not taken
        self.piece = piece  # at most this many bytes at a read, to split the replies; 0 for all
        self.files = {path: bytearray(data) for path, data in (files or {}).items()}
        self.dirs = {"/ext"}
        self.sent = []  # the commands, in order
        self.chunks = []  # the size each storage write_chunk asked for
        self.target = None  # the file the chunk goes to
        self.need = 0  # the bytes the chunk still wants
        self.card_full = False  # a write fails after its data
        self.not_ready = False  # no card: stat and mkdir say so
        self.quiet = None  # a reply stops: "silent" after a line, "partial" in a line, "unplugged" and the cable is out
        self.unplugged = False
        self.extract_output = EXTRACT_OK

    # The serial port
    @property
    def in_waiting(self):
        return min(len(self.out), self.piece) if self.piece else len(self.out)

    def read(self, size):
        if not self.out:
            if self.unplugged:
                raise serial.SerialException("device reports readiness to read but returned no data")
            return b""  # the port's time-out: nothing came
        if self.piece:
            size = min(size, self.piece)
        data = bytes(self.out[:size])
        del self.out[:size]
        return data

    def reset_input_buffer(self):
        self.out.clear()

    def write(self, data):
        if self.unplugged:
            raise serial.SerialException("write failed: [Errno 6] Device not configured")
        self.typed += data
        while self.typed:
            if self.need:
                take = bytes(self.typed[: self.need])
                del self.typed[: len(take)]
                self.files[self.target] += take
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

    # The shell
    def say(self, command, output):
        self.out += f"{command}\r\n{output}\r\n>: ".encode()

    def finish_chunk(self):
        self.out += (FULL if self.card_full else "").encode() + b"\r\n>: "

    def handle(self, command):
        self.sent.append(command)
        words = shlex.split(command)
        if self.quiet:
            # The reply stops: after a line, in the middle of a line, or with the cable pulled
            cut = "Unpacking" if self.quiet == "partial" else "Unpacking to /ext\r\n"
            self.out += f"{command}\r\n{cut}".encode()
            self.unplugged = self.quiet == "unplugged"
        elif words[:2] == ["storage", "write_chunk"]:
            path, size = words[2], int(words[3])
            if posixpath.dirname(path) not in self.dirs:
                self.say(command, NOT_EXIST)
                return
            self.chunks.append(size)
            self.files.setdefault(path, bytearray())
            self.target, self.need = path, size
            self.out += f"{command}\r\nReady\r\n".encode()
            if not size:
                self.finish_chunk()
        elif words[:2] == ["storage", "stat"]:
            path = words[2]
            if self.not_ready:
                self.say(command, NOT_READY)
            elif path == "/ext":
                self.say(command, "Storage, 7000000KiB total, 6000000KiB free\r\n")
            elif path in self.files:
                self.say(command, f"File, size: {len(self.files[path])}b\r\n")
            elif path in self.dirs:
                self.say(command, "Directory\r\n")
            else:
                self.say(command, NOT_EXIST)
        elif words[:2] == ["storage", "mkdir"]:
            path = words[2]
            if self.not_ready:
                self.say(command, NOT_READY)
            elif path in self.dirs or path in self.files:
                self.say(command, EXISTS)
            elif posixpath.dirname(path) not in self.dirs:
                self.say(command, NOT_EXIST)
            else:
                self.dirs.add(path)
                self.say(command, "")
        elif words[:2] == ["storage", "remove"]:
            path = words[2]
            if path in self.files:
                del self.files[path]
                self.say(command, "")
            else:
                self.say(command, NOT_EXIST)
        elif words[:2] == ["storage", "extract"]:
            self.say(command, self.extract_output)
        elif words == ["info", "device"]:
            self.say(command, INFO)
        else:
            self.say(command, RED_NOT_FOUND.format(words[0]))


def storage(device, chunk_size=fs.DEFAULT_CHUNK):
    """A Storage on the stand-in that gives up on a quiet device after a moment, not 30 seconds."""
    result = fs.Storage(device, chunk_size=chunk_size)
    result.idle_timeout = 0.5
    return result


def raised(fn, *args, **kwargs):
    """The exception fn raises, or None."""
    try:
        fn(*args, **kwargs)
    except Exception as e:
        return e
    return None


def says(error, *parts):
    """Is error a StorageError whose message holds every one of parts?"""
    return isinstance(error, fs.StorageError) and all(part in str(error) for part in parts)


def lost(error):
    """Is error a StorageError that says the connection was lost, not a serial exception?"""
    return isinstance(error, fs.StorageError) and str(error).startswith("the connection was lost")


def write(path, data):
    with open(path, "wb") as f:
        f.write(data)


check(fs.DEFAULT_CHUNK == 8192, f"the chunk size until the spike on the device sets it: {fs.DEFAULT_CHUNK}")

with tempfile.TemporaryDirectory() as tmp:
    # A file of 20,000 bytes goes over in chunks of 8,192, 8,192 and 3,616, and the bytes are the file's
    data = bytes(i % 251 for i in range(20000))
    big = os.path.join(tmp, "big.bin")
    write(big, data)
    device = Device()
    seen = []
    storage(device).send_file(big, "/ext/big.bin", lambda sent, total: seen.append((sent, total)))
    check(device.chunks == [8192, 8192, 3616], f"chunks of 8,192, 8,192 and 3,616: {device.chunks}")
    check(bytes(device.files["/ext/big.bin"]) == data, "the stand-in received the file's bytes")
    check(seen == [(8192, 20000), (16384, 20000), (20000, 20000)], f"progress after each chunk: {seen}")
    check(device.sent == ['storage stat "/ext/big.bin"'] + ['storage write_chunk "/ext/big.bin" %d' % n for n in device.chunks],
          f"a file that is not there is asked for, then written: {device.sent}")
    check(not device.out, "and the reply to the last chunk is read to the prompt")

    # The chunk size is the caller's
    device = Device()
    storage(device, chunk_size=10000).send_file(big, "/ext/big.bin")
    check(device.chunks == [10000, 10000], f"a chunk size of 10,000: {device.chunks}")
    check(bytes(device.files["/ext/big.bin"]) == data, "the bytes are the file's, and no progress function is fine")

    # A file already there goes first, since a chunk is appended to the file
    device = Device(files={"/ext/big.bin": b"the bytes of an earlier try"})
    storage(device).send_file(big, "/ext/big.bin")
    check(bytes(device.files["/ext/big.bin"]) == data, "a file already there is replaced, not appended to")
    check(device.sent[:2] == ['storage stat "/ext/big.bin"', 'storage remove "/ext/big.bin"'],
          f"it is removed before the first chunk: {device.sent[:2]}")

    # A file with nothing in it is made, with a chunk of no bytes
    empty = os.path.join(tmp, "empty.txt")
    write(empty, b"")
    device = Device()
    seen = []
    storage(device).send_file(empty, "/ext/empty.txt", lambda sent, total: seen.append((sent, total)))
    check(device.chunks == [0] and device.files.get("/ext/empty.txt") == b"", f"an empty file is made: {device.chunks}")
    check(seen == [(0, 0)], f"and reported once: {seen}")

    # The device's error before the data: its sentence and the path, and the console stays in step
    device = Device()
    s = storage(device)
    error = raised(s.send_file, big, "/ext/missing/big.bin")
    check(says(error, "file/dir not exist", "/ext/missing/big.bin"), f"a folder that is not there: {error!r}")
    check(not str(error).startswith("Storage error"), f"the sentence is the device's, not its line: {error}")
    check(not device.out and s.exists("/ext") is True, "the console is in step after the error")

    # The device's error after the data, such as a full card
    device = Device()
    device.card_full = True
    s = storage(device)
    error = raised(s.send_file, big, "/ext/big.bin")
    check(says(error, "internal error", "/ext/big.bin"), f"an error after the data: {error!r}")
    device.card_full = False
    check(not device.out and s.exists("/ext") is True, "and the console is in step after it")

    # A device that answers a chunk with something other than Ready
    device = Device()
    s = storage(device)
    device.handle = lambda command: device.say(command, "Usage:\r\nstorage <cmd> <path> <args>\r\n")
    error = raised(s.send_file, big, "/ext/big.bin")
    check(isinstance(error, fs.StorageError) and "/ext/big.bin" in str(error) and "Usage:" in str(error),
          f"an answer that is not Ready: {error!r}")

    # A folder goes with the folders it needs, in order, and the progress counts the whole
    tree = os.path.join(tmp, "pkg")
    os.makedirs(os.path.join(tree, "sub", "deeper"))
    os.makedirs(os.path.join(tree, "zzz"))
    contents = {
        "a.bin": bytes(i % 7 for i in range(10000)),
        "empty.txt": b"",
        "sub/c.bin": bytes(i % 11 for i in range(5000)),
        "zzz/d.bin": b"d",
    }
    for name, body in contents.items():
        write(os.path.join(tree, *name.split("/")), body)
    device = Device()
    seen = []
    storage(device, chunk_size=4096).send_tree(tree, "/ext/update/pkg", lambda sent, total: seen.append((sent, total)))
    mkdirs = [c for c in device.sent if c.startswith("storage mkdir")]
    check(mkdirs == ['storage mkdir "/ext/update"', 'storage mkdir "/ext/update/pkg"', 'storage mkdir "/ext/update/pkg/sub"',
                     'storage mkdir "/ext/update/pkg/sub/deeper"', 'storage mkdir "/ext/update/pkg/zzz"'],
          f"the folders, parents first, empty ones too: {mkdirs}")
    check({p: bytes(b) for p, b in device.files.items()} == {"/ext/update/pkg/" + n: b for n, b in contents.items()},
          "every file arrived under the remote folder, with its bytes")
    check(seen == [(4096, 15001), (8192, 15001), (10000, 15001), (10000, 15001), (14096, 15001), (15000, 15001), (15001, 15001)],
          f"progress counts the bytes of the whole folder: {seen}")
    writes = [c.split('"')[1] for c in device.sent if c.startswith("storage write_chunk")]
    check(list(dict.fromkeys(writes)) == ["/ext/update/pkg/" + n for n in ("a.bin", "empty.txt", "sub/c.bin", "zzz/d.bin")],
          f"the files go in sorted order, a folder's own files before its subfolders': {writes}")

    # A folder sent again: the folders are there, the files are replaced
    count = len(device.sent)
    storage(device, chunk_size=4096).send_tree(tree, "/ext/update/pkg")
    check(not [c for c in device.sent[count:] if c.startswith("storage mkdir")], "a second time makes no folder again")
    check({p: bytes(b) for p, b in device.files.items()} == {"/ext/update/pkg/" + n: b for n, b in contents.items()},
          "and the files are the same, not doubled")

    # A folder that is not there is an error, not a send of nothing
    device = Device()
    error = raised(storage(device).send_tree, os.path.join(tmp, "no-such-folder"), "/ext/x")
    check(isinstance(error, FileNotFoundError) and not device.sent, f"a folder that is not there: {error!r}, sent {device.sent}")

    # A name the console cannot take stops the folder before anything is sent
    odd = os.path.join(tmp, "odd")
    os.mkdir(odd)
    try:
        write(os.path.join(odd, 'say "hi".txt'), b"x")
    except OSError:
        pass  # a file system that does not allow it cannot have the problem
    else:
        device = Device()
        error = raised(storage(device).send_tree, odd, "/ext/odd")
        check(says(error, 'say "hi".txt') and not device.sent, f"a quote in a name: {error!r}, sent {device.sent}")

# mkdir, remove and exists
device = Device(files={"/ext/a.txt": b"abc"})
s = storage(device)
check(s.mkdir("/ext/update") is None and "/ext/update" in device.dirs, "mkdir makes the folder")
error = raised(s.mkdir, "/ext/update")
check(says(error, "file/dir already exist", "/ext/update"), f"mkdir of a folder that is there: {error!r}")
error = raised(s.mkdir, "/ext/no/such")
check(says(error, "file/dir not exist", "/ext/no/such"), f"mkdir without its parent: {error!r}")
check(s.remove("/ext/a.txt") is None and "/ext/a.txt" not in device.files, "remove takes the file away")
error = raised(s.remove, "/ext/a.txt")
check(says(error, "file/dir not exist", "/ext/a.txt"), f"remove of what is not there: {error!r}")
check(s.exists("/ext/update") is True, "exists: a folder")
device.files["/ext/b.txt"] = bytearray(b"b")
check(s.exists("/ext/b.txt") is True, "exists: a file, from its stat reply")
check(s.exists("/ext/nothing") is False, "exists: false for file/dir not exist")
device.not_ready = True
error = raised(s.exists, "/ext/b.txt")
check(says(error, "filesystem not ready", "/ext/b.txt"), f"exists on a card that is not there is an error, not false: {error!r}")

# command: the output without the echo, the prompt and the colour codes
device = Device()
s = storage(device)
check(s.command("info device") == INFO.replace("\r\n", "\n").strip("\n"), f"the output of a command: {s.command('info device')!r}")
check(s.command("nosuch") == "could not find command `nosuch`, try `help`", f"colour codes are gone: {s.command('nosuch')!r}")
check(s.command('storage mkdir "/ext/x"') == "", "a command without output gives an empty string")
device.out += b"leftover of an earlier reply\r\n>: "
check(s.command("info device").startswith("hardware_model"), "bytes left from before a command are not taken for its reply")

# Replies that come in small pieces, the prompt split too
device = Device(piece=3)
s = storage(device)
check(s.command("info device").endswith("sonar-0.0.0"), "a reply that comes three bytes at a time")
small = b"0123456789"
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "small.bin")
    write(path, small)
    s.send_file(path, "/ext/small.bin")
check(bytes(device.files["/ext/small.bin"]) == small, "and a file sent over such a console")

# extract: the entries are counted, and reported as they come
for piece in (0, 4):
    device = Device(piece=piece)
    s = storage(device)
    entries = []
    pending = []

    def on_entry(line):
        entries.append(line)
        pending.append(len(device.out))

    count = s.extract("/ext/pack.tar", "/ext", on_entry, timeout=5)
    check(count == 3, f"extract counts the entry lines: {count}")
    check(entries == ["D voice", "F voice/a.wav", "F voice/b c.wav"], f"on_entry once per line, as printed: {entries}")
    check(device.sent == ['storage extract "/ext/pack.tar" "/ext"'], f"the command: {device.sent}")
    if piece:
        check(pending and pending[0] > 0, f"the first entry is reported while the device is still talking: {pending}")
count = storage(Device()).extract("/ext/pack.tar", "/ext", timeout=5)
check(count == 3, f"extract without on_entry: {count}")

device = Device()
s = storage(device)
device.extract_output = "Failed to open archive\r\n"
error = raised(s.extract, "/ext/nope.tar", "/ext", timeout=5)
check(says(error, "open", "/ext/nope.tar"), f"an archive that does not open: {error!r}")
device.extract_output = "Unpacking to /ext\r\n\tF a.wav\r\nDecompression failed in 99 ticks \r\n"
entries = []
error = raised(s.extract, "/ext/pack.tar", "/ext", entries.append, timeout=5)
check(says(error, "/ext/pack.tar", "/ext"), f"an extract that fails: {error!r}")
check(entries == ["F a.wav"], f"the entries before the failure were reported: {entries}")
device.extract_output = "Usage:\r\nstorage <cmd> <path> <args>\r\n"
error = raised(s.extract, "/ext/pack.tar", "/ext", timeout=5)
check(says(error, "did not say", "/ext/pack.tar"), f"a reply that never says it unpacked: {error!r}")
check(not device.out and s.exists("/ext") is True, "the console is in step after a failed extract")

# A console that goes quiet, or whose cable is pulled, is a lost connection
device = Device()
device.quiet = "silent"
s = storage(device)
s.idle_timeout = 0.2
error = raised(s.command, "info device")
check(lost(error), f"a console that goes quiet mid-reply: {error!r}")
device = Device()
device.quiet = "partial"
s = storage(device)
s.idle_timeout = 0.2
error = raised(s.command, "info device")
check(lost(error), f"a console that stops in the middle of a line: {error!r}")
device.quiet = None
device.out.clear()
check(s.command("info device").startswith("hardware_model"), "and what it had said of that line is not in the next reply")
device = Device()
device.quiet = "unplugged"
s = storage(device)
error = raised(s.command, "info device")
check(lost(error) and not isinstance(error, serial.SerialException), f"a stream that ends mid-reply: {error!r}")
error = raised(s.command, "info device")
check(lost(error), f"a write on a port whose cable is out: {error!r}")
device = Device()
device.unplugged = True
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "small.bin")
    write(path, small)
    error = raised(storage(device).send_file, path, "/ext/small.bin")
check(lost(error), f"a file sent to a port whose cable is out: {error!r}")

# A command that goes on for longer than its time
device = Device()
device.quiet = "silent"
s = storage(device)
s.idle_timeout = 5
error = raised(s.command, "info device", timeout=0.2)
check(isinstance(error, fs.StorageError) and "info device" in str(error) and "0.2" in str(error),
      f"a command that does not finish in its time: {error!r}")
error = raised(s.extract, "/ext/pack.tar", "/ext", timeout=0.2)
check(isinstance(error, fs.StorageError) and "/ext/pack.tar" in str(error), f"and an extract: {error!r}")

# Paths the console cannot take are refused before they are sent
device = Device()
s = storage(device)
for bad in ('/ext/say "hi"', "/ext/a\nstorage remove /ext", "/ext/tab\there", "/ext/\x03"):
    error = raised(s.mkdir, bad)
    check(isinstance(error, fs.StorageError), f"{bad!r} is refused: {error!r}")
check(not device.sent, f"and nothing was sent: {device.sent}")
check(isinstance(raised(fs.Storage, Device(), chunk_size=0), ValueError), "a chunk size of nothing")

print(f"flipper storage: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
