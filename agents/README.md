# TI SDK Agents

Purpose-built autonomous investigator agents for TI Processor SDK Linux.

Agents are multi-step, read-only diagnostic sub-routines that correlate live board state with SDK knowledge to identify root causes. They do not modify files or board state — they investigate and hand off to action skills.

## Available Agents

| Agent | When to use | Key tools |
|---|---|---|
| `ti-boot-investigator` | Board won't boot, stuck in U-Boot, kernel panic, remoteproc load failure at boot | `dmesg`, boot log parsing, binary consistency check |
| `ti-m4f-investigator` | R5F/M4F firmware not loading, RPMsg channel not opening, TISCI denial | remoteproc sysfs, trace0, ELF inspection |
| `ti-build-investigator` | Yocto `bitbake` failure, bbappend error, kernel module compile error | Yocto log analysis, bblayers check |

## Planned Agents

| Agent | Capability |
|---|---|
| `ti-gpio-investigator` | Correlates gpioinfo output with DTS pad nodes; diagnoses RXACTIVE missing, wrong mux mode |
| `ti-yocto-investigator` | Deep Yocto dependency graph analysis; finds conflicting recipes |
| `ti-sysfw-investigator` | TISCI error decoder; maps error codes to resource partitioning issues |

## How agents differ from skills

| | Skill | Agent |
|---|---|---|
| Role | Guided workflow for a single task | Autonomous multi-step investigator |
| Invocation | User asks for a specific action | User reports a symptom |
| Output | DTS fragment, bbappend, flash command | JSON finding + hand-off skill recommendation |
| Writes files? | Yes (DTS, scripts, bbappend) | No — read-only |
| Decision making | Follows a scripted procedure | Branches based on what it finds |

## Agent format

Each agent is a Markdown file with YAML frontmatter:

```yaml
---
name: <kebab-case>
description: >-
  One-sentence description. Used for skill routing.
version: 0.1.0
license: Apache-2.0
tools:
  - Bash      # shell commands on host or target
  - Read      # read local files
  - Grep      # pattern search in files
---
```

The frontmatter `tools:` list governs what the agent can do. Agents without `Bash` are analysis-only.

## Invoking agents

Agents are invoked like skills — the agent name is the trigger. Claude Code loads the agent's Markdown file and follows its procedure.

Example:
```
User: "My board won't boot — it gets to 'Starting kernel...' and then nothing."
Agent: [loads ti-boot-investigator.md] [begins Step 1 classification]
```

Agents always end by returning structured JSON and recommending a fix skill.
