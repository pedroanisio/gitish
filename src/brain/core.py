"""
brain/core.py - Shared utilities for the Brain Protocol

This module contains common functionality used across all brain domains.
Following DRY principle: single source of truth for git ops, identity, and I/O.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
import uuid

# =============================================================================
# Configuration - Single source of truth
# =============================================================================

BRAIN_DIR = Path(".brain")
SELF_FILE = BRAIN_DIR / "self.json"
MESSAGES_DIR = BRAIN_DIR / "messages"
RECEIPTS_DIR = BRAIN_DIR / "receipts"
CLAIMS_DIR = BRAIN_DIR / "claims"
EVENTS_FILE = BRAIN_DIR / "events.jsonl"
MISSIONS_DIR = BRAIN_DIR / "missions"
ACTIVE_MISSIONS_DIR = MISSIONS_DIR / "active"
COMPLETED_MISSIONS_DIR = MISSIONS_DIR / "completed"
ABANDONED_MISSIONS_DIR = MISSIONS_DIR / "abandoned"
MISSION_EVENTS_DIR = MISSIONS_DIR / "events"

# Key directories
KEYS_DIR = BRAIN_DIR / "keys"
PRIVATE_KEYS_DIR = KEYS_DIR / "private"
PUBLIC_KEYS_DIR = KEYS_DIR / "public"

# Branch naming
DEV_BRANCH_PREFIX = "dev/"
EVENTS_BRANCH = "brain/events"


# =============================================================================
# Agent Identity - Colors & Emotions
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

AGENT_EMOJI = {
    "claude": "\U0001F7E0",    # Orange
    "gpt": "\U0001F7E2",       # Green
    "gemini": "\U0001F535",    # Blue
    "copilot": "\u26AB",       # Black
    "cursor": "\U0001F7E3",    # Purple
    "codex": "\U0001F7E1",     # Yellow
    "human": "\U0001F464",     # Human
    "default": "\U0001F916",   # Robot
}


# =============================================================================
# Time Utilities
# =============================================================================

def now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


def timestamp_filename() -> str:
    """Generate timestamp for filenames (includes microseconds for uniqueness)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")


# =============================================================================
# ID Generation
# =============================================================================

def generate_id(prefix: str = "id") -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


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
# Directory Management
# =============================================================================

def ensure_brain_dirs():
    """Create .brain directories if they don't exist."""
    for d in [BRAIN_DIR, MESSAGES_DIR, RECEIPTS_DIR, CLAIMS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def ensure_mission_dirs():
    """Create mission directories if they don't exist."""
    for d in [MISSIONS_DIR, ACTIVE_MISSIONS_DIR, COMPLETED_MISSIONS_DIR, ABANDONED_MISSIONS_DIR, MISSION_EVENTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def ensure_key_dirs():
    """Create key directories if they don't exist."""
    PRIVATE_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    PUBLIC_KEYS_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(PRIVATE_KEYS_DIR, 0o700)


def require_project_root():
    """Ensure we're in project root or exit."""
    if not Path("package.json").exists():
        print("\u274C Must run from project root", file=sys.stderr)
        sys.exit(1)


# =============================================================================
# Git Operations - Single implementation (DRY)
# =============================================================================

def run_git(*args, capture=True, check=True) -> subprocess.CompletedProcess:
    """Run a git command."""
    cmd = ["git"] + list(args)
    return subprocess.run(cmd, capture_output=capture, text=True, check=check)


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


def get_short_commit() -> str:
    """Get short HEAD commit hash."""
    return git_output("rev-parse", "--short", "HEAD")


def get_remote_head(branch: str) -> Optional[str]:
    """Get remote HEAD for a branch, or None if doesn't exist."""
    try:
        return git_output("rev-parse", f"origin/{branch}")
    except subprocess.CalledProcessError:
        return None


def safe_commit(message: str, files: list = None) -> tuple[bool, str, str]:
    """
    Commit files with error handling.

    Returns (success, commit_hash, error_message).
    """
    try:
        if files:
            run_git("add", *[str(f) for f in files])
        run_git("commit", "-m", message)
        commit_hash = get_short_commit()
        return True, commit_hash, ""
    except subprocess.CalledProcessError as e:
        error_output = e.stderr if e.stderr else e.stdout if e.stdout else "Unknown error"
        divider = "\u2500" * 50
        details = error_output[:500] if error_output else "(no details)"
        error_msg = f"""
\u274C COMMIT FAILED
{divider}
Command: git commit -m "{message[:50]}..."
Exit code: {e.returncode}

Possible causes:
  \u2022 Pre-commit hook failed (linter errors?)
  \u2022 No changes staged
  \u2022 Git configuration issue

Details:
{details}
{divider}
"""
        print(error_msg, file=sys.stderr)
        return False, "", error_msg


def safe_push(branch: str = None) -> bool:
    """Push to origin, handling missing remote gracefully."""
    try:
        if branch:
            run_git("push", "-u", "origin", branch)
        else:
            run_git("push")
        print(f"\U0001F4E4 Pushed to origin/{branch or 'current'}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\u26A0\uFE0F  Push failed: exit code {e.returncode}", file=sys.stderr)
        return False


# =============================================================================
# Identity Management
# =============================================================================

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
        print("\u274C No identity found. Run: brain init --name YOUR_NAME")
        sys.exit(1)
    return identity


def get_identity_name() -> str:
    """Get identity short name or 'unknown'."""
    identity = load_identity()
    if identity:
        return f"@{identity.get('short_name', 'unknown')}"
    return "@unknown"


def save_identity(identity: dict):
    """Save identity to file."""
    ensure_brain_dirs()
    with open(SELF_FILE, "w") as f:
        json.dump(identity, f, indent=2)
        f.write("\n")
    os.chmod(SELF_FILE, 0o600)


# =============================================================================
# Event Logging
# =============================================================================

def append_event(event: dict):
    """Append event to events.jsonl (local log)."""
    ensure_brain_dirs()
    with open(EVENTS_FILE, "a") as f:
        f.write(json.dumps(event) + "\n")


def read_events(limit: int = 100) -> list:
    """Read events from local log."""
    if not EVENTS_FILE.exists():
        return []
    with open(EVENTS_FILE) as f:
        events = [json.loads(line) for line in f if line.strip()]
    return events[-limit:]


# =============================================================================
# File I/O Helpers
# =============================================================================

def save_json(filepath: Path, data: dict):
    """Save dict to JSON file with trailing newline."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def load_json(filepath: Path) -> Optional[dict]:
    """Load JSON file or return None."""
    if not filepath.exists():
        return None
    try:
        with open(filepath) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


# =============================================================================
# Message Saving (shared by send and other commands)
# =============================================================================

def save_message(identity: dict, msg_type: str, content: dict) -> Path:
    """Save a message file and return its path."""
    ensure_brain_dirs()

    ts = timestamp_filename()
    filename = f"{ts}-{msg_type}.json"
    filepath = MESSAGES_DIR / identity["short_name"] / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)

    try:
        head_commit = get_head_commit()
    except subprocess.CalledProcessError:
        head_commit = None

    message = {
        "type": msg_type,
        "from": identity["short_name"],
        "from_id": identity["full_id"],
        "ts": now_iso(),
        "head_commit": head_commit,
        **content
    }

    save_json(filepath, message)
    return filepath
