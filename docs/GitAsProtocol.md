# Git as Protocol: The Theory Behind Brain

> **Audience**: Developers, architects, and curious minds wanting to understand the mechanics
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

## The Core Insight

**Git is not just version control—it's a distributed consensus protocol.**

Every Git repository is a cryptographically-verified, append-only log of state transitions. This makes it ideal for:

- Multi-party coordination without a central server
- Proof of authorship (signed commits)
- Proof of knowledge (merge commits prove you've seen content)
- Immutable audit trails
- Offline-first operation with eventual consistency

The Brain Protocol leverages these properties to create a **decentralized collaboration system** for AI agents and humans.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GIT AS PROTOCOL STACK                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     APPLICATION LAYER                                │   │
│  │  brain_cli.py - Unified CLI for multi-agent collaboration           │   │
│  │  brain/ package - core, identity, messaging, phases, missions       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     PROTOCOL LAYER                                   │   │
│  │  Messages, Claims, Receipts, Missions - Structured JSON events      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     STORAGE LAYER                                    │   │
│  │  .brain/ directory - Local state, events.jsonl, missions/           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     TRANSPORT LAYER                                  │   │
│  │  Git commits, branches, merges - Cryptographic verification         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     NETWORK LAYER                                    │   │
│  │  git push/fetch/pull - Peer-to-peer or via GitHub/GitLab            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## How Git Provides Protocol Guarantees

### 1. Identity (Authentication)

**Git Mechanism**: GPG-signed commits

```bash
git commit -S -m "message"  # -S = sign with GPG key
```

**What it proves**: The commit was made by someone with access to a specific private key.

**Brain Implementation**:

Each participant has a persistent identity with an Ed25519 key pair:

```
.brain/
├── self.json                    # Identity metadata (gitignored)
├── keys/
│   ├── private/
│   │   └── claude.pem          # Private key (gitignored, chmod 600)
│   └── public/
│       └── claude.pem          # Public key (committed to repo)
```

Identity file:
```json
{
  "uuid": "unique-identifier",
  "short_name": "claude",
  "color": "emerald",
  "emotion": "swift",
  "full_id": "claude-emerald-swift",
  "has_keys": true,
  "public_key_fingerprint": "abc123..."
}
```

**Key Generation**: Uses Ed25519 (same as SSH keys), generated on `brain init`:

```bash
$ python scripts/brain_cli.py init --name claude
🔐 Generating Ed25519 key pair...
✅ Keys generated
   📁 Private: .brain/keys/private/claude-emerald-swift.pem (gitignored)
   📁 Public:  .brain/keys/public/claude-emerald-swift.pem (committed to repo)
   🔑 Fingerprint: abc123def456...
✅ Identity created: claude-emerald-swift
```

**Note**: Keys now use the full identity (name-color-emotion) for uniqueness.

**Why Ed25519?**
- Fast signing and verification
- Small keys (256 bits) and signatures (512 bits)
- High security (128-bit equivalent)
- Same algorithm used by SSH and modern GPG

### 2. Proof of Read (Acknowledgment)

**Git Mechanism**: Merge commits

When you merge another branch, you create a commit that cryptographically references their commit hash:

```
Merge commit M
├── Parent 1: Your previous commit (abc123)
└── Parent 2: Their commit you're merging (def456)
```

This **proves** you had access to commit `def456` at the time of the merge.

**Brain Implementation**:
```json
// .brain/receipts/claude/20251203-150000.json
{
  "type": "read-receipt",
  "from": "claude",
  "up_to_commit": "def456789abc",  // The commit hash I've read up to
  "ts": "2025-12-03T15:00:00Z"
}
```

By committing a file that references a specific commit hash, the participant proves:
1. They had access to the repository at that state
2. They saw the content up to that commit
3. The timestamp of when they saw it

### 3. Ordering (Consensus)

**Git Mechanism**: Commit graph (DAG)

Git commits form a Directed Acyclic Graph (DAG). Each commit points to its parent(s), creating a partial ordering of events.

```
A ─── B ─── C ─── D (main)
       \
        E ─── F (feature)
```

When branches merge, the ordering becomes:

```
A ─── B ─── C ─── D ─── G (merge)
       \           /
        E ─── F ──┘
```

**Brain Implementation**:

Events in `events.jsonl` are ordered by commit history. When conflicts arise:
1. First valid claim by timestamp wins
2. Merge conflicts are resolved at sync time
3. The merged state becomes the canonical truth

### 4. Immutability (Audit Trail)

**Git Mechanism**: SHA-1/SHA-256 content hashing

Every Git object (commit, tree, blob) is identified by its content hash:

```
commit abc123def456...
├── tree: 789xyz...
├── parent: previous-commit-hash
├── author: Claude <claude@ai>
├── message: "claim: Phase 11"
└── signature: GPG signature (optional)
```

Changing any byte changes the hash, making history tamper-evident.

**Brain Implementation**:

All Brain events are Git commits. The `events.jsonl` file is append-only—each event is a new line, never modified:

```jsonl
{"type":"claim","phase":11,"developer":"@claude","ts":"2025-12-03T15:00:00Z"}
{"type":"message","from":"claude","body":"Starting work","ts":"2025-12-03T15:01:00Z"}
{"type":"read-receipt","from":"claude","up_to_commit":"abc123","ts":"2025-12-03T15:02:00Z"}
```

---

## The Decentralized Conversation Model

### Traditional Centralized Model

```
         ┌─────────────┐
         │   Server    │
         │  (central)  │
         └──────┬──────┘
                │
    ┌───────────┼───────────┐
    │           │           │
┌───┴───┐   ┌───┴───┐   ┌───┴───┐
│ Alice │   │  Bob  │   │Claude │
└───────┘   └───────┘   └───────┘

Problem: Server is single point of failure
```

### Git-Based Decentralized Model

```
┌─────────────────────────────────────────────────────────────┐
│                     Shared Repository                        │
│                    (GitHub/GitLab/etc)                       │
│                                                             │
│  main ──────────────────────────────────────────────────    │
│          │              │              │                    │
│  dev/alice ─────────────┼──────────────┼────────────────    │
│                         │              │                    │
│  dev/bob ───────────────┼──────────────┼────────────────    │
│                         │              │                    │
│  dev/claude ────────────┼──────────────┼────────────────    │
│                         │              │                    │
└─────────────────────────────────────────────────────────────┘

Each participant:
- Has their own persistent branch
- Commits messages/claims to their branch
- Merges from main to see others' updates
- Posts read receipts to prove they've seen content
```

### Message Flow

```
1. Alice sends a message:
   
   dev/alice:  A1 ── A2 ── A3 (message commit)
   
2. Bob syncs and sees Alice's message:
   
   dev/bob:    B1 ── B2 ── M (merge from dev/alice)
                           └── B3 (read-receipt for A3)
   
3. Claude syncs and sees both:
   
   dev/claude: C1 ── M (merge) ── C2 (read-receipt)
                     └── references A3 and B3
```

---

## Conflict Resolution Strategy

### The Problem

Two agents might try to claim the same phase simultaneously:

```
Time T1:
  dev/alice: claim Phase 11
  dev/claude: claim Phase 11  (at same time!)
```

### The Solution: First-Commit-Wins + Merge Detection

1. **Both agents commit their claims to their own branches** (no conflict yet)

2. **When branches merge**, the conflict is detected:
   ```
   main ─── M (merge conflict!)
            ├── alice's claim for Phase 11
            └── claude's claim for Phase 11
   ```

3. **Resolution rules**:
   - Compare timestamps in claim events
   - Earlier timestamp wins
   - Loser's claim is automatically marked as "conflict-rejected"
   - Both parties are notified via events.jsonl

4. **Brain hook prevents duplicate claims**:
   - Before claiming, sync first (`brain sync`)
   - Post receipt to prove you saw current state (`brain receipt`)
   - Pre-commit hook validates no conflicting claims exist

---

## Why JSONL for Events?

### Append-Only Log Pattern

```jsonl
{"type":"claim","phase":11,"developer":"@claude","ts":"2025-12-03T15:00:00Z"}
{"type":"message","from":"claude","body":"Working on it","ts":"2025-12-03T15:01:00Z"}
{"type":"complete","phase":11,"developer":"@claude","ts":"2025-12-03T17:00:00Z"}
```

**Benefits**:
1. **One event per line** = minimal merge conflicts
2. **Append-only** = no history rewriting
3. **Easy to parse** = `for line in file: json.loads(line)`
4. **Git-friendly** = each line change is one line in diff
5. **Streamable** = can process without loading entire file

### Contrast with JSON Array

```json
{
  "events": [
    {"type": "claim", ...},
    {"type": "message", ...}
  ]
}
```

**Problems**:
- Adding an event changes multiple lines (array brackets, commas)
- Merge conflicts on every concurrent write
- Must load entire file to append

---

## The Pre-Commit Hook as Consensus Enforcer

### What It Checks

```python
# scripts/hooks/pre-commit-brain

1. Identity exists?
   └── .brain/self.json must exist and be valid

2. Read receipt exists?
   └── .brain/receipts/{name}/*.json must have at least one

3. Receipt is fresh?
   └── Latest receipt timestamp < 24 hours old

4. (Optional) Mission beforeCommit checklist?
   └── All required items checked
```

### Why This Matters

The hook enforces the **proof-of-read** requirement:

> **You cannot contribute without first acknowledging the current state.**

This prevents:
- Blind commits that ignore others' work
- Conflicting claims from uninformed participants
- "I didn't know about that" excuses

---

## Event Types and Their Semantics

### Message Event

```json
{
  "type": "message",
  "from": "claude",
  "body": "Starting work on Phase 11",
  "ts": "2025-12-03T15:00:00Z"
}
```

**Semantics**: Broadcast to all participants. No response required.

### Read Receipt Event

```json
{
  "type": "read-receipt",
  "from": "claude",
  "up_to_commit": "abc123def456",
  "ts": "2025-12-03T15:00:00Z"
}
```

**Semantics**: Cryptographic proof that `claude` saw the repository state at commit `abc123def456`.

**Verification**: Anyone can verify by checking:
1. The receipt commit exists in history
2. It references a valid commit hash
3. The commit was authored by `claude`

### Claim Event

```json
{
  "type": "claim",
  "phase": 11,
  "developer": "@claude",
  "branch": "dev/claude/phase-11",
  "ts": "2025-12-03T15:00:00Z",
  "head_at_claim": "abc123"
}
```

**Semantics**: Exclusive lock on a resource. Only one valid claim per phase.

**Verification**:
1. `head_at_claim` must be a recent commit (proves sync was done)
2. No earlier claim for same phase exists
3. Developer has valid identity

### Complete Event

```json
{
  "type": "complete",
  "phase": 11,
  "developer": "@claude",
  "pr": "#42",
  "merge_commit": "def456",
  "ts": "2025-12-03T17:00:00Z"
}
```

**Semantics**: Release of claim + proof of work merged.

---

## Comparison with Traditional Protocols

| Feature | Git-as-Protocol | Slack/Discord | Database |
|---------|-----------------|---------------|----------|
| **Decentralized** | ✅ Fully | ❌ Server-dependent | ❌ Server-dependent |
| **Offline-first** | ✅ Full offline capability | ❌ Requires connection | ❌ Requires connection |
| **Proof of read** | ✅ Cryptographic | ❌ Server-reported | ❌ None |
| **Audit trail** | ✅ Immutable | ⚠️ Editable by admins | ⚠️ Mutable |
| **Conflict resolution** | ✅ Merge semantics | ❌ Last-write-wins | ⚠️ Complex locking |
| **Survives server loss** | ✅ Every clone is full backup | ❌ Data lost | ❌ Data lost |
| **Real-time** | ⚠️ Polling-based | ✅ WebSockets | ⚠️ Depends |

---

## Why This Matters for AI Agents

### The Multi-Agent Problem

AI agents face unique challenges:
1. **No persistent memory** - Each session starts fresh
2. **Parallel execution** - Multiple agents may work simultaneously
3. **No implicit coordination** - Unlike humans, agents don't "chat"
4. **Trust issues** - How do you verify an agent's claims?

### Git-as-Protocol Solutions

| Problem | Solution |
|---------|----------|
| No memory | Identity file persists across sessions |
| Parallel work | Branch-per-agent prevents direct conflicts |
| No coordination | Events.jsonl is the coordination channel |
| Trust | Commit history is cryptographically verifiable |

---

## Advanced: The Mathematics

### Commit Graph as Partial Order

Let C be the set of commits. Define relation ≺ where:

> a ≺ b if a is an ancestor of b

This is a **partial order** (reflexive, antisymmetric, transitive).

When we merge, we create a **join** in the lattice:

```
       c
      / \
     a   b    →    a ≺ c  and  b ≺ c
```

### Vector Clocks Analogy

Each participant's branch acts like a vector clock entry:

```
alice:  [5, -, -]  (5 commits on alice's branch)
bob:    [-, 3, -]  (3 commits on bob's branch)
claude: [-, -, 7]  (7 commits on claude's branch)
```

A merge creates a synchronization point:

```
main after merge: [5, 3, 7]  (incorporates all known events)
```

### Consistency Model

Git provides **eventual consistency** with **causal ordering**:

- **Eventual**: All participants will eventually see all events (via sync)
- **Causal**: If A happened-before B, everyone sees A before B

This is weaker than linearizability but sufficient for coordination.

---

## Implementation Details

### File Structure

```
.brain/
├── self.json                    # Identity (gitignored)
├── messages/
│   └── {name}/
│       └── {timestamp}-{type}.json
├── receipts/
│   └── {name}/
│       └── {timestamp}.json
├── claims/
│   ├── phase-11-claim.json      # Active claim
│   └── phase-11-complete.json   # Completed claim
├── missions/
│   ├── active/
│   ├── completed/
│   └── abandoned/
└── events.jsonl                 # Append-only event log
```

### Event Flow

```
1. User runs command
   └── brain.py send "Hello"

2. Create event file
   └── .brain/messages/claude/20251203-150000-message.json

3. Append to events.jsonl
   └── {"type":"message","from":"claude","body":"Hello","ts":"..."}

4. Git add + commit
   └── git add .brain/ && git commit -m "msg(claude): Hello"

5. (Optional) Push
   └── git push origin dev/claude
```

---

## Future Directions

### Possible Enhancements

1. **GPG Signing** - Require signed commits for higher security
2. **Automated Sync** - GitHub Actions to merge dev/* branches periodically
3. **Conflict Webhooks** - Notify participants of merge conflicts
4. **State Snapshots** - Periodic checkpoints for faster sync
5. **Encryption** - Encrypt sensitive events for specific recipients

### Scaling Considerations

For large teams:
- Use branch hierarchies: `dev/team-a/alice`
- Implement message pagination in events.jsonl
- Add summary events that checkpoint state

---

## Conclusion

Git-as-Protocol transforms version control into a **distributed coordination system**:

- **Commits are messages** with cryptographic integrity
- **Branches are identities** with persistent state
- **Merges are acknowledgments** that prove knowledge
- **History is consensus** that cannot be rewritten

The Brain Protocol builds on these primitives to create a robust, verifiable, and decentralized collaboration system for AI agents and humans alike.

---

## References

- [Git Internals](https://git-scm.com/book/en/v2/Git-Internals-Plumbing-and-Porcelain)
- [Vector Clocks](https://en.wikipedia.org/wiki/Vector_clock)
- [Lamport Timestamps](https://en.wikipedia.org/wiki/Lamport_timestamp)
- [CAP Theorem](https://en.wikipedia.org/wiki/CAP_theorem)
- [CRDTs](https://crdt.tech/) - Related distributed data structures

