"""
ingest_design_export — read a design export, framework-neutral, and summarise it as design.json.

Designers hand over a folder or a .zip holding any mix of:
  - HTML frames (one per screen; `*.dc.html` or plain `.html`) — the visual source of truth
  - token files (CSS variables, tailwind.config.js, W3C tokens.json)
  - a code export (Figma Make / Claude Design react-export / next-export / Vue / Svelte / …)
  - assets and notes
Every file is classified by its CONTENT, not its folder name. Build output (node_modules, .next,
dist, build) is never read. Frame colours are matched against the tokens; frames are paired with
export components by name; screen IDs (DES-001…) stay stable across re-imports. The result is
checked against the project's DESIGN-GUIDE.md rules.

Nothing is written unless write=True — the /design skill shows the plan first and writes only
after the designer approves.
"""

import colorsys
import json
import logging
import math
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from tools.epav import judgment
from tools.epav.formats import design as design_format
from tools.epav.formats import guides
from tools.epav.formats.ids import extract_ids, kind_of

logger = logging.getLogger(__name__)

SKIP_DIRS = {"node_modules", ".next", "dist", "build", ".git", ".turbo", ".cache", "coverage",
             "graphify-out", "__MACOSX", ".vercel", ".output", ".svelte-kit", ".dart_tool"}
MAX_FILES = 20_000
MAX_TOTAL_BYTES = 300 * 1024 * 1024        # of files actually considered (build output excluded)
MAX_TEXT_BYTES = 5 * 1024 * 1024           # per file read
GUIDE_PATH = Path("docs/designs/DESIGN-GUIDE.md")

_IMAGE = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".avif", ".ico"}
_NOTES = {".md", ".txt", ".pdf", ".docx"}
_COMPONENT = {".jsx", ".tsx", ".vue", ".svelte", ".dart"}
_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
_CSS_VAR = re.compile(r"--([a-zA-Z0-9_-]+)\s*:\s*([^;{}]+);")
_REFERENCE_FRAME = re.compile(r"(?i)^(design\s*system|style\s*guide|mockup\s*board|tokens?|components?|"
                              r"nav\s*bar|navigation|header|footer|sidebar|icons?)$")
# "empty: not applicable", "no loading state", "disabled — n/a": a note that a screen does NOT have a
# state. Removed before the state patterns run, so it isn't counted as the state being shown.
_STATE_ABSENT = re.compile(r"(?i)\b(?:no\s+(?:empty|loading|error|disabled)\s+state|"
                           r"(?:empty|loading|error|disabled)(?:\s+state)?\s*[:=—–-]?\s*(?:not applicable|n/?a|none|not needed|never)\b)")
_STATES = {
    "empty": re.compile(r"(?i)\bno (data|records?|results?|items?|entries)\b|there is no|nothing (here|yet)|\bempty\b"),
    "loading": re.compile(r"(?i)\bloading\b|spinner|skeleton|please wait"),
    "error": re.compile(r"(?i)\berror\b|\binvalid\b|\bfailed\b|is required"),
    "disabled": re.compile(r"(?i)\bdisabled\b|not-allowed"),
}
# Token name → role. Compound names first: "--primary-foreground" is text ON primary.
_ROLE_RULES = [
    ("typography", r"^(text|font)-(xs|sm|base|md|lg|\d?xl)$"),          # --text-2xl is a size, not a colour
    ("foreground", r"(foreground|(^|-)fg$|(^|-)(text|ink)(-|$)|(^|-)t\d$)"),   # --color-t1 / --color-text-2
    ("background", r"(^|-)(background|bg|surface|canvas|page|card|popover|chrome|segment)(-|$)"),
    ("primary", r"(^|-)(primary|brand|accent)(-|$)"),
    ("secondary", r"(^|-)secondary(-|$)"),
    ("error", r"(^|-)(error|danger|destructive|negative|red)(-|$)"),
    ("success", r"(^|-)(success|positive|confirm|green)(-|$)"),
    ("warning", r"(^|-)(warning|warn|caution|amber|yellow)(-|$)"),
    ("border", r"(^|-)(border|divider|outline|ring|input)(-|$)"),
    ("neutral", r"(^|-)(muted|neutral|gray|grey|subtle)(-|$)"),
    ("radius", r"(^|-)(radius|rounded|corner)(-|$)"),
    ("shadow", r"(^|-)(shadow|elevation)(-|$)"),
    ("typography", r"(^|-)(font|size|leading|weight|tracking)(-|$)"),
    ("spacing", r"(^|-)(space|spacing|gap|margin|padding)(-|$)"),
]


