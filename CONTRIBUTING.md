# Contributing

Sonar is made for blind users first, and help of every kind is welcome: a report of something that
goes wrong, a screen the reader gets wrong, a word that sounds wrong, an idea, or a change.

## Issues

Issues are welcome. For a bug, the bug report form asks for what helps most: the firmware's version
and commit, where the build came from, the `sr status` output, the steps, and what was spoken. For
a crash, the README's section When it crashes says what to include. A report of something the
reader says badly, or does not say at all, is a bug too.

## Pull requests

Pull requests are welcome, and so are those made with the help of AI tools, as long as the pull
request says so: which tool, which parts it wrote, and how you checked them. Sonar itself was
written almost entirely by AI coding agents under Robin Kipp's direction, as the README says, so
an AI-assisted change is no reason to hold back; it only has to be disclosed.

Where a change goes:

- The firmware is the fork https://github.com/robin24/Momentum-Firmware, branch `screen-reader`. A
  firmware change is a pull request there, and this repository then records the fork's new commit.
- Everything else is here: the tools, the tests, the continuous build and the documents.
- A fix that belongs in Momentum itself goes to Momentum, under its own rules, which do not accept
  AI-written code.

A pull request is merged after review, once its continuous build is green. A commit's message is
one sentence that says what is true after the change, ending with a short tag in parentheses, such
as "(install)" or "(docs)".

## Writing for a screen reader

Every document here is read with a screen reader first, and so is what a tool prints. So:

- Plain sentences, in prose and short lists. No tables.
- No em-dashes, and no contractions.
- Every command in its own fenced code block, marked `bash` when it is a shell command.
- Numbers with thousands commas, such as 10,535.
- Commit hashes with 9 characters, such as d74ea206a.
- Short headings that say what their section is about.
- A tool that talks to its user prints one plain line for each step, and an error as one sentence
  that says what failed and why, never a Python traceback.

## Tests

Run the host tests from the project folder before a pull request. They build the screen reader's
code with clang and run its unit tests, then the Python checks of the build's configuration and of
the tools, in a few seconds. A Mac has clang with Xcode's command line tools; on Linux, install it
from the distribution's packages.

```bash
tools/run_host_tests.sh
```

Some checks need the Python packages of `requirements.txt`, the Momentum commit named in
`tools/momentum-base.txt`, or the firmware's own tar reader, which comes with the firmware's
submodules, and they say "skipped" without them. The continuous build runs every check, with the
packages installed on Python 3.10 and with `--no-skips`, which fails the run when a check is
skipped. To run them the same way, with the virtual environment described under Building from
source in the README:

```bash
PATH="$PWD/.venv/bin:$PATH" tools/run_host_tests.sh --no-skips
```

A firmware change also needs a release build and the headroom check, as under Building from source
in the README, and a try on a Flipper with the reader on, listening to what it says.
