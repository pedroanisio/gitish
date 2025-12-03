# Brain Protocol Manual

> **Audience**: AI Agents (Claude, GPT, Codex, etc.) working on this codebase
> **Version**: 2.0.0
> **Last Updated**: 2025-12-03

---

## Multi-Agent Hierarchy

```
Mission (high-level goal, spans multiple agents)
  └── Phase (coordination unit, claimed by one agent)
       └── Task (individual work item, claimable independently)
```

---

## TL;DR for AI Agents

```bash
# First time setup:
python3 -m venv .venv && source .venv/bin/activate  # Optional: virtualenv
pip install cryptography                             # Optional: for key signing
python scripts/brain_cli.py init --name claude       # Create identity + keys

# Before ANY coding session:
source .venv/bin/activate                    # If using virtualenv
python scripts/brain_cli.py sync             # Fetch latest changes
python scripts/brain_cli.py receipt          # Post proof-of-read

# Now you can commit. Your commits will be blocked without these steps.
```

---

## What is the Brain Protocol?

The Brain Protocol is a **decentralized collaboration system** that ensures all participants (humans and AI agents) have read the latest project state before contributing. It uses Git as the transport layer and provides:

1. **Proof of Identity** - Each participant has a unique, persistent identity
2. **Proof of Read** - Cryptographic proof you've seen the latest changes
3. **Pre-commit Enforcement** - Commits blocked without valid identity + recent receipt

---

## Why This Matters for AI Agents

As an AI agent, you may:
- Start multiple sessions without memory of previous work
- Work in parallel with other agents or humans
- Make changes without knowing what others have done

The Brain Protocol ensures:
- ✅ You acknowledge the current state before changing it
- ✅ Other participants know you've seen their work
- ✅ Conflicts are detected early, not at merge time
- ✅ There's an audit trail of who read what, when

---

## Installation

### Prerequisites

- **Python 3.9+** (check: `python3 --version`)
- **Git 2.20+** (check: `git --version`)
- **OpenSSL** (for key generation fallback)

### Step 1: Install Python Dependencies

**Option A: Using Virtual Environment (Recommended)**

Many systems (Debian 12+, Ubuntu 23.04+, Fedora 38+) enforce PEP 668 which restricts global pip installs.

```bash
# Create virtual environment (one-time)
python3 -m venv .venv

# Activate it (every session)
source .venv/bin/activate    # Linux/macOS
# or
.venv\Scripts\activate       # Windows

# Install dependencies
pip install -r scripts/requirements.txt
```

> **Tip**: Add `.venv/` to your shell startup to auto-activate, or use tools like `direnv`.

**Option B: Global Install (if allowed)**

```bash
pip install -r scripts/requirements.txt
# or
pip install cryptography>=41.0.0
```

**Option C: System Package (Debian/Ubuntu)**

```bash
sudo apt install python3-cryptography
```

**Option D: No Dependencies**

The `cryptography` library is optional. Without it, the system falls back to OpenSSL commands for key generation. Core functionality works without any Python dependencies.

### Step 2: Install Pre-commit Hook

The pre-commit hook enforces the Brain Protocol (identity + read receipt required).

```bash
# Option A: Using simple-git-hooks (recommended if already configured)
pnpm install

# Option B: Manual installation
cp scripts/hooks/pre-commit-brain .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Step 3: Initialize Your Identity

```bash
python scripts/brain_cli.py init --name YOUR_NAME
```

This will:
1. Generate an Ed25519 key pair
2. Create your identity file (`.brain/self.json`)
3. Commit your public key to the repository

### Step 4: Verify Installation

```bash
# Check your identity and key status
python scripts/brain_cli.py status

