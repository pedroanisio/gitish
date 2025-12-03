#!/usr/bin/env python3
"""
brain.py - Decentralized collaboration CLI

A Git-based protocol for multi-participant, proof-of-read collaboration.
Each participant has their own branch and commits messages/claims there.
Periodic sync merges all branches to create unified conversation history.

Commands:
    brain init [--name NAME]     Initialize participant identity
    brain send MESSAGE           Send a message (commit to your branch)
    brain claim PHASE            Claim a phase for work
    brain release PHASE          Release a claimed phase
    brain complete PHASE PR      Mark phase as complete
    brain sync                   Fetch all, merge, show new messages
    brain receipt                Post read receipt (proof you've read current state)
    brain log [--limit N]        Show recent messages
    brain status                 Show current identity and phase claims
    brain phases                 Show all phases and their status

Usage:
    python scripts/brain.py init --name claude
    python scripts/brain.py send "Starting work on Phase 11"
    python scripts/brain.py claim 11
    python scripts/brain.py sync
    python scripts/brain.py receipt
    python scripts/brain.py status
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# =============================================================================
# Configuration
# =============================================================================

BRAIN_DIR = Path(".brain")
SELF_FILE = BRAIN_DIR / "self.json"
MESSAGES_DIR = BRAIN_DIR / "messages"
RECEIPTS_DIR = BRAIN_DIR / "receipts"
CLAIMS_DIR = BRAIN_DIR / "claims"
EVENTS_FILE = BRAIN_DIR / "events.jsonl"

# Key directories
KEYS_DIR = BRAIN_DIR / "keys"
PRIVATE_KEYS_DIR = KEYS_DIR / "private"  # gitignored
PUBLIC_KEYS_DIR = KEYS_DIR / "public"    # committed to repo

# Branch naming
DEV_BRANCH_PREFIX = "dev/"
CLAIMS_BRANCH = "claims/main"
EVENTS_BRANCH = "brain/events"  # Shared events branch for announcements

# =============================================================================
# Identity Generation - Colors & Emotions
# =============================================================================

COLORS = [
    "red", "blue", "green", "gold", "purple", "orange", "cyan", "magenta",
    "coral", "teal", "indigo", "amber", "lime", "rose", "violet", "silver",
    "crimson", "azure", "emerald", "ruby", "sapphire", "jade", "onyx", "pearl"
]

EMOTIONS = [
    "joy", "calm", "wonder", "spark", "glow", "peace", "bliss", "hope",
    "brave", "swift", "keen", "wise", "bold", "zen", "flow", "dream",
    "shine", "grace", "charm", "pride", "trust", "zeal", "muse", "awe"
]

# Agent emoji mappings for fun output
AGENT_EMOJI = {
    "claude": "🟠",      # Orange for Anthropic
    "gpt": "🟢",         # Green for OpenAI
    "gemini": "🔵",      # Blue for Google
    "copilot": "⚫",     # Black for GitHub
    "cursor": "🟣",      # Purple for Cursor
    "codex": "🟡",       # Yellow for Codex
    "human": "👤",       # Human
    "default": "🤖",     # Default robot
}


def generate_color_emotion_id() -> tuple[str, str, str]:
    """Generate a random color-emotion pair for identity."""
    import random
    color = random.choice(COLORS)
    emotion = random.choice(EMOTIONS)
    return color, emotion, f"{color}-{emotion}"


def get_agent_emoji(name: str) -> str:
    """Get emoji for an agent type."""
    name_lower = name.lower()
    for key, emoji in AGENT_EMOJI.items():
        if key in name_lower:
            return emoji
    return AGENT_EMOJI["default"]


# =============================================================================
# Utilities
# =============================================================================

def now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def run_git(*args, capture=True, check=True) -> subprocess.CompletedProcess:
    """Run a git command."""
    cmd = ["git"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check
    )


def git_output(*args) -> str:
    """Run git command and return stdout."""
    result = run_git(*args)
    return result.stdout.strip()


def get_current_branch() -> str:
    """Get current git branch name."""
    return git_output("branch", "--show-current")


def get_head_commit() -> str:
    """Get current HEAD commit hash."""
    return git_output("rev-parse", "HEAD")


def get_remote_head(branch: str) -> Optional[str]:
    """Get remote HEAD for a branch, or None if doesn't exist."""
    try:
        return git_output("rev-parse", f"origin/{branch}")
    except subprocess.CalledProcessError:
        return None


def safe_push(branch: str) -> bool:
    """Push to origin, handling missing remote gracefully."""
    try:
        run_git("push", "origin", branch)
        print(f"📤 Pushed to origin/{branch}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Push failed (no remote?): exit code {e.returncode}", file=sys.stderr)
        return False


def safe_commit(message: str, files: list[str] = None) -> tuple[bool, str]:
    """
    Commit files with error handling.
    
    Returns (success, error_message).
    On failure, prints clear error to stderr and returns False.
    """
    try:
        if files:
            run_git("add", *[str(f) for f in files])
        run_git("commit", "-m", message)
        return True, ""
    except subprocess.CalledProcessError as e:
        # Get the actual error output
        error_output = e.stderr if e.stderr else e.stdout if e.stdout else "Unknown error"
        
        # Provide helpful error message
        error_msg = f"""
❌ COMMIT FAILED
{'─' * 50}
Command: git commit -m "{message[:50]}..."
Exit code: {e.returncode}

Possible causes:
  • Pre-commit hook failed (linter errors?)
  • No changes staged
  • Git configuration issue

Details:
{error_output[:500] if error_output else '(no details)'}
{'─' * 50}

💡 To debug:
   git status
   git diff --cached
   BRAIN_BYPASS_HOOK=1 git commit -m "your message"
"""
        print(error_msg, file=sys.stderr)
        return False, error_msg


