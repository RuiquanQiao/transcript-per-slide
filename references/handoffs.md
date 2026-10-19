# When a script hands off to you

The scripts do the mechanical work and stop at the first thing that needs
judgment. They never crash with a bare traceback and never skip a file
silently. They print a block like this and exit with status **3**:

```
NEEDS AGENT [timestamped-text] transcripts/week3.txt
  problem: 212 of 230 lines carry timestamps in a layout the scripts do not parse; ...
  do: Convert it to .vtt in <output>/_converted/ ...
```

Lines starting `note:` are guesses the script already handled (for example "read as
captions by its content, not its extension"); read them, no action needed.

## Rules

1. **Act in the same turn.** A hand-off is your job, not something to report
   and leave. Do what `do:` says, re-run the script, and carry on with the
   workflow. The student should see a result, or a precise question, never
   "the script failed".
2. **Never edit the student's files.** Not the slides, not the transcripts, not
   their names or folders. When an input needs fixing, write a **converted
   copy** (below) and use that.
3. **Ask the student only for what you cannot do yourself**: files that are not
   on disk, an export only their software can do, a password, a choice between
   two plausible readings. Ask in their language, name the exact files, and say
   exactly what to do ("In PowerPoint: File > Export > PDF, save into `ppt/`").
4. **Do not re-run the same command unchanged** hoping for a different result.
5. **Decide once.** A file you judged irrelevant goes into `[paths] ignore` in
   `transcript-per-slide.toml` (globs from the course folder, e.g.
   `"ppt/old/*"`, `"*.png"`), so it is never raised again. Say in one line that
   you ignored it.

## Converted copies

When the scripts cannot read an input as it is, but you can (garbled
encoding, an unusual transcript layout, a Word file, a transcript exported as
PDF), write a faithful copy that the scripts can read:

- Put it in `<output>/_converted/`, named after the original
  (`_converted/week3.vtt` for `recordings/week3.txt`).
- **Faithful**: every word, in order, with the timings if the original has
  them. Convert the format; do not clean, summarize or fix the speech (that
  is what `notes` and `asr_fixes` are for).
- Pair the copy and record the original:
  ```json
  {"key": "lec3.1", "slides": "ppt/Week 3.pdf",
   "transcript": "study/_converted/week3.vtt", "transcript_from": "recordings/week3.txt",
   "why": "..."}
  ```
  `slides_from` works the same way for slides. The original then counts as
  paired, and the pack header names it.
- For short conversions, write the file directly. For long ones, a few lines
  of Python in the scratch area are fine; do not add scripts to the skill.
- Tell the student in one line what you converted and why.

Target formats: `.vtt` when the original has timings (`WEBVTT`, a blank line,
then `00:01:02.000 --> 00:01:09.000` and the text, per cue), otherwise a
UTF-8 `.txt` with a blank line between paragraphs.

## Codes

### Setup and environment

- **python-version**: Python older than 3.11. Try `py -3.12`, `python3.12`,
  `py -3`. If none exists, tell the student to install Python 3.11+.
- **missing-dependency**: PyMuPDF is not installed for the Python that ran.
  Give the install command (`python -m pip install pymupdf`, in the course's
  venv if there is one) and **ask before installing**.
- **no-course-folder**: `--root` points nowhere. Use the folder the student
  is working in.
- **bad-config**: `transcript-per-slide.toml` does not parse. Fix the line.
  The usual cause is a Windows path in double quotes (`"E:\Course"`): use
  single quotes or forward slashes.
- **bad-json**: `pairs.json` or `alignment.json` (your files) is not valid
  JSON. Fix it. For `inventory.json` or `extracted.json`, re-run the script
  that writes them.

### Finding and recognizing files

- **no-inputs**: no slides (or no transcripts while decks wait for one) where
  `[paths]` points. Run `locate.py`; fix `[paths]`; if the material is not in
  the course folder at all, tell the student what to add (SKILL.md, Find the
  files) and stop.
- **unrecognized-file**: files in the slide or transcript folders the scripts
  do not recognize: `.md` or extensionless text, images, archives. The
  `peek:` shows the start. Decide:
  - a transcript in plain text: pair it as it is (the scripts read by
    content, whatever the extension);
  - slides as images (a folder of `.png` per slide): ask the student for the
    PDF; packs need one;
  - a `.zip`: ask the student to unzip it (or unzip into `_converted/` if they
    agree);
  - anything else (reading lists, the student's own notes, assignment files):
    add to `[paths] ignore`.
- **deck**: `.pptx`/`.ppt`/`.key`/`.odp`. The scripts need PDF. Ask the
  student to export each one into the slides folder. If LibreOffice is
  installed (`soffice` on PATH), offer to convert instead:
  `soffice --headless --convert-to pdf --outdir <output>/_converted <deck>`
  and pair with `slides_from`. Ask first: that is a program writing files.
  If a PDF of the same lecture already exists, the deck is a duplicate: ignore
  it.
- **no-transcript**: video or audio. Neither the scripts nor you can listen to
  it. Tell the student where transcripts come from: the recording platform's
  caption or transcript download (Echo360, Panopto, Teams, Zoom; `.vtt` is
  best because it keeps timings), or running Whisper on the file. Until then,
  a slide-only pack is possible if they want it (`"transcript": null`).
- **word-file**: `.docx`/`.rtf`/`.odt`. Teams transcripts often come as
  `.docx`. Best: ask for the `.vtt` download from the same place. Otherwise
  read the document's text (python-docx if it is installed, or ask the
  student to Save As `.txt`) into `_converted/<name>.txt` (or `.vtt` if it
  carries timings) and pair with `transcript_from`. If it is not a transcript,
  ignore it.
- **pdf-in-transcripts**: PDFs in a transcript-only folder. Slides kept
  together with the recordings: add that folder to `[paths] slides`. A
  transcript exported as PDF: extract its text (PyMuPDF, `page.get_text()`)
  into `_converted/<name>.txt` and pair with `transcript_from`.
- **unknown-format**: a JSON the scripts do not read as a transcript. If it is
  another speech-to-text tool's output (AWS Transcribe `results.items`,
  Deepgram, AssemblyAI `words`/`utterances`, Otter export), convert it to
  `.vtt` with the times. If it is not a transcript, ignore it.

