#!/usr/bin/env python3
"""The build configuration's exclusions (fbt_options.py EXCLUDE_EXT_APPS and
EXCLUDE_EXT_CATEGORIES): an excluded app leaves the external app set, a plugin whose parent
is excluded goes with it, a plugin of a built app stays unless named itself, a plugin with two
parents stays while either of them is built unless named itself (test_js: unit_tests and js_app),
an unknown id is reported and nothing else. Run from the project root:
python3 tests/fbt/test_exclusions.py"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "Momentum-Firmware", "scripts"))
from fbt.appmanifest import AppBuildset, AppManager, FlipperApplication, FlipperAppType  # noqa: E402

failures = 0


def check(cond, what):
    global failures
    if not cond:
        failures += 1
        print("FAIL", what)


def app(appid, apptype, **kw):
    return FlipperApplication(appid=appid, apptype=apptype, _apppath=appid, _appdir=appid, **kw)


def manager():
    mgr = AppManager()
    for a in [
        app("default", FlipperAppType.METAPACKAGE, provides=["cli", "gui", "subghz"]),
        app("cli", FlipperAppType.SERVICE),
        app("gui", FlipperAppType.SERVICE),
        app("subghz", FlipperAppType.MENUEXTERNAL, fap_category="Sub-GHz"),
        app("js_app", FlipperAppType.EXTERNAL, fap_category="assets"),
        app("js_gui", FlipperAppType.PLUGIN, requires=["js_app"]),
        app("cli_js", FlipperAppType.PLUGIN, requires=["cli"]),
        # Two parents, like test_js (unit_tests and js_app); cli stands in for unit_tests
        app("test_js", FlipperAppType.PLUGIN, requires=["cli", "js_app"]),
        app("doom", FlipperAppType.EXTERNAL, fap_category="Games"),
        app("tetris", FlipperAppType.EXTERNAL, fap_category="Games"),
        app("nfc_tool", FlipperAppType.EXTERNAL, fap_category="NFC"),
        app("nfc_plugin", FlipperAppType.PLUGIN, requires=["nfc_tool"]),
    ]:
        mgr._add_known_app(a)
    return mgr


def ids(buildset):
    return sorted(a.appid for a in buildset.get_ext_apps())


# Nothing excluded: every external app and plugin with a built parent is in the set
bs = manager().filter_apps(applist=["default"], ext_applist=[], hw_target="f7")
check(
    ids(bs)
    == [
        "cli_js",
        "doom",
        "js_app",
        "js_gui",
        "nfc_plugin",
        "nfc_tool",
        "subghz",
        "test_js",
        "tetris",
    ],
    f"nothing excluded: {ids(bs)}",
)

# js_app and cli_js by id, Games by category: js_gui follows js_app, but test_js stays, because
# its other parent (cli, standing in for unit_tests) is still built; this is why the fork names
# test_js in EXCLUDE_EXT_APPS too
bs = manager().filter_apps(
    applist=["default"],
    ext_applist=[],
    hw_target="f7",
    exclude_apps=["js_app", "cli_js"],
    exclude_categories=["Games"],
)
check(
    ids(bs) == ["nfc_plugin", "nfc_tool", "subghz", "test_js"], f"js_app and cli_js by id: {ids(bs)}"
)

# A category exclusion alone leaves the JS apps alone
bs = manager().filter_apps(
    applist=["default"], ext_applist=[], hw_target="f7", exclude_categories=["Games"]
)
check(
    ids(bs) == ["cli_js", "js_app", "js_gui", "nfc_plugin", "nfc_tool", "subghz", "test_js"],
    f"category only: {ids(bs)}",
)

# The fork's configuration, test_js named, plus an unknown id: test_js leaves; the unknown id
# is reported once and does not fail the build; the count names what went
messages = []
bs = AppBuildset(
    manager(),
    hw_target="f7",
    appnames=["default"],
    extra_ext_appnames=[],
    exclude_apps=["js_app", "cli_js", "test_js", "nope"],
    exclude_categories=["Games"],
    message_writer=messages.append,
)
check(ids(bs) == ["nfc_plugin", "nfc_tool", "subghz"], f"unknown id: {ids(bs)}")
check(any("nope" in m and "unknown" in m for m in messages), f"unknown id reported: {messages}")
check(any(m.startswith("Excluded 5 external apps") for m in messages), f"count reported: {messages}")

print(f"fbt exclusions: {failures} failures")
sys.exit(1 if failures else 0)
