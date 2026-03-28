# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This System Is

A markdown-native multi-agent framework. No code, no databases, no build pipeline. Agents are defined entirely in markdown files and executed by Claude Code on a schedule (heartbeat). Agents share context through a shared journal; each agent maintains its own private MEMORY.md.

## How Agents Work

Each agent under `agents/` has five required files:

| File | Purpose |
|------|---------|
| `AGENT.md` | Mission, KPIs (baseline → target), skills, input/output contracts, hard constraints |
| `HEARTBEAT.md` | Schedule and 4-step cycle: read context → assess state → execute skill → log to journal |
| `MEMORY.md` | Agent-local learnings only. Only write confirmed patterns here — one-off observations go to the journal |
| `RULES.md` | What the agent can/cannot do; when to escalate to human, orchestrator, or journal |
| `skills/` | One markdown file per skill — purpose, inputs, step-by-step process, outputs, quality bar |

## Running an Agent

There are no CLI commands. To run an agent, read its `HEARTBEAT.md` and follow the cycle manually:
1. Read the agent's context sources (journal entries, `knowledge/`, own `MEMORY.md`)
2. Assess state (decision tree in HEARTBEAT.md determines which skill runs)
3. Execute the chosen skill from `skills/`
4. Write a dated journal entry to `journal/entries/`

## Creating a New Agent

Follow `NEW_AGENT_BOOTSTRAP.md` (9 steps). Short version:
1. Copy `agents/standard-agent/` to `agents/your-agent-name/`
2. Fill in `AGENT.md` (mission, KPIs, skills list)
3. Write each skill file in `skills/`
4. Define the heartbeat schedule in `HEARTBEAT.md`
5. Set boundaries in `RULES.md`
6. Register in `AGENT_REGISTRY.md`
7. Verify with `AGENT_CREATION_CHECKLIST.md` before activating

See `examples/podcast-agent/` for a complete working reference.

## Key Conventions

- Agent folders: `agents/lowercase-hyphen/`
- Output files: `YYYY-MM-DD_agent-name_description.md` → goes in agent's `outputs/`
- Journal entries: `YYYY-MM-DD_HHMM.md` → goes in `journal/entries/`
- Skill files: `skills/SKILL_NAME.md` (uppercase)
- **Agents never write to `knowledge/`** — propose changes via journal entry instead
- **`MEMORY.md` is the only file agents update in-place** — all other outputs are new dated files

## Data Flow

```
knowledge/          ← static, read-only (BRAND.md, AUDIENCE.md, STRATEGY.md)
journal/entries/    ← shared write, append-only (all agents log here)
agents/*/MEMORY.md  ← private per-agent, in-place updates only
agents/*/outputs/   ← dated output files produced by skills
agents/*/data/imports/ ← human-provided input data for the agent
```

## Orchestrator Role

`orchestrator/` is always-on (not heartbeat-driven). It routes tasks to the right agent, maintains `PRIORITIES.md`, and escalates to human when no existing agent fits a task. It does not do specialist work itself.

## Four Pillar Check (before activating any agent)

- Goals: KPIs are defined and measurable?
- Skills: Every skill serves a goal — no extras?
- Heartbeat: Cron loop is defined and predictable?
- Journal: Agent knows how to read from and write to journal?
- Registry: Agent is listed in `AGENT_REGISTRY.md`?
