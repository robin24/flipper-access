# The install protocol

This document describes what `tools/install.py` says to the Flipper Zero over its USB console, in
the order it says it, and how it reads each reply. It is written for a later desktop app that does
the same install without Python. The script and its helper `tools/flipper_storage.py` are the source
of truth. Where this document and the code differ, the code is right and this document is to be
corrected.

The script uses only console commands that the official firmware, Momentum and Sonar all have built
in, so a blank card works too. The one exception is the `sr voice` command, which only Sonar has.
The script sends no other commands than the ones listed here. In particular it never sends `loader`,
`power`, `input`, `sysctl` or `sr voice use`, and a test checks that.

## The console

### Opening it

The Flipper shows up as a serial port with the USB vendor id 0483 and product id 5740, which is the
id of the virtual COM port in STMicroelectronics USB code. Other boards share it, so a port whose
name, manufacturer or description mentions Flipper comes first. On a Mac, a port named like
`/dev/cu.usbmodemflip_<name>` is also taken when the listing lacks the id. The user may name the
port, and the environment variable `FLIPPER_PORT` does the same.

When there is no port, the Flipper may be unplugged, locked with its PIN (the lock turns the
console's USB off), in the updater, or held by qFlipper. The script says all four in one sentence.

The port is opened for one program alone, at 230400 baud with a read time-out of 0.1 seconds. When
qFlipper or another tool has it, the open fails at once, and the script says so instead of waiting,
in one sentence that ends by saying to close qFlipper or any other tool that uses the port. When the
system refuses the open itself, with EACCES or EPERM, the sentence says instead that this computer's
user may not use the port, and that on Linux the user is to be added to the group that owns it,
dialout on Debian, Ubuntu and Fedora and uucp on Arch, and to log in again. On those systems the
port belongs to root and that group, and a desktop user is not in it by default.

Right after opening, the script starts a fresh console session. It drops the DTR line of the port,
waits 0.5 seconds, throws away everything that arrived, and raises DTR again. The Flipper's console
ends its session when DTR drops and starts a new one when DTR rises, and the new session prints the
welcome banner and then the prompt. This is in the firmware's `cli_vcp.c`. The script reads
everything up to that prompt and throws it away, for at most 5 seconds, so that no part of the
banner is taken for the reply to the first command. When no prompt comes, it sends one carriage
return and waits for a prompt for at most 2 more seconds. When none comes then either, the open
fails with one sentence that names the port and says to restart the Flipper by holding Left and Back
together for five seconds. A port that goes away during all this also fails the open, with one
sentence that says to check that the Flipper is still plugged in.

The script does this on every open of the port, and so do the other tools that open the console
the same way, such as `tools/card_prune.py`. On 2026-10-11, after about ten idle hours, Robin's
Flipper answered nothing to a fresh open of its port: no echo, no prompt, and every command timed
out, though the Flipper itself worked. Dropping DTR for half a second and raising it again made it
print its banner and its prompt, and commands worked again.

### Sending a command and reading the reply

The prompt is the three characters greater-than, colon and space.

To send a command, the script first throws away any input that has not been read yet. Then it sends
the command text followed by one carriage return and no line feed.

The Flipper answers with the echo of the command, a carriage return and line feed, the output of the
command with each line ended by a carriage return and line feed, and then the prompt. The script
reads the reply like this:

- It removes the colour codes, which are an escape character, an opening square bracket, digits and
  semicolons, and one letter.
- It splits the reply into lines at the carriage return and line feed pairs.
- Text after the last line end and before the prompt counts as one more line when it is not empty.
- It drops the first line when it equals the command, which is the echo.
- The reply is over when the bytes received end in the prompt. A command with no output has an empty
  reply.

All text is decoded as UTF-8, with unreadable bytes replaced.

### Time limits

Every command has a limit for the whole reply. The default is 30 seconds. The listing of a folder
gets 60 seconds. `update backup`, `update install` and `update restore` get 120 seconds. `storage
extract` gets a limit worked out from the size of the pack, which is given with the unpacking below.

Independently of that, a reply that goes quiet in the middle for 30 seconds counts as a lost
connection. While the script waits for the Flipper to come back after an update, the quiet limit is
5 seconds instead, because a console that has just come back may say nothing at first. The same 5
seconds hold while the script asks whether the Flipper sees the card after it was put back, since
the answer to `storage stat` comes at once.

A read or write that fails on the port also means that the connection was lost. This happens when
the cable is pulled or the Flipper restarts. The sentence for a lost connection says to check that
the Flipper is still plugged in.

When the limit for a whole reply passes, the Flipper may still deliver its reply later, and the
connection is out of step with the commands. The script then does not use it for more commands, and
neither does it after a lost connection. A desktop app should do the same: close the port, and open
it again if it needs to go on.

### Errors

A command that fails prints a line that starts with `Storage error: ` followed by a sentence. The
sentences that the script knows, from the firmware's `filesystem_api.c`, are these:

- `file/dir not exist` and `invalid name/path`: the path is not there.
- `file/dir already exist`: the folder that is to be made is there already.
- `access denied`: for example, removing a folder that still has something in it.
- `internal error`. It is also the reply to a storage command while the microSD card is out of
  its slot: on 2026-10-11 Robin's Flipper answered `storage stat` with `Storage error: internal
  error` while its card was out.
- `filesystem not ready`, the firmware's sentence for a storage that is not ready.
- `invalid parameter`, `function not implemented` and `file is already open`.

The script turns an error line into one sentence for the user, made of the Flipper's sentence and
the path the command was about. A write that fails, such as one to a full card, prints its error
line after the bytes were sent.

### An application open on the Flipper

A command that needs the Flipper's loader is refused while an application is open on the Flipper.
Of the commands that the script sends, these are `update backup`, `update install` and `update
restore`. The firmware marks the `storage`, `info` and `sr` commands as safe to run beside an
application, so an open application does not stop them. The refusal is one line in red, with no
`Result` line, and then the prompt comes back. This is in the firmware's `cli_shell.c`:

```
this command cannot be run while an application is open
```

When a reply holds this sentence, the script stops, and its sentence says so and tells the user
what to do, which depends on the firmware that runs at that moment, as `info device` gave it.
When it is Sonar, whose reader says Home screen on the home screen, the user is told to press Back
on the Flipper until it says Home screen. Other firmware says nothing, so the user is told to
press Back on the Flipper a few times to reach the home screen. Either way, the sentence ends by
saying to run the script again.

### Paths

A path goes between double quotes in every `storage` command. The console has no way to escape a
quote, and its line editor acts on control characters: a line end ends the command and a tab
completes it. So the script refuses any path with a double quote or a control character, which is a
character below 32 or the character 127, before it sends anything.

The `update` commands take their path without quotes.

### Reading a path

```
storage stat "<path>"
```

The reply is `Directory` for a folder, `File, size: <n>b` for a file, and for the card itself,
`/ext`, `Storage, <n>KiB total, <n>KiB free`. A path that is not there gives an error line with
`file/dir not exist` or `invalid name/path`, and the script reads both as "no such file or folder".
Any other error is a failure.

Folders are listed with `storage list`:

```
storage list "<folder>"
```

Each output line is a tab, `[D] ` and a name for a folder, or a tab, `[F] `, a name, a space and the
size, such as `123b`, for a file. A folder with nothing in it prints the line `Empty`, which the
script ignores. An error line `file/dir not exist` means that there is no such folder, and the
script reads that as a folder with nothing in it.

A file or an empty folder is removed with this command. The console has no recursive remove, and a
folder that holds something gives `access denied`:

```
storage remove "<path>"
```

## Reading `info device`

The command is:

```
info device
```

Each output line is a key padded with spaces, a colon, a space and a value, as in `firmware.version
: sonar-0.1.0`. The script splits at the first colon, trims both sides, and keeps the line when the
key is not empty and has no space in it. A value may hold colons, such as a web address.

These keys are used:

- `hardware.name`: the name of the Flipper, such as R0skie, for the sentence that says which Flipper
  was found.
- `firmware.origin.fork`: `Sonar` for Sonar, `Momentum` for Momentum, `Official` for the official
  firmware. Sonar is recognised by this key alone.
- `firmware.version`: for example `sonar-0.1.0` for a release, `1.4.3` for the official firmware,
  and `mntm-dev` for any build that is not on a tag.
- `firmware.commit.hash`: eight hexadecimal digits.
- `firmware.commit.dirty`: `true` or `false`.
- `firmware.api.major` and `firmware.api.minor`: the API version is the two joined by a dot, such as
  `87.3`.
- `system.boot`: `0` in a normal boot. The wait after an update uses it, as described below.

A missing key is read as empty, except `system.boot`, which is read as `0` when it is missing.

## The order of the install

In short:

1. Check the files that were given. The Flipper is not touched yet.
2. Open the console and read `info device`.
3. When a backup on the card is to be restored, check that it is there.
4. Ask the questions, unless `--yes` was given.
5. Make the backup with `update backup`.
6. Put the voice on the card, over USB or through a card reader.
7. Send the update package and start it with `update install`.
8. Wait for the Flipper to come back, read `info device` again, and compare.
9. Restore the backup, when that was asked.
10. Remove the older update packages.

The voice packs, the update package and the restore are each optional, and the script needs at
least one of them. A step whose option was not given is skipped, and so are the steps that belong
to it: the wait, the comparison and the removal of older packages need an update package. The
sections below take the steps in this order.

### Before the Flipper is touched

The script checks every file it was given first, so that a wrong file is refused before the Flipper
is changed:

- `release.json` must be JSON and must name a non-empty `firmware_version` and `firmware_commit`.
- A voice pack must be a plain, uncompressed tar archive that is not empty and holds only the folder
  `sr` and plain files and folders below it, with no `..` in any name.
- A backup to restore from the computer must exist as a file.
- An update package is either a folder or a `.tgz` file. A `.tgz` is unpacked into a temporary
  folder on the computer, taking only plain files and folders whose real paths stay inside that
  folder. It must hold exactly one folder, and that folder must hold `update.fuf`. When
  `release.json` is given, the folder must be named `f7-update-<firmware_version>`.

### The console and the first `info device`

The console is opened as described above, and then the command is sent:

```
info device
```

The script says which Flipper, firmware and version it found. A build that is not on a tag has the
version `mntm-dev`, which says nothing, so its commit is named too. From here on the script knows
whether Sonar runs, which matters for the `sr voice` commands below.

A console can give its prompt on the open and then finish no command. A run that was stopped with
Ctrl-C most often stops inside a `storage write_chunk` or a `storage extract`, and the Flipper's
shell then still waits for the rest of it; on 2026-10-11 the new session's banner came after the
DTR reset, but no command finished until the Flipper was restarted. So when this first command
takes longer than its limit, or the connection is lost, the script's sentence ends by saying to
restart the Flipper by holding Left and Back together for five seconds and to run the script
again. The sentence for a run stopped with Ctrl-C says that a run again starts over, and that the
Flipper is to be restarted the same way if it does not answer on that run.

### The backup to restore from, when it is on the card

This is only done when the user asked to restore from a path that starts with `/ext/`. The script
checks that the file is there:

```
storage stat "<path>"
```

An error that says the path is not there stops the script before anything is changed.

### The questions

Without `--yes`, the script asks before it changes anything. The first question says what will
happen and wants yes or no. Enter alone means yes. When a voice pack was given, a second question
asks which way the voice goes. Enter alone means the card reader:

```
Copy the voice through a card reader (faster) or over USB? [R/u]
```

An answer that starts with R means the card reader and one that starts with U means USB. Anything
else is asked again. With `--yes`, nothing is asked and the voice goes over USB. When no one can
answer because the input has ended, nothing is changed at the first question, and the voice goes
over USB at the second. The card reader way then asks the user to press Enter twice: once the card
is in the computer's card reader, and once it is back in the Flipper. Between the two it asks one
more question, whether to copy the voice onto the card it found, and Enter alone means yes there
too. All three are described below.

### The backup

The name is `/ext/backup-<date>.tar`, with the date of the day as `YYYY-MM-DD`. A backup is never
overwritten: while a file of that name exists, the script tries `backup-<date>-2.tar`,
`backup-<date>-3.tar` and so on. Each try is one command:

```
storage stat "/ext/backup-<date>.tar"
```

This is the install's first command on the card. A Flipper without a card, or with one it cannot
read, answers it with `internal error` or `filesystem not ready`, and the script's sentence then
adds to check that a microSD card, formatted on the Flipper, is in the Flipper. Any other answer
gets no advice, `access denied` included: a stat never fails because a card is full, and the device
also gives `access denied` for removing a folder that still has something in it.

The first name for which the path is not there is used:

```
update backup /ext/backup-<date>.tar
```

The reply starts with a line `Backup /int to '<path>'` and ends with `Result: OK` or `Result: FAIL`.
The script counts the backup as made when `Result: OK` appears anywhere in the reply. When the reply
has `Result: FAIL`, it says that the Flipper said that it failed. Otherwise it quotes the last line
of the reply. A full card makes the backup fail, so after a `Result: FAIL` of the backup, and of no
other command, the sentence adds, after a semicolon, that a full card can cause this and to check the
card's free space.

### The voice over USB

This is done for each voice pack, in the order given. The pack is sent to the card as one file,
unpacked on the Flipper, and removed again.

First the file is sent to `/ext/<name of the pack file>` in chunks, as the next section describes.

When Sonar runs, its voice is turned off for the unpacking, so that its reader holds no clip open
that the unpacking replaces. The number is the length of the mute in seconds. It is the size of the
pack in megabytes (1,048,576 bytes each) times 13, rounded up, and at least 1 and at most 3600,
which is the longest that the command takes:

```
sr voice off <seconds>
```

The mute ends by itself after that time, so it ends even when the script dies. The reply is not
read. From the official firmware and from Momentum, no `sr` command is sent at all.

Then the unpacking:

```
storage extract "/ext/<name of the pack file>" "/ext"
```

The reply is read line by line as it arrives:

- The first line is `Unpacking to /ext`.
- Then comes one line for each entry that is unpacked: a tab, the letter `D` for a folder or `F` for
  a file, a space and the name. The script strips the line and counts it as an entry when it is one
  of those letters, a space and at least one more character. The count is compared with the number
  of entries in the pack, which the script has from the tar headers on the computer, to say how far
  the unpacking is.
- The last line is `Decompression success in <n> ticks ` when it worked, and `Decompression failed
  in <n> ticks ` when it did not. The script reads whether the line starts with `Decompression
  success`.
- When the archive cannot be opened, the only line is `Failed to open archive`.

The script reports an error when the archive could not be opened, when no `Decompression` line came,
and when the line did not say success. In the last case the error says how many entries were
unpacked before the failure.

The limit for the whole reply is the larger of 600 seconds and twice the size of the pack in
megabytes times 13, rounded up. The limit of 30 quiet seconds applies as well. The device prints a
line for each entry, and the unpacking of the heart pack in the spike did not reach it.

The unpacking overwrites the clips that are there and keeps the folders, so running the install
again is safe.

When Sonar runs, the voice is turned on again afterwards, and also after an unpacking that failed,
as long as the console is still in step:

```
sr voice on
```

Finally the pack file is removed from the card:

```
storage remove "/ext/<name of the pack file>"
```

### Sending a file in chunks

This is how every file reaches the card: the voice pack, the files of the update package, the backup
to restore from the computer, and the marker of the card reader way. The command that sends the
bytes is `storage write_chunk`. The device appends the bytes to the file, and makes the file when it
is not there.

First the script looks at the target:

```
storage stat "<remote path>"
```

When the reply starts with `File`, the file is removed first, because the chunks are appended and
the old bytes would stay in front of the new ones:

```
storage remove "<remote path>"
```

Then the file is read in chunks of 32,768 bytes, which is 32 KB. The size only decides how often the
computer waits for the prompt, since the device takes a chunk of any size. The measurements in
`docs/measurements/2026-10-11-transfer-spike.txt` show that 32 KB is as fast as anything larger, and
that 8 KB takes a quarter longer. For each chunk the command is this, where the number is the length
of the chunk in bytes:

```
storage write_chunk "<remote path>" <number of bytes>
```

The exchange for one chunk has these steps:

1. The script sends the command.
2. The Flipper echoes it and answers with a line that says only `Ready`. The script skips the echo
   and empty lines, and takes the first other line as the answer. It must be `Ready`. When it is
   not, the script reads on to the prompt and reports a `Storage error` line if there is one. When
   there is none, it reports that the Flipper did not say it was ready, and what it said instead.
3. Only after `Ready`, the script sends exactly that number of raw bytes, with nothing added to
   them.
4. The Flipper takes the bytes, writes them, and prints the prompt. The script reads up to the
   prompt, and reports a `Storage error` line if one is there.

An empty file is sent as one chunk of 0 bytes. The device then makes the file and takes no bytes.
The exchange is the same, with nothing sent in step 3.

A failed write leaves up to the rest of the chunk in the console as typed input, so the script ends
the install at the first error.

A whole folder is sent file by file. For the folder itself and for each folder inside it, the script
makes sure that the folder exists. It looks with `storage stat` at the folder, then at its parent,
and so on upwards until it finds a folder, which is a reply of `Directory` or one that starts with
`Storage`. Then it makes the missing folders from the outermost inwards:

```
storage mkdir "<folder path>"
```

A folder is made before its files. Its files come next, sorted by name, and then its subfolders,
sorted by name, each in the same way. The empty folders are made too. The script checks that every
path can be quoted before it sends the first byte.

### The voice through a card reader

This takes the place of the voice over USB, at the same position in the order. It is faster, because
the card's writes limit the USB way. It needs a card reader on the computer, and the user moves the
card. The script says each step on its own line, and it asks the user to press Enter after each move
of the card, and whether to copy the voice onto the card it found. No clock runs while the user
moves the card. When something fails on this way, the
script stops with one sentence that says what to do. It never sends the voice over USB instead by
itself.

1. A marker is written to the card over the console. It is an empty file named like this, where the
   eight hexadecimal digits are random. This is the chunked write of the previous section, with a
   chunk of 0 bytes: the device says `Ready`, takes no bytes, and has made the empty file. First the
   script looks at the name:

   ```
   storage stat "/ext/.sonar-install-<8 hex digits>"
   ```

   Then it makes the file:

   ```
   storage write_chunk "/ext/.sonar-install-<8 hex digits>" 0
   ```

2. The script closes the console. It opens a new one only after the card is back in the Flipper, as
   step 14 describes. On 2026-10-11, with a console session open while the card went back into the
   Flipper, the `storage stat` that found the file took 0.67 seconds, and the next one, a second
   later, lost the connection: the Flipper's USB port vanished and stayed away for about ten
   minutes, without a restart. A faulty USB cable was found to be the cause, and with another cable
   the Flipper saw the card at once on 2026-10-12. The script keeps the console closed while the
   card is out, and it keeps waiting for a port that vanishes, since any loose cable does the same.

3. The script tells the user to leave the Flipper plugged in and unlocked while its card is out.
   The Flipper must not lock itself meanwhile, because the console of a Flipper that is locked with
   its PIN is off. Then it asks, and waits for Enter:

   ```
   Take the microSD card out of the Flipper and put it into this computer's card reader, then press Enter.
   ```

4. After Enter, the script looks for the card every 2 seconds, for at most 30 seconds, since a Mac
   mounts a card within a few seconds. The constant that holds this time is `CARD_LOOK_SECONDS`. On
   each look it lists the mounted volumes:
   - On macOS, every folder that matches `/Volumes/*`.
   - On Linux, every folder that matches `/media/<user name>/*` or `/run/media/<user name>/*`.
   - On Windows, the drive letters D to Z that exist, as `D:\` and so on.

   The card is the first volume that holds a file named `.sonar-install-<8 hex digits>`, with the
   digits that were written. A folder of that name does not count.

5. When no card was found in time, the script stops with one sentence. It says that no drive with
   the marker file turned up within 30 seconds, to put the card back into the Flipper and run the
   script again, and to answer U for USB if the computer does not show the card. The marker stays
   on the card then, and the next run through a card reader removes it, as step 10 describes.

6. When the card was found, the script first asks the system whether it mounted the volume
   read-only, before it writes anything. On macOS and Linux this is the flag `ST_RDONLY` that
   `statvfs` gives for the volume. A microSD adapter whose lock slider is down makes the computer
   mount the card read-only, as it did on 2026-10-11. The script then stops with one sentence: the
   card is read-only on this computer; on a microSD adapter, push the lock slider up, towards the
   contacts, put the card back into the Flipper, and run the script again. Windows has no `statvfs`,
   so there the script cannot tell, and the first write that fails gives the sentence of step 9
   instead.

7. When the volume takes writes, the script says which card it found and asks whether to copy the
   voice onto it, before it writes anything to it. This is one line, with the answer after it. Enter
   alone means yes:

   ```
   Found the card "Flipper SD" at /Volumes/Flipper SD, 64.0 gigabytes with 60.1 gigabytes free, holding the marker this run wrote through the Flipper. Copy the voice onto it? [Y/n]
   ```

   The line has these parts:
   - The name, in quotation marks, is the volume's own. On macOS and on Linux it is the last part
     of the mount path. On Windows it is the drive's label, which the script reads with
     `GetVolumeInformationW` through `ctypes`, a module of the standard library that the script
     loads only on Windows. When the volume has no name, or the label cannot be read, the script
     leaves the name out and the line says only the drive, as in `Found the card at D:\, ...`.
   - The path is where the computer mounted the card, such as `/Volumes/Flipper SD` or `D:\`.
   - The size and the free space come from `shutil.disk_usage` for the volume. From one gigabyte up
     they are said in gigabytes with one decimal and thousands commas. The gigabyte is 1,000,000,000
     bytes, as a card's label and the Finder count it, so a card sold as 64 gigabytes reads about 64
     gigabytes, a little less once it is formatted. Less than that is said in megabytes, as the size
     of the update package is. When the system does not give the sizes, the script leaves them out
     and the question is still asked.
   - The marker is the file of step 1, which only this card holds. A drive without it is never
     taken, so a wrong card cannot be written to. The question is there for the user, who cannot see
     which drive was found.

   The script asks through the same function as its other questions. That function gives no answer
   when the input has ended. The answers are these:
   - Enter alone, `y` or `yes`, in any case and with spaces round them: the script goes on with
     step 8.
   - `n` or `no`, in the same way: nothing is written to the card. The script ejects it, as step 12
     describes, which writes no file, and stops with one sentence and the exit code 1: "You
     answered no, so nothing was copied to the card; put the card back into the Flipper and run this
     script again." The marker of this run stays on the card, and the next run through a card reader
     removes it, as step 10 describes.
   - Any other answer: the script says "Answer Y for yes or N for no." and asks again, with only the
     end of the line, `Copy the voice onto it? [Y/n]`, since the computer's screen reader would read
     the whole line aloud again. This repeats until the answer is one of the others.
   - No answer, because the input has ended: the same as no, with the sentence starting "No answer
     came" instead of "You answered no".

   The read-only check of step 6 comes first, so a card that is read-only is refused without being
   asked about.

8. Every entry of every pack is checked before any is written. An entry must be a plain file or a
   folder, and the real path of where it would be written, with links and `..` resolved, must stay
   inside the real path of the volume. This also holds for the names that Windows reads
   differently, those with a drive letter such as `C:\x` or with backslashes. A pack with one bad
   entry leaves the card as it was.

9. The packs are written onto the volume in the order of their entries, which is the order of the
   clips. Each folder entry makes a folder, and each file entry writes a file and replaces one that
   is there. The script copies no dates, modes or owners. It says the progress about once a minute.

   When the system refuses a write because the card is read-only or the access is denied, the
   sentence adds that the card may be locked, and that on a microSD adapter the lock slider must be
   pushed up, towards the contacts.

   When the writing fails, every marker file is removed from the volume as far as possible, and the
   sentence ends by saying to put the card back into the Flipper before the script is run again.

10. Every file at the top of the volume whose name starts with `.sonar-install-` is removed: the
    marker of this run, and any marker that an earlier run left, for example a run that stopped while
    the card was out of the Flipper. A folder of that name stays. When there were older markers, the
    script says how many it removed.

11. macOS puts a 4 KB helper file named `._<name>` beside every file and folder that a process
    writes to an exFAT card. It gives each of them the attribute `com.apple.provenance`, which exFAT
    keeps only in such a file. The script removes every file whose name starts with `._` below
    `sr/voices/<set>/` on the volume, for each set that the packs hold, and nothing else. A file
    that cannot be removed is left, and is not an error. The script says how many it removed. Files
    beside the set's folder, such as `sr/voices/._<set>`, are not touched.

12. The card is ejected, so that everything the computer still holds back is written. On macOS the
    script runs this, with a limit of 120 seconds:

    ```
    diskutil eject <volume>
    ```

    An exit code of 0 means that it worked. When it fails, or the program is not found, the script
    says why in one sentence, which is the last line of the output of `diskutil`, and asks the user
    to eject the card by hand and press Enter. On other systems it asks the user to eject the card
    safely and press Enter.

13. The script asks, and waits for Enter:

    ```
    Put the card back into the Flipper, then press Enter.
    ```

14. After Enter, the script waits for the Flipper to see the card, for at most 15 minutes, which is
    900 seconds, as long as the wait after an update. The constant that holds this time is
    `CARD_BACK_SECONDS`. It says that it waits and how long that may take, and then a line about
    once a minute with the time so far. Every 2 seconds it does the next of these steps:
    - The Flipper's port must be listed, as when the console is opened, and stay listed for 5
      seconds, which is the constant `PORT_STEADY_SECONDS`. A port that vanishes meanwhile starts
      this over. When the user named a port, that port is waited for. A named port counts as
      listed when the Flipper's list or the system's list of serial ports has it, compared without
      case on Windows, or when its device file exists. That covers a `/dev/tty.` name on a Mac and
      a `/dev/serial/by-id` link on Linux, which pyserial does not list, and which vanish with the
      device as well.
    - Then the console is opened as described under Opening it, with DTR dropped and raised and
      the banner read, and the quiet limit is 5 seconds.
    - On that console, for each set that the packs hold, the script asks:

      ```
      storage stat "/ext/sr/voices/<set>/voice.txt"
      ```

    - While the card is out, or still being mounted again, the reply is an error line, such as the
      `Storage error: internal error` that Robin's Flipper gave while its card was out. Any error
      line, and `file/dir not exist`, mean "not yet", and the script asks again on the same
      console. When the file is there, the reply is `File, size: <n>b`. When every set's file is
      there, the Flipper sees the card with the voice on it.
    - A port that vanishes, a console that cannot be opened or gives no prompt, and a reply that
      goes quiet or takes too long, close the console, and the wait goes back to waiting for the
      port. The script says that the connection was lost and that it waits for it to come back.
      This also holds during step 15.

    When the time runs out, the script stops with one sentence. It says whether the Flipper's
    console was not back, or whether the Flipper did not see the file, and it keeps the last reason
    when there was one: the Flipper's last error sentence, or the sentence of the last open of a
    port that was there but could not be opened, such as a port that qFlipper holds. A later
    answer of the Flipper takes the place of an earlier reason. It says to check that the card sits
    in the Flipper and that the Flipper is plugged in and unlocked, and to run the script again,
    which is safe.

15. The Flipper may still list some `._` files, because they can be made again when the card is
    ejected, or because they could not be removed on the computer. The script looks for them
    through the console, with the usual quiet limit of 30 seconds again. For each set, it lists the
    set's folder and then every folder below it, depth first, each with `storage list`, and collects
    every file whose name starts with `._`:

    ```
    storage list "/ext/sr/voices/<set>"
    ```

    It says how many it found and about how long the removal takes, which it works out at 0.04
    seconds for a file, since `storage remove` took 37 to 39 milliseconds a file in the spike. Then
    it removes each of them:

    ```
    storage remove "/ext/sr/voices/<set>/<folder>/._<name>"
    ```

    It reports how many it removed over the console. It reported the number it removed on the
    computer before, so the user can see whether the removal on the computer worked. An error line
    from the Flipper here stops the script with one sentence that names the step.

The console that is open at the end of step 15 is used afterwards for the update.

### The update package

The package folder goes to `/ext/update/<name of the folder>/`, for example
`/ext/update/f7-update-sonar-0.1.0/`. The commands are those of sending a folder, as described
above. Files of the same name are replaced.

### Starting the update

```
update install /ext/update/<name>/update.fuf
```

The Flipper prints these lines, from the firmware's `updater_cli.c`:

- `Verifying update package at '<path>'`
- Either `OK.` followed by `Restarting to apply update. BRB`, or `Error: <reason>. Stopping update.`

After the error line the prompt comes back, because the Flipper does not restart. After `Restarting
to apply update. BRB` the Flipper waits 0.1 seconds and resets itself, so the prompt never comes and
the port vanishes.

The script does not read the `Verifying` and `OK` lines. It decides by what happens to the
connection:

- When the connection is lost before a prompt came, the Flipper took the package and restarted. The
  script closes the port and goes on to the wait.
- When the prompt came back, the Flipper refused the package. The script takes the reason from the
  line that matches `Error: <reason>. Stopping update.`, and when there is none, from the last line
  of the reply. Then it stops.

### The wait after the update

The Flipper restarts, runs the updater, which unpacks the firmware and the resources, and restarts.
It may restart more than once: a radio stack update adds restarts and minutes. The console is silent
or missing during all of it. The script waits for at most 15 minutes, which is 900 seconds, and says
that it waits and how long that may take. It also says that a Flipper with a PIN asks for it again
when it restarts, and that the script waits until it is entered. Momentum and Sonar lock themselves
with the PIN at every start when one is set, which is Momentum's default, and a locked Flipper's
console is off, so its port stays missing until the PIN is entered.

The steps of the wait:

1. Sleep 5 seconds first. The Flipper restarts 0.1 seconds after its last line, and its old port
   must not be taken for the new one.
2. Try to open a console every 2 seconds. Each try looks for the port again, since it may have
   another name after a restart. If the user named a port, only that one is tried. A port that is
   not there, or cannot be opened, is a try that failed.
3. When the port opens, discard the banner as above, set the quiet limit to 5 seconds, and send:

```
info device
```

4. The console counts as back only when the reply has a `firmware.version` and `system.boot` is `0`.
   When `system.boot` is `4`, the updater is in its last boot. Its console is there, but it is still
   unpacking its resources, and one more restart follows. The script closes the port and tries
   again. A reply that cannot be read in time, or that has no `firmware.version`, is handled the
   same way.
5. When the console is back, the quiet limit is set to 30 seconds again.

While it waits, the script says a line about once a minute, with the time so far. After 900 seconds
it stops with a sentence that says that the Flipper did not come back, though the firmware may be
installed already, and that the user should let the update finish if it is still running, enter the
PIN if the Flipper is locked with it, and run the script again. When the run put a voice pack on
the card, the sentence adds that the next run may leave out `--voice`, since the voice is on the
card already.

### The second `info device` and the comparison

```
info device
```

The script says again which firmware runs, and compares it with what was meant to be installed. The
comparison with `release.json` is described in the section about the release description below.
Without `release.json`, the name of the package folder decides:

- A name that ends in a dash and eight lowercase hexadecimal digits is the package of a build, such
  as `f7-update-mntm-screen-reader-9149fe49`. The `firmware.commit.hash` must match those digits.
- Any other name that starts with `f7-update-` names a version, such as `f7-update-sonar-0.1.0` or
  `f7-update-1.4.3`. The `firmware.version` must equal what follows `f7-update-`.
- Any other name is not compared.

When anything differs, the script says each difference as a sentence and stops. The older packages
stay on the card then, because the new one may be needed again.

### The restore

This is only done when the user asked for it with `--restore`, and after the update, if there was
one. When the backup is a file on the computer, it is first sent to `/ext/<its file name>` as
described above. Then:

```
update restore <path on the card>
```

The reply starts with `Restore /int from '<path>'` and ends with `Result: OK` or `Result: FAIL`,
read as for the backup, without the advice about a full card. The Flipper reads the restored
settings when it restarts, so the script tells the user to restart it by holding Left and Back
together for five seconds.

### Removing the older update packages

This is only done when a package was installed. First the folders in the update folder are listed,
using the second reading of `info device`:

```
storage list "/ext/update"
```

The rule that picks the folders, from `tools/card_prune.py`, is this. Only the folders of the fork's
own builds are candidates, those whose names start with `f7-update-sonar-`,
`f7-update-mntm-screen-reader-`, `f7-update-mntm-HEAD-` or `f7-update-mntm-claude-`. Every other
folder stays, such as `f7-update-1.4.3` and `f7-update-mntm-012`, because a package of another
firmware may be the way back. Of the candidates, these stay as well:

- The folder that was just installed.
- The folder of the running build. Its name ends with a dash and the `firmware.commit.hash`, or,
  when the `firmware.version` is not `mntm-dev`, it is `f7-update-<firmware.version>`.

When the Flipper did not give a commit hash, nothing is removed. Each folder that goes is emptied
first, the way `storage list` and `storage remove` allow: the subfolders of a folder are emptied and
removed first, then its files are removed, and then the folder itself.

## The release description

When the script is given `release.json`, which the release process writes and the release publishes
as an asset, it compares the firmware that runs after the update with these fields. The values of
the Flipper are those of the second `info device`.

- `firmware_version` must equal `firmware.version` exactly, such as `sonar-0.1.0`. The field must be
  there. It also names the update package: the package folder must be called
  `f7-update-<firmware_version>`.
- `firmware_commit` must match `firmware.commit.hash`. The release carries nine characters and the
  Flipper prints eight, so the comparison is by prefix: both are lowercased, and the shorter one
  must be at least seven characters long and be the start of the longer one. The field must be
  there.
- `api_version` must equal `firmware.api.major` and `firmware.api.minor` joined by a dot, such as
  `87.3`. This one is compared only when the field is there.

Two more things are always expected of a release, and they are not fields of the file:

- `firmware.commit.dirty` must not be `true`, because a release is built from a tree without
  uncommitted changes.
- `firmware.origin.fork` must be `Sonar`.

Each difference becomes one sentence. A value that the Flipper did not report is called unknown in
it. The other fields of the file, such as `momentum_base`, `default_voice`, `voices` and `assets`,
are not compared.

## Measured figures

The measurements are in `docs/measurements/2026-10-11-transfer-spike.txt`, made on the device
R0skie, and for the card reader way in `docs/measurements/2026-10-11-installer-device-checks.txt`.

- The heart voice pack, 111.3 megabytes, took 653 seconds to send over USB. The unpacking took 964
  seconds on a card that had nothing of the set, and 786 seconds over a set that was there. So the
  voice over USB takes between 24 and 27 minutes.
- The update package, 12.4 megabytes, took 72 seconds to send.
- The unpacking took 8.66 seconds for a megabyte of pack at its slowest, and the script plans with
  13, which has half again on top.
- Sending the voice file by file took about the same time as sending the pack, 26 minutes. The pack
  is kept because it is what the release ships, and because the mute that goes with it ends by
  itself.
- The card reader way took, on 2026-10-11, about 3 minutes to copy the voice's 10,537 files onto the
  card, 26 seconds to remove the 10,537 `._` files and 3 seconds to eject the card. On 2026-10-12
  the whole of the computer's part, the look for the card, the copy, the removal and the eject, took
  2 minutes 40 seconds, between the user's Enter and the question to put the card back. The whole
  run took 11 minutes, with no update, and about 8 of them were the user moving the card twice. A
  whole install by this way was not timed as one run. It is composed of the voice's 3 minutes, the
  update package's minute and the update's 6 minutes from the install over USB, which makes about 10
  minutes, plus the two moves of the card.
