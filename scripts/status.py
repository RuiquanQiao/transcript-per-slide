#!/usr/bin/env python3
"""Show where every lecture is: paired, extracted, aligned, packed; and files not paired yet.

    python status.py [--root COURSE]
"""

from __future__ import annotations

import common as c
from validate import check


def main() -> int:
    args = c.parser(__doc__.split("\n\n")[0]).parse_args()
    proj = c.project(args)
    print(f"root:   {proj.root}")
    print(f"config: {proj.rel(proj.config_path) if proj.config_path.exists() else '(none, using defaults)'}")
    pairs = proj.pairs()
    paired_files = {proj.rel(proj.path(p[f])) for p in pairs for f in ("slides", "transcript") if p.get(f)}
    loose = [proj.rel(p) for p in c.find_files(proj.slide_dirs, {".pdf"})
             + c.find_files(proj.transcript_dirs, c.TRANSCRIPT_SUFFIXES)
             if proj.rel(p) not in paired_files]
    if not pairs:
        print("no pairs yet")
    for p in pairs:
        key, folder = p["key"], proj.out / p["key"]
        if proj.packed(key):
            n = len(c.kept_notes(folder / "pack.md"))
            figs = len([f for f in (folder / "extras").glob("*") if f.is_file()]) \
                if (folder / "extras").exists() else 0
            state = f"packed ({n} slide{'s' if n != 1 else ''} with tutoring notes, {figs} figure{'s' if figs != 1 else ''})"
        elif (folder / "alignment.json").exists():
            _, errors, _ = check(folder)
            state = "aligned, ready to render" if not errors else f"aligned with {len(errors)} error(s)"
        elif (folder / "extracted.json").exists():
            state = "extracted, needs alignment"
        else:
            state = "paired, needs extract"
        if not p.get("transcript"):
            state += "; no transcript yet"
        print(f"  {key:<12} {state}")
    if loose:
        print("not paired yet:")
        for f in loose:
            print(f"  {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
