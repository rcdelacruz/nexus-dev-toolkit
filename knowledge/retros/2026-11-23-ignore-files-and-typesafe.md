# Retro — .gitignore/.graphifyignore and TypeSafe in v4 (2026-11-23)

## Measured
- Team-run graph 1021 → 883 nodes with the new .graphifyignore; the 138 removed were all .nexus/manifest.json and a vendored htmx.min.js.
- TypeSafe (jev-1.14.0, real API): an architecture doc that doesn't follow the guide kept 0 sections with keywords, 3 of 4 with TypeSafe
  (it dropped "Release history"); a stack with no Choice lines dropped Kubernetes, which the doc only mentions as "e.g. Kubernetes Secrets".
- Claude Code passes the shell's TYPESAFE_API_KEY to the MCP server: the same call answered "typesafe" with the key, "built-in" without.

## Fixed during validate
- [FIX NOW] /scaffold check 20 used `git check-ignore -q .env graphify-out`; git rejects -q with several paths (exit 128), so the
  check could never pass. Now one path per check.

## Backlog
- [BACKLOG] resolve_package_versions: TypeSafe gave the same answer as the catalog on 6 of 6 hints but added 0.7–3.8 s each. Ask the
  catalog first and TypeSafe only when the catalog finds nothing — waiting for the owner's call.
- [BACKLOG] Token roles: 8 unplaced → 3 on the Crate tokens, but 2 of the 5 new roles look doubtful (--color-purple → primary,
  --color-info → secondary). Measure on more exports before relying on judged roles for rule D1.
- [BACKLOG] docs.html: the lowest prose-like contrast (5.82 light / 6.01 dark) is not a paragraph or list item; unidentified, predates this change.