# =============================================================================
# Cryptographic Key Management - Uses OpenSSL (no external Python dependencies)
# =============================================================================

def generate_key_pair(identity_name: str) -> tuple[str, str]:
    """
    Generate an Ed25519 key pair for signing.
    Returns (private_key_pem, public_key_pem).

    Uses system OpenSSL to avoid external Python package dependencies.
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        priv_path = Path(tmpdir) / "private.pem"
        pub_path = Path(tmpdir) / "public.pem"

        # Generate private key
        result = subprocess.run(
            ["openssl", "genpkey", "-algorithm", "Ed25519", "-out", str(priv_path)],
            capture_output=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"OpenSSL key generation failed: {result.stderr.decode()}")

        # Extract public key
        result = subprocess.run(
            ["openssl", "pkey", "-in", str(priv_path), "-pubout", "-out", str(pub_path)],
            capture_output=True
        )
        if result.returncode != 0:
            raise RuntimeError(f"OpenSSL public key extraction failed: {result.stderr.decode()}")

        return priv_path.read_text(), pub_path.read_text()


def save_key_pair(identity_name: str, private_pem: str, public_pem: str) -> tuple[Path, Path]:
    """Save key pair to appropriate directories."""
    ensure_key_dirs()
    
    private_path = PRIVATE_KEYS_DIR / f"{identity_name}.pem"
    public_path = PUBLIC_KEYS_DIR / f"{identity_name}.pem"
    
    # Save private key with restricted permissions
    private_path.write_text(private_pem)
    os.chmod(private_path, 0o600)
    
    # Save public key (will be committed)
    public_path.write_text(public_pem)
    
    return private_path, public_path


def load_private_key(identity_name: str) -> Optional[str]:
    """Load private key for identity."""
    private_path = PRIVATE_KEYS_DIR / f"{identity_name}.pem"
    if private_path.exists():
        return private_path.read_text()
    return None


def load_public_key(identity_name: str) -> Optional[str]:
    """Load public key for identity."""
    public_path = PUBLIC_KEYS_DIR / f"{identity_name}.pem"
    if public_path.exists():
        return public_path.read_text()
    return None


def sign_message(message: str, private_pem: str) -> str:
    """
    Sign a message with private key. Returns base64-encoded signature.

    Uses OpenSSL for signing to avoid external Python dependencies.
    """
    import base64
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        priv_path = Path(tmpdir) / "private.pem"
        msg_path = Path(tmpdir) / "message.txt"
        sig_path = Path(tmpdir) / "signature.bin"

        priv_path.write_text(private_pem)
        msg_path.write_text(message)

        result = subprocess.run(
            ["openssl", "pkeyutl", "-sign", "-inkey", str(priv_path),
             "-in", str(msg_path), "-out", str(sig_path)],
            capture_output=True
        )
        if result.returncode != 0:
            # Fallback: use hash as pseudo-signature
            import hashlib
            combined = private_pem + message
            hash_bytes = hashlib.sha256(combined.encode('utf-8')).digest()
            return base64.b64encode(hash_bytes).decode('utf-8')

        return base64.b64encode(sig_path.read_bytes()).decode('utf-8')


def verify_signature(message: str, signature_b64: str, public_pem: str) -> bool:
    """
    Verify a signature. Returns True if valid.

    Uses OpenSSL for verification to avoid external Python dependencies.
    """
    import base64
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        pub_path = Path(tmpdir) / "public.pem"
        msg_path = Path(tmpdir) / "message.txt"
        sig_path = Path(tmpdir) / "signature.bin"

        pub_path.write_text(public_pem)
        msg_path.write_text(message)
        sig_path.write_bytes(base64.b64decode(signature_b64))

        result = subprocess.run(
            ["openssl", "pkeyutl", "-verify", "-pubin", "-inkey", str(pub_path),
             "-in", str(msg_path), "-sigfile", str(sig_path)],
            capture_output=True
        )
        return result.returncode == 0


def get_public_key_fingerprint(public_pem: str) -> str:
    """Get a short fingerprint of a public key."""
    import hashlib
    import base64
    
    # Hash the public key and take first 16 chars
    hash_bytes = hashlib.sha256(public_pem.encode('utf-8')).digest()
    return base64.b64encode(hash_bytes).decode('utf-8')[:16]


def ensure_key_dirs():
    """Create key directories if they don't exist."""
    PRIVATE_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    
    # Ensure private key directory has restricted permissions
    os.chmod(PRIVATE_KEYS_DIR, 0o700)


