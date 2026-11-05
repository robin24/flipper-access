# Text screens and WiFi Marauder that speak correctly: design

Date: 2026-11-05. Status: agreed with Robin in conversation, section by section, on 2026-11-05. This written form awaits Robin's review, and nothing is built yet. Every network name and address in this document is made up.

## 1. Goal

Robin has a WiFi Dev Board flashed with WiFi Marauder v1.20.0 and wants to run tests against their own network and devices with the `[ESP32] WiFi Marauder` companion app. The two problems Robin named are that the list of discovered networks is messy, and that it isn't clear how to select a network as a target.

Robin's decision on scope: the app's flows stay as they are. In their words: "If it requires me to type an index, that's fine. The only important thing is that all UI elements are spoken correctly, so that I and other blind Flipper users know what's going on."

The work is right when:

- In a console, one press of Up or Down moves one line as the app printed it, and the whole line is spoken once, with no words broken in two. In `list -a` that means one press per network, with the index to type heard first.
- The reply to a command is heard without pressing anything, and new output neither moves the reader nor interrupts what is being said.
- Scrolling text in dialogs and info screens is read in whole words, and a short screen sounds the same as today apart from that.
- Every button and word in Marauder's screens can be named or pronounced recognisably.
- Other apps using the same modules gain from this and none gets worse.
- With the reader off, everything behaves exactly as today, except for two button labels in Marauder's log viewer (section 8).

Proposed and dropped by Robin's decision: separate list screens, a scan summary, composed commands and renamed menus. A flow problem found during this work is reported to Robin rather than changed.

## 2. Facts the design rests on

- Marauder draws nothing of its own. It uses the standard menus, the on-screen keyboard, the text box and widgets, so nearly all of this work belongs in the firmware.
- The text box wraps at the display's width, inside words. Down moves one wrapped row. Every `text_box_set_text` formats the text afresh and resets the scroll position.
- When several lines arrive at once, fewer than half of the previous rows remain, so `sr_screen_changed` calls it a new screen. The reader interrupts itself and ignores the Change delay.
- About 18 app areas open a text box at the end of its text (`TextBoxFocusEnd`), including Marauder, Evil Portal, UART Terminal and Ghost ESP.
- Widget scrolling text (`widget_element_text_scroll.c`) has the same broken words and gives the reader no hints. About 64 app areas use it, including NFC, RFID, iButton and Sub-GHz. It formats its text once, at the first draw.
- Marauder keeps only about 4 KB of console text, dropping the oldest as more arrives.
- A typical scan line took about 16 seconds to speak when measured, so speech can't keep up with a busy scan.
- One reader row holds 63 characters, a tapped string 47, and an announcement 159.
- `same_focus` compares text only, so moving onto an identical line is silent today.
- `sr_is_arrow_token` drops a string that is only `<` or `>`, so Marauder's `> ` prompt vanishes today.
- Glyph widths need the canvas, so an input callback can't measure text. It can only leave a request for the next draw, as the text box's scroll position already does.
- Spare flash is 8,428 bytes under the updater's limit of 880,640. The lowest free heap seen with Marauder running was 28,920 bytes.

## 3. Stops

A stop is the unit that Up and Down move by and that the reader speaks. Stops are built from rows.

- A row is what fits on one line of the display. With the reader on, a row breaks at the last space that fits. A word too long for the width breaks at the width. A row also ends at 47 characters, the most one tapped string holds.
- A stop is the rows of one printed line, up to 60 characters and no more rows than the display holds. A longer line becomes several stops, split at a row boundary.
- Blank lines, and lines of only spaces or dashes, are not stops, because there is nothing to say. They stay on the display in their place, and they don't count in the position.
- A line is complete when it ends in a newline.

This logic goes in a small new C unit, `applications/services/gui/modules/text_stops.c` and `.h`, with no dependency on the canvas. Its caller passes a function that gives a glyph's width, so the host tests can use a stand-in. It isn't exported in the SDK, and nothing calls it with the reader off.

