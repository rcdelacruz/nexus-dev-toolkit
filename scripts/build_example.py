"""
Regenerate the generated parts of examples/clinic-appointments with nexus's own tools, so they are
never hand-edited and can't drift from what nexus would produce.

    python3 scripts/build_example.py           # write them
    python3 scripts/build_example.py --check   # regenerate into a temp copy; exit 1 if anything differs

Generated:
  - the guides and BRD/PRD templates, exactly as `nexus init` writes them
  - docs/designs/careslot/design.json            (ingest_design_export)
  - TRACE_IDS in docs/dev-tasks/careslot/*.csv   (trace_tasks)
  - docs/change-requests/CR-001.json                 (record_change_request, from a real git diff:
    the docs as they were before CR-001 are committed in a temporary repo, then the current docs
    are put back and diffed)
Hand-written: the BRD, PRD, architecture doc + ADRs, design frames/tokens/export, task rows.
"""

import argparse
import filecmp
import re
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.epav import change_request as crm  # noqa: E402
from tools.epav import design_ingest  # noqa: E402
from tools.epav.formats import cr as cr_format  # noqa: E402
from tools.epav.formats import design as design_format  # noqa: E402
from tools.epav.formats import ids, tasks  # noqa: E402

EXAMPLE = ROOT / "examples" / "clinic-appointments"
PACK = ROOT / "examples" / "careslot-client-pack"
PACK_ZIP = ROOT / "public" / "careslot-client-pack.zip"
_SKIP_NAMES = ("__pycache__", ".ruff_cache", ".DS_Store", "node_modules", ".venv", "db.sqlite3", "graphify-out")
_COPY_SKIP = shutil.ignore_patterns("__pycache__", ".ruff_cache", ".DS_Store", "node_modules", ".venv", "db.sqlite3", "graphify-out")
MODULE = "careslot"
TEMPLATES = {  # same mapping as nexus_cli._GUIDES (minus CODEOWNERS), plus .graphifyignore
    "docs/requirements/REQUIREMENTS-GUIDE.md": "REQUIREMENTS-GUIDE.md",
    "docs/arch-docs/ARCHITECTURE-GUIDE.md": "ARCHITECTURE-GUIDE.md",
    "docs/designs/DESIGN-GUIDE.md": "DESIGN-GUIDE.md",
    "docs/requirements/templates/BRD-TEMPLATE.md": "BRD-TEMPLATE.md",
    "docs/requirements/templates/PRD-TEMPLATE.md": "PRD-TEMPLATE.md",
    ".graphifyignore": "graphifyignore",  # what nexus init writes for graph users (nexus_cli._write_ignores)
}
CR = {"id": "CR-001", "title": "SMS reminder 2 hours before (was 24); cancellation reason required",
      "date": "2026-11-30",
      "reason": "Clinic manager: 24-hour reminders were forgotten by the next day; no-show reasons are needed for the monthly report."}

