"""Shared pieces of the transcript-per-slide scripts: config, paths, transcript parsing,
and the hand-off to the agent.

Every script takes --root (the course folder, default: current directory) and
--config (default: <root>/transcript-per-slide.toml). See
assets/transcript-per-slide.example.toml for the settings.

Hand-off: when a script meets something it cannot handle (an unreadable or
misnamed file, a format it does not parse, a missing dependency, its own bug),
it never crashes with a bare traceback and never skips silently. It prints a
`NEEDS AGENT [code]` block saying what it could not do and what to do instead,
and exits with status 3. The codes are explained in references/handoffs.md.
"""

from __future__ import annotations

import argparse
import codecs
import fnmatch
import hashlib
import json
import locale
import os
import re
import sys
import traceback
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit("NEEDS AGENT [python-version] transcript-per-slide needs Python 3.11 or newer "
             f"(for tomllib); this is {sys.version.split()[0]}. Try `py -3.12` or `python3.12`, "
             "or tell the student to install Python 3.11+.")

import tomllib

# Slide titles and notes are full of non-ASCII; don't let a legacy console codepage mangle them.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

CONFIG_NAME = "transcript-per-slide.toml"
SKILL_DIR = Path(__file__).resolve().parents[1]
EXAMPLE_CONFIG = SKILL_DIR / "assets" / "transcript-per-slide.example.toml"
STUDY_README = SKILL_DIR / "assets" / "study-README.md"
TRANSCRIPT_SUFFIXES = {".txt", ".vtt", ".srt", ".json"}
# Never searched for course files: tool and environment folders (hidden ones are skipped too).
JUNK_DIRS = {"node_modules", "__pycache__", "venv", "env", "site-packages"}
JUNK_FILES = {"desktop.ini", "thumbs.db"}
DECK_SUFFIXES = {".pptx", ".ppt", ".key", ".odp"}
WORD_SUFFIXES = {".docx", ".doc", ".rtf", ".odt", ".pages"}
MEDIA_SUFFIXES = {".mp4", ".m4a", ".mp3", ".mov", ".wav", ".webm", ".mkv", ".aac", ".m4v"}

# Fields of a pairs.json entry that name an input file (the *_from ones: originals of converted copies).
PAIR_FILES = ("slides", "transcript", "slides_from", "transcript_from")

DEFAULTS = {
    "paths": {"slides": ["slides", "labs"], "transcripts": ["transcripts"], "output": "study",
              "ignore": []},
    "slides": {"footer_patterns": [], "zoom": 1.8, "border": True},
    "transcript": {"skip_speakers": [], "asr_fixes": {}, "min_segment_chars": 120,
                   "pause_split_seconds": 4},
}

SPEAKER_RE = re.compile(r"^SPEAKER\s+(\S+)\s*$", re.M)
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
TIME = r"(?:(\d{1,2}):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
TIMING_RE = re.compile(rf"{TIME}\s*-->\s*{TIME}")
VOICE_RE = re.compile(r"<v(?:\.[^ >]*)?\s+([^>]+)>")
TAG_RE = re.compile(r"<[^>]+>")
NOTE_RE = re.compile(r"<!-- note:(\d+) -->\n?(.*?)<!-- /note:\1 -->", re.S)
HANDOFFS_DOC = SKILL_DIR / "references" / "handoffs.md"
NEEDS_AGENT = 3  # exit status when something was handed to the agent


# --------------------------------------------------------------------------- hand-off


class NeedsAgent(Exception):
    """Something only the agent can sort out. Raise it to stop; use handoff() to carry on."""

    def __init__(self, code: str, subject, problem: str, do: str):
        super().__init__(f"[{code}] {subject}: {problem}")
        self.code, self.subject, self.problem, self.do = code, subject, problem, do


_handed: list[tuple[str, str]] = []
_noted: set[str] = set()
_root: Path | None = None


