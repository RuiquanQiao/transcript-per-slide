"""End-to-end tests: run the scripts on small course folders built from the demo lecture.

    python -m unittest discover tests

Course folders are built under <repo>/.cache/tests/ (git-ignored) and rebuilt per test.
Needs Python 3.11+ and PyMuPDF, like the scripts.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts"
DEMO = REPO / "examples" / "demo"
WORK = REPO / ".cache" / "tests"
PDF = DEMO / "slides" / "binary-search.pdf"
VTT = DEMO / "transcripts" / "binary-search-recording.vtt"

try:
    import fitz  # noqa: F401
    HAVE_PYMUPDF = True
except ImportError:
    HAVE_PYMUPDF = False


def run(script: str, root: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(SCRIPTS / f"{script}.py"), "--root", str(root), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, p.stdout + p.stderr


def codes(out: str) -> set[str]:
    return {ln.split("[", 1)[1].split("]", 1)[0] for ln in out.splitlines() if ln.startswith("NEEDS AGENT [")}


@unittest.skipUnless(HAVE_PYMUPDF, "PyMuPDF is not installed")
class Base(unittest.TestCase):
    def course(self, name: str) -> Path:
        root = WORK / name
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        return root

    def demo_copy(self, name: str) -> Path:
        root = WORK / name
        shutil.rmtree(root, ignore_errors=True)
        shutil.copytree(DEMO, root)
        return root

    def pairs(self, root: Path) -> list[dict]:
        return json.loads((root / "study" / "pairs.json").read_text(encoding="utf-8"))["pairs"]


class Demo(Base):
    def test_demo_is_clean(self):
        before = (DEMO / "study" / "pairs.json").read_bytes()
        for script in ("status", "validate"):
            code, out = run(script, DEMO)
            self.assertEqual(code, 0, out)
        self.assertEqual((DEMO / "study" / "pairs.json").read_bytes(), before,
                         "a plain run must not rewrite the demo's pairs.json")


class FindingFiles(Base):
    def test_odd_folder_names_and_skipped_folders(self):
        root = self.course("odd-names")
        for d in ("ppt", "Echo360 downloads", "env", ".claude/skills/tps", "node_modules/x", "venv"):
            (root / d).mkdir(parents=True)
        shutil.copy(PDF, root / "ppt" / "Week 2.pdf")
        shutil.copy(VTT, root / "Echo360 downloads" / "rec.vtt")
        shutil.copy(PDF, root / "env" / "Environment week 1.pdf")      # a course folder called env
        shutil.copy(PDF, root / ".claude/skills/tps" / "hidden.pdf")
        shutil.copy(PDF, root / "node_modules/x" / "junk.pdf")
        (root / "venv" / "pyvenv.cfg").write_text("home = x\n")
        shutil.copy(PDF, root / "venv" / "junk.pdf")
        code, out = run("locate", root)
        self.assertEqual(code, 0, out)
        for seen in ("ppt/", "Echo360 downloads/", "env/"):
            self.assertIn(seen, out)
        for hidden in ("hidden.pdf", "junk.pdf"):
            self.assertNotIn(hidden, out)

    def test_nothing_usable(self):
        root = self.course("empty")
        code, out = run("locate", root)
        self.assertEqual(code, 3, out)
        self.assertIn("no-inputs", codes(out))

    def test_files_loose_in_course_folder(self):
        root = self.course("loose")
        shutil.copy(PDF, root)
        shutil.copy(VTT, root)
        (root / "transcript-per-slide.toml").write_text('[paths]\nslides = ["."]\ntranscripts = ["."]\n')
        code, out = run("inventory", root)
        self.assertEqual(code, 0, out)
        self.assertIn("1 slide PDFs", out)
        self.assertIn("1 transcripts", out)
        # Our own working files are never taken for inputs on the next run.
        code, out = run("inventory", root)
        self.assertIn("1 transcripts", out)

    def test_config_with_bom(self):
        root = self.course("bom")
        (root / "ppt").mkdir()
        shutil.copy(PDF, root / "ppt")
        (root / "transcript-per-slide.toml").write_bytes(b"\xef\xbb\xbf[paths]\nslides = ['ppt']\n")
        code, out = run("status", root)
        self.assertEqual(code, 0, out)


class HandOffs(Base):
    def messy(self) -> Path:
        root = self.course("messy")
        (root / "ppt").mkdir()
        (root / "rec").mkdir()
        shutil.copy(PDF, root / "ppt" / "Week 2.pdf")
        shutil.copy(PDF, root / "ppt" / "Week2-copy")                                  # no extension
        (root / "ppt" / "Week 3.pptx").write_bytes(b"PK\x03\x04fake")
        (root / "ppt" / "broken.pdf").write_text("<html>Please log in</html>")           # failed download
        (root / "ppt" / "photo").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 300)
        vtt = VTT.read_text(encoding="utf-8")
        (root / "rec" / "captions.txt").write_text(vtt, encoding="utf-8")               # captions as .txt
        (root / "rec" / "lecture3").write_text(vtt, encoding="utf-8")                   # no extension
        (root / "rec" / "gbk.txt").write_bytes("今天我们讲二分查找。".encode("gbk"))
        (root / "rec" / "otter.txt").write_text("\n".join(
            f"Speaker 1  0:{s:02d}\nSentence {s}." for s in range(0, 60, 8)), encoding="utf-8")
        (root / "rec" / "teams.docx").write_bytes(b"PK\x03\x04fake")
        (root / "rec" / "lec.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42")
        (root / "rec" / "aws.json").write_text('{"results": {"items": []}}')
        shutil.copy(PDF, root / "rec" / "export.pdf")
        (root / "rec" / "empty.txt").write_text("")
        (root / "transcript-per-slide.toml").write_text('[paths]\nslides = ["ppt"]\ntranscripts = ["rec"]\n')
        return root

    def test_every_problem_is_handed_off(self):
        root = self.messy()
        code, out = run("inventory", root)
        self.assertEqual(code, 3, out)
        self.assertEqual(codes(out), {
            "pdf-unreadable", "transcript-empty", "encoding", "timestamped-text", "unrecognized-file",
            "deck", "unknown-format", "no-transcript", "word-file", "pdf-in-transcripts"})
        inv = json.loads((root / "study" / "inventory.json").read_text(encoding="utf-8"))
        slides = {s["path"]: s for s in inv["slides"]}
        self.assertIn("ppt/Week2-copy", slides)                       # used by content
        self.assertEqual(slides["ppt/broken.pdf"].get("problem"), "pdf-unreadable")
        self.assertIn("rec/lecture3", [t["path"] for t in inv["transcripts"]])
        self.assertIn("ppt/photo", [o["path"] for o in inv["other"]])  # an image, not UTF-16 text

    def test_settled_problems_are_not_raised_again(self):
        root = self.messy()
        conv = root / "study" / "_converted"
        conv.mkdir(parents=True)
        shutil.copy(VTT, conv / "otter.vtt")
        (root / "study" / "pairs.json").write_text(json.dumps({"method": "agent-semantic", "pairs": [
            {"key": "w2", "slides": "ppt/Week 2.pdf", "transcript": "study/_converted/otter.vtt",
             "transcript_from": "rec/otter.txt", "why": "test"},
            {"key": "w2b", "slides": "ppt/Week2-copy", "transcript": "rec/gbk.txt", "why": "test"}]}))
        with open(root / "transcript-per-slide.toml", "a") as f:
            f.write('ignore = ["ppt/broken.pdf", "ppt/photo", "ppt/*.pptx", "rec/*.docx", "rec/*.mp4", '
                    '"rec/aws.json", "rec/export.pdf", "rec/empty.txt", "rec/captions.txt", "rec/lecture3"]\n')
        code, out = run("inventory", root)
        self.assertEqual(code, 0, out)

    def test_broken_inputs_and_crashes(self):
        root = self.demo_copy("broken")
        (root / "study" / "w2-binary-search" / "alignment.json").write_text('{"assignments": [ {"slide": 1,, }')
        code, out = run("validate", root)
        self.assertEqual((code, codes(out)), (3, {"bad-json"}), out)
        (root / "study" / "w2-binary-search" / "alignment.json").write_text('{"assignments": [{"slide": "x"}]}')
        code, out = run("validate", root)
        self.assertEqual((code, codes(out)), (3, {"crash"}), out)
        (root / "transcript-per-slide.toml").write_text('[paths]\nslides = "E:\\Course"\n')
        code, out = run("status", root)
        self.assertEqual((code, codes(out)), (3, {"bad-config"}), out)
        code, out = run("status", root / "does-not-exist")
        self.assertEqual((code, codes(out)), (3, {"no-course-folder"}), out)


class Renames(Base):
    def test_renamed_and_moved_files_are_followed(self):
        root = self.demo_copy("rename")
        (root / "slides" / "binary-search.pdf").rename(root / "slides" / "Week 2 - final.pdf")
        (root / "Recordings").mkdir()
        (root / "transcripts" / "binary-search-recording.vtt").rename(root / "Recordings" / "echo.vtt")
        code, out = run("status", root)
        self.assertEqual(code, 0, out)
        pair = self.pairs(root)[0]
        self.assertEqual((pair["slides"], pair["transcript"]),
                         ("slides/Week 2 - final.pdf", "Recordings/echo.vtt"))
        ex = json.loads((root / "study" / "w2-binary-search" / "extracted.json").read_text(encoding="utf-8"))
        self.assertEqual(ex["slides_pdf"], "slides/Week 2 - final.pdf")
        pack = (root / "study" / "w2-binary-search" / "pack.md").read_text(encoding="utf-8")
        self.assertIn("Slides: `slides/Week 2 - final.pdf`", pack)
        notes_before = pack.count("<!-- note:")
        code, out = run("render", root, "--key", "w2-binary-search")
        self.assertEqual(code, 0, out)
        pack = (root / "study" / "w2-binary-search" / "pack.md").read_text(encoding="utf-8")
        self.assertEqual(pack.count("<!-- note:"), notes_before)

    def test_line_endings_are_not_a_change(self):
        root = self.demo_copy("crlf")
        vtt = root / "transcripts" / "binary-search-recording.vtt"
        vtt.write_bytes(vtt.read_bytes().replace(b"\n", b"\r\n"))
        code, out = run("status", root)
        self.assertEqual(code, 0, out)

    def test_changed_input_is_raised_until_settled(self):
        root = self.demo_copy("changed")
        with open(root / "slides" / "binary-search.pdf", "ab") as f:
            f.write(b"\n% updated by the lecturer\n")
        for _ in range(2):  # every run, not once
            code, out = run("status", root)
            self.assertEqual((code, codes(out)), (3, {"input-changed"}), out)
        code, out = run("extract", root, "--from-pairs", "--key", "w2-binary-search", "--force")
        self.assertEqual(code, 0, out)
        code, out = run("status", root)
        self.assertEqual(code, 0, out)

    def test_changed_input_can_be_kept_as_is(self):
        root = self.demo_copy("keep")
        with open(root / "slides" / "binary-search.pdf", "ab") as f:
            f.write(b"\n% updated\n")
        data = json.loads((root / "study" / "pairs.json").read_text(encoding="utf-8"))
        del data["pairs"][0]["fingerprints"]["slides"]
        (root / "study" / "pairs.json").write_text(json.dumps(data))
        code, out = run("status", root)
        self.assertEqual(code, 0, out)

    def test_renamed_and_changed_is_handed_off(self):
        root = self.demo_copy("renamed-changed")
        (root / "slides" / "binary-search.pdf").rename(root / "slides" / "w2.pdf")
        with open(root / "slides" / "w2.pdf", "ab") as f:
            f.write(b"\n% changed\n")
        code, out = run("status", root)
        self.assertEqual((code, codes(out)), (3, {"pair-missing-file"}), out)
        self.assertIn("unpaired: slides/w2.pdf", out)


if __name__ == "__main__":
    unittest.main()
