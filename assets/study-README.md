# Study packs

This folder is for **reading** and **asking**.

1. **Pack**: each slide image, then a polished version of what the lecturer said
   on that page (their voice, talking to you). Starred `###` headings are notices
   (marks, exams, deadlines, required actions); they are also listed at the top.
2. **See it**: ask your agent about a slide (`/tps 12 why ...`). The answer is
   written under that slide in `pack.md`, and when words are not enough the agent
   draws a figure into `extras/` and links it there.

When a new slide deck or recording arrives, `/tps` packs **only that lecture**.
Lectures that are already packed are left alone, and your notes under each slide
survive any re-render.

Folders:

- `<lecture>/pack.md`: what you read
- `<lecture>/pages/`: slide images
- `<lecture>/extras/`: figures drawn while tutoring
- `<lecture>/extracted.json`, `alignment.json`; `pairs.json`, `inventory.json`:
  working files for the agent