# Should show:
# ┌─────────────────────────────────────────────────────────┐
# │                    🧠 BRAIN STATUS                      │
# ├─────────────────────────────────────────────────────────┤
# │  Identity:    @your-name                                │
# │  Full ID:     your-name-abc12345                        │
# │  🔑 Keys:     ✅ Configured                             │
# │  ...                                                    │
# └─────────────────────────────────────────────────────────┘
```

### Step 5: First Sync and Receipt

```bash
python scripts/brain_cli.py sync
python scripts/brain_cli.py receipt
```

You're now ready to commit!

### Troubleshooting Installation

| Issue | Solution |
|-------|----------|
| `externally-managed-environment` (PEP 668) | Use virtualenv: `python3 -m venv .venv && source .venv/bin/activate` |
| `ModuleNotFoundError: cryptography` | `pip install cryptography` or system falls back to OpenSSL |
| `openssl: command not found` | Install OpenSSL: `apt install openssl` or `brew install openssl` |
| `Permission denied` on hook | `chmod +x .git/hooks/pre-commit` |
| `python: command not found` | Use `python3` instead of `python` |
| Key generation failed | Ensure OpenSSL is installed and in PATH |
| `No module named venv` | `apt install python3-venv` or `dnf install python3-venv` |

### Directory Structure After Installation

```
.brain/
├── self.json              # Your identity (gitignored)
├── keys/
│   ├── private/           # Your private key (gitignored)
│   │   └── {name}.pem
│   └── public/            # All participants' public keys (committed)
│       └── {name}.pem
├── messages/              # Sent messages
├── receipts/              # Read receipts
├── claims/                # Phase claims
└── events.jsonl           # Event log
```

---

## Quick Reference

### Commands

| Command | Purpose | When to Use |
|---------|---------|-------------|
| `brain_cli.py init --name NAME` | Create identity + keys | First time only |
| `brain_cli.py sync` | Fetch all changes | Start of every session |
| `brain_cli.py receipt` | Post read receipt | After sync, before commits |
| `brain_cli.py msg send "message"` | Send a message | Communicate on your branch |
| `brain_cli.py msg announce "message"` | **Announce to ALL agents** | Cross-branch announcements |
| `brain_cli.py msg listen` | **Listen for announcements** | See messages from all branches |
| `brain_cli.py phase claim PHASE` | Claim a work phase | Before starting phase work |
| `brain_cli.py phase release PHASE` | Release claimed phase | When blocked or done |
| `brain_cli.py phase complete PHASE PR` | Mark phase done | After PR merged |
| `brain_cli.py phase list` | Show all phases | Plan work |
| `brain_cli.py status` | Show current state | Anytime |
| `brain_cli.py msg log` | Show recent events | Review activity |
| `brain_cli.py keys show` | Show key status | Verify keys |
| `brain_cli.py keys verify NAME` | Show someone's public key | Verify identity |
| `brain_cli.py keys regenerate` | Regenerate your keys | If compromised |

### Task Commands (Multi-Agent)

| Command | Purpose |
|---------|---------|
| `brain_cli.py task add <mission> "Title"` | Add task to mission |
| `brain_cli.py task claim <mission> <task>` | Claim task (multi-agent) |
| `brain_cli.py task release <mission> <task>` | Release claimed task |
| `brain_cli.py task start <mission> <task>` | Start task (auto-claims) |
| `brain_cli.py task complete <mission> <task>` | Complete task |

### Mission Commands

| Command | Purpose |
|---------|---------|
| `brain_cli.py mission create "Title"` | Create new mission |
| `brain_cli.py mission list` | List all missions |
| `brain_cli.py mission show <id>` | Show mission details |
| `brain_cli.py mission start <id>` | Start mission |
| `brain_cli.py mission complete <id>` | Complete mission |

### Quality Gate Commands

| Command | Purpose |
|---------|---------|
| `brain_cli.py gate beforecode <mission>` | Show beforeCode checklist |
| `brain_cli.py gate check <mission> <item>` | Check checklist item |
| `brain_cli.py gate dod <mission>` | Show Definition of Done |
| `brain_cli.py gate verify <mission> <criterion>` | Verify DoD criterion |
| `brain_cli.py gate run <mission>` | Run automated checks |

### Cross-Branch Communication (Announcements)

The **announce/listen** system solves the problem of agents on different branches not seeing each other's messages.

```
Branch: claude/phase-11          Branch: gpt/phase-12
        │                                │
        ├── announce "Starting!"         │
        │         │                      │
        │         └──────────────────────┼──→ gpt runs: brain.py listen
        │                                │    "📢 claude: Starting!"
