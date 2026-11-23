# Pattern: an AI judgment only where the code would otherwise guess

Used for TypeSafe in v4 (tools/epav/judgment.py).

- Explicit sources always win and never call the judgment: the guide's section names, **Choice** lines, a package manager named in
  the hint, header names that normalise. Only the keyword fallback gets a judgment.
- One switch: the API key in the environment. No flag, no config written to shared files (a key in .mcp.json would be in git).
- Skip the call entirely when disabled; on any error, or an answer missing a single question, use the built-in rules for the whole batch.
- Every result names its source (`sections_from`, `token_roles_from`, `stack_from`, `package_manager_from`) so a user can see which path answered.
- Don't judge what has its own template (ADRs) — it costs one call per file for no gain.
- Tests: an autouse fixture removes the key (tests/conftest.py); TypeSafe tests mock the client. Check the real API once, by hand, before shipping.