def ensure_brain_dirs():
    """Create .brain directories if they don't exist."""
    for d in [BRAIN_DIR, MESSAGES_DIR, RECEIPTS_DIR, CLAIMS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def load_identity() -> Optional[dict]:
    """Load participant identity."""
    if not SELF_FILE.exists():
        return None
    try:
        with open(SELF_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def require_identity() -> dict:
    """Load identity or exit with error."""
    identity = load_identity()
    if not identity:
        print("❌ No identity found. Run: python scripts/brain.py init --name YOUR_NAME")
        sys.exit(1)
    return identity


def append_event(event: dict):
    """Append event to events.jsonl."""
    ensure_brain_dirs()
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def save_message(identity: dict, msg_type: str, content: dict) -> Path:
    """Save a message file and return its path."""
    ensure_brain_dirs()
    
    # Include microseconds for uniqueness
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    filename = f"{ts}-{msg_type}.json"
    filepath = MESSAGES_DIR / identity["short_name"] / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Get current HEAD to prove we've seen the latest state
    try:
        head_commit = get_head_commit()
    except:
        head_commit = None
    
    message = {
        "type": msg_type,
        "from": identity["short_name"],
        "from_id": identity["full_id"],
        "ts": now_iso(),
        "head_commit": head_commit,  # Proof-of-read: "I saw up to this commit"
        **content
    }
    
    with open(filepath, "w") as f:
        json.dump(message, f, indent=2)
        f.write("\n")  # Trailing newline for Biome
    
    return filepath


# =============================================================================
# Commands
# =============================================================================

def cmd_init(args):
    """Initialize participant identity."""
    import uuid
    import re
    
    SHORT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,23}$")
    
    def validate_name(name):
        if not name or len(name) < 2 or len(name) > 24:
            return False
        return bool(SHORT_NAME_PATTERN.match(name))
    
    existing = load_identity()
    
    if existing and not args.reset:
        print("✅ Identity already exists:")
        cmd_status(args)
        return
    
    if args.name:
        short_name = args.name.lower()
        if not validate_name(short_name):
            print("❌ Invalid name. Use 2-24 chars, start with letter, only a-z 0-9 - _")
            sys.exit(1)
    elif existing:
        short_name = existing["short_name"]
    else:
        print("Enter short name (e.g., claude, gpt, gemini, human):")
        short_name = input("> ").strip().lower()
        if not validate_name(short_name):
            print("❌ Invalid name")
            sys.exit(1)
    
    # Generate color-emotion identity
    color, emotion, color_emotion = generate_color_emotion_id()
    emoji = get_agent_emoji(short_name)
    full_id = f"{short_name}-{color}-{emotion}"
    
    print(f"\n{emoji} Generating identity for @{short_name}...")
    print(f"   🎨 Color:   {color}")
    print(f"   💫 Emotion: {emotion}")
    print(f"   🏷️  Full ID: {full_id}")
    
    # Generate cryptographic key pair
    print("\n🔐 Generating Ed25519 key pair...")
    try:
        private_pem, public_pem = generate_key_pair(short_name)
        private_path, public_path = save_key_pair(short_name, private_pem, public_pem)
        public_key_fingerprint = get_public_key_fingerprint(public_pem)
        has_keys = True
        print(f"✅ Keys generated")
        print(f"   📁 Private: {private_path} (gitignored)")
        print(f"   📁 Public:  {public_path} (committed to repo)")
        print(f"   🔑 Fingerprint: {public_key_fingerprint}")
    except Exception as e:
        print(f"⚠️  Key generation failed: {e}")
        print("   Continuing without cryptographic keys (signing disabled)")
        public_key_fingerprint = None
        has_keys = False
    
    identity = {
        "uuid": str(uuid.uuid4()),
        "short_name": short_name,
        "color": color,
        "emotion": emotion,
        "full_id": full_id,
        "emoji": emoji,
        "created_at": now_iso(),
        "version": 3,
        "has_keys": has_keys,
        "public_key_fingerprint": public_key_fingerprint
    }
    
    ensure_brain_dirs()
    with open(SELF_FILE, "w") as f:
        json.dump(identity, f, indent=2)
        f.write("\n")  # Trailing newline for Biome
    os.chmod(SELF_FILE, 0o600)
    
    print(f"\n✅ Identity created: {emoji} {full_id}")
    print(f"📁 Saved to: {SELF_FILE}")
    
    # Commit public key to repo
    if has_keys:
        print("📤 Committing public key to repository...")
        success, error = safe_commit(f"brain: add public key for {short_name}", [str(public_path)])
        if success:
            print(f"✅ Public key committed")
        else:
            print(f"⚠️  Public key saved but NOT committed. Commit manually.", file=sys.stderr)


def cmd_send(args):
    """Send a message."""
    identity = require_identity()
    message = " ".join(args.message)
    
    if not message:
        print("❌ Message cannot be empty")
        sys.exit(1)
    
    # Save message file
    filepath = save_message(identity, "message", {"body": message})
    
    # Append to events (with proof-of-read)
    append_event({
        "type": "message",
        "from": identity["short_name"],
        "body": message,
        "ts": now_iso(),
        "head_commit": get_head_commit()  # Proof: "I saw up to this commit"
    })
    
    # Git add and commit (only message file, not events.jsonl which is gitignored)
    commit_msg = f"msg({identity['short_name']}): {message[:50]}{'...' if len(message) > 50 else ''}"
    success, error = safe_commit(commit_msg, [str(filepath)])
    
    if not success:
        # Clean up on failure
        print(f"\n⚠️  Message saved to {filepath} but NOT committed.", file=sys.stderr)
        print("   Run 'git add' and 'git commit' manually after fixing issues.", file=sys.stderr)
        sys.exit(1)
    
    print(f"✅ Message sent: {message[:60]}{'...' if len(message) > 60 else ''}")
    print(f"📝 Commit: {get_head_commit()[:8]}")
    
    if args.push:
        safe_push(get_current_branch())


def cmd_claim(args):
    """Claim a phase."""
    identity = require_identity()
    phase = args.phase
    
    # Create claim event
    event = {
        "type": "claim",
        "phase": phase,
        "developer": f"@{identity['short_name']}",
        "developer_id": identity["full_id"],
        "branch": f"{DEV_BRANCH_PREFIX}{identity['short_name']}/phase-{phase}",
        "ts": now_iso(),
        "head_at_claim": get_head_commit()
    }
    
    # Save claim file
    claim_file = CLAIMS_DIR / f"phase-{phase}-claim.json"
    with open(claim_file, "w") as f:
        json.dump(event, f, indent=2)
        f.write("\n")  # Trailing newline for Biome
    
    # Append to events
    append_event(event)
    
    # Save message
    save_message(identity, "claim", {"phase": phase})
    
    # Git add and commit
    run_git("add", "-A")
    success, error = safe_commit(f"claim: Phase {phase} by @{identity['short_name']}")
    
    if not success:
        print(f"\n⚠️  Claim saved but NOT committed.", file=sys.stderr)
        sys.exit(1)
    
    print(f"✅ Claimed Phase {phase}")
    print(f"📝 Commit: {get_head_commit()[:8]}")
    print(f"🌿 Suggested branch: {event['branch']}")
    
    if args.push:
        safe_push(get_current_branch())


def cmd_release(args):
    """Release a claimed phase."""
    identity = require_identity()
    phase = args.phase
    reason = args.reason or "released"
    
    event = {
        "type": "release",
        "phase": phase,
        "developer": f"@{identity['short_name']}",
        "reason": reason,
        "ts": now_iso()
    }
    
    # Remove claim file if exists
    claim_file = CLAIMS_DIR / f"phase-{phase}-claim.json"
    if claim_file.exists():
        claim_file.unlink()
    
    append_event(event)
    save_message(identity, "release", {"phase": phase, "reason": reason})
    
    run_git("add", "-A")
    success, error = safe_commit(f"release: Phase {phase} by @{identity['short_name']} ({reason})")
    
    if not success:
        print(f"\n⚠️  Release saved but NOT committed.", file=sys.stderr)
        sys.exit(1)
    
    print(f"✅ Released Phase {phase}: {reason}")
    
    if args.push:
        safe_push(get_current_branch())


def cmd_complete(args):
    """Mark phase as complete."""
    identity = require_identity()
    phase = args.phase
    pr = args.pr
    
    event = {
        "type": "complete",
        "phase": phase,
        "developer": f"@{identity['short_name']}",
        "pr": pr,
        "merge_commit": get_head_commit(),
        "ts": now_iso()
    }
    
    # Remove claim file
    claim_file = CLAIMS_DIR / f"phase-{phase}-claim.json"
    if claim_file.exists():
        claim_file.unlink()
    
    # Create completion file
    complete_file = CLAIMS_DIR / f"phase-{phase}-complete.json"
    with open(complete_file, "w") as f:
        json.dump(event, f, indent=2)
        f.write("\n")  # Trailing newline for Biome
    
    append_event(event)
    save_message(identity, "complete", {"phase": phase, "pr": pr})
    
    run_git("add", "-A")
    success, error = safe_commit(f"complete: Phase {phase} (PR {pr}) by @{identity['short_name']}")
    
    if not success:
        print(f"\n⚠️  Completion saved but NOT committed.", file=sys.stderr)
        sys.exit(1)
    
    print(f"✅ Phase {phase} marked complete (PR {pr})")
    
    if args.push:
        safe_push(get_current_branch())


def cmd_receipt(args):
    """Post a read receipt."""
    identity = require_identity()
    
    # Get current state
    run_git("fetch", "--all", check=False)
    current_head = get_head_commit()
    
    # Create receipt
    receipt = {
        "type": "read-receipt",
        "from": identity["short_name"],
        "from_id": identity["full_id"],
        "up_to_commit": current_head,
        "ts": now_iso()
    }
    
    # Save receipt file
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    receipt_file = RECEIPTS_DIR / identity["short_name"] / f"{ts}.json"
    receipt_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(receipt_file, "w") as f:
        json.dump(receipt, f, indent=2)
        f.write("\n")  # Trailing newline for Biome
    
    append_event(receipt)  # Local event log (gitignored)
    
    success, error = safe_commit(
        f"receipt({identity['short_name']}): read up to {current_head[:8]}",
        [str(receipt_file)]  # Only commit receipt file, not events.jsonl (gitignored)
    )
    
    if not success:
        print(f"\n⚠️  Receipt saved but NOT committed.", file=sys.stderr)
        sys.exit(1)
    
    print(f"✅ Read receipt posted")
    print(f"📍 Up to commit: {current_head[:8]}")
    
    if args.push:
        safe_push(get_current_branch())


def cmd_sync(args):
    """Sync with all remote branches."""
    identity = require_identity()
    
    print("🔄 Fetching all branches...")
    run_git("fetch", "--all")
    
    # Get list of dev/* branches
    result = run_git("branch", "-r", "--list", "origin/dev/*")
    dev_branches = [b.strip() for b in result.stdout.split("\n") if b.strip()]
    
    if not dev_branches:
        print("📭 No dev/* branches found")
        return
    
    print(f"📥 Found {len(dev_branches)} dev branches")
    
    # Show recent events from each branch
    print("\n📨 Recent messages:")
    print("-" * 60)
    
    for branch in dev_branches[:10]:  # Limit to 10 branches
        dev_name = branch.replace("origin/dev/", "").split("/")[0]
        
        # Get recent commits from this branch
        try:
            result = run_git(
                "log", branch, "--oneline", "-5",
                "--grep=msg(", "--grep=claim:", "--grep=complete:",
                check=False
            )
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n")[:3]:
                    print(f"  [{dev_name}] {line}")
        except:
            pass
    
    print("-" * 60)
    print(f"\n✅ Synced. You are: @{identity['short_name']}")


def cmd_announce(args):
    """
    Announce a message to all participants via shared events branch.
    
    This pushes to brain/events branch which all participants can fetch,
    regardless of which feature branch they're working on.
    """
    identity = require_identity()
    message = " ".join(args.message)
    
    if not message:
        print("❌ Message cannot be empty")
        sys.exit(1)
    
    emoji = identity.get("emoji", "🤖")
    
    # Save current branch to return to it
    original_branch = get_current_branch()
    
    print(f"{emoji} Announcing to all participants...")
    
    # Stash all changes (including untracked) with timestamp
    stash_ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    stash_name = f"brain-announce-{stash_ts}"
    stash_result = run_git("stash", "push", "-u", "-m", stash_name, check=False)
    has_stash = "No local changes" not in stash_result.stdout
    
    # Fetch latest events branch
    run_git("fetch", "origin", EVENTS_BRANCH, check=False)
    
    # Check if events branch exists remotely
    result = run_git("branch", "-r", "--list", f"origin/{EVENTS_BRANCH}", check=False)
    events_branch_exists = bool(result.stdout.strip())
    
    # Create or checkout events branch
    if events_branch_exists:
        # Checkout and update from remote
        run_git("checkout", EVENTS_BRANCH, check=False)
        run_git("pull", "origin", EVENTS_BRANCH, check=False)
    else:
        # Create orphan branch for events (no history from main)
        try:
            run_git("checkout", "--orphan", EVENTS_BRANCH)
            # Remove all files from staging
            run_git("rm", "-rf", ".", check=False)
        except subprocess.CalledProcessError:
            # Branch might exist locally
            run_git("checkout", EVENTS_BRANCH)
    
    # Ensure .brain directory exists on events branch
    ensure_brain_dirs()
    
    # Create announcement event (with proof-of-read from original branch)
    ts = now_iso()
    
    # Get the head commit from original branch before switching
    try:
        original_head = git_output("rev-parse", f"{original_branch}")
    except:
        original_head = None
    
    event = {
        "type": "announcement",
        "from": identity["short_name"],
        "from_id": identity["full_id"],
        "body": message,
        "ts": ts,
        "source_branch": original_branch,
        "head_commit": original_head  # Proof: "I saw up to this commit on my branch"
    }
    
    # Append to shared events file
    shared_events_file = BRAIN_DIR / "shared-events.jsonl"
    with open(shared_events_file, "a") as f:
        f.write(json.dumps(event) + "\n")
    
    # Commit and push (bypass hooks since brain/events is an orphan branch)
    run_git("add", str(shared_events_file))
    
    commit_msg = f"📢 {identity['short_name']}: {message[:50]}{'...' if len(message) > 50 else ''}"
    
    # Use env to bypass pre-commit hooks on orphan branch
    env = os.environ.copy()
    env["SKIP_SIMPLE_GIT_HOOKS"] = "1"
    
    try:
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=os.getcwd(),
            capture_output=True,
            text=True,
            env=env
        )
        if result.returncode == 0:
            print(f"✅ Announcement committed")
        else:
            print("⚠️  No changes to commit (maybe duplicate?)")
    except subprocess.CalledProcessError:
        print("⚠️  No changes to commit (maybe duplicate?)")
    
    # Push to remote
    try:
        run_git("push", "-u", "origin", EVENTS_BRANCH)
        print(f"📤 Pushed to origin/{EVENTS_BRANCH}")
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Push failed: {e}", file=sys.stderr)
    
    # Return to original branch (force if needed due to orphan branch state)
    checkout_result = run_git("checkout", original_branch, check=False)
    if checkout_result.returncode != 0:
        # Force checkout if normal fails (orphan branch has no common files)
        run_git("checkout", "-f", original_branch)
    
    # Restore and drop stash
    if has_stash:
        run_git("stash", "pop", check=False)
        # Drop stash entry if pop failed (conflict) - find by name
        stash_list = run_git("stash", "list", check=False)
        for i, line in enumerate(stash_list.stdout.splitlines()):
            if stash_name in line:
                run_git("stash", "drop", f"stash@{{{i}}}", check=False)
                break
    
    print(f"\n✅ Announcement sent: {message[:60]}{'...' if len(message) > 60 else ''}")
    print(f"📣 All participants will see this via: brain.py listen")


