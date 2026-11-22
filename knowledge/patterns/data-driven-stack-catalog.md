# Data-driven stack support

## Add a stack by adding data, not code

Stack detection reads `tools/epav/stack_catalog.json` (name, category, aliases,
optional `exact_case`, optional `package_manager`). `_infer_stack` and the
resolver's hint detection both go through `tools/epav/stack_catalog.py`, so a new
framework is one JSON line. `tests/test_stack_catalog.py` enforces: unique names,
unique aliases, and every `package_manager` exists in the resolver registry.

## Whole-word matching, case-sensitive for English words

Aliases match only when both neighbours are not `[A-Za-z0-9_]` — the old
`"t3" in text` matched inside any word. Names that are also English words
("Go", "Rails", "Swift", "Express", "Phoenix") go in `exact_case`, never in
`aliases`. Keyword matching still can't tell "we use X" from "we rejected X"
(tested, documented) — that's what the jev TypeSafe judgment adds.

## Resolve versions from the real source, and say so when you can't

`resolve_package_versions` writes a minimal manifest in a temp dir and runs the
real lock step, or (JVM, CocoaPods, which can't resolve in an empty dir) reads
the official registry metadata. Anything it can't do returns a structured
`status` (`tool_missing`, `unsupported`, `partial`, `failed`) with
instructions — never a silent npm guess. Real-run tests are marked `network`
and skip when the binary isn't installed; lock-file readers are covered by
fixtures in `tests/fixtures/locks/` so every ecosystem is tested on any machine.

Gotcha found while building it: `go get`, `flutter pub add` and `cargo add` all
fail in an empty directory (no go.mod / pubspec.yaml / Cargo.toml) — the old
registry had no init step for them, so they never returned versions. Always
run a real resolution per package manager, not just the lock reader.
