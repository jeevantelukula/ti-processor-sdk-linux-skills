#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Copy shared files into every skill that uses them, so each skills/<name>/ is self-contained.

A skill directory must work on its own (copied alone into ~/.claude/skills/, or used from this
repo): it may not reach into lib/, context/, templates/ or another skill. Files several skills
need have ONE source, listed in SHARED below; this script writes the copies.

  python3 tools/sync-shared.py           write/refresh all copies
  python3 tools/sync-shared.py --check   exit 1 if any copy is missing, stale or orphaned (CI)

Edit the source, never a copy: each copy carries a "GENERATED COPY" marker naming its source.
"""
import os, pathlib, stat, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SKILLS = sorted(p.name for p in (ROOT / "skills").iterdir() if (p / "SKILL.md").is_file())
MARK = "GENERATED COPY of {src} by tools/sync-shared.py: edit the source, then run python3 tools/sync-shared.py"

# source (repo-relative) -> list of destinations (repo-relative)
SHARED = {
    # every skill uses SDK values ($TI_DOCS_DEVICE at least) and the docs MCP rules
    "lib/ti-sdk-env.sh": [f"skills/{s}/scripts/ti-sdk-env.sh" for s in SKILLS],
    "context/mcp-usage.md": [f"skills/{s}/references/mcp-usage.md" for s in SKILLS],
    "templates/target-profile.yaml": [f"skills/{s}/assets/target-profile.yaml" for s in ("ti-sdk-quick-start", "ti-sdk-setup")],
    "lib/gen-sdk-facts.py": ["skills/ti-generate-kb/scripts/gen-sdk-facts.py"],
    # scripts owned by one skill and used by others
    "skills/ti-remoteproc/scripts/dt-cores.sh": ["skills/ti-pru/scripts/dt-cores.sh"],
    "skills/ti-remoteproc/scripts/rproc.sh": ["skills/ti-pru/scripts/rproc.sh"],
    "skills/ti-device-tree-overlay/scripts/build-dtbo.sh": [
        f"skills/{s}/scripts/build-dtbo.sh" for s in ("ti-customize-clocks", "ti-custom-board-port", "ti-gpio-pinmux")],
}


def render(src: str) -> str:
    """Source text with the marker inserted after any shebang/shellcheck/SPDX header lines."""
    text = (ROOT / src).read_text()
    mark = MARK.format(src=src)
    if src.endswith(".md"):
        return f"<!-- {mark} -->\n{text}"
    lines = text.splitlines(keepends=True)
    i = 0
    while i < len(lines) and (lines[i].startswith("#!") or lines[i].startswith("# shellcheck")
                              or lines[i].startswith("# SPDX")):
        i += 1
    return "".join(lines[:i]) + f"# {mark}\n" + "".join(lines[i:])


def main() -> int:
    check = "--check" in sys.argv[1:]
    problems, wanted = [], set()
    for src, dests in SHARED.items():
        body = render(src)
        mode = (ROOT / src).stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        for d in dests:
            wanted.add(d)
            p = ROOT / d
            if p.is_file() and p.read_text() == body and (p.stat().st_mode & stat.S_IXUSR) == (mode & stat.S_IXUSR):
                continue
            if check:
                problems.append(f"{d}: {'stale' if p.exists() else 'missing'} copy of {src}")
                continue
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(body)
            p.chmod((p.stat().st_mode & ~0o111) | mode)
            print(f"wrote {d}")
    # a file carrying the marker that the table no longer lists is an orphan
    for p in (ROOT / "skills").rglob("*"):
        if p.is_file() and str(p.relative_to(ROOT)) not in wanted:
            head = p.read_text(errors="replace")[:600] if p.stat().st_size < 2_000_000 else ""
            if "GENERATED COPY of " in head and "tools/sync-shared.py" in head:
                problems.append(f"{p.relative_to(ROOT)}: orphaned generated copy (remove it or list it in SHARED)")
    for m in problems:
        print(m, file=sys.stderr)
    if problems and check:
        print("run: python3 tools/sync-shared.py", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