def cmd_listen(args):
    """
    Listen for announcements from all participants.
    
    Fetches the shared brain/events branch and shows recent announcements.
    """
    identity = load_identity()
    
    print("👂 Listening for announcements...")
    
    # Fetch events branch
    try:
        run_git("fetch", "origin", EVENTS_BRANCH)
    except subprocess.CalledProcessError:
        print("📭 No announcements yet (brain/events branch doesn't exist)")
        return
    
    # Check if events branch exists
    result = run_git("branch", "-r", "--list", f"origin/{EVENTS_BRANCH}", check=False)
    if not result.stdout.strip():
        print("📭 No announcements yet")
        return
    
    # Read shared events from remote branch without checking out
    try:
        result = run_git("show", f"origin/{EVENTS_BRANCH}:.brain/shared-events.jsonl", check=False)
        if not result.stdout.strip():
            print("📭 No announcements yet")
            return
        
        events = [json.loads(line) for line in result.stdout.strip().split("\n") if line.strip()]
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        print("📭 No announcements yet")
        return
    
    # Filter to announcements only
    announcements = [e for e in events if e.get("type") == "announcement"]
    
    if not announcements:
        print("📭 No announcements yet")
        return
    
    # Show recent announcements
    limit = args.limit if hasattr(args, 'limit') and args.limit else 20
    recent = announcements[-limit:]
    
    print(f"\n📢 Last {len(recent)} announcements:")
    print("=" * 70)
    
    for event in recent:
        ts = event.get("ts", "")[:19]
        sender_id = event.get("from_id", event.get("from", "?"))  # Use full identity (color+emotion)
        sender_short = event.get("from", "?")
        body = event.get("body", "")
        branch = event.get("source_branch", "")
        
        # Highlight if from current user
        marker = "→" if identity and sender_short == identity.get("short_name") else " "
        
        print(f"{marker} [{ts}] @{sender_id} (from {branch}):")
        # Word wrap long messages
        for i in range(0, len(body), 65):
            prefix = "    " if i > 0 else "    "
            print(f"{prefix}{body[i:i+65]}")
        print()
    
    print("=" * 70)
    print(f"💡 To announce: python scripts/brain.py announce \"Your message\"")


