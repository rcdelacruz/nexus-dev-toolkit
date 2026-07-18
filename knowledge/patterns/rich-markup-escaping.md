---
name: rich-markup-escaping
description: Rich silently swallows literal square-bracket text in console.print()/console.input() unless escaped — caught after it broke three [y/N]-style prompts.
metadata:
  type: pattern
---

# Escape literal brackets in Rich console text

`rich.console.Console` parses `[...]` in any string passed to `.print()` or `.input()` as a
markup style tag (`[cyan]`, `[/dim]`, etc.). If the bracket content isn't a recognized style
name — `[y/N]`, `[1]`, any literal bracketed hint meant for the human reader — Rich doesn't
error and doesn't render it literally either. It just **silently drops it**, no exception, no
warning. `console.input("Choice [1]: ")` renders as `Choice: ` with the default hint gone.

This is easy to miss because it doesn't break anything mechanically — the prompt still shows,
still accepts input, tests that only check `result.exit_code` or substrings unrelated to the
bracket text still pass. It just quietly loses information the user needed. Found in
`nexus_cli.py` when `[y/N]` vanished from an update prompt — traced back to a pre-existing bug
in `_check_and_offer_install()`'s install prompt that had been there before this session, and
a second copy in `_resolve_graph_backend()`'s `Choice [1]:` hint. All three had the exact same
root cause because the buggy pattern got copy-pasted forward.

## Fix

```python
from rich.markup import escape

console.input(f"  Install {name} now? {escape('[y/N]')} ")
```

## How to catch it

Don't trust that a prompt "looks right" in the source string — render it. A one-line check
against a real `Console()` (not just running the CLI and skimming) would have caught this
immediately:

```python
from rich.console import Console
Console().print("Choice [1]: ", end="")
```

Anywhere `[BLOCKER]`/`[FIX NOW]`/similar literal-bracket text is printed via Rich (this
project's EPAV skill output format uses that exact convention), it's at the same risk if it
ever moves from an agent-authored text block into a `console.print()` call.
