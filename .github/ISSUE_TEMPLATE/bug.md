---
name: Bug report
about: Something Sonar or its tools do wrong, a crash or a wrong reading included
labels: bug
---

Write your answer below each heading, in place of the sentences there. A short answer is fine.

## What happened

What did you do, step by step, and what did you expect to happen?

## What was spoken

What did the reader say, word for word if you can? Or did it say nothing? If a word was spelled
letter by letter, which word was it?

## The firmware

The two lines `firmware.version` and `firmware.commit.hash` of `info device`. From the install's
folder of a release, this command prints them:

```bash
.venv/bin/python flipper_cli.py "info device"
```

On Windows, the same is:

```bash
.venv\Scripts\python flipper_cli.py "info device"
```

From a clone of this repository, the command is:

```bash
.venv/bin/python tools/flipper_cli.py "info device"
```

On Windows, the same is:

```bash
.venv\Scripts\python tools\flipper_cli.py "info device"
```

Copy only those two lines, since the rest of `info device` names your Flipper and gives its unique
id. On the Flipper, the same is on the Firmware Info page under Settings, About: the version
comes first, then the build date, then the commit.

## Where the build came from

Was it a release, and which one; a continuous build from this repository's Actions, and which run;
or a build of your own, and from which commit?

## The output of sr status

The whole output of `sr status`. It holds the last crash's address and the build that recorded it.
From the install's folder of a release:

```bash
.venv/bin/python flipper_cli.py "sr status"
```

On Windows:

```bash
.venv\Scripts\python flipper_cli.py "sr status"
```

From a clone of this repository:

```bash
.venv/bin/python tools/flipper_cli.py "sr status"
```

On Windows:

```bash
.venv\Scripts\python tools\flipper_cli.py "sr status"
```

## Anything else

What was open on the Flipper, whether it happens every time, and anything else that may help.