### Reading files

- **encoding**: the file is not UTF-8 (Windows ANSI, GBK/GB18030, Shift-JIS,
  Latin-1); it was decoded with the system codepage and may be garbled. Look
  at the preview or segments. Fine: carry on. Garbled: work out the real
  encoding (try decoding with `gb18030`, `cp1252`, `shift_jis`, `utf-16` until
  the text reads right), write a UTF-8 copy to `_converted/`, pair that.
- **timestamped-text**: a `.txt` with timestamps on its lines (YouTube
  "0:03", Otter "Speaker 1  0:03", "[00:01:23] text"). Convert it to `.vtt`
  in `_converted/`: each timestamp starts a cue that runs to the next one, the
  text is everything until the next timestamp, a speaker name goes in
  `<v Name>`. Pair with `transcript_from`. This keeps the timings the
  alignment needs.
- **transcript-empty**: no text came out. Open the file. Empty or an HTML
  error page: ask the student to download it again. The text is there in a
  layout the scripts miss: convert it.
- **transcript-unsplit**: the whole recording came out as one or two
  segments (no punctuation, no line breaks, no timings), which cannot be
  placed on slides. Set `min_segment_chars` lower in the config (for
  example 60) and re-extract. If it is still one block, write a converted
  copy with a paragraph break every few sentences.
- **pdf-unreadable**: PyMuPDF cannot open it. A `.pdf` that is really text or
  HTML is a failed download (a login page): ask for it again. A
  PowerPoint/zip file named `.pdf`: treat as **deck**. Otherwise it is
  damaged: ask the student to download it again.
- **pdf-locked**: password-protected. Ask for an unlocked copy. If they give
  the password, save an unlocked copy into `_converted/`
  (`doc.authenticate(pw); doc.save(...)`) and pair with `slides_from`.
- **pdf-no-text**: slides with no text layer (scanned, or exported as
  pictures). Pair by looking at the pages (open the PDF itself). After
  `extract.py`, read the slides from `pages/NNN.png`; give each slide a
  `title` in `alignment.json` (see alignment.md), and use the images, not
  `slides[].text`, to follow the lecture.

### Pairing, extracting, rendering

- **no-pairs**: `extract.py --from-pairs` without `pairs.json`, or a `--key`
  that is not in it. Do the pairing step first.
- **pair-missing-file**: a file named in `pairs.json` is gone, and no file in
  the course folder has its fingerprint. (A plain rename or move never gets
  here: the scripts follow those by content on their own.) So it was renamed
  *and* changed (the lecturer re-uploaded an edited deck under a new name), or
  deleted, or it was renamed before any script recorded a fingerprint. The
  `unpaired:` lines list the candidates. Compare by content (title slide,
  opening lines, page count against `extracted.json`) and fix the path in
  `pairs.json`; the next run fingerprints it. If it changed, that is then an
  **input-changed**. If nothing matches, ask the student where the file went.
  Never re-pair a packed lecture from scratch.
- **input-changed**: a file of a lecture that was already extracted (or
  packed) keeps its name, but its content differs from what was extracted.
  It is raised on **every run** until it is settled. Look at the file:
  - the same lecture, updated (slides fixed, a re-uploaded recording):
    - not packed yet: re-extract it (`extract.py --from-pairs --key K`), then
      redo the alignment against the new `extracted.json`;
    - packed: tell the student and ask whether to redo the pack (Redo intent,
      `--key K --force`: their tutoring notes survive, the lecture notes are
      rewritten). The re-extract records the new fingerprint.
    - If they want to keep the pack as it is, delete that field's entry under
      `fingerprints` in the pair (e.g. `fingerprints.slides`). The next run
      records the current file and stops asking. This is the only time you
      touch fingerprints.
  - a different lecture saved over the old name: fix `pairs.json` (pair it with
    its own lecture, and find the old file again or set this one aside).
- **hand-edits**: the student (or you) edited `pack.md` outside the tutoring
  blocks; a re-render would lose those lines. Move them into
  `alignment.json` notes or into the slide's `<!-- note:N -->` block, then
  render. `--discard-edits` only when the student says to drop them.
- **figure-render**: a figure would not render, or rendered blank. Try the
  other engine (`--engine mupdf` / `--engine browser`). If both fail, the file
  is broken: open it as text and fix it (missing `viewBox`/size, everything
  drawn in the background colour, a syntax error), or redraw it simpler.

### Anything else

- **crash**: the script itself failed on something nobody planned for. The
  block shows the error and where. Then:
  1. If an input file caused it (an odd PDF, a strange transcript), handle
     that file the way the closest code above says, usually with a converted
     copy, and re-run.
  2. If it is a bug in the script, do not stop the student's work: produce
     that step's output by hand in the same format (`pairs.json`,
     `extracted.json` as described in alignment.md, `alignment.json`, the
     `pack.md` layout in SKILL.md), carry on, and tell the student in one line
     that the script has a bug and what triggered it, so it can be reported.
  3. Never patch the skill's scripts in the middle of a student's session
     unless they ask.