def cmd_log(args):
    """Show recent events from events.jsonl."""
    if not EVENTS_FILE.exists():
        print("📭 No events yet")
        return
    
    with open(EVENTS_FILE) as f:
        events = [json.loads(line) for line in f if line.strip()]
    
    limit = args.limit or 20
    recent = events[-limit:]
    
    print(f"\n📜 Last {len(recent)} events:")
    print("-" * 60)
    
    for event in recent:
        ts = event.get("ts", "")[:19]
        event_type = event.get("type", "?")
        
        if event_type == "message":
            body = event.get("body", "")[:50]
            print(f"[{ts}] 💬 {event.get('from', '?')}: {body}")
        elif event_type == "claim":
            print(f"[{ts}] 🎯 {event.get('developer', '?')} claimed Phase {event.get('phase')}")
        elif event_type == "release":
            print(f"[{ts}] 🔓 {event.get('developer', '?')} released Phase {event.get('phase')}")
        elif event_type == "complete":
            print(f"[{ts}] ✅ {event.get('developer', '?')} completed Phase {event.get('phase')}")
        elif event_type == "read-receipt":
            print(f"[{ts}] 👁️ {event.get('from', '?')} read up to {event.get('up_to_commit', '?')[:8]}")
        else:
            print(f"[{ts}] ❓ {event_type}: {event}")
    
    print("-" * 60)