# The docs as they were before CR-001: (file, text now, text before).
BEFORE_CR_001 = [
    ("docs/requirements/PRD.md", "| Version | 1.1 |", "| Version | 1.0 |"),
    ("docs/requirements/PRD.md", "| Date | 2026-11-30 |", "| Date | 2026-11-23 |"),
    ("docs/requirements/PRD.md",
     "made up.\n     v1.1 includes change request CR-001 (see docs/change-requests/CR-001.json). -->", "made up. -->"),
    ("docs/requirements/PRD.md",
     '- AC-015 A cancellation reason must be chosen before cancelling ("Reason is required"). *(added by CR-001)*\n', ""),
    ("docs/requirements/PRD.md",
     "| FR-BOOK-004 | A cancellation reason (from a fixed list) is required to cancel; reasons are reported monthly. *(added by CR-001)* | BR-005 | US-005 |\n", ""),
    ("docs/requirements/PRD.md",
     "An SMS reminder is sent 2 hours before each appointment. *(changed by CR-001: was 24 hours)*",
     "An SMS reminder is sent 24 hours before each appointment."),
    ("docs/requirements/PRD.md", "D -. 2 h before .->", "D -. 24 h before .->"),
    ("docs/requirements/PRD.md",
     "| 2 | Since CR-001 the reminder arrives 2 hours before the visit — exactly when online cancelling closes (BR-005), "
     "so the SMS can't offer a working cancel link. Move the cut-off, send the reminder earlier, or make the SMS link "
     "call the front desk? *(raised by CR-001)* | Clinic manager | Before the reminder task ships |\n", ""),
    ("docs/requirements/PRD.md", "FR-BOOK-001 – FR-BOOK-004,", "FR-BOOK-001 – FR-BOOK-003,"),
    ("docs/arch-docs/careslot/ARCH-CARESLOT-v1.0.md", "| Version | 1.0 (updated for CR-001 on 2026-11-30) |", "| Version | 1.0 |"),
    ("docs/arch-docs/careslot/ARCH-CARESLOT-v1.0.md", "Book, cancel (with reason),", "Book, cancel,"),
    ("docs/arch-docs/careslot/ARCH-CARESLOT-v1.0.md", "FR-BOOK-002, FR-BOOK-003, FR-BOOK-004 |", "FR-BOOK-002, FR-BOOK-003 |"),
    ("docs/arch-docs/careslot/ARCH-CARESLOT-v1.0.md", "starts_at, status, cancel_reason |", "starts_at, status |"),
    ("docs/arch-docs/careslot/ARCH-CARESLOT-v1.0.md",
     "; cancel_reason required when status = cancelled — FR-BOOK-004", ""),
    ("docs/arch-docs/careslot/ADR-CARESLOT-E003-Notifications-v1.0.md",
     "Accepted (updated by CR-001: reminder moved from 24 h to 2 h before the appointment)", "Accepted"),
    ("docs/arch-docs/careslot/ADR-CARESLOT-E001-Booking-v1.0.md", "FR-BOOK-003, FR-BOOK-004\n", "FR-BOOK-003\n"),
    ("docs/designs/careslot/Frame - My Appointments.dc.html", "US-006, FR-BOOK-004, FR-NOTIF-001", "US-006, FR-NOTIF-001"),
    ("docs/designs/careslot/Frame - My Appointments.dc.html", "Reminder by SMS 2 hours before", "Reminder by SMS 24 hours before"),
    ("docs/designs/careslot/Frame - My Appointments.dc.html",
     "    <label>Reason for cancelling<select><option>Feeling better</option><option>Can't make it</option>"
     "<option>Booked elsewhere</option></select></label>\n    <p class=\"err\">Reason is required</p>\n", ""),
]


@contextmanager
def _cwd(path: Path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


def build_templates(root: Path) -> None:
    for rel, name in TEMPLATES.items():
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "tools" / "templates" / name, dst)


def build_design(root: Path) -> design_format.DesignManifest:
    src = root / "docs" / "designs" / MODULE
    out = src / "design.json"
    previous = design_format.read_manifest(out) if out.is_file() else None
    manifest, _ = design_ingest.build_manifest(src, MODULE, previous, sources=[f"docs/designs/{MODULE}"])
    design_format.write_manifest(out, manifest)
    return manifest


def build_traces(root: Path) -> None:
    for f in sorted((root / "docs" / "dev-tasks" / MODULE).glob("*.csv")):
        tf = tasks.read_tasks(f)
        proposal = {p["task_id"]: p["proposed"] for p in crm.propose_trace_ids(f)}
        for r in tf.rows:
            r["trace_ids"] = ids.format_id_list(proposal.get(r.get("task_id", ""), []))
        tasks.write_tasks(f, tf.rows, tf.extra_columns)


def _git(cwd: Path, *args: str) -> None:
    env = dict(os.environ, GIT_AUTHOR_NAME="nexus example", GIT_AUTHOR_EMAIL="example@invalid",
               GIT_COMMITTER_NAME="nexus example", GIT_COMMITTER_EMAIL="example@invalid")
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, env=env)


def before_cr_docs(root: Path, repo: Path) -> None:
    """repo/docs = root's docs as they were before CR-001 (no change-requests, no dev tasks re-planned)."""
    shutil.copytree(root / "docs", repo / "docs", ignore=shutil.ignore_patterns("change-requests", *_SKIP_NAMES))
    for rel, now, before in BEFORE_CR_001:
        p = repo / rel
        text = p.read_text(encoding="utf-8")
        if text.count(now) != 1:
            raise SystemExit(f"build_example: expected exactly one {now[:60]!r} in {rel} — update BEFORE_CR_001")
        p.write_text(text.replace(now, before), encoding="utf-8")
    (repo / "docs" / "designs" / MODULE / "design.json").unlink()   # the importer keeps confirmed links
    build_design(repo)                                   # design.json as it was before CR-001


