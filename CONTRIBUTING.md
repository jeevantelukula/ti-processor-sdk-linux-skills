# Contributing

- Every factual claim must be traceable to the SDK, a live board, or a TI docs page. Cite it
  (file:line or doc path) in skill references.
- Skills are device-agnostic: no SoC, board, file, thermal-zone or OPP names in instructions. Read them
  from the SDK at run time or from the generated KB (`$TI_KB`). An illustrative value is allowed only on a
  line containing `example` or `e.g.`, or in a fenced block introduced by an `(example` line, and should say
  which SDK it came from. `check_repo.py` warns on other hits.
- A skill is `skills/ti-<topic>/SKILL.md` (< 200 lines, `name` equals directory) plus optional
  `references/`, `scripts/` and `assets/`. Each SKILL.md has: Docs (MCP), Prerequisites, Steps, Verify, Troubleshooting.
- Skills are self-contained: a skill directory must work when copied alone into `~/.claude/skills/`.
  Paths in a skill are relative to its directory; never point into `lib/`, `context/`, `templates/`,
  the installed `.claude/` layout or another skill (naming another skill for routing is fine).
- Shared files have one source (`lib/ti-sdk-env.sh`, `lib/gen-sdk-facts.py`, `context/mcp-usage.md`,
  `templates/target-profile.yaml`, and scripts one skill owns and others use). Edit the source, then run
  `python3 tools/sync-shared.py`; never edit a file marked `GENERATED COPY`. To share a new file, add it
  to `SHARED` in that script. `check_repo.py` fails on stale copies and on paths leaving a skill.
- Scripts that need SDK values load the skill's `scripts/ti-sdk-env.sh` themselves when `TI_*` is unset:
  an agent's shell variables do not persist from one command to the next.
- Scripts: `set -euo pipefail` (read-only probe scripts may omit `-e` with a comment saying why),
  `bash -n` and `shellcheck` clean, referenced by a SKILL.md, no hardcoded devices.
- Do not add benchmark or eval claims unless results are reproducible and checked in.
- When an SDK release changes a fact, regenerate the KB (`ti-generate-kb`); do not hand-edit generated facts.
- Before a PR: `python3 .github/scripts/check_repo.py`.