# ── colours ──────────────────────────────────────────────────────────────────

def _hex6(h: str) -> str:
    h = h.lower().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return "#" + h[:6]


def _rgb_to_hex(r: float, g: float, b: float) -> str:
    clamp = lambda v: max(0, min(255, round(v)))  # noqa: E731
    return "#{:02x}{:02x}{:02x}".format(clamp(r), clamp(g), clamp(b))


def _oklch_to_hex(l: float, c: float, h: float) -> str:
    a, b = c * math.cos(math.radians(h)), c * math.sin(math.radians(h))
    l_ = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (l - 0.0894841775 * a - 1.2914855480 * b) ** 3
    lin = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.7076147010 * s_)
    srgb = [255 * (12.92 * v if v <= 0.0031308 else 1.055 * (max(v, 0) ** (1 / 2.4)) - 0.055) for v in lin]
    return _rgb_to_hex(*srgb)


def colour_to_hex(value: str) -> str | None:
    """#hex, rgb()/rgba(), hsl(), oklch() → #rrggbb. None for anything else (var(), keywords)."""
    v = value.strip().lower()
    m = _HEX.fullmatch(v)
    if m:
        return _hex6(v)
    nums = [float(x.rstrip("%")) if not x.endswith("%") else float(x[:-1]) for x in re.findall(r"-?[\d.]+%?", v)]
    if v.startswith("rgb") and len(nums) >= 3:
        return _rgb_to_hex(*nums[:3])
    if v.startswith("hsl") and len(nums) >= 3:
        r, g, b = colorsys.hls_to_rgb(nums[0] / 360, nums[2] / 100, nums[1] / 100)
        return _rgb_to_hex(r * 255, g * 255, b * 255)
    if v.startswith("oklch") and len(nums) >= 3:
        l = nums[0] / 100 if "%" in v.split()[0] or nums[0] > 1 else nums[0]
        return _oklch_to_hex(l, nums[1], nums[2])
    return None


def _close(a: str, b: str, tol: int = 2) -> bool:
    return all(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) <= tol for i in (1, 3, 5))


def token_role(name: str) -> str:
    n = name.lower().lstrip("-")
    n = re.sub(r"^(color|colour|c)-", "", n)
    for role, pattern in _ROLE_RULES:
        if re.search(pattern, n):
            return role
    return "other"


_ROLE_CRITERIA = {
    "background": "A page, surface or card background colour",
    "foreground": "A text or icon colour",
    "primary": "The brand, primary or accent colour",
    "secondary": "A secondary brand or action colour",
    "error": "Error, danger or destructive colour",
    "success": "Success or positive colour",
    "warning": "Warning or caution colour",
    "border": "Border, divider, outline, input or focus-ring colour",
    "neutral": "A muted, neutral or grey colour",
    "radius": "Corner radius",
    "shadow": "Shadow or elevation",
    "typography": "Font family, font size, weight, line height or letter spacing",
    "spacing": "Spacing, gap, margin or padding",
    "other": "None of these (an animation timing, z-index, breakpoint, or unclear)",
}
_MAX_JUDGED_TOKENS = 120


async def judge_unplaced_tokens(roles: dict[str, str], values: dict[str, str]) -> tuple[dict[str, str], str]:
    """Token names the rules above leave as "other" ("--brand-500", "--btn-danger-bg", "--c-ink-2"…):
    TypeSafe picks the role when the key is set, from the name and its value. The rules' answers are
    never replaced. Returns (roles, "typesafe" | "built-in")."""
    unplaced = [n for n, r in roles.items() if r == "other"][:_MAX_JUDGED_TOKENS]
    if not unplaced or not judgment.enabled():
        return roles, judgment.BUILT_IN
    result = await judgment.system_one_async(state={}, questions={
        f"t{i}": judgment.Choice(
            instructions=f'Which design-token role is the CSS custom property "--{name.lstrip("-")}" '
                         f'(value: "{values.get(name, "")[:80]}")?',
            criteria=_ROLE_CRITERIA)
        for i, name in enumerate(unplaced)})
    if result is None:
        return roles, judgment.BUILT_IN
    try:
        picks = {name: result.choices[f"t{i}"].choice for i, name in enumerate(unplaced)}
    except Exception:
        return roles, judgment.BUILT_IN
    return {**roles, **{n: r for n, r in picks.items() if r in _ROLE_CRITERIA}}, judgment.TYPESAFE


