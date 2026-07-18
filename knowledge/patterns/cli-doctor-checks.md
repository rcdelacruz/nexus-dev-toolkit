# CLI doctor-style status checks

## Don't reuse a query-dispatch detector for "does output exist" UI copy

A `detect_backend()`-style function that falls back from "output exists" to "tool is
merely installed" (so callers always get *something* to query) must not be reused
directly to decide whether a status row can claim a build artifact exists. On a
machine where the tool is installed but never run, that fallback makes the row lie
("graphify-out/graph.json exists" when it doesn't). Keep the two questions separate:
`<x>_built` (artifact-on-disk check) drives existence claims; the detector's install
fallback is only for "what would a query use right now."

Caught in `nexus_cli.py doctor()` via `graphify` being installed on the dev machine
but no graph ever built in the test's tmp project — the bug only showed up when
testing against a *clean* project, not one that inherited dev-machine state.

## Rich `Table` wraps long cell text — strip borders before substring-asserting

When a `rich.table.Table` cell's text is long enough to wrap, Rich inserts the
table's border characters (`│`, plus continuation padding) *between* words on the
wrapped line. A test asserting `"some long message" in result.output` can fail even
though the message is correct and would read fine in a real terminal — the wrap
point splits the substring across a border character.

Fix: normalize captured CLI output before asserting, not by shortening the message:

```python
import re

def _flat(output: str) -> str:
    cleaned = re.sub(r"[─-╿]", " ", output)   # strip the Box Drawing block (U+2500–257F)
    return re.sub(r"\s+", " ", cleaned)
```

Then assert against `_flat(result.output)`. See `tests/test_cli.py`.