def show(p) -> str:
    """A path as the student would name it: relative to the course folder when possible."""
    if not isinstance(p, Path):
        return str(p)
    try:
        return p.resolve().relative_to(_root).as_posix() if _root else p.as_posix()
    except ValueError:
        return p.resolve().as_posix()


def handoff(code: str, subject, problem: str, do: str, details: list[str] | None = None) -> None:
    """Report something the agent must handle, and let the script carry on with the rest."""
    key = (code, show(subject))
    if key in _handed:
        return
    _handed.append(key)
    print(f"NEEDS AGENT [{code}] {show(subject)}")
    print(f"  problem: {problem}")
    for d in details or []:
        print(f"    {d}")
    print(f"  do: {do}")


def handoff_from(e: NeedsAgent) -> None:
    handoff(e.code, e.subject, e.problem, e.do)


def note(msg: str) -> None:
    """Something the script guessed and handled; worth one line, no action needed."""
    if msg not in _noted:
        _noted.add(msg)
        print(f"note: {msg}")


def run(main) -> int:
    """Run a script's main(): turn NeedsAgent and crashes into hand-offs, never a bare traceback."""
    try:
        status = main() or 0
    except NeedsAgent as e:
        handoff_from(e)
        status = NEEDS_AGENT
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:
        tb = traceback.extract_tb(e.__traceback__)
        where = f"{Path(tb[-1].filename).name}:{tb[-1].lineno}" if tb else "?"
        handoff("crash", Path(sys.argv[0]).name,
                f"the script itself failed: {e.__class__.__name__}: {e} (at {where})",
                "Read the error. If an input file caused it, convert or fix a copy of that input "
                "(handoffs.md#crash); if it is a bug in the script, do this step by hand to the same "
                "output format and tell the student the script has a bug.",
                details=[ln.rstrip() for ln in traceback.format_exception(e)[-4:]])
        status = NEEDS_AGENT
    if _handed:
        print(f"\n{len(_handed)} item(s) NEED THE AGENT (above). Playbook: {HANDOFFS_DOC.as_posix()}")
        return NEEDS_AGENT
    return status


# --------------------------------------------------------------------------- reading files by content


def sniff(path: Path) -> str:
    """What a file really is, from its first bytes: pdf, captions, json, text, office, binary."""
    try:
        with open(path, "rb") as f:
            head = f.read(4096)
    except OSError:
        return "unreadable"
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        return "office"  # .pptx/.docx/.key are zip containers (or any zip)
    if head.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)) or head[1:200:2].count(0) > 50:
        text = head.decode("utf-16", errors="replace")
    elif b"\x00" in head:
        return "binary"
    else:
        text = head.decode("utf-8", errors="replace").lstrip("﻿")
    s = text.lstrip()
    if s.startswith("WEBVTT") or TIMING_RE.search(text):
        return "captions"
    if s[:1] in "{[":
        return "json"
    return "text"


def read_text_any(path: Path) -> str:
    """Decode a text file whatever Windows/Mac tool saved it; hand off when it had to guess."""
    data = path.read_bytes()
    if data.startswith(codecs.BOM_UTF8):
        return data[3:].decode("utf-8", errors="replace")
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", errors="replace")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        pass
    sample = data[:4000]
    if sample[1::2].count(0) > len(sample) // 4:  # UTF-16 without a BOM
        return data.decode("utf-16-le" if sample[1:2] == b"\x00" else "utf-16-be", errors="replace")
    enc = locale.getpreferredencoding(False) or "latin-1"
    handoff("encoding", path,
            f"not UTF-8; read it as {enc}, which may garble words (accents, Chinese, quotes)",
            "Look at the preview / segments. If any text is garbled, write a UTF-8 copy into "
            "<output>/_converted/ and pair that copy (handoffs.md#encoding).")
    return data.decode(enc, errors="replace")


