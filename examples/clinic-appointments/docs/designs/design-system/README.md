<!-- Example project for nexus v4. CareSlot and everything in it is made up. -->
# CareSlot design system

The product designer's own system. `/design <app> --system docs/designs/design-system` builds every screen
from it — nothing else. A screen that needs something not listed here is a question for the designer.

## Tokens — `tokens.css`

Colour roles, light and dark: `--background`, `--foreground`, `--surface`, `--primary`,
`--primary-foreground`, `--muted`, `--muted-foreground`, `--border`, `--destructive`, `--success`,
`--warning`; `--radius` 0.5 rem (8 px); `--font-sans` Inter.

## Components

| Component | Look | States |
|---|---|---|
| Card (`.card`) | `--background` on `--surface`, 1 px `--border`, radius 8 px, 20 px padding, max 420 px wide | — |
| Button (`.btn`) | `--primary` / `--primary-foreground`, radius 8 px, 600 weight | disabled: `--muted` / `--muted-foreground`, not-allowed cursor; busy: label "…ing" |
| Field | label above, 1 px `--border`, radius 8 px | error: message below in `--destructive`, 13 px |
| Hint (`.hint`) | `--muted-foreground`, 13 px | — |
| Status (`.ok`, `.warn`, `.err`) | `--success` (done), `--warning` (attention), `--destructive` (failed / error) | — |

## Rules

- Every screen shows its **empty**, **loading** and **error** states where it has them, and **disabled** for
  actions that can't run yet — each marked in the frame with a `<!-- state: … -->` comment.
- Errors are inline, next to what caused them — no toasts.
- Each screen is one card (max 420 px), phones first.
- The logo is `assets/careslot-logo.svg`.
- Frames name their epic and the IDs they serve in their first comment.
