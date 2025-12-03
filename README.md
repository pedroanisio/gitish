# gitish

**Git as Message Medium** — A decentralized collaboration protocol for multi-agent coordination.

## What is this?

Gitish treats Git as a **distributed consensus protocol**, not just version control. It enables AI agents and humans to coordinate work using Git's cryptographic properties:

- **Proof of authorship** via Ed25519 signed commits
- **Proof of read** via receipts referencing commit hashes
- **Exclusive work claims** to prevent conflicts
- **Cross-branch announcements** for team-wide communication

## Quick Start

```bash
# 1. Initialize identity (generates Ed25519 key pair)
python scripts/brain_cli.py init --name claude

# 2. Before every session
python scripts/brain_cli.py sync      # Fetch latest
python scripts/brain_cli.py receipt   # Post proof-of-read

# 3. Now you can commit (pre-commit hook validates identity + receipt)
```

## Commands

| Command | Purpose |
|---------|---------|
| `brain init --name NAME` | Create identity + keys |
| `brain sync` | Fetch all branches |
| `brain receipt` | Post read receipt |
| `brain msg send "text"` | Send message on branch |
| `brain msg announce "text"` | Broadcast to ALL agents |
| `brain msg listen` | Listen for announcements |
| `brain phase claim N` | Claim exclusive phase |
| `brain phase complete N #PR` | Mark phase done |
| `brain status` | Show current state |

## Multi-Agent Hierarchy

```
Mission (high-level goal, spans multiple agents)
  └── Phase (coordination unit, claimed by one agent)
       └── Task (individual work item)
```

## How It Works

1. **Each agent gets a unique identity**: `claude-emerald-swift` (name + color + emotion)
2. **Each agent works on their own branch**: `dev/claude/phase-11`
3. **Claims prevent conflicts**: Only one agent can claim a phase at a time
4. **Read receipts prove knowledge**: Commits reference the HEAD you've seen
5. **Pre-commit hook enforces protocol**: No commits without valid identity + recent receipt

## Storage

```
.brain/
├── self.json           # Your identity (gitignored)
├── keys/
│   ├── private/        # Ed25519 private key (gitignored)
│   └── public/         # Public keys (committed)
├── messages/           # Sent messages
├── receipts/           # Read receipts
├── claims/             # Phase claims
└── events.jsonl        # Local event log
```

## Requirements

- Python 3.9+
- Git 2.20+
- OpenSSL (for key generation)

No external Python dependencies required.

## Documentation

- [`MANUAL.md`](MANUAL.md) — Complete reference for AI agents
- [`GitAsProtocol.md`](GitAsProtocol.md) — Theory and architecture

## License

MIT
