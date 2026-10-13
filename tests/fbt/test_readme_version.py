#!/usr/bin/env python3
"""The README's commands name the release they are for, and the release is the newest one in
CHANGELOG.md: the first heading of the form "## X.Y.Z, <date>" gives its version, and every release
name of the form sonar-<version> inside a fenced code block of README.md, such as the one in a
download command or in the name of a file, is exactly sonar-<that version>; so is every one inside
an inline code span of its prose, such as the file names it lists, and so is the version that a
sentence of its prose says in words, "name version X.Y.Z". A name of another version fails, a
release candidate's name, sonar-<version>-rc1, fails too, and so does a README whose code blocks
name no release at all. The rest of the prose, outside backticks, is free: it may name an older
release, or a release candidate, as a sentence about it.
The checks: the checker itself on small made-up texts, a stale version failing, the right one
passing, an rc name failing, a README without any failing, prose outside backticks left out, inline
code spans, also wrapped, doubled and unpaired ones, the version in words, also wrapped and in
other case, other versions in words left out, fences indented in a list, tilde fences, a version
that only starts like the newest failing, the newest version being the first heading and not the
highest, and a changelog without a version failing; then the real README.md and CHANGELOG.md,
whose fences must be balanced, whose code blocks must name at least one release, and which must
agree.
Run from the project root: python3 tests/fbt/test_readme_version.py"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
failures = 0
checks = 0

HEADING = re.compile(r"^## (\d+\.\d+\.\d+), .+$", re.MULTILINE)
RELEASE_NAME = re.compile(r"sonar-\d+\.\d+\.\d+(?:-rc\d+)?")
FENCE = re.compile(r"^\s*(```|~~~)")
CODE_SPAN = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)", re.DOTALL)  # `text`, or ``text`` with a backtick inside
STATED = re.compile(r"\bnames? version (\d+(?:\.\d+)*)", re.IGNORECASE)  # "These commands name version 0.1.0"


def check(cond, what):
    global failures, checks
    checks += 1
    if not cond:
        failures += 1
        print("FAIL", what)


def newest_version(changelog):
    """The version of the first heading of the form "## X.Y.Z, <date>", else None."""
    found = HEADING.search(changelog)
    return found.group(1) if found else None


def fences(text):
    """The number of lines of text that open or close a fenced code block."""
    return sum(1 for line in text.splitlines() if FENCE.match(line))


def code_lines(readme):
    """The lines of README that are inside fenced code blocks, the fence lines themselves left out.
    A block is closed by a fence of the same kind (backticks or tildes); one left open runs to the
    end of the text."""
    inside = None
    for line in readme.splitlines():
        fence = FENCE.match(line)
        if fence and inside is None:
            inside = fence.group(1)
        elif fence and fence.group(1) == inside:
            inside = None
        elif inside is not None:
            yield line


def prose_paragraphs(readme):
    """The paragraphs of README outside its fenced code blocks, each its lines joined by line ends:
    a blank line ends a paragraph, and so does a fence."""
    paragraphs, current, inside = [], [], None
    for line in readme.splitlines():
        fence = FENCE.match(line)
        if fence and inside is None:
            inside = fence.group(1)
        elif fence and fence.group(1) == inside:
            inside = None
        elif inside is None and line.strip():
            current.append(line)
            continue
        elif inside is not None:
            continue
        if current:
            paragraphs.append("\n".join(current))
            current = []
    if current:
        paragraphs.append("\n".join(current))
    return paragraphs


def release_names(readme):
    """Every release name, sonar-X.Y.Z with or without -rcN, inside the README's code blocks, in
    order."""
    return [name for line in code_lines(readme) for name in RELEASE_NAME.findall(line)]


def inline_names(readme):
    """Every release name inside an inline code span of the README's prose, in order. A span ends
    with the paragraph, so a lone backtick pairs with none in another."""
    return [name for paragraph in prose_paragraphs(readme) for span in CODE_SPAN.finditer(paragraph)
            for name in RELEASE_NAME.findall(span.group(2))]


def stated_versions(readme):
    """The versions the README's prose names in words, "name version X.Y.Z" or "names version
    X.Y.Z", in order; a line end between the words counts as a space."""
    return [version for paragraph in prose_paragraphs(readme) for version in STATED.findall(" ".join(paragraph.split()))]


