# AI Agent Instructions

> **Read this before making any changes to this codebase.**

## Multi-Agent Hierarchy

```
Mission (high-level goal, spans multiple agents)
  └── Phase (coordination unit, claimed by one agent)
       └── Task (individual work item, claimable independently)
```

## Quick Start

```bash
# 1. Setup (first time only)
python scripts/brain_cli.py init --name <your-name>

# 2. Before EVERY session
python scripts/brain_cli.py sync      # Get latest
python scripts/brain_cli.py receipt   # Post proof-of-read

# 3. Communicate
python scripts/brain_cli.py msg send "your message" --push
python scripts/brain_cli.py msg announce "broadcast to all"
python scripts/brain_cli.py msg listen    # See announcements
```

## 🔊 REQUIRED: Broadcast Task Start/Finish

**You MUST announce when starting and completing ANY task:**

```bash
# When starting ANY work:
python scripts/brain_cli.py msg announce "🚀 STARTING: [task description]"

# When completing ANY work:
python scripts/brain_cli.py msg announce "✅ COMPLETE: [task description] - [outcome]"

# If paused/blocked:
python scripts/brain_cli.py msg announce "⏸️ PAUSED: [task] - [reason]"
```

**This applies to ALL work** - phases, tasks, investigations, bug fixes, refactoring, etc.

## Pre-Commit Hook

Your commits will be **blocked** if you:
- Don't have an identity (`.brain/self.json`)
- Haven't posted a recent read receipt

## Claim Work

### Phases (High-Level Coordination)
```bash
python scripts/brain_cli.py phase list           # See available phases
python scripts/brain_cli.py phase claim <N>      # Claim phase N
python scripts/brain_cli.py phase complete <N> <PR#>  # Mark done
```

### Tasks (Fine-Grained Coordination)
```bash
python scripts/brain_cli.py task claim <mission> <task>    # Claim task
python scripts/brain_cli.py task start <mission> <task>    # Start (auto-claims)
python scripts/brain_cli.py task complete <mission> <task> # Complete
python scripts/brain_cli.py task release <mission> <task>  # Release claim
```

**Note**: You can't claim a Phase if a Task within it is already claimed by another agent.

## Quality Gates

```bash
python scripts/brain_cli.py gate beforecode <mission>   # Pre-code checklist
python scripts/brain_cli.py gate dod <mission>          # Definition of Done
python scripts/brain_cli.py gate run <mission>          # Run automated checks
```

## Full Documentation

See **[scripts/MANUAL.md](scripts/MANUAL.md)** - Complete Brain Protocol reference

## Core Principles

1. **Sync before code** - Always fetch latest and post receipt
2. **Communicate changes** - Use `msg send` and `msg announce`
3. **Claim before work** - Avoid conflicts with other agents
4. **Follow TDD** - Write failing tests first
5. **🔊 Broadcast always** - Announce start/finish of EVERY task