```

**How it works:**
1. `announce` pushes to shared `brain/events` branch
2. `listen` fetches from `brain/events` and shows all announcements
3. Works regardless of which feature branch you're on

**Usage:**

```bash
# Announce something important to ALL participants
python scripts/brain.py announce "📢 IMPORTANT: Phase 11 complete, ready for review!"

# Listen for announcements from others
python scripts/brain.py listen

# Output:
# 👂 Listening for announcements...
# 
# 📢 Last 3 announcements:
# ======================================================================
#  [2025-12-03T16:03:58] @claude (from claude/phase-11-validation):
#     📢 IMPORTANT: Phase 11 complete, ready for review!
# 
#  [2025-12-03T15:30:00] @gpt (from gpt/phase-12):
#     Starting work on Phase 12
# ======================================================================
```

**When to use announce vs send:**

| Scenario | Use |
|----------|-----|
| Message to your branch history | `send` |
| Critical update ALL agents must see | `announce` |
| Status update | `send` |
| Blocking issue affecting others | `announce` |
| Routine progress | `send` |
| Proposal for team discussion | `announce` |

### File Locations

```
.brain/
├── self.json              # Your identity (gitignored)
├── keys/
│   ├── private/           # Private keys (gitignored, chmod 600)
│   │   └── {name}.pem
│   └── public/            # Public keys (committed to repo)
│       └── {name}.pem
├── messages/              # Your sent messages
│   └── {name}/
│       └── {timestamp}-{type}.json
├── receipts/              # Your read receipts
│   └── {name}/
│       └── {timestamp}.json
├── claims/                # Phase claim files
│   └── phase-{N}-claim.json
└── events.jsonl           # Append-only event log
```

---

## Detailed Workflow

### 1. Initialize Identity (Once Per Agent)

```bash
python scripts/brain.py init --name claude
```

Output:
```
🟠 Generating identity for @claude...
   🎨 Color:   coral
   💫 Emotion: wonder
   🏷️  Full ID: claude-coral-wonder

🔐 Generating Ed25519 key pair...
✅ Keys generated
   📁 Private: .brain/keys/private/claude.pem (gitignored)
   📁 Public:  .brain/keys/public/claude.pem (committed to repo)
   🔑 Fingerprint: abc123def456...

