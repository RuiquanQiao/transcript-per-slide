#!/usr/bin/env python3
"""Set up a course folder: write transcript-per-slide.toml and the study folder's README.

Never overwrites an existing config or README.

    python init.py [--root COURSE]
"""

from __future__ import annotations

import shutil

import common as c


def main() -> int:
    args = c.parser(__doc__.split("\n\n")[0]).parse_args()
    proj = c.project(args)
    if proj.config_path.exists():
        print(f"{proj.rel(proj.config_path)} already exists; leaving it alone.")
    else:
        shutil.copyfile(c.EXAMPLE_CONFIG, proj.config_path)
        print(f"wrote {proj.rel(proj.config_path)}")
    for d in proj.slide_dirs + proj.transcript_dirs:
        print(f"  {proj.rel(d)}/: {'ok' if d.exists() else 'missing (fine if unused)'}")
    print(f"  packs go to {proj.rel(proj.out)}/")
    proj.ensure_study_readme()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
