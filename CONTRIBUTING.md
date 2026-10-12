# Contributing

- Every factual claim must be traceable to the SDK, a live board, or a TI docs page. Cite it
  (file:line or doc path) in skill references.
- Skills are device-agnostic: no SoC, board, file, thermal-zone or OPP names in instructions. Read them
  from the SDK at run time or from the generated KB (`$TI_KB`). An illustrative value is allowed only on a
  line containing `example` or `e.g.`, or in a fenced block introduced by an `(example` line, and should say
  which SDK it came from. `check_repo.py` warns on other hits.
- A skill is `skills/ti-<topic>/SKILL.md` (< 200 lines, `name` equals directory) plus optional
  `references/` and `scripts/`. Each SKILL.md has: Docs (MCP), Prerequisites, Steps, Verify, Troubleshooting.
- Scripts: `set -euo pipefail` (read-only probe scripts may omit `-e` with a comment saying why),
  `bash -n` and `shellcheck` clean, referenced by a SKILL.md, no hardcoded devices.
- Do not add benchmark or eval claims unless results are reproducible and checked in.
- When an SDK release changes a fact, regenerate the KB (`ti-generate-kb`); do not hand-edit generated facts.
- Before a PR: `python3 .github/scripts/check_repo.py`.
