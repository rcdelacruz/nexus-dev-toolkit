"""
ingest_design_export — MCP tool for Day 0 EVALUATE/PLAN.

Given a design export (a Figma export ZIP, a Figma dev-mode export
directory, or a standalone HTML mockup such as one produced by Claude's
Design artifact type), extracts its CSS custom-property design tokens and
classifies each into a canonical role.

Two judgments are involved here, and only one of them is a TypeSafe
candidate:
  - Which FORMAT the export is in -- this is fully deterministic (a Figma
    export is always a .zip; a Claude-Design mockup is always a standalone
    .html file), so it's plain code, no judgment needed.
  - Which ROLE a given token name plays (e.g. "brand-500" -> primary,
    "btn-danger-bg" -> error) -- this genuinely varies by naming
    convention and tool, the same shape as task_loader.py's CSV-header
    mapping, so it goes through TypeSafe with a keyword fallback.
"""

import json
import logging
import re
import tempfile
import zipfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tools.epav import judgment

logger = logging.getLogger(__name__)

_TOKEN_ROLE_CRITERIA = {
    "primary": "The primary/brand accent color used for main interactive elements (buttons, links)",
    "secondary": "A secondary accent color, less prominent than primary",
    "success": "Indicates a successful/positive state (green, checkmarks, confirmations)",
    "warning": "Indicates a caution/warning state (yellow/amber)",
    "error": "Indicates an error/danger/destructive state (red)",
    "neutral": "A neutral/muted gray tone, not tied to brand or status",
    "background": "A background surface color (page, card, or container background)",
    "foreground": "Text or icon foreground color",
    "border": "A border or divider color",
    "spacing": "A spacing/sizing value (margin, padding, gap), not a color",
    "typography": "A font family, size, weight, or line-height value",
    "radius": "A border-radius/corner-rounding value",
    "shadow": "A box-shadow/elevation value",
    "other": "Doesn't clearly map to any of the above roles",
}

# Keyword fallback, used only when TypeSafe is unavailable.
_TOKEN_ROLE_KEYWORDS: dict[str, list[str]] = {
    "primary": ["primary", "brand"],
    "secondary": ["secondary"],
    "success": ["success", "positive", "confirm"],
    "warning": ["warning", "warn", "caution"],
    "error": ["error", "danger", "destructive", "negative"],
    "neutral": ["neutral", "muted", "gray", "grey"],
    "background": ["background", "bg", "surface"],
    "foreground": ["foreground", "fg", "text", "ink"],
    "border": ["border", "divider", "outline"],
    "spacing": ["space", "spacing", "gap", "margin", "padding"],
    "typography": ["font", "size", "leading", "line height", "weight"],
    "radius": ["radius", "rounded", "corner"],
    "shadow": ["shadow", "elevation"],
}

_CSS_VAR_RE = re.compile(r"--([a-zA-Z0-9_-]+)\s*:\s*([^;{}]+);")


def _extract_css_custom_properties(text: str) -> dict[str, str]:
    """Pull CSS custom properties (--name: value;) out of raw HTML/CSS text.

    Covers a Claude-Design HTML mockup and a Figma export's sibling
    tokens.css/design-tokens.css. Does NOT parse a token set embedded as a
    JS object/array literal (e.g. a Figma export's inline COLORS/TYPE_SCALE
    script variable) -- that's a different, open-ended parsing problem,
    out of scope here; read those directly instead.
    """
    return {m.group(1): m.group(2).strip() for m in _CSS_VAR_RE.finditer(text)}


def _detect_design_format(path: Path) -> str:
    """Deterministic, not a judgment call: the format is fully implied by
    file structure, no ambiguity to resolve."""
    if path.is_file() and path.suffix.lower() == ".zip":
        return "figma_export_zip"
    if path.is_dir():
        if list(path.rglob("*.dc.html")):
            return "figma_dev_mode_export"
        if list(path.rglob("*.html")):
            return "html_mockup"
    if path.is_file() and path.suffix.lower() == ".html":
        return "html_mockup"
    return "unknown"


