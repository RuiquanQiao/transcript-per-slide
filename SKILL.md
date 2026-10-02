---
name: tps
description: >-
  transcript-per-slide. Turns lecture slides plus a lecture recording's
  transcript into one Markdown study pack per lecture: every slide image is
  followed by what the lecturer actually said on that slide (polished, in the
  lecturer's voice), then a tutoring block where the student's own questions
  about that slide are answered, with figures drawn when words are not enough.
  Use for /tps, when new slide PDFs or transcripts (.txt, .vtt, .srt, .json)
  arrive in a course folder, when the student wants to catch up on a lecture
  they missed without watching the recording, or when they are stuck on a
  slide of a lecture that is already packed.
argument-hint: "[anything, e.g. '12 why is this slow?' | 'draw slide 5' | 'keep that' | 'lec3.1 slides changed' | nothing to pack new lectures]"
---

# transcript-per-slide

The student did not sit through the lecture and is not going to watch the whole
recording. They will read it a few slides at a time, whenever they have ten
minutes, and stop for as long as it takes when a slide does not make sense.
This skill has **two jobs**, and packing is not the whole product:

1. **Pack** the lecture: put the right stretch of the recording under each
   slide, rewritten into readable notes, so the slide and the explanation sit
   together.
2. **Help them see it**: when they are stuck on a slide, explain it on the
   pack, and **draw** when text alone cannot show the idea.

Arguments: `$ARGUMENTS`
(If that shows literally as `$ARGUMENTS`, read the arguments from the user's message.)

## Split of labour

The scripts only photocopy. Everything that needs understanding is yours.

| Job | Who |
|---|---|
| Write the config and the study folder's README | `init.py` |
| List every slide PDF and transcript with a short preview | `inventory.py` |
| Decide which transcript belongs to which slide deck | **You. Read title slides and the start of each recording.** |
| Turn pages into PNGs and the transcript into numbered segments | `extract.py` |
| Place speech on each slide, name the lecture's parts, write `notes`, flag notices | **You.** |
| Check the alignment | `validate.py` |
| Write `pack.md`, keeping tutoring blocks | `render.py` |
| Explain stuck slides, draw figures | **You.** |
| Rasterize figures so you can look at them | `figure.py` |
| Where every lecture stands | `status.py` |

Never pair files with a filename regex (`lecture-1-1-slides.pdf` ↔ `lec1.1.txt`;
the next file may be `lec1-1.txt` or worse). Read the content. Never
keyword-score speech onto slides. Never edit the transcript files.

**Running them.** All scripts are in `<skill-dir>/scripts/` (the folder next to
this file): `python <skill-dir>/scripts/<name>.py`. Use `python3` or `py -3` if
that is what the machine has. Run from the course folder (the one with
`slides/` and `transcripts/`) or pass `--root <course folder>`; every script
has `--help`. They need Python 3.11+ and PyMuPDF. If PyMuPDF is missing, tell
the user the install command (`python -m pip install pymupdf`, ideally in the
course's venv) and ask before installing anything.

## What the student wants

`/tps` has no fixed syntax. Students type whatever comes to mind, in any
language: `/tps 12 没看懂`, `/tps lec3.1`, `/tps keep that`, `/tps draw it`,
`/tps why O(n log n)`. Work out the intent from the arguments **and** the
conversation, then act. The words below are what the student might say, not
keywords to match.

| Intent | Typical signals | Do this |
|---|---|---|
| **Pack** | no arguments; "pack", "new lecture", "added files", a lecture name that has no pack yet | **Pack workflow** for every lecture without a `pack.md`, or only the ones named. |
| **Ask** | a slide number, a quoted phrase or a concept from a slide, a question, "don't get", "why", "?" | **Tutor** on that slide and write into its tutoring block. Draw if text cannot show it. With no question, explain what is most likely to trip someone up there. |
| **Draw** | "draw", "picture", "diagram", "show me", "画", "I can't picture it" | Tutor with a figure: draw into `extras/`, look at it, link it under the slide. |
| **Save** | "save", "keep", "put it under the slide", "记下来" right after a chat explanation or figure | Move that explanation (and freeze any figure into `extras/`) into the slide's tutoring block, organized as in tutoring.md. |
| **Redo** | "redo", "slides changed", "new recording for", "notes are wrong for lec3.1" | Pack workflow for a lecture that already has a pack, with `--key K --force`. Tutoring blocks survive, but the lecture notes are rewritten: **confirm first**. |
| **Status** | "status", "what's left", "which lectures" | `status.py` and summarize: packed, half-done, not yet paired. |
| **Setup** | first run (no config and nothing paired), "setup", "config", wrong footers in titles, recurring caption errors | `init.py`, then ask what slide footers look like and which words the captions keep getting wrong; fill in `footer_patterns` and `asr_fixes`; point `paths` at the real folders. |
| **Check** | "check", "validate", something looks off in a pack | `validate.py` and fix what it reports. |

Filling in what they left out:

- **Which lecture**: the one being discussed or most recently opened in this
  conversation; otherwise the most recently packed. A bare slide number means
  that lecture.
- **Which slide**: if they quote or describe something, search the lecture's
  slide texts and notes (`extracted.json`, `pack.md`) for it; look at slide
  images when text is not enough.
- **Mixed requests** ("pack lec4.2 then explain slide 7") are done in order.
- Ask a short question only when a wrong guess would cost something: two
  plausible lectures, two slides that both match, or anything destructive.
  Otherwise act, and say in one line which lecture and slide you took.

A question about a slide **without** `/tps`: answer in chat, then offer once, in
one line, to keep it under the slide. With `/tps`, write it on the paper
directly, in the same turn. The student decides what goes on the paper; never
pin anything they did not ask to keep.

## Pack workflow

A lecture that already has `<output>/<key>/pack.md` is **done**: the recording
will not change. Do not extract, re-align, rewrite `notes` or re-render it;
that would wipe work. Only pack **new** lectures, unless the student asked for
a redo of a named one.

1. `inventory.py` writes `<output>/inventory.json`: every slide PDF and
   transcript with name, size, a text preview, and `paired_as` for files
   already paired.
2. **Pair by reading.** Read the previews of files that are not already in a
   pair. Match by **what the lecture is**: week and lecture number on the title
   slide, the topics, the recording's opening lines. Merge new entries into
   `<output>/pairs.json`; never delete existing pairs:
   ```json
   {
     "method": "agent-semantic",
     "pairs": [
       {"key": "lec3.1", "slides": "slides/week3-a.pdf",
        "transcript": "transcripts/Echo360_0812.vtt",
        "why": "Title slide is Week 3 Lecture 1; the recording opens by introducing the same topic."}
     ]
   }
   ```
   `key` comes from the lecture's identity (week + lecture), not from dots vs
   hyphens in the filename. `transcript` may be `null` if there is no recording
   yet. If a pairing is a guess, say so and do not proceed on it.
3. `extract.py --from-pairs` (add `--key K` for named lectures; `--force` when
   redoing). It skips lectures that already have `pack.md`. Each lecture gets
   `<output>/<key>/extracted.json` (slide titles and text, numbered transcript
   `segments`) and `pages/NNN.png`. For a one-off without pairs.json:
   `extract.py --slides <pdf> --transcript <file> --key K`.
4. **Align and write notes, only for unpacked lectures.** Read
   `extracted.json` and write `<output>/<key>/alignment.json`. Follow the
   lecture: which segments were spoken while each slide was up, how it divides
   into parts, what the lecturer meant. Look at slide images when the text
   extract is not enough. Flag every notice that affects the student's marks,
   standing or obligations; judge that yourself from what was said.
   Schema and rules: [references/alignment.md](references/alignment.md).
   How to write `notes`: [references/notes-voice.md](references/notes-voice.md).
   Large lectures: work in slide ranges, but keep segment ids monotonic.
5. `validate.py` must print `OK`. Fix every `error`. Treat `warn` as a prompt
   to look: unused segments are fine for boilerplate, but slides after the
   recording ends need the `> **No recording**` block.
6. `render.py --all` writes `pack.md` (it skips packed lectures; `--key K`
   renders one lecture, `--draft` previews a half-aligned one). Report per
   lecture: slide count, notices found, and where the recording was cut off.

## Help them see it

Full playbooks: [references/tutoring.md](references/tutoring.md) and
[references/figures.md](references/figures.md). Short version:

- Open `pack.md`, the slide image (`pages/NNN.png`) and, if needed, the
  transcript segments before you answer. Stay with this course's notation and
  what the lecturer said; do not invent a second textbook.
- Write between `<!-- note:N -->` and `<!-- /note:N -->` under slide N: the
  shared paper. Never edit the lecture notes above that block unless asked.
  `render.py` keeps these blocks; nothing else in `pack.md` survives a
  re-render. Chat stays short ("see the pack under slide 12").
- Organize around the few things they actually misunderstood (`####` each,
  named so they recognize it later). A follow-up about the same thing rewrites
  that stretch so the missing piece was always there; it never becomes a new
  heading.
- **Draw when text cannot show the idea.** Put the figure in
  `<output>/<key>/extras/`, link it under a `####` that names the knowledge,
  then `figure.py <file>` and **open the PNG and look** before saying it is
  done. A parser accepting the SVG proves nothing. Delete the check PNGs with
  `figure.py --clean <extras dir>`. Never paste raw `<svg>` into chat; a chat
  canvas or side panel is not the record.

## Files

```
<course>/
  transcript-per-slide.toml        settings (init.py)
  slides/  transcripts/            inputs; never edited
  study/                           output (configurable)
    README.md                      how to read this folder (written once)
    inventory.json  pairs.json
    <key>/  pages/NNN.png  extracted.json  alignment.json  pack.md  extras/
```

Packs stay Markdown: `##` part, `###` slide, the lecturer's notes, then the
tutoring block with `####` cores.