✅ Identity created: 🟠 claude-coral-wonder
📁 Saved to: .brain/self.json
📤 Committing public key to repository...
✅ Public key committed
```

Each identity gets a **random color + emotion** combination for easy recognition!

This creates:

1. **`.brain/self.json`** (gitignored):
```json
{
  "uuid": "43dcd25e-fc29-4067-a23c-bda55304677a",
  "short_name": "claude",
  "color": "coral",
  "emotion": "wonder",
  "full_id": "claude-coral-wonder",
  "emoji": "🟠",
  "created_at": "2025-12-03T15:00:32.507977+00:00",
  "version": 3,
  "has_keys": true,
  "public_key_fingerprint": "abc123def456..."
}
```

**Available Colors**: red, blue, green, gold, purple, orange, cyan, magenta, coral, teal, indigo, amber, lime, rose, violet, silver, crimson, azure, emerald, ruby, sapphire, jade, onyx, pearl

**Available Emotions**: joy, calm, wonder, spark, glow, peace, bliss, hope, brave, swift, keen, wise, bold, zen, flow, dream, shine, grace, charm, pride, trust, zeal, muse, awe

2. **`.brain/keys/private/claude.pem`** (gitignored, chmod 600)
3. **`.brain/keys/public/claude.pem`** (committed to repo)

**Naming conventions for AI agents:**

| Name | Emoji | Provider |
|------|-------|----------|
| `claude` | 🟠 | Anthropic Claude |
| `gpt` | 🟢 | OpenAI GPT |
| `gemini` | 🔵 | Google Gemini |
| `copilot` | ⚫ | GitHub Copilot |
| `cursor` | 🟣 | Cursor AI |
| `codex` | 🟡 | OpenAI Codex |
| `human` | 👤 | Human participant |
| (other) | 🤖 | Default |

Use session IDs if running multiple instances: `claude-session1`

**About the keys:**
- **Ed25519** algorithm (same as modern SSH keys)
- **Private key** never leaves your machine
- **Public key** is committed so others can verify your signatures
- Keys are generated with Python's `cryptography` library or OpenSSL fallback

### 2. Sync Before Every Session

```bash
python scripts/brain.py sync
```

This:
- Fetches all remote branches
- Shows recent messages from other participants
- Prepares you to post a read receipt

**Always sync first, even if you think nothing changed.**

### 3. Post Read Receipt

```bash
python scripts/brain.py receipt
```

This creates a cryptographic proof that you've read the current state:

```json
{
  "type": "read-receipt",
  "from": "claude",
  "from_id": "claude-5cd6b28d",
  "up_to_commit": "abc123def456789",
  "ts": "2025-12-03T15:05:00+00:00"
}
```

**The pre-commit hook will block commits if:**
- No identity exists
- No receipts exist
- Your latest receipt is older than 24 hours

### 4. Claim Work Phases

Before starting work on a phase:

```bash
python scripts/brain.py claim 11
```

This:
- Records your claim in `.brain/claims/phase-11-claim.json`
- Appends to `events.jsonl`
- Commits the claim

**Check phase availability first:**

```bash
python scripts/brain.py phases
```

### 5. Send Messages

Communicate with other participants:

```bash
python scripts/brain.py send "Starting work on Phase 11 validation functions"
python scripts/brain.py send "Found issue with token references, investigating"
python scripts/brain.py send "Phase 11 complete, opening PR"
```

### 6. Complete or Release Phases

When done:

```bash
python scripts/brain.py complete 11 "#42"
```

If blocked or handing off:

```bash
python scripts/brain.py release 11 --reason "blocked on Phase 10"
```

---

## Pre-Commit Hook Behavior

The hook at `scripts/hooks/pre-commit-brain` runs before every commit:

```
🧠 Brain Protocol Pre-Commit Check
────────────────────────────────────────
✅ Identity: @claude
✅ Receipt age: 2.5 hours (max: 24h)
ℹ️  Last read: abc123de at 2025-12-03T15:05:00
────────────────────────────────────────
✅ All checks passed - commit allowed
```

### What Gets Blocked

| Condition | Result | Fix |
|-----------|--------|-----|
| No `.brain/self.json` | ❌ Blocked | Run `brain.py init --name NAME` |
| No receipts | ❌ Blocked | Run `brain.py sync` then `brain.py receipt` |
| Receipt > 24 hours old | ❌ Blocked | Run `brain.py sync` then `brain.py receipt` |
| Only docs files staged | ✅ Allowed | Skip brain check for docs-only commits |

### Emergency Bypass

If you absolutely must commit without the brain check:

```bash
BRAIN_BYPASS_HOOK=1 git commit -m "emergency fix"
```

**Use sparingly. The bypass is logged.**

---

## Event Types Reference

### Message Event

```json
{
  "type": "message",
  "from": "claude",
  "body": "Starting Phase 11 work",
  "ts": "2025-12-03T15:00:00+00:00"
}
```

### Claim Event

```json
{
  "type": "claim",
  "phase": 11,
  "developer": "@claude",
  "developer_id": "claude-5cd6b28d",
  "branch": "dev/claude/phase-11",
  "ts": "2025-12-03T15:00:00+00:00",
  "head_at_claim": "abc123def456"
}
```

### Release Event

```json
{
  "type": "release",
  "phase": 11,
  "developer": "@claude",
  "reason": "blocked",
  "ts": "2025-12-03T16:00:00+00:00"
}
```

### Complete Event

```json
{
  "type": "complete",
  "phase": 11,
  "developer": "@claude",
  "pr": "#42",
  "merge_commit": "def456789abc",
  "ts": "2025-12-03T17:00:00+00:00"
}
```

### Read Receipt

```json
{
  "type": "read-receipt",
  "from": "claude",
  "from_id": "claude-5cd6b28d",
  "up_to_commit": "abc123def456789",
  "ts": "2025-12-03T15:05:00+00:00"
}
```

---

## Cryptographic Keys

### Overview

Each participant has an **Ed25519 key pair**:
- **Private key**: Kept secret, used for signing
- **Public key**: Shared with others, used for verification

Keys are automatically generated during `brain.py init`.

### Key Commands

```bash
# Show your key status and list all known participants
python scripts/brain.py keys show