def cmd_status(args):
    """Show current status."""
    identity = load_identity()
    
    print()
    print("┌─────────────────────────────────────────────────────────┐")
    print("│                    🧠 BRAIN STATUS                      │")
    print("├─────────────────────────────────────────────────────────┤")
    
    if identity:
        emoji = identity.get("emoji", get_agent_emoji(identity["short_name"]))
        print(f"│  {emoji} Identity: @{identity['short_name']:<39} │")
        print(f"│  Full ID:     {identity['full_id']:<42} │")
        
        # Show color and emotion (v3+)
        color = identity.get("color")
        emotion = identity.get("emotion")
        if color and emotion:
            print(f"│  🎨 Color:    {color:<42} │")
            print(f"│  💫 Emotion:  {emotion:<42} │")
        
        # Show key status
        has_keys = identity.get("has_keys", False)
        if has_keys:
            fingerprint = identity.get("public_key_fingerprint", "N/A")
            print(f"│  🔑 Keys:     ✅ Configured                            │")
            print(f"│  Fingerprint: {fingerprint:<42} │")
        else:
            print(f"│  🔑 Keys:     ❌ Not configured                         │")
    else:
        print("│  Identity:    ❌ Not initialized                        │")
    
    print(f"│  Branch:      {get_current_branch():<42} │")
    print(f"│  HEAD:        {get_head_commit()[:8]:<42} │")
    
    # Count events
    event_count = 0
    if EVENTS_FILE.exists():
        with open(EVENTS_FILE) as f:
            event_count = sum(1 for _ in f)
    print(f"│  Events:      {event_count:<42} │")
    
    # Show active claims
    print("├─────────────────────────────────────────────────────────┤")
    print("│  Active Claims:                                        │")
    
    claims = list(CLAIMS_DIR.glob("*-claim.json")) if CLAIMS_DIR.exists() else []
    if claims:
        for claim_file in claims[:5]:
            with open(claim_file) as f:
                claim = json.load(f)
            phase = claim.get("phase", "?")
            dev = claim.get("developer", "?")
            print(f"│    Phase {phase}: {dev:<44} │")
    else:
        print("│    (none)                                               │")
    
    print("└─────────────────────────────────────────────────────────┘")
    print()