# ── token files ──────────────────────────────────────────────────────────────

def _css_blocks(text: str):
    """Yield (selector-with-context, body) for every rule block, tracking @media context."""
    stack, buf, i = [], [], 0
    sel_start = 0
    while i < len(text):
        ch = text[i]
        if ch == "{":
            selector = text[sel_start:i].strip().split("}")[-1].strip()
            stack.append((selector, i + 1))
            sel_start = i + 1
        elif ch == "}" and stack:
            selector, body_start = stack.pop()
            body = text[body_start:i]
            context = " ".join(s for s, _ in stack)
            buf.append((f"{context} {selector}".strip(), body))
            sel_start = i + 1
        elif ch == ";" and not stack:
            sel_start = i + 1
        i += 1
    return buf


def is_compiled_css(text: str) -> bool:
    head = text[:300].lower()
    return "tailwindcss v" in head or text.count("--tw-") > 40


def parse_css_tokens(text: str) -> dict[str, dict[str, str]]:
    """CSS custom properties split into light (:root, html, @theme, *) and dark (.dark,
    [data-theme=dark], prefers-color-scheme: dark)."""
    out = {"light": {}, "dark": {}}
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)   # a comment mentioning ".dark" is not a selector
    for selector, body in _css_blocks(text):
        if "{" in body:
            body = re.sub(r"[^{}]*\{[^{}]*\}", " ", body)   # nested rules were handled separately
        props = {f"--{k}": v.strip() for k, v in _CSS_VAR.findall(body)}
        if not props:
            continue
        s = selector.lower()
        theme = "dark" if (".dark" in s or 'theme="dark"' in s or "theme=dark" in s or "theme='dark'" in s
                           or "prefers-color-scheme: dark" in s or "prefers-color-scheme:dark" in s) else "light"
        out[theme].update(props)
    return out


def parse_tailwind_config(text: str) -> dict[str, str]:
    return {f"tailwind:{k}": v for k, v in re.findall(r"['\"]?([\w-]+)['\"]?\s*:\s*['\"](#[0-9a-fA-F]{3,8})['\"]", text)}


def parse_tokens_json(text: str) -> dict[str, str]:
    out: dict[str, str] = {}

    def walk(node, path):
        if isinstance(node, dict):
            if "$value" in node or "value" in node and not isinstance(node.get("value"), dict):
                v = node.get("$value", node.get("value"))
                if isinstance(v, (str, int, float)):
                    out["--" + "-".join(path)] = str(v)
                return
            for k, v in node.items():
                if not k.startswith("$"):
                    walk(v, path + [str(k)])
    try:
        walk(json.loads(text), [])
    except Exception:
        return {}
    return out


# ── reading the export ───────────────────────────────────────────────────────

class TooLarge(Exception):
    pass


class UnsafeZip(Exception):
    pass


def _safe_extract(zip_path: Path, dest: Path) -> list[str]:
    """Extract a zip without build output, refusing paths that escape dest. Returns skipped dirs."""
    skipped: set[str] = set()
    total = 0
    with zipfile.ZipFile(zip_path) as z:
        members = z.infolist()
        kept = []
        for m in members:
            parts = Path(m.filename).parts
            hit = next((p for p in parts if p in SKIP_DIRS), None)
            if hit:
                skipped.add("/".join(parts[: parts.index(hit) + 1]))
                continue
            if m.is_dir():
                continue
            target = (dest / m.filename).resolve()
            if not str(target).startswith(str(dest.resolve()) + os.sep):
                raise UnsafeZip(f"zip entry points outside its folder: {m.filename}")
            kept.append(m)
            total += m.file_size
        if len(kept) > MAX_FILES:
            raise TooLarge(f"{len(kept)} files in the zip (limit {MAX_FILES}) after skipping build output")
        if total > MAX_TOTAL_BYTES:
            raise TooLarge(f"{total // 1_048_576} MB in the zip (limit {MAX_TOTAL_BYTES // 1_048_576} MB) after skipping build output")
        for m in kept:
            z.extract(m, dest)
    return sorted(skipped)