# View someone's public key and fingerprint
python scripts/brain.py keys verify alice

# Sign a test message (debugging)
python scripts/brain.py keys sign "test message"

# Verify a signature (debugging)
python scripts/brain.py keys check alice "test message" "base64signature..."

# Regenerate your keys (if compromised)
python scripts/brain.py keys regenerate
```

### Key Status Output

```
┌─────────────────────────────────────────────────────────┐
│                    🔑 KEY STATUS                        │
├─────────────────────────────────────────────────────────┤
│  Private Key: ✅ .brain/keys/private/claude.pem        │
│  Public Key:  ✅ .brain/keys/public/claude.pem         │
│  Fingerprint: abc123def456...                          │
├─────────────────────────────────────────────────────────┤
│  Known Participants (Public Keys):                     │
│    @alice               xyz789...                      │
│    @claude              abc123...        (you)         │
│    @human               def456...                      │
└─────────────────────────────────────────────────────────┘
```

### Security

| File | Location | Permissions | Git Status |
|------|----------|-------------|------------|
| Private key | `.brain/keys/private/{name}.pem` | `chmod 600` | **gitignored** |
| Public key | `.brain/keys/public/{name}.pem` | `chmod 644` | **committed** |

**Never share your private key.** If compromised:

```bash
python scripts/brain.py keys regenerate
```

### Dependencies

Keys require the `cryptography` Python library:

```bash
pip install cryptography>=41.0.0
```

If not available, the system falls back to OpenSSL commands. If neither is available, key generation is skipped with a warning.

---

## Best Practices for AI Agents

### DO ✅

1. **Always sync at session start**
   ```bash
   python scripts/brain.py sync
   python scripts/brain.py receipt
   ```

2. **🔊 BROADCAST task start and finish (REQUIRED)**
   ```bash
   # When starting ANY task:
   python scripts/brain.py announce "🚀 STARTING: [Task description]"
   
   # When completing ANY task:
   python scripts/brain.py announce "✅ COMPLETE: [Task description] - [brief outcome]"
   ```
   **This applies to ALL work items** - phases, tasks, investigations, fixes, etc.

3. **Send messages for progress updates**
   ```bash
   python scripts/brain.py send "Found root cause: missing export in index.ts"
   python scripts/brain.py send "Investigating token validation issue"
   ```

4. **Claim phases before starting work**
   ```bash
   python scripts/brain.py claim 11
   ```

5. **Post receipts after reading important updates**
   ```bash
   # After reviewing a PR or significant change
   python scripts/brain.py receipt
   ```

6. **Release phases if blocked or interrupted**
   ```bash
   python scripts/brain.py release 11 --reason "session ended"
   ```

### DON'T ❌

1. **Don't skip the sync/receipt step** - You'll be blocked at commit time

2. **Don't claim multiple phases** - Finish one before claiming another

3. **Don't use bypass routinely** - It defeats the purpose of proof-of-read

4. **Don't ignore other participants' messages** - Check `brain.py log` regularly

5. **Don't commit without understanding current state** - Sync first, always

6. **Don't start or finish work silently** - Always broadcast with `announce`

---

## Troubleshooting

### "No identity found"

```bash
python scripts/brain.py init --name your-name
```

### "No read receipts found"

```bash
python scripts/brain.py sync
python scripts/brain.py receipt
```

### "Receipt is too old"

```bash
python scripts/brain.py sync
python scripts/brain.py receipt
```

### "Phase already claimed"

```bash
python scripts/brain.py phases  # Check who has it
python scripts/brain.py log     # See recent activity
# Wait for release or coordinate with the owner
```

### Push fails (no remote)

The `-p` flag tries to push after each action. If there's no remote configured, it will warn but continue:

```
⚠️  Push failed (no remote?): exit code 128
```

This is fine for local development.

---

## Integration with Existing Workflow

The Brain Protocol integrates with the existing phase-based refactoring workflow:

1. **Check phases**: `brain.py phases` (reads `docs/PHASE-CLAIMS.md`)
2. **Claim phase**: `brain.py claim N`
3. **Do TDD work**: Red → Green → Refactor
4. **Validate**: `pnpm run validate`
5. **Commit**: (brain hook checks identity + receipt)
6. **Push & PR**: `git push`
7. **Complete**: `brain.py complete N "#PR"`

---

## Summary Checklist for AI Agents

```
□ Session Start
  ├─ □ python scripts/brain.py sync
  ├─ □ python scripts/brain.py receipt
  └─ □ python scripts/brain.py status (verify identity)

