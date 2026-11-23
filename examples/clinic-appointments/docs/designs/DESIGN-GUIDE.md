# Design Guide

This guide is how designers hand designs to developers. Three ways in, all checked against the
rules below:

- `/design <app> --system <design system>` — Claude creates the screens from your own design system;
- `/design <app> <export>` — Claude reviews an export you made and tells you what to fix, per screen;
- **no command** — copy a Claude Design (Claude Desktop) or Figma Make export into `docs/designs/<app>/`
  and commit it; the tech lead's `/scaffold` reads it and runs the same checks.

**Edit this file to match your team.** Only the block at the bottom is read by nexus.

## What to export

Put each app's designs in `docs/designs/<app>/` (a folder or a .zip — both work). The product's design
system, when there is one, lives in `docs/designs/design-system/`. Screens follow the architecture's epics.

- **HTML frames** — one file per screen, named `Frame - <Screen>.dc.html` (or `<Screen>.html`).
  These are the visual source of truth for every stack, React or not.
- **Tokens** — one CSS file defining the design's colour roles as variables (`--background`,
  `--foreground`, `--primary`, `--muted`, `--destructive`, `--border`, `--radius`, …), light and
  dark. A `tailwind.config.js` or W3C `tokens.json` is fine too.
- **react-export/** (optional) — the same screens as code (Figma Make, Claude Design export,
  a Next.js/Vite project). Developers reuse it only when the app's stack is React; for every
  other stack it's a reference for behaviour.
- **assets/** — images and icons the frames use.
- Never include `node_modules/`, `.next/`, `dist/` or `build/` — they are generated and can be
  hundreds of MB. nexus skips them anyway.

## What every screen needs

- Colours from the tokens only. A colour that isn't a token is either a new token or a mistake.
- The four component states where the screen has them: **empty**, **loading**, **error**,
  **disabled** — and say which pattern each uses (inline field error vs toast, empty-table copy).
- Breakpoints the requirements ask for (mobile and/or desktop frames). If one layout serves all
  widths, say so.
- Interactions a static frame can't show, written next to the frame: what closes a dropdown,
  what a button does while waiting, what happens on session timeout.
- The requirement IDs the screen covers (US-, FR-, AC-) and its epic (E001 …), in the frame's title or a note.

## Rules nexus checks

```nexus-guide
{
  "kind": "design",
  "format_version": 1,
  "required_sections": [],
  "id_patterns": {},
  "rules": [
    {"id": "D1", "severity": "BLOCKER", "text": "A tokens file exists and defines the core colour roles (background, foreground, primary)."},
    {"id": "D2", "severity": "BLOCKER", "text": "Every requirement with a UI part has at least one screen."},
    {"id": "D3", "severity": "FIX NOW", "text": "One HTML frame per screen."},
    {"id": "D4", "severity": "FIX NOW", "text": "Colours in frames come from the tokens."},
    {"id": "D5", "severity": "FIX NOW", "text": "Screens show their empty / loading / error / disabled states where they have them."},
    {"id": "D6", "severity": "FIX NOW", "text": "Mobile and desktop frames exist when the requirements ask for both."},
    {"id": "D7", "severity": "BACKLOG", "text": "Each frame has a matching component in react-export, when one is provided."},
    {"id": "D8", "severity": "BACKLOG", "text": "Assets live in assets/, not linked from outside the export."}
  ]
}
```