def cmd_phases(args):
    """Show all phases from .brain/claims/."""
    claims_dir = BRAIN_DIR / "claims"
    
    print("\n🧠 Phase Claims:")
    print("-" * 70)
    
    if not claims_dir.exists():
        print("   (no claims directory)")
        print("-" * 70)
        return
    
    # Collect all claims and completions
    active_claims = []
    completed = []
    
    for claim_file in sorted(claims_dir.glob("*.json")):
        try:
            with open(claim_file) as f:
                data = json.load(f)
            
            phase = data.get("phase", "?")
            developer = data.get("developer", "?")
            developer_id = data.get("developer_id", "")
            claim_type = data.get("type", "?")
            
            if claim_type == "claim":
                branch = data.get("branch", "-")
                ts = data.get("ts", "-")
                if ts != "-":
                    ts = ts[:10]  # Just the date
                active_claims.append({
                    "phase": phase,
                    "developer": developer,
                    "developer_id": developer_id,
                    "branch": branch,
                    "ts": ts
                })
            elif claim_type == "complete":
                pr = data.get("pr", "-")
                completed.append({
                    "phase": phase,
                    "developer": developer,
                    "pr": pr
                })
        except (json.JSONDecodeError, KeyError):
            continue
    
    # Display active claims
    if active_claims:
        print("  Active Claims:")
        for claim in sorted(active_claims, key=lambda x: x["phase"]):
            dev_display = claim["developer_id"] or claim["developer"]
            print(f"    🟡 Phase {claim['phase']}: {dev_display}")
            print(f"       Branch: {claim['branch']}")
            print(f"       Started: {claim['ts']}")
    else:
        print("   (no active claims)")
    
    # Display completed
    if completed:
        print("\n  Completed:")
        for comp in sorted(completed, key=lambda x: x["phase"]):
            print(f"    ✅ Phase {comp['phase']}: {comp['developer']} (PR: {comp['pr']})")
    
    print("-" * 70)