def problems(readme, changelog):
    """What is wrong when the README does not name the newest release of the changelog: a list of
    sentences, empty when all is well. The release names in the code blocks and in inline code must
    each be sonar-<version>, with at least one in the code blocks, the commands a reader copies, and
    the version said in words must be the version. The rest of the prose is free."""
    version = newest_version(changelog)
    if version is None:
        return ["the changelog has no heading of the form ## X.Y.Z, <date>."]
    wanted = f"sonar-{version}"
    found = []
    names = release_names(readme)
    if not names:
        found.append("the README's code blocks name no release of the form sonar-X.Y.Z.")
    for where, got in (("code blocks name", names), ("inline code names", inline_names(readme))):
        wrong = sorted({name for name in got if name != wanted})
        if wrong:
            found.append(f"the README's {where} {', '.join(wrong)}, but the newest release is {wanted}.")
    wrong = sorted({stated for stated in stated_versions(readme) if stated != version})
    if wrong:
        found.append(f"the README says in words that its commands name version {', '.join(wrong)}, "
                     f"but the newest version is {version}.")
    return found


CHANGELOG = "# Changelog\n\nThe version 0.1.0 is the tag `sonar-0.1.0`.\n\n## 0.2.0, 2026-11-01\n\nNew.\n\n## 0.1.0, 2026-10-13\n\nFirst.\n"


def readme_with(*lines, prose=""):
    """A README with one code block that holds lines, and prose."""
    return f"# Sonar\n\n{prose}\n\n```bash\n" + "\n".join(lines) + "\n```\n"


# The version: the first heading, which is the newest, and not a mention in prose
check(newest_version(CHANGELOG) == "0.2.0", f"the newest version is the first heading's, not the highest or a mention: {newest_version(CHANGELOG)}")
check(newest_version("## 0.1.0, 2026-10-13\n\n## 0.10.0, 2026-11-01\n") == "0.1.0", "and the first heading is the newest even when a later one reads higher")
check(newest_version("# Changelog\n\nThe tag is `sonar-0.1.0`.\n") is None, "a changelog without such a heading has no version")
check(newest_version("## Unreleased\n\n## 0.1.0 2026-10-13\n") is None, "a heading that is not of the form X.Y.Z, <date> is not one")

# The checker on made-up texts
right = readme_with("curl -f -L -O https://example.org/releases/download/sonar-0.2.0/flipper-z-f7-update-sonar-0.2.0.tgz",
                    "unzip install-sonar-0.2.0.zip")
check(problems(right, CHANGELOG) == [], f"the right version in every name passes: {problems(right, CHANGELOG)}")
stale = readme_with("curl -f -L -O https://example.org/releases/download/sonar-0.1.0/flipper-z-f7-update-sonar-0.1.0.tgz")
said = problems(stale, CHANGELOG)
check(len(said) == 1 and "sonar-0.1.0" in said[0] and "sonar-0.2.0" in said[0], f"a stale version fails and names both: {said}")
mixed = readme_with("mkdir sonar-0.2.0", "cd sonar-0.2.0", "unzip install-sonar-0.1.0.zip")
said = problems(mixed, CHANGELOG)
check(len(said) == 1 and "sonar-0.1.0" in said[0] and "sonar-0.2.0," not in said[0], f"one stale name among right ones fails, and only it is named: {said}")
release_candidate = readme_with("mkdir sonar-0.2.0-rc1")
said = problems(release_candidate, CHANGELOG)
check(len(said) == 1 and "sonar-0.2.0-rc1" in said[0], f"a release candidate's name fails, even of the newest version: {said}")
check(problems(readme_with("mkdir sonar-0.2.0", "cd sonar-0.2.0-rc2"), CHANGELOG) != [], "and so does one among right names")
check(problems(readme_with("mkdir sonar-0.2.00"), CHANGELOG) != [] and problems(readme_with("mkdir sonar-0.2.01"), CHANGELOG) != [],
      "a version that only starts like the newest fails")