def _walk(root: Path) -> tuple[list[Path], list[str]]:
    files, skipped, total = [], [], 0
    for dirpath, dirnames, filenames in os.walk(root):
        for d in list(dirnames):
            if d in SKIP_DIRS:
                skipped.append(str((Path(dirpath) / d).relative_to(root)))
                dirnames.remove(d)
        for f in filenames:
            if f == ".DS_Store" or (f == "design.json" and Path(dirpath) == root):   # our own output
                continue
            p = Path(dirpath) / f
            files.append(p)
            total += p.stat().st_size
            if len(files) > MAX_FILES:
                raise TooLarge(f"more than {MAX_FILES} files after skipping build output")
            if total > MAX_TOTAL_BYTES:
                raise TooLarge(f"more than {MAX_TOTAL_BYTES // 1_048_576} MB after skipping build output")
    return sorted(files), sorted(skipped)


def _read(p: Path) -> str:
    if p.stat().st_size > MAX_TEXT_BYTES:
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _export_roots(files: list[Path], root: Path) -> dict[Path, str]:
    """Folders holding a code export → framework."""
    roots: dict[Path, str] = {}
    for f in files:
        if f.name == "package.json":
            try:
                pkg = json.loads(_read(f) or "{}")
            except Exception:
                continue
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            fw = ("next" if "next" in deps else "react" if "react" in deps else "vue" if "vue" in deps
                  else "svelte" if "svelte" in deps or "@sveltejs/kit" in deps else "angular" if "@angular/core" in deps
                  else "solid" if "solid-js" in deps else "")
            if fw:
                if fw in ("react",) and "vite" in deps:
                    fw = "react (vite)"
                roots[f.parent] = fw
        elif f.name == "pubspec.yaml" and "flutter" in _read(f):
            roots[f.parent] = "flutter"
    # Code exports shipped without a package.json (e.g. a "react-export" folder of src/ files):
    # the outermost folder named *export* or holding an App/main entry file. Loose helper
    # scripts next to the HTML frames don't qualify, so frames are never swallowed.
    entry = ("App.tsx", "App.jsx", "App.vue", "main.tsx", "main.jsx", "src/App.tsx", "src/App.jsx",
             "src/App.vue", "src/main.tsx", "src/main.jsx")
    for f in files:
        ext = f.suffix.lower()
        if ext not in (".jsx", ".tsx", ".vue", ".svelte") or _under(f, roots) is not None:
            continue
        candidates = [a for a in f.parents if (a == root or root in a.parents)
                      and ("export" in a.name.lower() or any((a / e).is_file() for e in entry))]
        if candidates:
            fw = {".vue": "vue", ".svelte": "svelte"}.get(ext, "react")
            roots[candidates[-1]] = f"{fw} (no package.json)"
    return roots


_ROUTE_DIRS = {"app", "pages", "routes"}


def _is_route_page(rel: Path) -> bool:
    """A route page written in plain .js/.ts (Next.js app/*/page.js, pages/*.js, SvelteKit +page.ts)."""
    if rel.suffix.lower() not in (".js", ".ts") or rel.name.endswith((".config.js", ".config.ts", ".d.ts")):
        return False
    return bool(_ROUTE_DIRS & set(rel.parts[:-1])) and (rel.stem in ("page", "+page") or "pages" in rel.parts[:-1])


def _under(p: Path, roots) -> Path | None:
    return next((r for r in roots if r == p.parent or r in p.parents), None)


def _norm(name: str) -> str:
    n = re.sub(r"(?i)\.dc$", "", name)
    n = re.sub(r"(?i)^frame\s*-\s*", "", n)
    n = re.sub(r"[^a-z0-9]", "", n.lower())
    return re.sub(r"(screen|page|view|frame|component)$", "", n) or n


def _screen_name(frame: Path) -> str:
    stem = re.sub(r"(?i)\.dc$", "", frame.stem)
    return re.sub(r"(?i)^frame\s*-\s*", "", stem).strip()


