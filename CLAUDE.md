# nexus-dev-toolkit — Claude Instructions

## Version Bump Checklist

When bumping the version, update ALL of these — every single time, no exceptions:

1. `pyproject.toml` — `version = "X.Y.Z"`
2. `nexus_cli.py` — `_VERSION = "X.Y.Z"`
3. `public/index.html` — `<span>vX.Y.Z</span>`
4. `public/docs.html` — `<div class="nav-version">vX.Y.Z</div>`
5. `CHANGELOG.md` — add new section `## [X.Y.Z] - YYYY-MM-DD`
6. `python3 scripts/build_changelog.py` — rebuilds `public/changelog.html` and the docs "What's new" blocks (`tests/test_changelog_page.py` fails CI if skipped)
7. Commit and push → GitHub Actions auto-publishes to PyPI
8. Deploy Cloudflare Pages: `wrangler pages deploy public/ --project-name nexus-coderstudio --branch main --commit-dirty=true`
9. Create GitHub release: `gh release create vX.Y.Z --title "vX.Y.Z" --notes "..."`

After a nexus-jev release (its `## [jev X.Y.Z]` entry is on the `experimental-jev` branch): on main, `git fetch origin experimental-jev`, run `python3 scripts/build_changelog.py`, update the `#jev` section of `public/docs.html` if needed, commit, push, deploy (step 8).

## After Every Commit

- If `public/` changed → deploy Cloudflare Pages immediately (step 8 above)
- Never commit and stop — always run the full sequence

## Key Facts

- PyPI package: `nexus-dev-toolkit`
- Cloudflare Pages project: `nexus-coderstudio`
- Landing page: https://nexus.coderstudio.co
- GitHub repo: rcdelacruz/nexus-dev-toolkit
- Python version badge: static (`https://img.shields.io/badge/python-3.10%2B-blue`)

## graphify

This project has a knowledge graph at graphify-out/.

- For codebase questions, run `graphify query "<question>"` when graphify-out/graph.json exists.
- After modifying code, run `graphify update .` to keep the graph current.
