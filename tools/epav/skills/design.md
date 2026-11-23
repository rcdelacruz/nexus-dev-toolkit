# /design

**DESIGN** — the designer's step, and an **optional** one. It does one of two jobs in `docs/designs/<app>/`:

- **create** the screens from the designer's **own design system** (`--system`) — the way Claude Design works: every screen of every epic, built only from that system's tokens and components;
- **review** an export the designer already has (Claude Design, Figma Make, any HTML/React/Next.js export) against the team's design guide and the requirements.

Either way it hands developers a framework-neutral summary (`design.json`). Runs EVALUATE → PLAN → stop for approval → APPLY → VALIDATE.

**Without this command:** a designer who works in Claude Desktop (Claude Design) or Figma Make copies the exported files into `docs/designs/<app>/` and commits them. The tech lead's `/scaffold` reads them directly (`ingest_design_export` in preview) — `design.json` is not required.

## Usage

- `/design <app> --system <path>` — create. `<path>` is the design system: a folder or .zip with its tokens (CSS variables, `tailwind.config.*` or W3C `tokens.json`), components, brand rules, or a Claude Design design-system export. Kept product-wide in `docs/designs/design-system/`.
- `/design <app> [path]` — review an export (folder or .zip: HTML frames, tokens, optional code export). Default: `docs/designs/<app>/`.

## Rules for the whole command

- Follow `docs/designs/DESIGN-GUIDE.md`: its rules and severities. If it doesn't exist, nexus's defaults apply (same rules); say so once.
- The HTML frames are the visual truth for every stack. A code export (React, Next.js, …) is a bonus, used as code only when the architecture's stack is the same framework.
- **Create mode uses the design system and nothing else:** colours, type, spacing and radius come from its tokens; components from its components. Never invent a colour or a component the system doesn't have — if a screen needs one, ask the designer (it's a new token/component for the system, or the screen changes).
- Screens follow the **epics** from the architecture (`ingest_architecture_doc` → `epics`): each screen names its epic and the story / requirement IDs it serves.
- Explain every finding in plain words for a designer: which screen, which colour/state, and what to do — never just a rule number.
- Write only under `docs/designs/`. Never touch code, `docs/requirements/` or `docs/arch-docs/`. Never copy `node_modules/`, `.next/`, `dist/` or `build/`.

## EVALUATE

1. Read the guide. Read the requirement IDs from `docs/requirements/` (the product's BRD/PRD) — note which have a UI part (screens, forms, reports).
2. Run `ingest_architecture_doc` (`module=<app>`, `save_summary=false`) for the stack per client and the **epics** with the IDs each covers. No architecture yet → say so; screens are grouped by PRD area instead, and the architect maps them later.
3. **Create:** read the design system — token roles (light/dark), type scale, components and their states, brand rules. Missing core roles (background, foreground, primary) are a BLOCKER to raise now.
   **Review:** run `ingest_design_export` with `path`, `module=<app>`, `requirement_ids=<UI requirement IDs>`, **write=false** (preview).

```
DESIGN — EVALUATE
─────────────────
App:           <app>
Mode:          create from <design system> | review <export path>
Design system: <token roles found, components, gaps>            (create)
Export:        <frames: n, exports: <framework list>, tokens: <files>; skipped build output>   (review)
Epics:         <E001 name — UI IDs …>
Screens:       <planned (create) | found: DES-id  name  ← frame  → component (review)>
Stack:         <from the architecture: per client> — React reuse: yes/no
Findings:      <BLOCKER / FIX NOW / BACKLOG counts>
```

## PLAN

Show, then **stop**:

```
DESIGN — PLAN
─────────────
Screens:     <epic — screen name — serves US/FR/AC ids — states (empty / loading / error / disabled) — breakpoints>
Coverage:    <each UI requirement ID → screen(s)>; <IDs with no screen>
Tokens:      <roles used, from the design system>; <anything the system lacks → question>
To fix:      <review: each BLOCKER / FIX NOW, in plain words, with what to change>
Write:       docs/designs/design-system/ (create: the system, as given)
             docs/designs/<app>/ — one frame per screen, tokens.css, Design System frame, design.json
```

Ask the designer to confirm the screen list, the screen ↔ requirement links, and (review) whether each off-token colour is a new token or a mistake.

> Plan ready. Reply **go**, or send an updated design system / export.

Do not write anything before the designer approves.

## APPLY

1. Branch: `git switch -c docs/design-<app>` (or the designer's docs branch).
2. **Create:**
   - copy the design system, unchanged, into `docs/designs/design-system/` (unzipped, build output excluded);
   - write `docs/designs/<app>/tokens.css` from the system's tokens (CSS variables, light and dark; a first-line comment says which file it came from — edit the system, not the copy);
   - write one HTML frame per screen, `Frame - <Screen>.dc.html`: plain HTML + CSS whose colours are only `tokens.css` values (as `var(--…)` or the token's exact value), the system's components, every state the screen has (each marked with a `<!-- state: empty -->` / `loading` / `error` / `disabled` comment), and a note naming its epic and the IDs it serves;
   - write `Design System.dc.html`, a reference board of the tokens and components.
   **Review:** copy the export into `docs/designs/<app>/` (unzipped, build output excluded).
3. Run `ingest_design_export` with **write=true**. Then add the confirmed requirement IDs to each screen's `trace_ids` in `docs/designs/<app>/design.json` (keep its JSON layout).
4. Screen IDs are stable: an existing screen keeps its DES-id on re-import; new screens get the next number.

## VALIDATE

1. Run `ingest_design_export` (write=false) once more and report every finding as BLOCKER / FIX NOW / BACKLOG, in the designer's words.
2. **Create:** fix your own frames until no BLOCKER or FIX NOW is left. **Review:** BLOCKERs (no tokens file, missing core colour roles, a UI requirement without a screen) and FIX NOWs (off-token colours, missing states, missing breakpoints) go back to the designer with the exact fix; re-import after they send a new export. Do not "fix" a designer's own export by editing their files yourself.
3. When none are left:
   - `git add docs/designs` — **only** docs/. `git commit -m "design(<app>): …"`.
   - If the repo has a remote, `gh pr create` titled `Design: <app>`, with the screen list and coverage; with no remote (e.g. a repo that isn't on GitHub yet) stop at the commit and say so.

```
DESIGN — VALIDATE COMPLETE
──────────────────────────
Screens:      <n> (DES-001 … DES-0nn), by epic; paired with a code export: <n>
Coverage:     <n/n UI requirements>
Checks:       <rule → PASS / FIXED / BACKLOG>
Pull request: <url | none — no remote>
```

Next: the tech lead runs `/scaffold` (Day 0, once) — it builds the screens from the frames and tokens — and then
`/dev-tasks-planner <app>` against that code, one task CSV per epic.