def build_manifest(src_root: Path, module: str, previous: design_format.DesignManifest | None = None,
                   id_patterns: dict | None = None, sources: list[str] | None = None) -> tuple[design_format.DesignManifest, dict]:
    files, skipped_dirs = _walk(src_root)
    roots = _export_roots(files, src_root)
    m = design_format.DesignManifest(module=module, sources=sources or [str(src_root)])
    m.exports = [{"path": str(r.relative_to(src_root)) or ".", "framework": fw} for r, fw in sorted(roots.items())]
    frames, components, token_files, notes = [], [], [], []
    for f in files:
        rel = f.relative_to(src_root)
        ext = f.suffix.lower()
        export_root = _under(f, roots)
        name = f.name.lower()
        if ext in _IMAGE:
            m.assets.append(str(rel))
        elif ext == ".css":
            token_files.append(f)
        elif name.startswith("tailwind.config"):
            token_files.append(f)
        elif ext == ".json" and ("token" in name or "variables" in name):
            token_files.append(f)
        elif ext == ".html" and export_root is None:
            frames.append(f)
        elif export_root is not None and (ext in _COMPONENT or _is_route_page(rel)):
            components.append(f)
        elif ext in _NOTES and export_root is None:
            notes.append(str(rel))
        elif export_root is None:
            m.unrecognised.append(str(rel))

    # tokens: source CSS/config/json; compiled Tailwind output is ignored
    for tf in token_files:
        text = _read(tf)
        if not text:
            continue
        rel = str(tf.relative_to(src_root))
        if tf.suffix.lower() == ".css":
            if is_compiled_css(text):
                continue
            parsed = parse_css_tokens(text)
            if len(parsed["light"]) + len(parsed["dark"]) < 3:
                continue
            m.tokens["light"].update(parsed["light"])
            m.tokens["dark"].update(parsed["dark"])
        elif tf.name.lower().startswith("tailwind.config"):
            vals = parse_tailwind_config(text)
            if not vals:
                continue
            m.tokens["light"].update(vals)
        else:
            vals = parse_tokens_json(text)
            if not vals:
                continue
            m.tokens["light"].update(vals)
        m.token_sources.append(rel)

    # Colours shown in a "Design System" frame count as the palette too — some exports keep
    # their palette there as swatches instead of in a tokens file (D1 still flags that).
    palette_hex = set()
    for fr in frames:
        if re.match(r"(?i)^(design\s*system|style\s*guide)$", _screen_name(fr)):
            palette_hex |= {_hex6(c) for c in _HEX.findall(_read(fr))}
    token_hex = set(palette_hex)
    for theme in ("light", "dark"):
        table = m.tokens[theme]
        for k, v in table.items():
            ref = re.fullmatch(r"\s*var\((--[\w-]+)\)\s*", v)
            hx = colour_to_hex(table.get(ref.group(1), "") if ref else v)
            if hx:
                token_hex.add(hx)

    # screens from frames (reference frames like "Design System" are not screens)
    old_ids = {s.name: s.id for s in (previous.screens if previous else [])}
    next_no = max([int(i.split("-")[1]) for i in old_ids.values() if re.fullmatch(r"DES-\d+", i)] + [0]) + 1
    comp_index = {}
    for c in components:
        stem = c.parent.name if c.stem in ("page", "index", "+page") else c.stem
        if "ui" in c.relative_to(src_root).parts:
            continue
        comp_index.setdefault(_norm(stem), []).append(c)
    reference_frames = []
    for fr in frames:
        name = _screen_name(fr)
        if _REFERENCE_FRAME.match(name):
            reference_frames.append(str(fr.relative_to(src_root)))
            continue
        text = _read(fr)
        sid = old_ids.get(name)
        if not sid:
            sid = f"DES-{next_no:03d}"
            next_no += 1
        key = _norm(name)
        match = comp_index.get(key) or next(
            (v for k, v in sorted(comp_index.items(), key=lambda kv: len(kv[0])) if key and (k.endswith(key) or key.endswith(k)) and len(k) > 2),
            None)
        trace = [i for i in extract_ids(text, id_patterns) if kind_of(i, id_patterns) not in ("adr", "design", "change", "epic")]
        if previous:
            prev = next((s for s in previous.screens if s.name == name), None)
            trace = list(dict.fromkeys((prev.trace_ids if prev else []) + trace))
        m.screens.append(design_format.Screen(
            id=sid, name=name, frame=str(fr.relative_to(src_root)),
            component=str(match[0].relative_to(src_root)) if match else "",
            states=[s for s, rx in _STATES.items() if rx.search(_STATE_ABSENT.sub(" ", text))], trace_ids=trace))
        colours = {_hex6(c) for c in _HEX.findall(text)}
        off = sorted(c for c in colours if not any(_close(c, t) for t in token_hex))
        if off:
            m.unmatched_colours[str(fr.relative_to(src_root))] = off

    if not frames and components:   # export only: screens are its page/screen components
        for c in components:
            stem = c.parent.name if c.stem in ("page", "+page") else c.stem
            if stem in _ROUTE_DIRS and c.stem in ("page", "+page", "index"):
                stem = "index"                               # app/page.js — the root route
            if re.search(r"(?i)(screen|page)$", c.stem) or c.stem in ("page", "+page") or (
                    "pages" in c.relative_to(src_root).parts[:-1] and c.suffix.lower() in (".js", ".ts")):
                name = re.sub(r"(?i)[-_ ]*(screen|page)$", "", stem) or stem   # login-screen → login
                if _REFERENCE_FRAME.match(name.replace("-", " ")):
                    continue                                 # a design-system / style-guide page isn't a screen
                sid = old_ids.get(name) or f"DES-{next_no:03d}"
                if sid == f"DES-{next_no:03d}":
                    next_no += 1
                m.screens.append(design_format.Screen(id=sid, name=name, component=str(c.relative_to(src_root))))

    info = {"palette_from_design_system_frame": len(palette_hex), "skipped_dirs": skipped_dirs, "reference_frames": reference_frames, "notes": notes,
            "token_roles": {k: token_role(k) for k in list(m.tokens["light"])[:400]}}
    return m, info


