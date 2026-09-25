#!/usr/bin/env python3
"""Flash and static RAM per library, app or object from the firmware's linker map.
Usage: python3 tools/map_size.py Momentum-Firmware/build/f7-firmware-C/firmware.elf.map [lib|obj]
Counts loaded sections only: flash addresses for flash, RAM addresses for data and bss, with
.data counted in both since its initial values sit in flash. Output: flash bytes, RAM bytes,
group, largest first, then the totals."""
import collections
import re
import sys


def main():
    path = sys.argv[1]
    groupby = sys.argv[2] if len(sys.argv) > 2 else "lib"
    flash = collections.Counter()
    ram = collections.Counter()

    def key_of(obj):
        obj = re.sub(r"^build/f7-firmware-C/", "", obj)
        obj = re.sub(r"^/.*?/arm-none-eabi/", "toolchain/", obj)
        if groupby == "obj":
            return obj
        m = re.match(r"lib/(lib\w+\.a)\((.*)\)", obj)
        if m:
            return "lib/" + m.group(1)
        parts = obj.split("/")
        if parts[0] == "applications":
            return "/".join(parts[:3])
        if parts[0] in ("lib", "targets"):
            return "/".join(parts[:2])
        return parts[0]

    pending = None
    started = False
    for line in open(path, errors="replace"):
        if line.startswith("Linker script and memory map"):
            started = True
            continue
        if not started:
            continue
        if line.startswith("OUTPUT("):
            break
        m = re.match(r"^ (\.\S+)\s*$", line)
        if m:
            pending = m.group(1)
            continue
        m = re.match(r"^ (\.\S+)?\s+0x([0-9a-f]+)\s+0x([0-9a-f]+)\s+(\S.*)$", line)
        if not m:
            pending = None
            continue
        sec = m.group(1) or pending
        pending = None
        if not sec:
            continue
        addr = int(m.group(2), 16)
        size = int(m.group(3), 16)
        obj = m.group(4).strip()
        if size == 0 or obj.startswith("*") or "load address" in obj:
            continue
        k = key_of(obj)
        if 0x08000000 <= addr < 0x08100000:
            flash[k] += size
        elif 0x20000000 <= addr < 0x20040000:
            ram[k] += size
            if sec.startswith(".data"):
                flash[k] += size
    print(f"{'flash':>8} {'ram':>7}  group")
    for k, v in flash.most_common():
        print(f"{v:8d} {ram[k]:7d}  {k}")
    for k in ram:
        if k not in flash:
            print(f"{0:8d} {ram[k]:7d}  {k}")
    print("TOTAL flash", sum(flash.values()), "static ram", sum(ram.values()))


if __name__ == "__main__":
    main()