check(problems(readme_with("mkdir sonar-0.2.0"), "## 0.2.0, 2026-11-01\n") == [] and problems(readme_with("mkdir sonar-0.20.0"), "## 0.2.0, 2026-11-01\n") != [],
      "and the whole name is compared, not its start")
nothing = readme_with("python3 install.py --help", "mkdir release")
said = problems(nothing, CHANGELOG)
check(len(said) == 1 and "name no release" in said[0], f"a README whose code blocks name no release fails: {said}")
check(problems("# Sonar\n\nNo code here.\n", CHANGELOG) != [], "so does one without a code block")
check(len(problems(right, "# Changelog\n")) == 1, "a changelog without a version fails once")

# Prose outside backticks is free, and a release named only outside the code blocks does not count as named
prose = ("The older release sonar-0.1.0 and its candidate sonar-0.1.0-rc1 are described in the changelog, "
         "and version 0.1.0 had a guide.\n\n    sonar-0.0.5 indented\n")
check(problems(readme_with("mkdir sonar-0.2.0", prose=prose), CHANGELOG) == [],
      f"prose outside backticks that names an older release or a candidate does not fail: {problems(readme_with('mkdir sonar-0.2.0', prose=prose), CHANGELOG)}")
check(release_names(prose) == [] and inline_names(prose) == [] and stated_versions(prose) == [], "and is not looked at")
check(problems(readme_with("echo hello", prose="Use `sonar-0.2.0`."), CHANGELOG) != [], "a release named only in inline code does not count as named by a command")
after = readme_with("mkdir sonar-0.2.0") + "\nThe old sonar-0.1.0, and sonar-0.1.0 again.\n\n```text\nsonar-0.2.0\n```\n\nsonar-0.0.1\n"
check(release_names(after) == ["sonar-0.2.0", "sonar-0.2.0"], f"only the names inside the blocks are taken: {release_names(after)}")

# Inline code spans: every release name in one is the newest too
files = "The files are `flipper-z-f7-update-sonar-0.2.0.tgz` and `install-sonar-0.2.0.zip`, for the release `sonar-0.2.0`."
check(problems(readme_with("mkdir sonar-0.2.0", prose=files), CHANGELOG) == [], f"inline code with the right version passes: {problems(readme_with('mkdir sonar-0.2.0', prose=files), CHANGELOG)}")
check(inline_names(files) == ["sonar-0.2.0", "sonar-0.2.0", "sonar-0.2.0"], f"each name in an inline span is taken: {inline_names(files)}")
old_files = "The files are `flipper-z-f7-update-sonar-0.2.0.tgz` and `voice-heart-sonar-0.1.0.tar`."
said = problems(readme_with("mkdir sonar-0.2.0", prose=old_files), CHANGELOG)
check(len(said) == 1 and "sonar-0.1.0" in said[0] and "inline code" in said[0] and "sonar-0.2.0." in said[0], f"a stale name in inline code fails, naming where: {said}")
said = problems(readme_with("mkdir sonar-0.2.0", prose="For the release `sonar-0.2.0-rc1`."), CHANGELOG)
check(len(said) == 1 and "sonar-0.2.0-rc1" in said[0], f"a candidate's name in inline code fails: {said}")
check(inline_names("A name that wraps `flipper-z-f7-update-\nsonar-0.1.0.tgz` over two lines.") == ["sonar-0.1.0"], "a span that wraps over a line end is looked at")
check(inline_names("A pair ``one `sonar-0.1.0` two`` of double backticks.") == ["sonar-0.1.0"], "and so is one with double backticks")
check(inline_names("A lone ` backtick, and then\n\nsonar-0.1.0 ` another lone one.") == [], "a backtick does not pair with one in another paragraph")
check(inline_names("```text\nsonar-0.1.0\n```\n\nAnd `sonar-0.2.0`.") == ["sonar-0.2.0"], "the inside of a block is not read as inline code")
check(inline_names("~~~\nsonar-0.1.0\n~~~\n`sonar-<version>-source.tar.gz`, such as `sonar-0.2.0-source.tar.gz`") == ["sonar-0.2.0"],
      "a placeholder with no digits is no name, and a name in a file name counts")