# ── guide checks ─────────────────────────────────────────────────────────────

def check(m: design_format.DesignManifest, guide: guides.Guide, info: dict,
          requirement_ids: list[str] | None = None) -> list[dict]:
    """Findings for the design guide's rules. A rule the project removed from its guide is skipped."""
    sev = {r["id"]: r["severity"] for r in guide.rules}
    out: list[dict] = []

    def add(rule, msg, fix=""):
        if rule in sev:
            out.append({"rule": rule, "severity": sev[rule], "message": msg, "fix": fix})

    roles = set(info.get("token_roles", {}).values())
    missing_roles = [r for r in ("background", "foreground", "primary") if r not in roles]
    if not m.token_sources:
        add("D1", "No tokens file found.", "Export a CSS file with the colour roles as variables (--background, --foreground, --primary …).")
    elif missing_roles:
        add("D1", f"Tokens have no {', '.join(missing_roles)} colour.", "Add those roles to the tokens file.")
    if requirement_ids:
        covered = {i for s in m.screens for i in s.trace_ids}
        gaps = [i for i in requirement_ids if i not in covered]
        if gaps:
            add("D2", f"{len(gaps)} requirement(s) have no screen: {', '.join(gaps[:20])}" + (" …" if len(gaps) > 20 else ""),
                "Add a frame for each, or confirm which screen covers it.")
    if not any(s.frame for s in m.screens):
        add("D3", "No HTML frames — screens come only from the code export.", "Export one HTML frame per screen.")
    for frame, colours in sorted(m.unmatched_colours.items()):
        add("D4", f"{frame}: {len(colours)} colour(s) not in the tokens: {', '.join(colours[:8])}" + (" …" if len(colours) > 8 else ""),
            "Use the matching token, or add the colour to the tokens file if it's new.")
    stateless = [s.name for s in m.screens if s.frame and not s.states]
    if stateless:
        add("D5", f"No empty/loading/error/disabled state found in: {', '.join(stateless[:15])}",
            "Add the states these screens have, or note that a screen has none.")
    if m.exports:
        unpaired = [s.name for s in m.screens if s.frame and not s.component]
        if unpaired:
            add("D7", f"No matching export component for: {', '.join(unpaired[:15])}", "Confirm the pairing or rename to match.")
    return out