□ Before ANY Task/Phase Work
  ├─ □ python scripts/brain.py phases (check availability)
  ├─ □ python scripts/brain.py claim N
  └─ □ python scripts/brain.py announce "🚀 STARTING: [task description]"  ⬅️ REQUIRED

□ During Work
  ├─ □ python scripts/brain.py send "status updates"
  └─ □ Commits work (hook validates automatically)

□ After ANY Task/Phase Complete
  ├─ □ pnpm run validate
  ├─ □ git push & create PR
  ├─ □ python scripts/brain.py complete N "#PR"
  └─ □ python scripts/brain.py announce "✅ COMPLETE: [task] - [outcome]"  ⬅️ REQUIRED

□ If Interrupted/Blocked
  ├─ □ python scripts/brain.py release N --reason "..."
  └─ □ python scripts/brain.py announce "⏸️ PAUSED: [task] - [reason]"
```

---

## 🎯 MissionOnHand - Higher-Level Task Management

For complex work involving multiple tasks, use the **MissionOnHand** system.

### Mission Concepts

| Concept | Purpose |
|---------|---------|
| **Mission** | A high-level goal with multiple tasks |
| **Strategy** | How to approach the mission (sequential/parallel) |
| **Tasks** | Individual work items within the mission |
| **beforeCode** | Checklist to complete BEFORE writing any code |
| **beforeCommit** | Checklist to complete BEFORE every commit |
| **DoD** | Definition of Done - criteria for mission completion |

### Mission Workflow

```bash
# 1. Create a mission
python scripts/mission.py create "Extract Phase 11 Validation" \
  --priority high \
  --approach sequential

# 2. Review and complete beforeCode checklist
python scripts/mission.py beforecode show mission-abc123
python scripts/mission.py beforecode check mission-abc123 bc-1
python scripts/mission.py beforecode check mission-abc123 bc-2
# ... check all required items

# 3. Start the mission
python scripts/mission.py start mission-abc123

# 4. Add and work on tasks
python scripts/mission.py task add mission-abc123 "Fix TypeScript errors" --type bugfix
python scripts/mission.py task start mission-abc123 task-xyz789
python scripts/mission.py task complete mission-abc123 task-xyz789

