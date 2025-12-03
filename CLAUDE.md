# Claude Instructions

## Brain Protocol

This project uses the **Brain Protocol** for multi-agent collaboration.

### Hierarchy: Mission → Phase → Task

```
Mission (high-level goal, spans multiple agents)
  └── Phase (coordination unit, claimed by one agent)
       └── Task (individual work item, claimable independently)
```

### Before ANY Code Changes

```bash
python scripts/brain_cli.py sync      # Fetch latest from all branches
python scripts/brain_cli.py receipt   # Post proof-of-read (required to commit)
```

### Communication

```bash
python scripts/brain_cli.py msg send "message" --push   # Message on your branch
python scripts/brain_cli.py msg announce "broadcast"    # Cross-branch announcement
python scripts/brain_cli.py msg listen                  # Hear all announcements
```

### 🔊 REQUIRED: Broadcast Task Start/Finish

**You MUST announce when starting and completing ANY task:**

```bash
# When starting ANY work:
python scripts/brain_cli.py msg announce "🚀 STARTING: [task description]"

# When completing ANY work:
python scripts/brain_cli.py msg announce "✅ COMPLETE: [task description] - [outcome]"

# If paused/blocked:
python scripts/brain_cli.py msg announce "⏸️ PAUSED: [task] - [reason]"
```

### Phase Claims

```bash
python scripts/brain_cli.py phase list           # Show active/completed phases
python scripts/brain_cli.py phase claim <N>      # Claim phase N
python scripts/brain_cli.py phase complete <N> <PR#>  # Mark phase done
```

### Task Claims (Multi-Agent)

```bash
python scripts/brain_cli.py task add <mission> "Title"    # Add task
python scripts/brain_cli.py task claim <mission> <task>   # Claim task
python scripts/brain_cli.py task start <mission> <task>   # Start (auto-claims)
python scripts/brain_cli.py task complete <mission> <task> # Complete task
```

### Missions & Quality Gates

```bash
python scripts/brain_cli.py mission create "Title"        # Create mission
python scripts/brain_cli.py mission list                  # List missions
python scripts/brain_cli.py gate beforecode <mission>     # Pre-code checklist
python scripts/brain_cli.py gate dod <mission>            # Definition of Done
```

### First Time Setup

```bash
python scripts/brain_cli.py init --name claude
```

## Full Documentation

See **[scripts/MANUAL.md](scripts/MANUAL.md)** for complete reference.

## Project Conventions

- **TDD**: Write failing tests first
- **No placeholders**: Production-ready code only
- **Root cause fixes**: Understand WHY before fixing
- **Communicate**: Use brain CLI to coordinate with other agents
- **🔊 Broadcast**: Always announce task start/finish via `msg announce`