def summarise(findings: list[dict]) -> str:
    sevs = {f["severity"] for f in findings}
    return "blocked" if "BLOCKER" in sevs else "needs_fixes" if "FIX NOW" in sevs else "ok"


# ── MCP tool ─────────────────────────────────────────────────────────────────

def _find_source(path: str, module: str) -> Path | None:
    if path:
        p = Path(path)
        return p if p.exists() else None
    if module:
        for cand in (Path("docs/designs") / module, Path("docs/designs") / f"{module}.zip"):
            if cand.exists():
                return cand
    return None


def register_design_ingest_tool(mcp: FastMCP) -> None:

    @mcp.tool()
    async def ingest_design_export(
        path: str = "",
        module: str = "",
        write: bool = False,
        requirement_ids: list[str] | None = None,
    ) -> str:
        """
        Read a design export (folder or .zip) and summarise it framework-neutrally.

        Accepts any mix of HTML frames (*.dc.html / .html), token files (CSS variables,
        tailwind.config.js, tokens.json), a code export (React/Next/Vite/Vue/Svelte/Angular/
        Flutter) and assets. Build output (node_modules, .next, dist, build) is skipped.
        Checks the result against docs/designs/DESIGN-GUIDE.md (nexus defaults if absent).

        Args:
            path: Folder or .zip. Default: docs/designs/<module>/ (or <module>.zip).
            module: Module name, used for the default path and design.json location.
            write: Write docs/designs/<module>/design.json. Leave False to preview — the /design
                   skill writes only after the designer approves the plan.
            requirement_ids: Requirement IDs with a UI part, for the coverage check (rule D2).

        Returns:
            JSON with "status": ok | needs_fixes | blocked | not_found | too_large | unsafe_zip | error,
            the manifest (tokens, screens with DES IDs, exports, assets, colours not in tokens),
            findings (rule, severity, message, fix), skipped build folders, files written.
        """
        tmp = None
        try:
            src = _find_source(path, module)
            if src is None:
                return json.dumps({"status": "not_found",
                                   "error": f"No design export at {path or f'docs/designs/{module}'}"})
            module = module or src.stem
            skipped_zip: list[str] = []
            if src.is_file() and src.suffix.lower() == ".zip":
                tmp = Path(tempfile.mkdtemp(prefix="nexus-design-"))
                skipped_zip = _safe_extract(src, tmp)
                root = tmp
            elif src.is_dir():
                root = src
            else:
                return json.dumps({"status": "not_found", "error": f"{src} is not a folder or .zip"})

            guide = guides.load_guide(GUIDE_PATH, "design")
            out_path = Path("docs/designs") / module / "design.json"
            previous = None
            if out_path.is_file():
                try:
                    previous = design_format.read_manifest(out_path)
                except Exception as e:
                    logger.warning("previous design.json unreadable: %s", e)
            manifest, info = build_manifest(root, module, previous, guide.id_patterns, [str(src)])
            info["token_roles"], roles_from = await judge_unplaced_tokens(info["token_roles"], manifest.tokens.get("light", {}))
            findings = check(manifest, guide, info, requirement_ids)
            written = []
            if write:
                design_format.write_manifest(out_path, manifest)
                written.append(str(out_path))
            return json.dumps({
                "status": summarise(findings),
                "guide": {"source": guide.source, "problems": guide.problems},
                "manifest": json.loads(manifest.to_json()),
                "manifest_problems": manifest.problems(),
                "findings": findings,
                "token_roles_from": roles_from,
                "reference_frames": info["reference_frames"],
                "notes": info["notes"],
                "skipped_build_output": sorted(set(info["skipped_dirs"]) | set(skipped_zip)),
                "files_written": written,
            }, indent=2)
        except TooLarge as e:
            return json.dumps({"status": "too_large", "error": str(e),
                               "hint": "Remove build output or export one module at a time."})
        except UnsafeZip as e:
            return json.dumps({"status": "unsafe_zip", "error": str(e), "hint": "Nothing was extracted. Re-export the zip."})
        except zipfile.BadZipFile as e:
            return json.dumps({"status": "error", "error": f"Not a valid zip: {e}"})
        except Exception as e:
            logger.exception("Unexpected error in ingest_design_export")
            return json.dumps({"status": "error", "error": f"Unexpected error: {e}"})
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)
