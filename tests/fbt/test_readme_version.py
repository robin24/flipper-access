#!/usr/bin/env python3
"""The README's commands name the release they are for, and the release is the newest one in
CHANGELOG.md: the first heading of the form "## X.Y.Z, <date>" gives its version, and every release
name of the form sonar-<version> inside a fenced code block of README.md, such as the one in a
download command or in the name of a file, is exactly sonar-<that version>. A name of another
version fails, a release candidate's name, sonar-<version>-rc1, fails too, and so does a README
whose code blocks name no release at all. The prose is left out on purpose: it may name an older
release, or a release candidate, as a sentence about it, and a command is what a reader copies.
The checks: the checker itself on small made-up texts, a stale version failing, the right one
passing, an rc name failing, a README without any failing, prose and inline code left out, fences
indented in a list, tilde fences, a version that only starts like the newest failing, the newest
version being the first heading and not the highest, and a changelog without a version failing;
then the real README.md and CHANGELOG.md, whose fences must be balanced, whose code blocks must
name at least one release, and which must agree.
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


def release_names(readme):
    """Every release name, sonar-X.Y.Z with or without -rcN, inside the README's code blocks, in
    order."""
    return [name for line in code_lines(readme) for name in RELEASE_NAME.findall(line)]


def problems(readme, changelog):
    """What is wrong when the README's commands do not name the newest release of the changelog: a
    list of sentences, empty when all is well."""
    version = newest_version(changelog)
    if version is None:
        return ["the changelog has no heading of the form ## X.Y.Z, <date>."]
    names = release_names(readme)
    if not names:
        return ["the README's code blocks name no release of the form sonar-X.Y.Z."]
    wanted = f"sonar-{version}"
    wrong = sorted({name for name in names if name != wanted})
    if wrong:
        return [f"the README's code blocks name {', '.join(wrong)}, but the newest release is {wanted}."]
    return []


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

# Prose and inline code are left out, and so is everything outside a code block
prose = "The older release `sonar-0.1.0` and its candidate sonar-0.1.0-rc1 are described in the changelog.\n\n    sonar-0.0.5 indented\n"
check(problems(readme_with("mkdir sonar-0.2.0", prose=prose), CHANGELOG) == [],
      "prose and inline code that name an older release or a candidate do not fail")
check(release_names(prose) == [], "and are not looked at")
check(problems(readme_with("echo hello", prose="Use `sonar-0.2.0`."), CHANGELOG) != [], "a release named only in prose does not count as named")
after = readme_with("mkdir sonar-0.2.0") + "\nThe old `sonar-0.1.0`, and sonar-0.1.0 again.\n\n```text\nsonar-0.2.0\n```\n\nsonar-0.0.1\n"
check(release_names(after) == ["sonar-0.2.0", "sonar-0.2.0"], f"only the names inside the blocks are taken: {release_names(after)}")

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
said = problems(readme, changelog)
check(not said, f"the README's commands name the newest release of the changelog, {version}: {said}")

print(f"readme version: {checks - failures} of {checks} checks passed")
sys.exit(1 if failures else 0)