# 5. Verify DoD criteria
python scripts/mission.py dod show mission-abc123
python scripts/mission.py dod run mission-abc123  # Run automated checks
python scripts/mission.py dod verify mission-abc123 dod-1

# 6. Complete the mission
python scripts/mission.py complete mission-abc123
```

### Default beforeCode Checklist

Every mission starts with these items to check:

| ID | Description | Required |
|----|-------------|----------|
| bc-1 | Run `brain sync` and `brain receipt` | ✅ |
| bc-2 | Read relevant documentation and understand context | ✅ |
| bc-3 | Check for dependencies and blockers | ✅ |
| bc-4 | Understand WHY before fixing WHAT (root cause) | ✅ |
| bc-5 | Review existing tests for expected behavior | ✅ |
| bc-6 | Verify no one else is working on related code | ◽ |
| bc-7 | Plan approach and identify risks | ◽ |

### Default beforeCommit Checklist

Before every commit, verify:

**Manual:**
- Code is production-ready (no TODOs, no stubs)
- Commit message follows format
- No secrets or sensitive data
- Changes are minimal and focused
- Self-reviewed the diff

**Automated:**
- Brain identity and receipt valid
- TypeScript compiles
- Linting passes

### Default Definition of Done

| ID | Description | Type |
|----|-------------|------|
| dod-1 | All tasks completed | manual |
| dod-2 | All tests pass | automated |
| dod-3 | Code reviewed | review |
| dod-4 | Documentation updated if needed | manual |

### Mission Commands Reference

```bash
# Create and manage missions
mission.py create "Title"              # Create new mission
mission.py list                        # List all missions
mission.py show <id>                   # Show mission details
mission.py start <id>                  # Start mission (requires beforeCode)
mission.py complete <id>               # Complete mission (requires DoD)

# Task management
mission.py task add <id> "Title"       # Add task
mission.py task start <id> <task-id>   # Start working on task
mission.py task complete <id> <task-id> # Mark task done

# beforeCode checklist
mission.py beforecode show <id>        # Show checklist
mission.py beforecode check <id> <item-id>  # Check item
mission.py beforecode check <id> <item-id> --uncheck  # Uncheck

# Definition of Done
mission.py dod show <id>               # Show DoD
mission.py dod verify <id> <criterion-id>  # Verify criterion
mission.py dod run <id>                # Run automated checks
```

### Mission File Storage

```
.brain/missions/
├── active/                    # Current missions
│   └── mission-abc123.json
├── completed/                 # Finished missions
│   └── mission-xyz789.json
└── abandoned/                 # Cancelled missions
```

---

## Integration: Brain + Mission Together

Recommended workflow combining both systems:

```bash
# === SESSION START ===
python scripts/brain.py init --name claude    # First time only
python scripts/brain.py sync
python scripts/brain.py receipt

# === CREATE MISSION ===
python scripts/mission.py create "Phase 11 Extraction"
python scripts/mission.py beforecode check mission-xxx bc-1
python scripts/mission.py beforecode check mission-xxx bc-2
# ... complete beforeCode
python scripts/mission.py start mission-xxx

# === DO WORK ===
python scripts/mission.py task add mission-xxx "Fix imports"
python scripts/mission.py task start mission-xxx task-yyy
# ... write code ...
git add -A && git commit -m "fix(validation): update imports"
python scripts/mission.py task complete mission-xxx task-yyy

# === COMPLETE MISSION ===
python scripts/mission.py dod run mission-xxx
python scripts/mission.py dod verify mission-xxx dod-1
python scripts/mission.py complete mission-xxx
python scripts/brain.py send "Phase 11 mission complete"
```

---

## Questions?

Check the tests for examples of all functionality:

```bash
cd scripts && python -m pytest tests/ -v
```

136 tests cover identity, messages, claims, receipts, git integration, CLI parsing, pre-commit hooks, and missions.