def open_pdf(path: Path):
    """Open a slide deck with PyMuPDF by content (a PDF saved without .pdf still opens)."""
    fz = fitz()
    kind = sniff(path)
    try:
        # PyMuPDF also opens HTML, images and e-books as "documents"; a login page saved as
        # slides.pdf would become a one-page deck. Only real PDF bytes count.
        if kind != "pdf":
            raise ValueError(f"the file is not a PDF inside (looks like {kind})")
        doc = fz.open(path, filetype="pdf")
    except Exception as e:
        do = {"office": "It is a PowerPoint/Keynote/zip file, not a PDF: the student exports it as PDF.",
              "text": "It is a text/HTML file named .pdf: usually a failed download (a login or error "
                      "page). Ask the student to download the slides again while logged in."}.get(
            kind, "Check the file opens in a PDF viewer. If it is damaged, ask the student to "
                  "download it again.")
        raise NeedsAgent("pdf-unreadable", path, f"PyMuPDF cannot open it as a PDF ({e})", do)
    if doc.needs_pass:
        doc.close()
        raise NeedsAgent("pdf-locked", path, "the PDF is password-protected",
                         "Ask the student for an unlocked copy (or the password, then save an "
                         "unlocked copy into <output>/_converted/ and pair that).")
    return doc


# --------------------------------------------------------------------------- project


