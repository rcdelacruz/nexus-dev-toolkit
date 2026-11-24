"""
Build the changelog page and the "What's new" blocks from the CHANGELOG files.

    python3 scripts/build_changelog.py

Writes:
  - public/changelog.html: one tab per package (nexus-dev-toolkit, nexus-jev)
  - public/docs.html: the "What's new" block for nexus (#whats-new) and for jev
    (inside #jev), between <!-- whats-new:<product>:start/end --> markers

Sources:
  - nexus: CHANGELOG.md on this checkout
  - jev:   only the "## [jev X.Y.Z]" entries of CHANGELOG.md on the
           experimental-jev branch, read with `git show origin/experimental-jev:CHANGELOG.md`
           (or --jev-file PATH). If neither is available, the jev blocks already in
           the files are kept as they are and a warning is printed.

Run it after every CHANGELOG change, for either package (see CLAUDE.md).
tests/test_changelog_page.py fails when the nexus parts are out of date.
Standard library only.
"""

import argparse
import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = Path(__file__).resolve().parent / "changelog_template.html"
CHANGELOG_PAGE = ROOT / "public" / "changelog.html"
DOCS_PAGE = ROOT / "public" / "docs.html"
JEV_REF = "origin/experimental-jev"
V4_REF = "origin/v4"

_PRE = re.compile(r"\d(a|b|rc|dev)\d+$")
_HEADER = re.compile(r"^## \[(?P<label>[^\]]+)\](?:\s*-\s*(?P<date>\S+))?\s*$")
NAV_RELEASES = 6         # releases linked from the sidebar per product
WHATS_NEW_MAX = 6        # highlights shown in a What's new block


# ── markdown subset → HTML ──────────────────────────────────────────────────

def _inline(text: str) -> str:
    """Escape, then render `code`, **bold** and [text](url). Code spans are left untouched; bold may
    span code (**`/create-pr` does X**)."""
    codes: list[str] = []

    def stash(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"
    s = re.sub(r"`([^`]*)`", stash, text)
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)",
               lambda m: f'<a href="{html.escape(m.group(2))}" target="_blank">{m.group(1)}</a>', s)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)


def _render_body(lines: list[str], indent: str = "      ") -> str:
    """Render one release body: ### headings, paragraphs, '- ' bullets with '  - ' sub-bullets."""
    html_lines: list[str] = []
    items: list[list] = []      # [text, [subitems]]
    para: list[str] = []

    def flush_para():
        if para:
            html_lines.append(f"{indent}<p>{_inline(' '.join(para))}</p>")
            para.clear()

    def flush_list():
        if not items:
            return
        html_lines.append(f"{indent}<ul>")
        for text, subs in items:
            if subs:
                inner = "".join(f"<li>{_inline(s)}</li>" for s in subs)
                html_lines.append(f"{indent}  <li>{_inline(text)}<ul>{inner}</ul></li>")
            else:
                html_lines.append(f"{indent}  <li>{_inline(text)}</li>")
        html_lines.append(f"{indent}</ul>")
        items.clear()

    for raw in lines:
        line = raw.rstrip()
        if not line.strip() or line.strip() == "---":
            flush_para()
            continue
        if line.startswith("### "):
            flush_para(); flush_list()
            html_lines.append(f"{indent}<h3>{_inline(line[4:].strip())}</h3>")
        elif re.match(r"^\s{2,}- ", line) and items:
            items[-1][1].append(line.strip()[2:])
        elif line.startswith("- "):
            flush_para()
            items.append([line[2:].strip(), []])
        elif re.match(r"^\s+\S", line) and items:
            # continuation of the previous bullet (or sub-bullet)
            target = items[-1][1] if items[-1][1] else None
            if target is not None:
                target[-1] += " " + line.strip()
            else:
                items[-1][0] += " " + line.strip()
        else:
            flush_list()
            para.append(line.strip())
    flush_para(); flush_list()
    return "\n".join(html_lines)


# ── changelog parsing ───────────────────────────────────────────────────────