def cmd_keys(args):
    """Manage cryptographic keys."""
    identity = load_identity()
    
    if args.subcommand == "show":
        print()
        print("┌─────────────────────────────────────────────────────────┐")
        print("│                    🔑 KEY STATUS                        │")
        print("├─────────────────────────────────────────────────────────┤")
        
        if not identity:
            print("│  ❌ No identity found. Run: brain init               │")
            print("└─────────────────────────────────────────────────────────┘")
            return
        
        short_name = identity["short_name"]
        
        # Check private key
        private_path = PRIVATE_KEYS_DIR / f"{short_name}.pem"
        if private_path.exists():
            print(f"│  Private Key: ✅ {private_path}  │")
        else:
            print(f"│  Private Key: ❌ Not found                             │")
        
        # Check public key
        public_path = PUBLIC_KEYS_DIR / f"{short_name}.pem"
        if public_path.exists():
            print(f"│  Public Key:  ✅ {public_path}   │")
            public_pem = public_path.read_text()
            fingerprint = get_public_key_fingerprint(public_pem)
            print(f"│  Fingerprint: {fingerprint:<42} │")
        else:
            print(f"│  Public Key:  ❌ Not found                             │")
        
        # List all public keys in repo
        print("├─────────────────────────────────────────────────────────┤")
        print("│  Known Participants (Public Keys):                      │")
        
        if PUBLIC_KEYS_DIR.exists():
            for key_file in sorted(PUBLIC_KEYS_DIR.glob("*.pem")):
                name = key_file.stem
                pub_pem = key_file.read_text()
                fp = get_public_key_fingerprint(pub_pem)
                is_me = " (you)" if name == short_name else ""
                print(f"│    @{name:<20} {fp:<16}{is_me:<8} │")
        else:
            print("│    (none)                                              │")
        
        print("└─────────────────────────────────────────────────────────┘")
    
    elif args.subcommand == "verify":
        # Verify a participant's public key
        target = args.name
        if not target:
            print("❌ Usage: brain keys verify <name>")
            sys.exit(1)
        
        public_path = PUBLIC_KEYS_DIR / f"{target}.pem"
        if not public_path.exists():
            print(f"❌ No public key found for @{target}")
            sys.exit(1)
        
        public_pem = public_path.read_text()
        fingerprint = get_public_key_fingerprint(public_pem)
        
        print(f"✅ Public key for @{target}")
        print(f"   Fingerprint: {fingerprint}")
        print(f"   File: {public_path}")
        print()
        print("   Key contents:")
        print("-" * 60)
        print(public_pem)
        print("-" * 60)
    
    elif args.subcommand == "sign":
        # Sign a test message
        identity = require_identity()
        message = args.message or "test message"
        
        private_pem = load_private_key(identity["short_name"])
        if not private_pem:
            print("❌ No private key found")
            sys.exit(1)
        
        signature = sign_message(message, private_pem)
        print(f"📝 Message: {message}")
        print(f"🔐 Signature: {signature}")
    
    elif args.subcommand == "check":
        # Verify a signature
        target = args.name
        message = args.message
        signature = args.signature
        
        if not all([target, message, signature]):
            print("❌ Usage: brain keys check <name> <message> <signature>")
            sys.exit(1)
        
        public_pem = load_public_key(target)
        if not public_pem:
            print(f"❌ No public key found for @{target}")
            sys.exit(1)
        
        if verify_signature(message, signature, public_pem):
            print(f"✅ Signature valid: message was signed by @{target}")
        else:
            print(f"❌ Signature invalid: message was NOT signed by @{target}")
            sys.exit(1)
    
    elif args.subcommand == "regenerate":
        # Regenerate keys for current identity
        identity = require_identity()
        short_name = identity["short_name"]
        
        print(f"⚠️  This will regenerate keys for @{short_name}")
        print("   Your old signatures will become invalid.")
        confirm = input("   Continue? [y/N]: ").strip().lower()
        
        if confirm != "y":
            print("Cancelled.")
            return
        
        print("🔐 Generating new Ed25519 key pair...")
        private_pem, public_pem = generate_key_pair(short_name)
        private_path, public_path = save_key_pair(short_name, private_pem, public_pem)
        fingerprint = get_public_key_fingerprint(public_pem)
        
        # Update identity
        identity["has_keys"] = True
        identity["public_key_fingerprint"] = fingerprint
        identity["keys_regenerated_at"] = now_iso()
        
        with open(SELF_FILE, "w") as f:
            json.dump(identity, f, indent=2)
        
        print(f"✅ New keys generated")
        print(f"   Fingerprint: {fingerprint}")
        
        # Commit new public key
        run_git("add", str(public_path))
        run_git("commit", "-m", f"brain: regenerate public key for {short_name}")
        print(f"✅ Public key committed to repository")
    
    else:
        print("Usage: brain keys [show|verify|sign|check|regenerate]")
        sys.exit(1)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Decentralized collaboration CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  brain.py init --name claude       Initialize identity
  brain.py send "Hello team!"       Send a message
  brain.py claim 11                 Claim phase 11
  brain.py sync                     Sync with all branches
  brain.py receipt                  Post read receipt
  brain.py status                   Show current status
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # init
    p_init = subparsers.add_parser("init", help="Initialize participant identity")
    p_init.add_argument("--name", "-n", help="Short name")
    p_init.add_argument("--reset", "-r", action="store_true", help="Reset identity")
    
    # send
    p_send = subparsers.add_parser("send", help="Send a message")
    p_send.add_argument("message", nargs="+", help="Message to send")
    p_send.add_argument("--push", "-p", action="store_true", help="Push after commit")
    
    # claim
    p_claim = subparsers.add_parser("claim", help="Claim a phase")
    p_claim.add_argument("phase", type=int, help="Phase number")
    p_claim.add_argument("--push", "-p", action="store_true", help="Push after commit")
    
    # release
    p_release = subparsers.add_parser("release", help="Release a claimed phase")
    p_release.add_argument("phase", type=int, help="Phase number")
    p_release.add_argument("--reason", "-r", help="Reason for release")
    p_release.add_argument("--push", "-p", action="store_true", help="Push after commit")
    
    # complete
    p_complete = subparsers.add_parser("complete", help="Mark phase as complete")
    p_complete.add_argument("phase", type=int, help="Phase number")
    p_complete.add_argument("pr", help="PR number or URL")
    p_complete.add_argument("--push", "-p", action="store_true", help="Push after commit")
    
    # receipt
    p_receipt = subparsers.add_parser("receipt", help="Post read receipt")
    p_receipt.add_argument("--push", "-p", action="store_true", help="Push after commit")
    
    # sync
    p_sync = subparsers.add_parser("sync", help="Sync with all remote branches")
    
    # announce
    p_announce = subparsers.add_parser("announce", help="Announce message to ALL participants (cross-branch)")
    p_announce.add_argument("message", nargs="+", help="Message to announce")
    
    # listen
    p_listen = subparsers.add_parser("listen", help="Listen for announcements from all participants")
    p_listen.add_argument("--limit", "-n", type=int, default=20, help="Number of announcements to show")
    
    # log
    p_log = subparsers.add_parser("log", help="Show recent events")
    p_log.add_argument("--limit", "-n", type=int, default=20, help="Number of events")
    
    # status
    p_status = subparsers.add_parser("status", help="Show current status")
    
    # phases
    p_phases = subparsers.add_parser("phases", help="Show all phases")
    
    # keys
    p_keys = subparsers.add_parser("keys", help="Manage cryptographic keys")
    p_keys.add_argument("subcommand", nargs="?", default="show",
                        choices=["show", "verify", "sign", "check", "regenerate"],
                        help="Keys subcommand")
    p_keys.add_argument("name", nargs="?", help="Participant name (for verify/check)")
    p_keys.add_argument("message", nargs="?", help="Message (for sign/check)")
    p_keys.add_argument("signature", nargs="?", help="Signature (for check)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Ensure we're in project root
    if not Path("package.json").exists():
        print("❌ Must run from project root", file=sys.stderr)
        sys.exit(1)
    
    # Dispatch command
    commands = {
        "init": cmd_init,
        "send": cmd_send,
        "claim": cmd_claim,
        "release": cmd_release,
        "complete": cmd_complete,
        "receipt": cmd_receipt,
        "sync": cmd_sync,
        "announce": cmd_announce,
        "listen": cmd_listen,
        "log": cmd_log,
        "status": cmd_status,
        "phases": cmd_phases,
        "keys": cmd_keys,
    }
    
    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

