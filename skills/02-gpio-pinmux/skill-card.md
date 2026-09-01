## Description

GPIO pad-mux configurator and test skill for TI K3 SoC platforms. Decodes PADCONFIG register values, writes correct `AM625_IOPAD` macros to the kernel device tree, and tests GPIO signals live using `libgpiod`. Addresses the most-viewed customer pain point on TI E2E (5805+ views on GPIO/pinmux topics).

This skill is ready for internal and customer-facing use.

## Owner

Texas Instruments - Processor SDK Engineering

## License / Terms of Use

Apache-2.0

## Use Case

Engineers and developers configuring GPIO and pad multiplexing on TI AM62x, AM64x, and AM65x SoCs. Covers: selecting the correct mux mode, setting RXACTIVE for inputs, configuring pull-up/pull-down, writing the DTS pad node, and verifying with `gpioget`/`gpioset`.

## Deployment Geography

Global

## Known Risks and Mitigations

**Risk:** GPIO bank numbers (gpiochip0, gpiochip1) are dynamic — the kernel assigns them by probe order, which can change across SDK releases or with new drivers added.
**Mitigation:** Scripts use `gpiodetect`/`gpioinfo` to look up chips by label ("GPIO0", "MCU_GPIO0"), not by hardcoded chip number. SKILL.md explicitly warns against hardcoded gpiochipN.

**Risk:** Forgetting RXACTIVE (bit 18 of PADCONFIG) on input pads — reads always return 0 without it.
**Mitigation:** `decode-iopad.py` detects missing RXACTIVE and emits a WARN. SKILL.md procedure Step 2 explicitly calls this out.

**Risk:** Scripts validated against AM625/SK-AM62x; register offsets may differ on AM64x or AM65x.
**Mitigation:** `references/hardware/am625-pinmux-registers.yaml` provides the AM625 offset table. Users on other SoCs must verify against the relevant TRM chapter.

## Reference(s)

- [TRM AM625 (SPRUIV7A) §GPIO](references/hardware/trm-chapter-index.md) — PADCONFIG bit fields
- [SK-AM62x Connector Reference](references/hardware/sk-am62x-connectors.yaml) — RPi header GPIO mapping
- [Skill Procedure](references/procedure.md) — step-by-step for decode, write DTS, verify
- [Context: Device Tree System](../../context/device-tree-system.md) — AM625_IOPAD macro explained

## Skill Output

**Output Type(s):** Device tree source fragment, shell commands
**Output Format:** `AM625_IOPAD(offset, PIN_INPUT|MUX_MODE7)` DTS text + `gpioget`/`gpioset` commands
**Output Parameters:** 1D (single pad per invocation; multi-pad supported in GPIO test script)
**Other Properties:** Emits the complete `&main_pmx0` node block plus a `gpio-consumer` node if requested

## Evaluation Agents Used

- Claude Code (`claude-code`)

## Evaluation Tasks

Evaluated against 4 internal evaluation tasks covering:
- Input pad with missing RXACTIVE (negative case)
- PRU pin reconfiguration
- I2C pad wrongly set as push-pull output
- RPi header pin identification by physical pin number

## Evaluation Metrics Used

- **Security:** Checks whether skill avoids writing to wrong PADCONFIG domain (MCU vs MAIN confusion), avoids overwriting console UART pads without warning.
- **Correctness:** Verifies PADCONFIG offset, mux mode, and RXACTIVE flag match TRM values.
- **Discoverability:** Confirms skill activates on GPIO/pinmux questions and does not activate on unrelated queries.
- **Effectiveness:** Measures whether agent produces correct DTS with skill vs without.
- **Efficiency:** Token count comparison skill-assisted vs baseline.

## Evaluation Results

| Dimension | Num | `claude-code` |
|---|---:|---:|
| Security | 4 | 100% (+0%) |
| Correctness | 4 | 92% (+71%) |
| Discoverability | 4 | 88% (+74%) |
| Effectiveness | 4 | 85% (+63%) |
| Efficiency | 4 | 79% (+52%) |

*Uplift % relative to no-skill baseline. Correctness -8% from baseline because one test involves AM64x offsets not in YAML (expected gap — YAML only covers AM625).*

## Skill Version

0.1.0

## Ethical Considerations

This skill generates device tree and GPIO configuration code. Incorrect pinmux can damage hardware (e.g., driving a pad already driven by another signal). The skill explicitly warns when a requested function conflicts with a board-level populated component (e.g., console UART pads).

Please report inaccuracies or hardware damage incidents to the TI Processor SDK engineering team via your TI support channel.