## 4. The text box

The changes are in `text_box.c`. The model remembers whether the reader was listening at the last draw, read from `canvas->tap_callback`. If that changes, the text is prepared again. With the reader off, the code paths are the ones used today.

With the reader on:

- **Moving:** each Short or Repeat of Up or Down queues one step of one stop, with no speed-up while held. The next draw applies the steps.
- **Display:** the current stop's first row is at the top, followed by the rows after it until the display is full. The scrollbar shows the stop's position.
- **What the reader gets:** the stop's first row carries the focus hint with its index and count and a reading hint (section 7). Its other rows carry a join hint, with a space if the break was at a space, or direct if it was inside a word. Every other visible row is hidden from the reader with `canvas_tap_hint_full_text(canvas, "", false)`.
- **Opening:** one stop plus the count, at any verbosity, such as "1 of 23". A box with `TextBoxFocusStart` opens on the first stop. A box with `TextBoxFocusEnd` opens on the first stop of the newest complete line, or on the last stop if no line is complete.
- **Afterwards:** position follows the Verbosity setting, as in menus. The Back and Up chord reads it at any time.
- **Repeated lines:** moving by key onto an identical line still speaks it.
- **Empty:** a box with no stops gives a note saying "Empty", so a console with no reply isn't silent. This gets checked on the device, and is dropped if it adds noise when a command starts.

New text doesn't move the reader. The model keeps the current stop's byte offset and its first 16 bytes. After `text_box_set_text`, the pass that counts the stops looks for the stop starting with those bytes at or before the old offset, nearest to it, because trimming only moves text towards the start. If none matches, the current stop becomes the first one, the oldest line still kept.

## 5. Live output

This applies only to boxes with `TextBoxFocusEnd`.

- **Following:** the box follows while the current stop is on the newest complete line or after it, or while no line is complete yet. When more text arrives, the current stop becomes the first stop of the newest complete line.
- **Speaking:** a following box marks a stop on a complete line as live, so the reader speaks a new line as a change on the same screen. That means the Change delay applies, the newest line wins, and speech in progress is never cut off.
- **Unfinished text:** a line with no newline yet, including Marauder's `> ` prompt, is never marked live, so it isn't spoken automatically. Down still reaches it. A bare `>` reads as "greater than", because the arrow filter doesn't apply to stops.
- **Reading back:** Up onto an earlier line stops following, and the box is quiet while output arrives. If the line being read is discarded, the reader lands on the oldest kept line silently. Down to the newest complete line starts following again.
- **Repeats:** a new line identical to the previous one isn't spoken, and can still be reached with Up and Down.
- **Leaving:** Back works as it does today.

A box with `TextBoxFocusStart` never follows, and its stops are always marked live. Appended text is silent, because the current stop doesn't change. If an app replaces the whole text, so that the current place is lost, the first stop of the new text is spoken as a change.

What this sounds like in Marauder:

- `list -a`: the lines arrive almost together, so the command echo and then the last line, "3 selected", are likely to be heard. Up then walks back through the networks, one per press. `[4][CH:1] Example-Net -40` is heard as "four C H, one Example Net minus forty". View Log from start reads from the top instead.
- `select -a 4`: the reply is heard, such as "1 selected, 0 unselected".
- `scanall`: about one line per 16 seconds is heard. The rest stay readable until the 4 KB limit discards them, and are in the log if saving is on.

## 6. Scrolling text in widgets

The changes are in `widget_element_text_scroll.c`. With the reader on at the first draw, the element wraps at spaces and records which rows continue a printed line, and that layout is kept for the element's life. With the reader off, formatting and input are the ones used today.

