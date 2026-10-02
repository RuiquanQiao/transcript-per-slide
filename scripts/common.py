"""Shared pieces of the transcript-per-slide scripts: config, paths, transcript parsing.

Every script takes --root (the course folder, default: current directory) and
--config (default: <root>/transcript-per-slide.toml). See
assets/transcript-per-slide.example.toml for the settings.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

if sys.version_info < (3, 11):
    sys.exit("transcript-per-slide needs Python 3.11 or newer (for tomllib).")

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

DEFAULTS = {
    "paths": {"slides": ["slides", "labs"], "transcripts": ["transcripts"], "output": "study"},
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


# --------------------------------------------------------------------------- project


class Project:
    def __init__(self, root: Path, config_path: Path | None = None):
        self.root = root.resolve()
        self.config_path = config_path or self.root / CONFIG_NAME
        cfg = {k: dict(v) for k, v in DEFAULTS.items()}
        if self.config_path.exists():
            loaded = tomllib.loads(self.config_path.read_text(encoding="utf-8"))
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
        if not self.pairs_path.exists():
            return []
        return read_json(self.pairs_path).get("pairs", [])

    def packed(self, key: str) -> bool:
        return (self.out / key / "pack.md").exists()

    def ensure_study_readme(self) -> None:
        """Put the reader's guide into the output folder once; never overwrite it."""
        target = self.out / "README.md"
        if not target.exists() and STUDY_README.exists():
            self.out.mkdir(parents=True, exist_ok=True)
            target.write_text(STUDY_README.read_text(encoding="utf-8"), encoding="utf-8")
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
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def fitz():
    try:
        import fitz as mod  # PyMuPDF
    except ImportError:
        sys.exit("PyMuPDF is required: python -m pip install pymupdf")
    return mod


def find_files(dirs: list[Path], suffixes: set[str]) -> list[Path]:
    found = []
    for d in dirs:
        if d.exists():
            found += [p for p in sorted(d.rglob("*"))
                      if p.is_file() and p.suffix.lower() in suffixes and not p.name.startswith(".")]
    return found


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


def transcript_units(proj: Project, path: Path) -> list[dict]:
    """Return [{speaker, start, end, text}] in spoken order, before chunking.

    start/end are seconds for caption and JSON files, None for plain text.
    """
    raw = path.read_text(encoding="utf-8-sig", errors="replace").replace("\r\n", "\n")
    suffix = path.suffix.lower()
    units: list[dict] = []
    if suffix == ".json":
        units = _json_units(raw)
    elif suffix in {".vtt", ".srt"}:
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