class Project:
    def __init__(self, root: Path, config_path: Path | None = None):
        global _root
        self.root = _root = root.resolve()
        if not self.root.is_dir():
            raise NeedsAgent("no-course-folder", self.root.as_posix(), "this folder does not exist",
                             "Run from the course folder, or pass --root <course folder>.")
        self.config_path = config_path or self.root / CONFIG_NAME
        cfg = {k: dict(v) for k, v in DEFAULTS.items()}
        if self.config_path.exists():
            # utf-8-sig: Windows editors and PowerShell often save with a BOM, which tomllib rejects.
            try:
                loaded = tomllib.loads(self.config_path.read_text(encoding="utf-8-sig"))
            except tomllib.TOMLDecodeError as e:
                raise NeedsAgent("bad-config", self.config_path, f"not valid TOML: {e}",
                                 "Fix that line (Windows paths need single quotes or forward "
                                 "slashes: 'E:\\Course\\ppt' or \"E:/Course/ppt\").") from None
            for section, values in loaded.items():
                if isinstance(values, dict):
                    cfg.setdefault(section, {}).update(values)
                else:
                    cfg[section] = values
        self.cfg = cfg
        paths = cfg["paths"]
        self.slide_dirs = [self.path(p) for p in _as_list(paths["slides"])]
        self.transcript_dirs = [self.path(p) for p in _as_list(paths["transcripts"])]
        self.out = self.path(paths["output"])
        self.footer_res = [re.compile(p, re.I | re.M) for p in cfg["slides"]["footer_patterns"]]
        self.asr_fixes = [
            (re.compile(rf"\b{re.escape(wrong)}\b", re.I), right)
            for wrong, right in cfg["transcript"]["asr_fixes"].items()
        ]
        self.skip_speakers = {str(s) for s in cfg["transcript"]["skip_speakers"]}

    def path(self, p: str | Path) -> Path:
        q = Path(p)
        return q if q.is_absolute() else self.root / q

    def rel(self, p: Path) -> str:
        try:
            return p.resolve().relative_to(self.root).as_posix()
        except ValueError:
            return p.resolve().as_posix()

    @property
    def pairs_path(self) -> Path:
        return self.out / "pairs.json"

    def pairs(self) -> list[dict]:
        """pairs.json: which deck goes with which recording. Read once per run and kept
        in step with the files (see _track): a renamed or moved file is followed."""
        if not hasattr(self, "_pairs"):
            if not self.pairs_path.exists():
                self._pairs = []
            else:
                data = read_json(self.pairs_path)
                self._pairs = data.get("pairs", [])
                if self._track(self._pairs):
                    write_json(self.pairs_path, data)
        return self._pairs

    def _track(self, pairs: list[dict]) -> bool:
        """Record a fingerprint (sha256 + size) of every paired file, and follow files the
        student renamed or moved: a missing file is looked up by its fingerprint anywhere in
        the course folder and pairs.json is pointed at it. Returns True if pairs.json changed."""
        changed = False
        in_use = {self.path(p[f]).resolve() for p in pairs for f in PAIR_FILES if p.get(f)}
        for p in pairs:
            key = p.get("key", "?")
            fps = p.get("fingerprints") if isinstance(p.get("fingerprints"), dict) else {}
            for field in PAIR_FILES:
                if not p.get(field):
                    continue
                path, old = self.path(p[field]), fps.get(field) or {}
                if path.is_file():
                    size = path.stat().st_size
                    if old.get("bytes") == size and old.get("sha256"):
                        continue  # same name, same size: unchanged (no need to re-hash every run)
                    new = fingerprint(path)
                    if new == old:
                        continue
                    if old.get("sha256") and new["sha256"] != old["sha256"]:
                        if self.packed(key):
                            handoff("input-changed", path,
                                    f"{key}: this file's content changed since the lecture was packed "
                                    "(the lecturer updated it, or another file was saved under this name)",
                                    "Look at it. Same lecture, updated: ask the student whether to redo the "
                                    "pack (Redo; tutoring notes survive). A different lecture: fix pairs.json "
                                    "(handoffs.md#input-changed).")
                        else:
                            note(f"{key}: {p[field]} changed since it was paired; re-extract before aligning")
                    fps[field], changed = new, True
                    continue
                found = self.find_by_fingerprint(old, in_use) if old.get("sha256") else None
                if found:
                    new_rel = self.rel(found)
                    note(f"{key}: {p[field]} was renamed or moved to {new_rel}; pairs.json updated")
                    self._repath(key, p[field], new_rel)
                    in_use.add(found.resolve())
                    p[field], changed = new_rel, True
                else:
                    loose = [self.rel(f) for f in (self.slide_files() if field.startswith("slides")
                                                   else self.transcript_files())
                             if f.resolve() not in in_use][:12]
                    handoff("pair-missing-file", path,
                            f"{key}: the {field.replace('_', ' ')} file is gone, and no file in the course "
                            "folder has the same content" if old.get("sha256") else
                            f"{key}: the {field.replace('_', ' ')} file is gone (no fingerprint recorded yet)",
                            "Renamed and changed, or deleted. Find it by content among the unpaired files "
                            "(inventory.json previews) and fix the path in pairs.json; if it is really gone, "
                            "ask the student (handoffs.md#pair-missing-file).",
                            details=[f"unpaired: {f}" for f in loose])
            if fps and p.get("fingerprints") is not fps:
                p["fingerprints"], changed = fps, True
        return changed

    def walk_files(self):
        """Every file in the course folder that could be an input (same skips as locate.py)."""
        for dirpath, dirnames, filenames in os.walk(self.root):
            here = Path(dirpath)
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in JUNK_DIRS
                           and not self.skipped(here / d / "_", self.root)]
            for name in filenames:
                if not name.startswith("."):
                    yield here / name

    def find_by_fingerprint(self, fp: dict, exclude: set[Path]) -> Path | None:
        """The one file with this content (size first, then sha256); None if none or ambiguous."""
        # Size first so only likely files get hashed; text files may differ in size by their
        # line endings alone (one byte per line), so those are compared on a size band.
        def close(f: Path) -> bool:
            size, want = f.stat().st_size, fp.get("bytes") or 0
            return size == want or (f.suffix.lower() != ".pdf" and want // 2 <= size <= want * 2)

        candidates = [f for f in self.walk_files() if f.resolve() not in exclude and close(f)]
        matches = [f for f in candidates if fingerprint(f)["sha256"] == fp["sha256"]]
        if len(matches) > 1:
            note(f"{len(matches)} identical copies found ({', '.join(self.rel(m) for m in matches)}); "
                 f"using {self.rel(matches[0])}")
        return matches[0] if matches else None

    def _repath(self, key: str, old: str, new: str) -> None:
        """A renamed input: update the lecture's working files that name it (never the notes)."""
        old_rel = self.rel(self.path(old))
        ex_path = self.out / key / "extracted.json"
        if ex_path.exists():
            ex = read_json(ex_path)
            hit = [f for f in ("slides_pdf", "transcript", "slides_from", "transcript_from")
                   if ex.get(f) and self.rel(self.path(ex[f])) == old_rel]
            for f in hit:
                ex[f] = new
            if hit:
                write_json(ex_path, ex)
        pack = self.out / key / "pack.md"
        if pack.exists():  # only the two header lines; everything else is the student's
            text = pack.read_text(encoding="utf-8")
            lines = text.split("\n")
            for i, ln in enumerate(lines[:8]):
                if ln.startswith(("Slides: ", "Transcript: ")):
                    lines[i] = ln.replace(f"`{old_rel}`", f"`{new}`")
            if lines != text.split("\n"):
                pack.write_text("\n".join(lines), encoding="utf-8", newline="\n")

    def paired_files(self) -> dict[str, str]:
        """Input files already in a pair -> key. A converted copy also covers its original
        (`slides_from` / `transcript_from`), so the original never shows up as unpaired."""
        paired = {}
        for p in self.pairs():
            for field in PAIR_FILES:
                if p.get(field):
                    paired[self.rel(self.path(p[field]))] = p["key"]
        return paired

    def packed(self, key: str) -> bool:
        return (self.out / key / "pack.md").exists()

    def skipped(self, path: Path, base: Path) -> bool:
        """True for files that are never course inputs: our own output, the skill's
        demo files, and anything under a hidden or tool folder (.git, .claude, .venv)."""
        path = path.resolve()
        if path.is_relative_to(self.out.resolve()):
            return True
        # The skill's demo files, unless the course *is* inside the skill (examples/demo).
        if path.is_relative_to(SKILL_DIR) and not self.root.is_relative_to(SKILL_DIR):
            return True
        parts = path.relative_to(base.resolve()).parts[:-1] if path.is_relative_to(base.resolve()) else ()
        return any(p.startswith(".") or p in JUNK_DIRS for p in parts)

    def ignored(self, path: Path) -> bool:
        """Files the agent marked as not lecture material: [paths] ignore, globs from the course folder."""
        rel = self.rel(path)
        return any(fnmatch.fnmatch(rel, g) or fnmatch.fnmatch(path.name, g)
                   for g in _as_list(self.cfg["paths"].get("ignore", [])))

    def inputs(self) -> tuple[list[Path], list[Path], list[tuple[Path, str]]]:
        """Every file in the slide and transcript folders, sorted by what it *is*, not what it
        is called: (slide PDFs, transcripts, [(other file, kind)]). Misnamed PDFs and caption
        files are used as they are; everything else is for the agent to decide."""
        if hasattr(self, "_inputs"):
            return self._inputs
        roles: dict[Path, set[str]] = {}
        for role, dirs in (("slides", self.slide_dirs), ("transcripts", self.transcript_dirs)):
            for d in dirs:
                if not d.is_dir():
                    continue
                for p in sorted(d.rglob("*")):
                    if (p.is_file() and not p.name.startswith(".") and p.name.lower() not in JUNK_FILES
                            and not self.skipped(p, d) and not self.ignored(p)):
                        roles.setdefault(p, set()).add(role)
        slides, transcripts, other = [], [], []
        for p, r in roles.items():
            suffix = p.suffix.lower()
            known = suffix in {".pdf"} | TRANSCRIPT_SUFFIXES | DECK_SUFFIXES | WORD_SUFFIXES | MEDIA_SUFFIXES
            kind = sniff(p) if not known or suffix == ".pdf" else ""
            if suffix == ".pdf" or kind == "pdf":
                if "slides" in r:
                    slides.append(p)
                    if suffix != ".pdf":
                        note(f"{self.rel(p)}: a PDF without .pdf in its name; used as slides")
                else:
                    other.append((p, "pdf-in-transcripts"))
            elif suffix in DECK_SUFFIXES or (kind == "office" and "slides" in r and "transcripts" not in r):
                other.append((p, "deck"))
            elif suffix in WORD_SUFFIXES or kind == "office":
                other.append((p, "word"))
            elif suffix in MEDIA_SUFFIXES:
                other.append((p, "media"))
            elif suffix in TRANSCRIPT_SUFFIXES or kind in {"captions", "json"}:
                if "transcripts" not in r:
                    other.append((p, "text"))
                elif (suffix == ".json" or kind == "json") and not transcript_units(self, p):
                    other.append((p, "json"))
                else:
                    transcripts.append(p)
            else:
                other.append((p, kind or "unknown"))
        self._inputs = (sorted(slides), sorted(transcripts), sorted(other))
        return self._inputs

    def slide_files(self) -> list[Path]:
        return self.inputs()[0]

    def transcript_files(self) -> list[Path]:
        return self.inputs()[1]

    def ensure_study_readme(self) -> None:
        """Put the reader's guide into the output folder once; never overwrite it."""
        target = self.out / "README.md"
        if not target.exists() and STUDY_README.exists():
            self.out.mkdir(parents=True, exist_ok=True)
            target.write_text(STUDY_README.read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
            print(f"wrote {self.rel(target)}")


def parser(description: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=description)
    ap.add_argument("--root", type=Path, default=Path.cwd(), help="course folder (default: cwd)")
    ap.add_argument("--config", type=Path, help=f"config file (default: <root>/{CONFIG_NAME})")
    return ap


def project(args) -> Project:
    return Project(args.root, args.config)


def _as_list(v) -> list:
    return v if isinstance(v, list) else [v]


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def fingerprint(path: Path) -> dict:
    """Content identity of an input, independent of its name. Text files are hashed with
    line endings normalized, so git autocrlf or an editor re-save is not a "change"."""
    h = hashlib.sha256()
    if sniff(path) == "pdf":
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
    else:
        h.update(path.read_bytes().replace(b"\r\n", b"\n"))
    return {"sha256": h.hexdigest(), "bytes": path.stat().st_size}


def read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        raise NeedsAgent("bad-json", path, f"not valid JSON at line {e.lineno}, column {e.colno}: {e.msg}",
                         "pairs.json and alignment.json are yours: fix the JSON and rerun. "
                         "inventory.json / extracted.json: rerun the script that writes them.") from None


def fitz():
    try:
        import fitz as mod  # PyMuPDF
    except ImportError:
        raise NeedsAgent("missing-dependency", "PyMuPDF", f"not installed for {sys.executable}",
                         "Tell the student the command (python -m pip install pymupdf, ideally in "
                         "the course's venv) and ask before installing anything.") from None
    return mod


def kept_notes(pack: Path) -> dict[int, str]:
    """Tutoring blocks already written into pack.md, by slide number."""
    if not pack.exists():
        return {}
    kept = {}
    for k, body in NOTE_RE.findall(pack.read_text(encoding="utf-8", errors="replace")):
        if body.strip():
            kept[int(k)] = body.strip("\n")
    return kept


# --------------------------------------------------------------------------- transcripts


def _seconds(h, m, s, frac) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(frac.ljust(3, "0")) / 1000


def _hms(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600:02d}:{sec % 3600 // 60:02d}:{sec % 60:02d}"


def _json_units(raw: str) -> list[dict]:
    """Whisper-style JSON: {"segments": [{start, end, text, speaker?}]} or a bare list."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    items = data.get("segments") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    units = []
    for it in items:
        if isinstance(it, dict) and isinstance(it.get("text"), str):
            start, end = it.get("start"), it.get("end")
            units.append({
                "speaker": str(it.get("speaker") or ""),
                "start": float(start) if isinstance(start, (int, float)) else None,
                "end": float(end) if isinstance(end, (int, float)) else None,
                "text": it["text"],
            })
    return units


STAMP_LINE_RE = re.compile(
    r"^\s*[\[(]?\d{1,2}:\d{2}(?::\d{2})?(?:[.,]\d+)?[\])]?(\s|$)"   # "[00:01:23] text", "0:03"
    r"|\s\d{1,2}:\d{2}(?::\d{2})?\s*$")                                # "Speaker 1  0:03" (Otter, Zoom)


def transcript_format(path: Path, raw: str) -> str:
    """captions / json / text, by content first: a .txt full of '-->' timings is captions."""
    head = raw[:4000].lstrip()
    if head.startswith("WEBVTT") or TIMING_RE.search(head):
        fmt = "captions"
    elif path.suffix.lower() == ".json" or (head[:1] in "{[" and _json_units(raw)):
        fmt = "json"  # (a text that merely opens with "[Music]" stays text)
    else:
        fmt = "text"
    expected = {".vtt": "captions", ".srt": "captions", ".json": "json", ".txt": "text"}.get(path.suffix.lower())
    if expected != fmt:
        note(f"{show(path)}: read as {fmt} (by its content{', not its extension' if expected else ''})")
    return fmt


def transcript_units(proj: Project, path: Path) -> list[dict]:
    """Return [{speaker, start, end, text}] in spoken order, before chunking.

    start/end are seconds for caption and JSON files, None for plain text.
    """
    raw = read_text_any(path).replace("\r\n", "\n")
    fmt = transcript_format(path, raw)
    units: list[dict] = []
    if fmt == "json":
        units = _json_units(raw)
    elif fmt == "captions":
        for block in re.split(r"\n\s*\n", raw):
            lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
            timing = next((i for i, ln in enumerate(lines) if "-->" in ln), None)
            if timing is None:
                continue  # WEBVTT header, NOTE, STYLE
            m = TIMING_RE.search(lines[timing])
            start = _seconds(*m.groups()[:4]) if m else None
            end = _seconds(*m.groups()[4:]) if m else None
            text = " ".join(lines[timing + 1:])
            vm = VOICE_RE.search(text)
            speaker = vm.group(1).strip() if vm else ""
            text = TAG_RE.sub("", text).strip()
            if text:
                units.append({"speaker": speaker, "start": start, "end": end, "text": text})
    else:
        parts = SPEAKER_RE.split(raw)
        if len(parts) > 1:  # Echo360-style "SPEAKER N" blocks
            for speaker, body in zip(parts[1::2], parts[2::2]):
                # Each block is its own turn: a segment never spans two blocks.
                units.append({"speaker": speaker, "start": None, "end": None, "text": body,
                              "block": True})
        else:
            lines = [ln for ln in raw.split("\n") if ln.strip()]
            stamped = sum(1 for ln in lines if STAMP_LINE_RE.search(ln))
            if stamped >= 5 and stamped >= len(lines) // 4:
                handoff("timestamped-text", path,
                        f"{stamped} of {len(lines)} lines carry timestamps in a layout the scripts "
                        "do not parse; they would end up in the text and the timings would be lost",
                        "Convert it to .vtt in <output>/_converted/ keeping every word and time, "
                        "and pair the copy with transcript_from (handoffs.md#timestamped-text).")
            units = [{"speaker": "", "start": None, "end": None, "text": p}
                     for p in re.split(r"\n\s*\n", raw)]
    out = []
    for u in units:
        if u["speaker"] in proj.skip_speakers:
            continue
        text = re.sub(r"\s+", " ", u["text"]).strip()
        for rx, right in proj.asr_fixes:
            text = rx.sub(right, text)
        if text:
            out.append({**u, "text": text})
    return out


def transcript_preview(proj: Project, path: Path, limit: int = 1200) -> str:
    return " ".join(u["text"] for u in transcript_units(proj, path))[:limit]