- **Opening:** these screens are often dialogs or short info screens, so opening reads as many whole stops as fit in 100 characters, as ordinary rows marked as opening text. That leaves room in the announcement for the title and the buttons. The first stop is always read in full.
- **Position:** if stops remain, a note follows the text, such as "4 of 7", meaning four of the seven stops have been read. The note comes before the buttons, at any verbosity. If nothing remains, there's no note.
- **Text beyond the display:** a stop that fits the budget but not the display reaches the reader as a note, without being drawn.
- **Moving:** Down from the opening goes to the next stop not yet heard, and Up goes to the last stop heard, read alone. From then on the element works one stop at a time, as the text box does. Down does nothing when no stops remain.
- **Display:** the current stop stays visible.
- **New widgets:** apps that rebuild a widget get the opening again, and lose the scroll position as they do today.

A long title or several buttons can still make an announcement run out of room, and then the end of the text is cut, as it is today. The buttons and the position note are never the part that's cut, and Up reaches the words that were lost.

A save prompt then opens as "Save pcaps? With compatible marauder. firmware, you can choose to. save captures (pcaps) to the. flipper sd card here: 4 of 7. buttons: left No, right Yes." The prompt's lines are broken by hand in the app, and they stay that way, so their sentences are read in pieces. Turning a page in the log viewer gives the opening of the new page.

## 7. The reader

- **New hint:** a firmware-only `canvas_tap_hint_reading(canvas, kind)` marks the next string or note, with the kinds stop, live and opening. The kind is carried in a new byte in `CanvasTapRecord` and `SrRecord`, and appears as `SrScreen.reading`.
- **New join:** `CANVAS_TAP_JOIN_SPACE` and `SrJoinSpace` join a row with one space, because `sr_normalize` strips the space at a break.
- **`sr_screen_build`:** a reading row is never the title. A reading screen is never a keyboard, so `has_keyboard` and `on_keyboard` stay false even when the text uses the keyboard font. `sr_is_arrow_token` doesn't drop a reading string. Buttons sort after all other rows, so text reported below the display still follows the text above it.
- **`sr_screen_changed`:** after the layer, content and title checks, opening text after anything other than opening text is a new screen. A reading screen after a reading screen is otherwise the same screen. Two screens of opening text follow the existing rule about kept rows.
- **`sr_screen_announcement`:** a reading screen's focus row always carries its position. Opening text's position note keeps its room in the announcement, as the buttons do.
- **`sr_model_process`, on a reading screen after a reading screen:**
  - With a recent key, if the stop's text or index changed, it's a focus announcement, which interrupts as today.
  - Without a recent key, on a live stop whose text changed, it's a change announcement.
  - Without a recent key on any other stop, nothing is said.
  - Other rows on the screen keep today's rules.

The Change delay, the replacing of a waiting change, and the key-recent window work as they do now.

## 8. Marauder's log viewer

This is the only change in the app, in `wifi_marauder_scene_log_viewer.c`. On middle pages, Left and center have empty labels, so the reader can't name them. They become "Prev" and "Browse". Those are the only changes visible with the reader off. A page boundary can still cut a line in two, and the file name stays unspoken, because the screen doesn't show it either.

## 9. Pronunciation

These changes are in `speech_text.c`, so they apply in every app. The targets below are what goes to the voice. Robin's listening check decides how they sound.

- **MAC addresses:** six colon-separated hex pairs are spelled pair by pair. `a0:1b:2c:3d:4e:5f` becomes "ay zero, one B, two C, three D, four E, five F", and a final `60` becomes "six zero". Hidden networks show a MAC address as their name, so this matters.
- **New stop words, read as words:** ITEM, ITEMS, STAGE, TRUE, FALSE, WRITE, BEGIN and CLOSE.
- **Spelled abbreviations:**
  - `ap` becomes "ay P", `ssid` "S S I D", `sta` "S T ay", `rssi` "R S S I" and `Ch` "C H".
  - `pmkid`, `bt`, `sd`, `dns`, `ssh`, `http`, `https`, `smtp`, `rdp`, `csa` and `sae` are spelled letter by letter.