def build_cr(root: Path) -> cr_format.ChangeRequest:
    with tempfile.TemporaryDirectory(prefix="nexus-example-cr-") as tmp:
        repo = Path(tmp)
        before_cr_docs(root, repo)
        _git(repo, "init", "-q")
        _git(repo, "add", "-A")
        _git(repo, "commit", "-q", "-m", "before CR-001")
        shutil.rmtree(repo / "docs")
        shutil.copytree(root / "docs", repo / "docs", ignore=shutil.ignore_patterns("change-requests"))
        with _cwd(repo):
            d = crm.diff_ids("HEAD")
    record = cr_format.ChangeRequest(CR["id"], CR["title"], CR["date"], changed_ids=d["changed"], added_ids=d["added"],
                                     removed_ids=d["removed"], files=d["files"], reason=CR["reason"])
    cr_format.write_cr(root / "docs" / "change-requests" / f"{CR['id']}.json", record)
    return record


def build(root: Path) -> None:
    build_templates(root)
    build_design(root)
    build_traces(root)
    build_cr(root)


def build_pack(example: Path, pack: Path) -> None:
    """The client pack's design system is the example's (one source)."""
    dst = pack / "design-system"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(example / "docs" / "designs" / "design-system", dst, ignore=_COPY_SKIP)


def _pack_target(rel: Path) -> str:
    """Where a pack file lands in the project: the zip is unzipped in the repository root, so its
    paths are the project's (notes → docs/requirements/sources/, design system → docs/designs/)."""
    if rel.parts[0] == "design-system":
        return Path("docs/designs", *rel.parts).as_posix()
    return Path("docs/requirements/sources", *rel.parts).as_posix()


def pack_zip_bytes(pack: Path) -> bytes:
    """careslot-client-pack.zip — what the team receives on day one (no later/), byte-for-byte
    reproducible (sorted entries, fixed timestamps). Unzipped in the repository root."""
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(p for p in pack.rglob("*") if p.is_file() and p.name != ".DS_Store"
                        and "later" not in p.relative_to(pack).parts):     # the CR email arrives later
            info = zipfile.ZipInfo(_pack_target(f.relative_to(pack)), date_time=(2026, 11, 23, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            z.writestr(info, f.read_bytes())
    return buf.getvalue()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="regenerate into a temp copy and compare")
    args = ap.parse_args(argv)
    if not args.check:
        build(EXAMPLE)
        build_pack(EXAMPLE, PACK)
        PACK_ZIP.write_bytes(pack_zip_bytes(PACK))
        print(f"rebuilt generated parts of {EXAMPLE.relative_to(ROOT)}, {PACK.relative_to(ROOT)} and {PACK_ZIP.relative_to(ROOT)}")
        return 0

    def tree_diff(built: Path, committed: Path) -> list[str]:
        files = lambda d: {p.relative_to(d) for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts  # noqa: E731
                           and p.name not in (".DS_Store", "db.sqlite3") and ".ruff_cache" not in p.parts and "graphify-out" not in p.parts}
        a, b = files(built), files(committed)
        changed = [str(r) for r in sorted(a & b) if not filecmp.cmp(built / r, committed / r, shallow=False)]
        return changed + [f"(missing) {r}" for r in sorted(a - b)] + [f"(extra) {r}" for r in sorted(b - a)]

    with tempfile.TemporaryDirectory(prefix="nexus-example-check-") as tmp:
        copy, pack = Path(tmp) / "example", Path(tmp) / "pack"
        shutil.copytree(EXAMPLE, copy, ignore=_COPY_SKIP)
        build(copy)
        shutil.copytree(PACK, pack, ignore=_COPY_SKIP)
        build_pack(copy, pack)
        diffs = tree_diff(copy, EXAMPLE) + [f"client-pack/{d}" for d in tree_diff(pack, PACK)]
        new = [] if PACK_ZIP.is_file() and PACK_ZIP.read_bytes() == pack_zip_bytes(pack) else [str(PACK_ZIP.relative_to(ROOT))]
    if diffs or new:
        print("example out of date — run python3 scripts/build_example.py:\n  " + "\n  ".join(diffs + new), file=sys.stderr)
        return 1
    print("example up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
