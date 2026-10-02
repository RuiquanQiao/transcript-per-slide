# transcript-per-slide

An agent skill (`/tps`) that puts **what the lecturer said under each slide it was said on**.

Give it slide PDFs and lecture-recording transcripts. For each lecture it writes
one Markdown study pack:

- each slide's image,
- under it, that slide's stretch of the recording, rewritten into clean notes
  in the lecturer's own voice,
- under that, a tutoring block where the agent's answers to *your* questions
  about the slide are kept, if you want them kept, with **figures drawn** when
  words are not enough.

Anything that affects your marks or what you have to do (deadlines, mark
weights, required actions) gets a ★ and a list at the top, so it doesn't get
lost in a two-hour recording.

## Who it is for

Students who missed the lecture and don't want to choose between reading bare
slides and sitting through the whole recording. With a pack, you can:

- read three slides on the bus and stop,
- spend an hour on the one slide you don't get, without the lecture running on,
- jump around and follow whatever you're curious about. In a live lecture, that
  is how you fall behind.

See [a complete example pack](examples/demo/study/w2-binary-search/pack.md) (a short
demo lecture written for this repo, including a tutoring note with a figure).

## Install

The skill is this whole folder, in the [Agent Skills](https://agentskills.io)
format (`SKILL.md` plus `scripts/` and `references/`).

The skill is called `tps`, so the folder must be named `tps`.

**Claude Code**, for one course:

```bash
git clone https://github.com/RuiquanQiao/transcript-per-slide <course>/.claude/skills/tps
```

Or for all your courses, clone it into `~/.claude/skills/tps`.

**Cursor**: clone into `<course>/.cursor/skills/tps`.
**Other agents** that read `SKILL.md`: put the folder, named `tps`, wherever they load skills from.

You also need Python 3.11+ and PyMuPDF:

```bash
python -m pip install -r requirements.txt
```

## Use

Put your files in a course folder:

```
my-course/
  slides/        lecture PDFs, named however your course names them
  transcripts/   .txt (Echo360 "SPEAKER N" or plain), .vtt, .srt, or Whisper .json
```

Then, in that folder, run `/tps`. On the first run it sets things up; after
that, it packs every lecture that is new.

Everything else is just `/tps` plus whatever you want, in your own words and
any language. There is no syntax to remember. For example:

| You type | What happens |
|---|---|
| `/tps` | Pack every new lecture (first run: set up) |
| `/tps 12 why is this O(n log n)?` | Explain slide 12 of the lecture you're on, and write it under the slide |
| `/tps the bit about the midpoint overflow` | Find that slide, then explain it |
| `/tps draw slide 5, I can't picture it` | Draw a figure, check it renders, put it under slide 5 |
| `/tps keep that` | Put the explanation you just got in chat under its slide |
| `/tps lec3.1 slides were updated` | Re-pack that lecture (asks first; your tutoring stays) |
| `/tps what's left?` | What is packed, half-done, or not paired yet |

Without `/tps`, questions are answered in chat. The agent then offers to save
the answer under the slide, so you decide what goes on the page.

Packs land in `study/<lecture>/pack.md`. Open them in any Markdown viewer
(VS Code, Obsidian, GitHub).

## How it works

The work splits along one line: **the agent does everything that needs
understanding; the scripts in `scripts/` do everything that doesn't.**

| Step | Who | Why |
|---|---|---|
| List PDFs and transcripts with previews | `inventory.py` | mechanical |
| Decide which recording belongs to which deck | **agent**, by reading title slides and opening lines | filenames lie (`lec1.1` vs `Lecture 1-1` vs `Echo360_0812`) |
| Render slide PNGs, cut the transcript into numbered segments | `extract.py` | mechanical; caption files are also cut at pauses, where slide changes usually happen |
| Assign segments to slides, name the lecture's parts, write notes, flag notices | **agent** | needs to follow the lecture, not match keywords |
| Check every slide is covered, segment order, missing notes, cut-off recordings | `validate.py` | catches agent mistakes before they reach the page |
| Write `pack.md`, keeping tutoring blocks | `render.py` | re-rendering never loses your notes |
| Explain stuck slides, draw figures | **agent** | needs to know what you misunderstood |
| Rasterize figures so the agent can look at them | `figure.py` | headless Chrome/Edge (what Markdown viewers show), PyMuPDF fallback; a parser accepting an SVG proves nothing |

Lectures that already have a pack are never touched again unless you ask
for a redo, so a new week's files don't disturb old notes.

Every script also works on its own; run any of them with `--help`. Also there:
`init.py` (config + a README for the study folder) and `status.py`.

## Configuration

`transcript-per-slide.toml` in the course folder (created by `init.py`; every key
is optional). See [the example](assets/transcript-per-slide.example.toml).
Highlights:

- `slides.footer_patterns`: regexes for footers and page counters, so slide
  titles come out clean
- `transcript.asr_fixes`: words your captioning keeps getting wrong
  (`cash` → `cache`)
- `transcript.skip_speakers`: e.g. the speaker that carries a copyright notice
- `paths.*`: where slides, transcripts and packs live

## A note on course material

Lecture slides and recordings usually belong to your university. Keep packs for
your own study, and don't commit course materials to a public repository. The
demo lecture in `examples/` was written for this repo.

## License

MIT