def _map_token_roles_fallback(names: list[str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name in names:
        name_lower = f" {name.lower().replace('-', ' ').replace('_', ' ')} "
        for role, keywords in _TOKEN_ROLE_KEYWORDS.items():
            if any(k in name_lower for k in keywords):
                mapping[name] = role
                break
    return mapping


async def _map_token_roles(names: list[str]) -> dict[str, str]:
    """Map each design-token name to a canonical role.

    Same shape as task_loader.py's CSV-header mapping: naming conventions
    vary a lot between design tools and hand-authored files ("brand-500",
    "color-primary", "btn-danger-bg", ...), so a keyword match alone misses
    real cases -- that's exactly why the fallback below is intentionally
    more limited than the TypeSafe path.

    Each question embeds its own token name directly in `instructions`
    rather than referencing a shared list by index, per the index-binding
    lesson from arch_ingest.py's heading classifier.
    """
    if judgment.Choice is None:
        return _map_token_roles_fallback(names)

    result = await judgment.system_one_async(
        state={},
        questions={
            f"t{i}": judgment.Choice(
                instructions=f'Which design-token role does the CSS custom property "--{name}" correspond to?',
                criteria=_TOKEN_ROLE_CRITERIA,
            )
            for i, name in enumerate(names)
        },
    )
    if result is not None:
        mapping = {}
        for i, name in enumerate(names):
            role = result.choices[f"t{i}"].choice
            if role != "other":
                mapping[name] = role
        return mapping

    return _map_token_roles_fallback(names)


def _find_design_export(hint: str) -> Path | None:
    """Locate a design export from a path hint or by scanning docs/designs/."""
    if hint:
        p = Path(hint)
        if p.exists():
            return p
    designs_dir = Path("docs/designs")
    if designs_dir.exists():
        candidates = sorted(designs_dir.iterdir())
        if candidates:
            return candidates[0]
    return None


def register_design_ingest_tool(mcp: FastMCP) -> None:

    @mcp.tool()
    async def ingest_design_export(doc_path: str = "") -> str:
        """
        Ingest a design export and extract its design tokens, mapped to
        canonical roles (primary, secondary, success, warning, error,
        neutral, background, foreground, border, spacing, typography,
        radius, shadow).

        Accepts a Figma export ZIP, a Figma dev-mode export directory, or a
        standalone HTML mockup (e.g. one produced by Claude's Design
        artifact type). Only extracts tokens expressed as CSS custom
        properties (`--name: value;`), from the file itself or a sibling
        tokens.css/design-tokens.css. Does NOT parse a Figma export's
        inline JS token arrays (e.g. a COLORS/TYPE_SCALE script variable)
        -- read those directly instead, per /scaffold's EVALUATE guidance.

        Args:
            doc_path: Path to the design export (a .zip, a directory, or a
                      .html file). If empty, uses the first entry found in
                      docs/designs/.

        Returns:
            JSON: { "format": "figma_export_zip" | "figma_dev_mode_export" |
                    "html_mockup" | "unknown", "tokens": {name: {"value":
                    ..., "role": ...}}, "files_read": [...] }
        """
        try:
            source = _find_design_export(doc_path)
            if not source:
                return json.dumps({
                    "error": "No design export found. Provide doc_path or place one in docs/designs/."
                })

            fmt = _detect_design_format(source)
            if fmt == "unknown":
                return json.dumps({
                    "error": f"Unrecognised design export at {source} (expected a .zip, a directory "
                             "containing .html, or a .html file).",
                    "format": fmt,
                })

            tmpdir_obj = None
            extract_root = source
            try:
                if fmt == "figma_export_zip":
                    tmpdir_obj = tempfile.TemporaryDirectory(prefix="nexus-design-")
                    with zipfile.ZipFile(source) as zf:
                        zf.extractall(tmpdir_obj.name)
                    extract_root = Path(tmpdir_obj.name)

                candidate_files = (
                    [extract_root] if extract_root.is_file()
                    else sorted(extract_root.rglob("*.html")) + sorted(extract_root.rglob("*.css"))
                )

                if not candidate_files:
                    return json.dumps({"error": f"No .html/.css files found in {source}", "format": fmt})

                raw_tokens: dict[str, str] = {}
                files_read = []
                for f in candidate_files:
                    try:
                        text = f.read_text(encoding="utf-8", errors="ignore")
                        raw_tokens.update(_extract_css_custom_properties(text))
                        files_read.append(str(f))
                    except Exception as e:
                        logger.warning("Could not read %s: %s", f, e)

                if not raw_tokens:
                    return json.dumps({
                        "error": "No CSS custom properties (--name: value;) found. If this export uses "
                                 "an inline JS token array instead, read it directly per /scaffold's "
                                 "EVALUATE guidance.",
                        "format": fmt,
                    })

                role_map = await _map_token_roles(list(raw_tokens.keys()))
                tokens = {
                    name: ({"value": value, "role": role_map[name]} if name in role_map else {"value": value})
                    for name, value in raw_tokens.items()
                }

                return json.dumps({
                    "format": fmt,
                    "tokens": tokens,
                    "files_read": files_read,
                }, indent=2)
            finally:
                if tmpdir_obj:
                    tmpdir_obj.cleanup()

        except Exception as e:
            logger.exception("Unexpected error in ingest_design_export")
            return json.dumps({"error": f"Unexpected error: {e}"})