# The version in words: "name version X.Y.Z"
for says in ("These commands name version 0.2.0, and more.", "This names version 0.2.0.", "These commands name\nversion 0.2.0 now.", "These commands Name Version 0.2.0 now."):
    check(problems(readme_with("mkdir sonar-0.2.0", prose=says), CHANGELOG) == [], f"the right version in words passes: {says!r}")
for says in ("These commands name version 0.1.0, and more.", "This names version 0.1.0.", "These commands name\nversion 0.1.0 now.",
             "These commands Name Version 0.1.0 now.", "These commands name version 0.2.00.", "These commands name version 0.2.0.1."):
    said = problems(readme_with("mkdir sonar-0.2.0", prose=says), CHANGELOG)
    check(len(said) == 1 and "version" in said[0] and "0.2.0" in said[0], f"a stale version in words fails: {says!r}: {said}")
others = "Taken from version 1.4.3 of the official firmware, and the app interface is version 87.3, not named for Sonar."
check(problems(readme_with("mkdir sonar-0.2.0", prose=others), CHANGELOG) == [] and stated_versions(others) == [],
      "other versions in words, such as the official firmware's, are not looked at")
check(stated_versions("These commands name version 0.2.0, and later ones name version 0.3.0.") == ["0.2.0", "0.3.0"], "every sentence of the kind is taken")
check(stated_versions("```text\nWe name version 0.1.0\n```\n") == [], "and none inside a block")

# The fences as a README has them
listed = "1. Make a folder:\n\n   ```bash\n   mkdir sonar-0.1.0\n   ```\n\n2. Then more.\n"
check(release_names(listed) == ["sonar-0.1.0"], f"a block indented in a list item is looked at: {release_names(listed)}")
tilde = "~~~\nmkdir sonar-0.1.0\n~~~\n\nsonar-0.9.9\n"
check(release_names(tilde) == ["sonar-0.1.0"], f"so is a block fenced with tildes: {release_names(tilde)}")
mixed_fences = "```text\n~~~\nsonar-0.1.0\n```\n\nsonar-0.9.9\n"
check(release_names(mixed_fences) == ["sonar-0.1.0"], f"a tilde line inside a backtick block does not close it: {release_names(mixed_fences)}")
check(fences(listed) == 2 and fences("```\nx\n") == 1 and fences("no fence") == 0, "the fence lines are counted")
check(release_names("```\nsonar-0.1.0\n") == ["sonar-0.1.0"], "a block left open runs to the end")

# The real files
with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
    readme = f.read()
with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
    changelog = f.read()
check(fences(readme) % 2 == 0, f"the README's fences are balanced: {fences(readme)}")
version = newest_version(changelog)
check(version is not None, "the changelog has a newest version")
names = release_names(readme)
check(len(names) >= 1, f"the README's code blocks name at least one release: {len(names)}")
check(len(inline_names(readme)) >= 1 and len(stated_versions(readme)) >= 1,
      f"and its inline code and its sentence in words are there to be looked at: {len(inline_names(readme))}, {len(stated_versions(readme))}")
said = problems(readme, changelog)
check(not said, f"the README's commands name the newest release of the changelog, {version}: {said}")

print(f"readme version: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