def parse(text: str, prefix: str = "", include_pre: bool = False) -> list[dict]:
    """Releases in file order. With prefix="jev ", only "## [jev X]" entries (prefix stripped).
    Pre-releases (4.0.0a1, b1, rc1) are left out unless include_pre=True."""
    releases: list[dict] = []
    current = None
    for line in text.splitlines():
        m = _HEADER.match(line)
        if m:
            label = m.group("label")
            current = None
            if label.lower() == "unreleased":
                continue
            if prefix:
                if not label.startswith(prefix):
                    continue
                label = label[len(prefix):]
            elif label.startswith("jev "):
                continue
            elif not include_pre and _PRE.search(label):
                continue  # 4.0.0a1 etc. live on the v4 branch; the site's stable tab lists releases only
            current = {"version": label, "date": m.group("date") or "", "lines": []}
            releases.append(current)
        elif current is not None:
            current["lines"].append(line)
    return releases


def _anchor(product: str, version: str) -> str:
    return f"{product}-{version}"


def render_releases(releases: list[dict], product: str) -> str:
    blocks = []
    for r in releases:
        date = f'<span class="release-date">{html.escape(r["date"])}</span>' if r["date"] else ""
        blocks.append(f'      <h2 id="{_anchor(product, r["version"])}">v{html.escape(r["version"])}{date}</h2>\n'
                      + _render_body(r["lines"]))
    return "\n\n".join(blocks)


def render_nav(releases: list[dict], product: str) -> str:
    links = [f'    <a href="#{_anchor(product, r["version"])}" class="sub" onclick="showTab(\'{product}\')">'
             f'→ v{html.escape(r["version"])}</a>' for r in releases[:NAV_RELEASES]]
    return "\n".join(links)


def _highlight(bullet: str) -> str:
    """Short form of a changelog bullet: its lead-in before ': ' (when that is a real phrase),
    else its first sentence, capped at 180 characters on a word boundary."""
    colon = re.search(r":\s", bullet)
    if colon and colon.start() >= 25:
        return bullet[: colon.start()]
    sentence = re.search(r"\.\s", bullet)
    short = bullet[: sentence.start() + 1] if sentence else bullet
    if len(short) > 180:
        short = short[:177].rsplit(" ", 1)[0] + "…"
    return short


def render_whats_new(release: dict, product: str, indent: str = "    ") -> str:
    """Highlights of one release: each top-level bullet, shortened, grouped by its ### heading."""
    groups: list[tuple[str, list[str]]] = []
    for line in release["lines"]:
        if line.startswith("### "):
            groups.append((line[4:].strip(), []))
        elif line.startswith("- ") and groups:
            groups[-1][1].append(_highlight(line[2:].strip()))
    shown, out = 0, []
    for heading, bullets in groups:
        bullets = bullets[: max(0, WHATS_NEW_MAX - shown)]
        if not bullets:
            continue
        shown += len(bullets)
        out.append(f"{indent}<p><strong>{_inline(heading)}</strong></p>")
        out.append(f"{indent}<ul>")
        out += [f"{indent}  <li>{_inline(b)}</li>" for b in bullets]
        out.append(f"{indent}</ul>")
    link = f'/changelog#{_anchor(product, release["version"])}'
    date = f" ({html.escape(release['date'])})" if release["date"] else ""
    head = f'{indent}<p class="whats-new-title"><strong>v{html.escape(release["version"])}</strong>{date}</p>'
    tail = f'{indent}<p><a href="{link}">Full {html.escape(release["version"])} notes →</a> · <a href="/changelog{"#jev" if product == "jev" else ""}">all releases</a></p>'
    return "\n".join([head, *out, tail])


# ── file assembly ───────────────────────────────────────────────────────────

def _between(text: str, name: str) -> str | None:
    m = re.search(rf"<!-- {name}:start -->\n(.*?)\n?<!-- {name}:end -->", text, re.S)
    return m.group(1) if m else None