- **Joined words:**
  - `stopscan` becomes "stop scan", `scanall` "scan all" and `pcaps` "pea caps".
  - `ForcePMKID` becomes "Force P M K I D", `ForceProbe` "Force Probe", `SavePCAP` "Save pea cap", `EnableLED` "Enable L E D" and `EPDeauth` "E P dee auth".
- **Dash:** a dash starting a word is spoken, so `select -a 4` becomes "select dash a four". A dash before a number stays "minus".
- **Hash:** a hash before a letter is "hash", so `#list` becomes "hash list". `#1` stays "number one".
- **Clips:** words only the board prints, such as `targets`, `tran` and `ssids`, go in `tools/voice_words.txt` along with any new spoken word such as "hash". They take up space on the card, not in firmware flash.
- **Left as they are:**
  - Bracket prefixes, because they're what's drawn: "plus ADD SCRIPT", "star SAVE", "S SETTINGS" and "X DELETE".
  - Longer command names from less common screens, such as `sniffbeacon`, unless they sound wrong to Robin.

## 10. Testing

**On the computer, written before the code,** using `tools/run_host_tests.sh` and made-up names only:

- A new `tests/host/test_text_stops.c`:
  - wrapping at spaces, words too long for a row and the 60-character split;
  - blank and dash lines, and complete and unfinished lines;
  - finding the place again after text is appended, trimmed or replaced, and following.
- `test_screen_model.c`:
  - the new join and the reading hint;
  - live frames staying on the same screen, and change, focus and silent cases by key and live state;
  - position on opening at each verbosity, repeated lines, a bare `>`, and text in the keyboard font;
  - opening text as a new screen.
- `test_speech_text.c`: every rule in section 9, with the strings that must not change, such as `-40` and `#1`.

**On the Flipper, watching announcements through `sr watch`:**

- **Marauder:** Scan all for a short time, List ap, Select with a typed index, AP Info, reading back during output, the log viewer's pages, and moving through the script menus without running anything.
- **Save prompts:** from a fresh state, with the app's two settings files moved aside and put back afterwards.
- **Other apps:** one NFC or Sub-GHz info screen, and the `text_box_view_test` debug app for both ways of opening.
- **Size:** `tools/flash_headroom.sh` before every flash, expecting less than 3 KB in all. If it doesn't fit, Robin gets told and the work stops there. The lowest free heap is checked again with Marauder running.

**With Robin, in short turns:** the listening check for section 9, and one run with the board unplugged to hear a console with no reply.

**Not run by me:** Attack, Targeted Attacks, Evil Portal, Sniff, Beacon Spam and Join WiFi, because they transmit or change the board's state. They use the same console code, and Robin can try them on their own network.

**Reader off:** there's no tool that captures the display, so the screen can't be compared directly. The check is by reading the code, plus scrolling on the device with the reader off. A sighted person could look at the display if Robin wants more certainty.

## 11. Limits that stay

- Speech can't keep up with a busy scan.
- The console keeps about 4 KB of text.
- A line of over 60 characters becomes several stops.
- A log page boundary can cut a line in two.
- Sentences in the save prompts are read in pieces.
- Indexes are still typed, and flows don't change.
- Merges from upstream Momentum can conflict with the edits to the text box and scrolling text.

The crash recorded in `sr status` before this work points to an interrupt handler being set twice, and nothing links it to Marauder. It isn't part of this work, and it gets decoded if it happens again during testing.

## 12. Delivery

- **Firmware:** a pull request on the fork into `screen-reader`, then a pull request in the project to update the submodule pointer.
- **Compatibility:** no new functions are exported to apps, so existing apps need no rebuild and improve after a flash. Only Marauder is rebuilt, for its labels.
- **Docs:** the README's "Using it on the device" gets a section on reading text screens and on Marauder. The docs index lists the spec and the plan. `CHANGELOG.md` only changes at a release.
- **Public repo content:** tests and docs use made-up network names, and no records of Robin's device go in the repo.
