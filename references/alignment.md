# alignment.json

One file per lecture: `<output>/<key>/alignment.json`. You write it;
`validate.py` checks it; `render.py` turns it into `pack.md`.

## Inputs (from extracted.json)

- `slides[]`: `index`, `title` (first readable line), `text` (the PDF page
  extract: everything printed on the slide, footers removed), `image`. This is
  what the slide *shows*.
- `segments[]`: `id`, `raw_text`, optional `speaker` and `start` (HH:MM:SS,
  caption and JSON transcripts only). This is unpolished speech recognition
  from the recording: fillers, wrong words, no structure.

Neither is what the student reads in `pack.md`. They read your `notes`.

Never edit the transcript files themselves. Corrections go into `notes`, or
into `asr_fixes` in the config if the same error keeps coming back.

## Schema

```json
{
  "method": "agent-semantic",
  "parts": [
    {"name": "Why memory is the bottleneck", "slides": [1, 2]},
    {"name": "Admin", "slides": [3]}
  ],
  "assignments": [
    {"slide": 1, "segment_ids": []},
    {"slide": 2, "segment_ids": [0, 1],
     "notes": "A trip to main memory costs hundreds of instructions' worth of time. That gap is the **memory wall**."},
    {"slide": 3, "segment_ids": [2], "notice": "deadline",
     "notes": "- Assignment 1 is due **Friday of week 4, 5 pm**.\n- Late work loses marks unless you have an approved extension."}
  ]
}
```

- `method`: always `"agent-semantic"`, recording that an agent aligned this by
  following the lecture (the same field goes in `pairs.json`).
  `validate.py` prints it.
- `parts`: the lecture's own structure, named by topic. Becomes `##` headings.
  Slides not in any part fall under "Lecture".
- `assignments`: **every slide exactly once**.
  - `segment_ids`: what was said while that slide was up. Monotonic: in slide
    order, ids never go backwards and no id is used twice. A segment that
    straddles a slide change goes on the slide where most of it belongs; the
    notes can still use both halves.
  - `notes`: polished Markdown under the slide, in the lecturer's voice. See
    [notes-voice.md](notes-voice.md). Required whenever `segment_ids` is
    non-empty.
  - `notice` (optional): set it when what was said on this slide affects **the
    student's own marks, standing or obligations**, not the subject matter.
    Judge by the effect on the student, not by keywords: would missing this
    cost them marks, a deadline, eligibility, access they need to arrange, or
    an action they have to take? Rules that can cost marks count too (late
    penalties, academic integrity, what tools are allowed in assessed work).
    When in doubt whether missing it could hurt them, flag it. The value is a
    short lowercase tag you choose that names the kind of notice (for example
    `"deadline"`, `"marks"`, `"action"`). Notices get a ★ in the heading and a
    list at the top of the pack.

## Following the lecture

- Read the segments in order alongside the slide texts. Lecturers announce
  slide changes ("next slide", "so here", "now let's look at"), pause (caption
  files are already cut at pauses), or start talking about what the next slide
  shows. Follow the lecture; do not keyword-score speech onto slides.
- They go back to earlier slides, skip slides, and talk past the end of one.
  Assign each stretch to the slide that was up; a skipped slide gets
  `"segment_ids": []`.
- Small talk, logistics before the start, and recording boilerplate (copyright
  notices) can stay unassigned. Unassigned ids are only warnings.

## Empty slides

- **Title, section divider, skip, or silent at the start** (empty
  `segment_ids`, not at the end): omit `notes` or leave it empty. The pack
  shows "_No spoken stretch belongs on this page (title, skip, or silent)._"
- **Notice slide with no speech** (e.g. a deadline table nobody read out):
  polish `slides[].text` into `notes` in the same teaching voice, and set
  `notice`.
- **Recording cut off.** Recordings often **end earlier** than the lecture. Empty `segment_ids` on the **last slides** when
  speech stops early are almost always a cut recording, not a silent page.
  Check whether the slides are clear enough to understand alone. If not, write
  `notes` as a Markdown blockquote (`>` on every line) explaining the slides as
  the lecturer would: same first-person voice, staying on the slide, no second
  textbook. Start with the marker line so the student can see there was no
  recording here:

  ```markdown
  > **No recording** (the recording ended earlier).
  >
  > Explain the slide here, as the lecturer, staying on what the slide shows.
  ```

  If the slide is already self-explanatory, still write that one-line `>`
  marker. Do not leave the renderer's "no spoken stretch" line there; that
  line is for title and skipped pages, not a cut recording.
