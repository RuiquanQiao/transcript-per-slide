# Tutoring on the pack

The student asks in chat. The tutoring block under a slide in `pack.md` is the
shared paper: sitting next to them, the Markdown is the paper. What ends up
there is what they will reread in a week. Chat is for their questions and a
short "look at the pack under slide N".

## Where to write

Between `<!-- note:N -->` and `<!-- /note:N -->` under slide N of
`<output>/<key>/pack.md`. Nothing else in `pack.md` survives a re-render; these
blocks do.

- A question asked through `/tps` is written there directly, **in the same
  turn**. Do not explain fully in chat and later paste a different essay.
- A question asked without `/tps` is answered in chat, followed by one line
  offering to keep it under the slide. If they say yes (in any words), move it
  onto the paper, reorganized as below, not pasted. Do not pin anything they
  did not ask to keep.
- Do not rewrite the lecturer's notes above the block unless they ask.
- Do not create separate notes files. The pack is the record.

## Before you answer

Open the pack, the slide image (`pages/NNN.png`) and, if needed, the
transcript segments for that slide. Stay with this course: its notation, the
lecturer's framing and numbers. Do not invent a second textbook. Work out what
they actually misunderstand before explaining; often it is one step earlier
than the question.

## Shape of the paper

After a thread, organize into **the few cores they actually failed to
understand**. Follow-up questions nest under those cores. Do not promote every
round to a sibling `####`.

```
#### core mix-up 1
  ##### a new module that only exists because of this core
#### core mix-up 2
#### core mix-up 3
```

- `###` is the slide (already there). `####` is a **core**: title it so they
  will recognize it later. Not a question sentence, not "Q&A".
- Nested `#####` / bullets sit under the core that spawned them.
- Do not lead with unexplained foundations. Do not dump a textbook. Do not
  archive one heading per chat message.

**New module or follow-up?** If the question is a new module (a distinct
mix-up that was not the last stretch), start a new heading: a new `####`, or a
`#####` only when that stretch is a new piece of the core. If it is an inquiry
about details or concepts of the last answer, a term, process or figure from
the last stretch, it is **not** a new heading: edit and polish the last answer
as if you reversed time, so the missing piece was always there. **Do not add a
`#####` titled as their follow-up.**

## When they ask about a phrase on the paper

- **Keep it** if it is correct (or standard in this course). Explain it next to
  the sentence that still uses it.
- **If it was a bad metaphor or a wrong step: rewind.** Rewrite that stretch as
  if those words were never used. Do not quote, deny or gloss the discarded
  wording anywhere: headings, figures, captions or asides. Future them should
  only see the clean wording.

## Draw on the paper

If text cannot make it seeable, draw a figure into `<output>/<key>/extras/` and
link it **in the same turn**, then rasterize it and **look at the PNG** before
saying it is done. Full rules: [figures.md](figures.md).

## Markdown traps

C products and other runs of `*` (`x*x*x*x`), and anything with `_`: wrap in
backticks or a fenced code block. Markdown treats `*` as emphasis and will eat
the line or the table.

Packs stay Markdown: `##` part, `###` slide, the lecturer's notes, then the
tutoring block with `####` cores.
