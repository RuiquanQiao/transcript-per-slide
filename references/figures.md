# Drawing on the pack

Helping the student **see** it is half the job, not an extra. The point of a
pack is that they never have to sit through the recording; when something is
hard to see from text alone, **draw on the pack**: a figure under the slide, in the same
turn as the explanation.

## When to draw

Draw when the idea is spatial, sequential or quantitative and a paragraph would
make them build the picture in their head: structures and layouts, processes
and cycles, timelines, things flowing through a system, before/after states,
two things that look alike side by side, the shape of a function, where a
number comes from.

Do not draw when a sentence or a small table already shows it. **Never wrap a
paragraph in an SVG**: a figure that is mostly prose is a worse paragraph.

## Where it goes

- The file lives in `<output>/<key>/extras/`, named for what it teaches
  (`halving-to-one.svg`, not `figure1.svg`).
- It is linked from the slide's tutoring block, under a `####` heading that
  names the **knowledge**, never "diagram", "figure" or "extra":

  ```markdown
  #### What log2 n counts: halvings, not items
  ![Halving 16 items down to 1](extras/halving-to-one.svg)
  ```

- The paper is the record. A chat canvas, artifact, side panel or
  `.canvas.tsx` is not; nothing there survives into `study/`. Never paste raw
  `<svg>` into chat.
- A figure drawn in chat (a question asked without `/tps`) stays in chat until
  the student asks to keep it. Then freeze it as a static SVG or PNG in
  `extras/` and link it as above. Do not create a separate notes file, and do
  not pin anything they did not ask to keep.

## Content

- One misunderstanding per figure. Title it with the point, not the topic.
- Use the course's notation, variable names and numbers from the slide. Stay
  with this course; do not draw a second textbook.
- Label things directly; avoid legends that send the eye back and forth.
- A short caption line inside the figure may state the takeaway.
- If the student questioned a phrase and you rewound it, the old wording must
  not survive in a figure title, label or caption either.

## SVG that renders the same everywhere

Packs are read in VS Code, Obsidian, GitHub and browsers. Keep the SVG plain:

- Root `<svg>` with `xmlns`, `width`, `height` and a matching `viewBox`.
- A full-size background `<rect>` (light), so it reads on dark themes too.
- Put `text-anchor`, `font-size` and `font-family` **on each `<text>`**, not
  only on a parent `<g>` or in CSS. Some renderers ignore inherited values.
- Generic font families only, `sans-serif` by default. Use `monospace` only for
  code, and check it: on some systems it falls back to a serif font. No web
  fonts, no external images, no scripts, no `foreignObject`.
- Leave a margin: nothing within ~16 px of the edge. Long text is the usual
  thing that runs off the right side.
- ASCII-safe text (`--`, `->`, `^2`) avoids corrupt bytes on odd encodings.
  It is not a substitute for looking.

## Look at it (required)

A parser accepting the XML proves nothing: blank canvases, clipped labels,
encoding garbage and arrows on the wrong cells all parse fine. An image-reading
tool will not open `.svg` at all. So:

1. `python <skill-dir>/scripts/figure.py <output>/<key>/extras/<name>.svg`
   writes `extras/.check/<name>.png`, using headless Chrome/Edge when installed
   (what Markdown viewers show) or PyMuPDF otherwise. It warns if the result
   looks blank.
2. **Open that PNG and look**: every label readable, nothing overlapping or
   cut off, the claimed content actually drawn, lines and arrows where the text
   says they are, not crossing out the values they point at.
3. Fix the source and render again until it is right.
4. `python <skill-dir>/scripts/figure.py --clean <output>/<key>/extras` removes
   the check PNGs. Never leave or commit them.

Do not tell the student a figure is done because it parsed.
