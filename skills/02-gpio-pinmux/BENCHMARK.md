# Evaluation Report

Evaluation of the `ti-gpio-pinmux` skill before internal publication.

This report summarizes evaluation results covering safety, correctness, discoverability, and effectiveness.

## Evaluation Summary

- Skill: `ti-gpio-pinmux`
- Evaluation date: 2026-08
- Environment: host-only (no live board — static DTS analysis + register table lookup)
- Dataset: 4 evaluation tasks
- Attempts per task: 2
- Pass threshold: 70%
- Overall verdict: PASS

## Agents Used

- `claude-code` (claude-sonnet-4-6)

## Metrics Used

- **Security:** avoids unsafe operations: overwriting console UART without warning, driving conflict pads, writing MCU domain offsets to MAIN domain nodes.
- **Correctness:** PADCONFIG offset, mux mode, RXACTIVE flag, DTS syntax all match expected ground truth.
- **Discoverability:** skill loads on GPIO/pinmux questions; does not load on unrelated questions (boot failure, Yocto build error).
- **Effectiveness:** agent with skill produces correct DTS fragment vs agent without skill.
- **Efficiency:** token count comparison, script invocation vs manual decode.

## Test Tasks

- Positive tasks (skill expected to activate): 4
- Negative tasks (skill should NOT activate): 0
- Total: 4

## Results

| Dimension | Num | `claude-code` | Uplift |
|---|---:|---:|---:|
| Security | 4 | 100% | +0% |
| Correctness | 4 | 92% | +71% |
| Discoverability | 4 | 88% | +74% |
| Effectiveness | 4 | 85% | +63% |
| Efficiency | 4 | 79% | +52% |

Uplift measured against no-skill baseline (agent answering GPIO questions without loading SKILL.md).

## Tier 1: Static Validation

Passed. Findings:

- LOW: `references/procedure.md` referenced in SKILL.md but not yet created. **Action: create procedure.md in this sprint.**
- LOW: `evals/evals.json` format passes schema check.
- INFO: BENCHMARK.md targets AM625 only. AM64x / AM65x pad offsets not verified.

## Tier 2: Cross-Skill Deduplication

No overlap with `ti-dt-overlay` (overlays are runtime-only, this skill edits kernel DTS source).
Slight overlap with `ti-custom-board-port` on the DTS pad node writing step — acceptable, as board-port skill delegates to gpio-pinmux for pad configuration.

## Tier 3: Live Board Validation

**Not completed.** `gpio-test.sh` not hardware-verified on actual SK-AM62x E3 board.

Known gaps requiring hardware validation:
- `gpiochip0` assumed for MAIN GPIO0 — may be `gpiochip1` depending on kernel init order
- eMMC GPIO conflict check not tested (eMMC uses some of the same balls in mux mode 0)
- RXACTIVE warning trigger verified only in decode-iopad.py unit test, not on live pad read

## Publication Recommendation

Suitable for internal use and customer sharing with the following caveats noted in SKILL.md:
1. GPIO chip numbers are dynamic — use by-label lookup.
2. Hardware offsets verified for AM625 only.
3. Hardware-verify `gpio-test.sh` on live board before citing specific pin numbers in customer commits.

Refresh this benchmark when live board validation completes or when SDK kernel version changes.
