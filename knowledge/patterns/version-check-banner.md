---
name: version-check-banner
description: How the PyPI-backed update banners on public/index.html and public/docs.html work, and the gotcha that makes them look broken when they aren't.
metadata:
  type: pattern
---

# Version-check banner (public/index.html, public/docs.html)

Both pages fetch `https://pypi.org/pypi/nexus-dev-toolkit/json` client-side and compare
`info.version` against the page's own baked-in version (`#site-version` on index.html,
`.nav-version` on docs.html). If the page version is behind, a hidden `#version-banner` div is
unhidden with an "update available" message. Same logic exists server-side in `nexus_cli.py`'s
`_fetch_latest_pypi_version()`/`_is_outdated()`, used by `nexus doctor` and `nexus update` — the
JS and Python versions are independent reimplementations (no shared code between a static page
and a CLI), so a future change to the comparison logic needs to land in both places.

## Version comparison is tuple-based, not string-based

`"3.9.0" > "3.10.0"` as a plain string compare (wrong — 3.10 is newer). Both the JS
(`versionTuple`/`isOutdated`) and Python (`_version_tuple`/`_is_outdated`) split on `.` and
compare int tuples instead.

## Why the banner might look broken when it isn't

1. **The page version already matches (or is ahead of) PyPI's real latest.** Local edits often
   bump the version before it's actually published — the banner correctly stays hidden until
   the bumped version is live on PyPI. Not a bug; check `curl -s
   https://pypi.org/pypi/nexus-dev-toolkit/json | python3 -c "import json,sys;
   print(json.load(sys.stdin)['info']['version'])"` against the page's shown version before
   assuming something's wrong.

2. **Opened via `file://` instead of a local server.** Browsers commonly block `fetch()` to
   external HTTPS APIs from `file://` origins. The `.catch()` swallows this silently — no
   banner, no visible console error either, unless you have devtools open and are specifically
   watching the Network tab. Always test by serving the file over `http://` (`python3 -m
   http.server`), not by double-clicking it open.

## To force the banner visible for testing

Copy the file elsewhere, sed the version span down to something old (e.g. `v1.0.0`), serve it
locally, open in a real browser. Never edit the version down in the tracked file itself just to
test — too easy to forget to revert.