def _replace_between(text: str, name: str, body: str) -> str:
    pattern = re.compile(rf"(<!-- {name}:start -->\n).*?(\n?<!-- {name}:end -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"marker <!-- {name}:start/end --> not found")
    return pattern.sub(lambda m: m.group(1) + body + "\n" + m.group(2).lstrip("\n"), text, count=1)


def _read_jev_changelog(path: str | None) -> str | None:
    if path:
        return Path(path).read_text(encoding="utf-8")
    try:
        return subprocess.run(["git", "-C", str(ROOT), "show", f"{JEV_REF}:CHANGELOG.md"],
                              capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _current_version() -> str:
    """The version the site shows: pyproject's, or — on the pre-release branch — the newest
    stable release in CHANGELOG.md (the site is deployed from main and shows stable)."""
    m = re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(), re.M)
    v = m.group(1) if m else ""
    if _PRE.search(v):
        stable = parse((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
        return stable[0]["version"] if stable else v
    return v


def _v4_releases() -> tuple[list[dict], str]:
    """Pre-release entries (4.0.0a1 …) for the "v4 preview" tab: from this checkout's CHANGELOG.md
    when it is the pre-release branch, otherwise from origin/v4. ([], source) when unavailable."""
    local = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    pre = [r for r in parse(local, include_pre=True) if _PRE.search(r["version"])]
    if pre:
        return pre, "CHANGELOG.md"
    try:
        text = subprocess.run(["git", "-C", str(ROOT), "show", f"{V4_REF}:CHANGELOG.md"],
                              capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [], ""
    return [r for r in parse(text, include_pre=True) if _PRE.search(r["version"])], V4_REF


def build_page(nexus: list[dict], jev_html: str, jev_nav: str, v4_html: str = "", v4_nav: str = "") -> str:
    page = TEMPLATE.read_text(encoding="utf-8")
    for key, value in {"{{VERSION}}": _current_version(),
                       "{{V4_NAV}}": v4_nav,
                       "{{V4}}": v4_html,
                       "{{NEXUS_NAV}}": render_nav(nexus, "nexus"),
                       "{{JEV_NAV}}": jev_nav,
                       "{{NEXUS}}": render_releases(nexus, "nexus"),
                       "{{JEV}}": jev_html}.items():
        page = page.replace(key, value)
    return page


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--jev-file", help="path to the jev CHANGELOG.md (default: git show origin/experimental-jev:CHANGELOG.md)")
    args = ap.parse_args(argv)

    nexus = parse((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    if not nexus:
        raise SystemExit("no releases found in CHANGELOG.md")

    jev_text = _read_jev_changelog(args.jev_file)
    jev = parse(jev_text, prefix="jev ") if jev_text else []
    old_page = CHANGELOG_PAGE.read_text(encoding="utf-8") if CHANGELOG_PAGE.exists() else ""
    if jev:
        jev_html, jev_nav = render_releases(jev, "jev"), render_nav(jev, "jev")
    else:
        print(f"warning: jev changelog not readable ({JEV_REF}); keeping the jev blocks already published",
              file=sys.stderr)
        jev_html = _between(old_page, "changelog:jev") or ""
        nav = re.search(r"(?m)^    <a href=\"#jev\".*\n((?:    <a href=\"#jev-.*\n)*)", old_page)
        jev_nav = nav.group(1).rstrip("\n") if nav else ""

    v4, v4_src = _v4_releases()
    if v4:
        v4_html, v4_nav = render_releases(v4, "v4"), render_nav(v4, "v4")
    else:
        v4_html = _between(old_page, "changelog:v4") or '      <p>No v4 pre-release yet.</p>'
        nav = re.search(r"(?m)^    <a href=\"#v4\".*\n((?:    <a href=\"#v4-.*\n)*)", old_page)
        v4_nav = nav.group(1).rstrip("\n") if nav else ""

    CHANGELOG_PAGE.write_text(build_page(nexus, jev_html, jev_nav, v4_html, v4_nav), encoding="utf-8")

    docs = DOCS_PAGE.read_text(encoding="utf-8")
    docs = _replace_between(docs, "whats-new:nexus", render_whats_new(nexus[0], "nexus"))
    if jev:
        docs = _replace_between(docs, "whats-new:jev", render_whats_new(jev[0], "jev"))
    DOCS_PAGE.write_text(docs, encoding="utf-8")

    print(f"changelog.html: {len(nexus)} nexus releases, {len(jev) if jev else 'kept'} jev releases, "
          f"{len(v4) if v4 else 'kept'} v4 pre-releases; "
          f"docs.html What's new: nexus v{nexus[0]['version']}" + (f", jev v{jev[0]['version']}" if jev else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
