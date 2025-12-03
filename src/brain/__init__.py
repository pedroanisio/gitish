"""
brain - Unified CLI for AI Agent Collaboration

Combines:
- Identity management (init, status, keys)
- Messaging (msg send, msg announce, msg listen)
- Phase coordination (phase claim, phase complete)
- Mission management (mission create, task add, gate dod)
"""

__version__ = "2.0.0"

# =============================================================================
# Backward compatibility re-exports for existing tests
# =============================================================================

# Core paths and utilities
from brain.core import (
    BRAIN_DIR,
    SELF_FILE,
    MESSAGES_DIR,
    RECEIPTS_DIR,
    CLAIMS_DIR,
    EVENTS_FILE,
    KEYS_DIR,
    PRIVATE_KEYS_DIR,
    PUBLIC_KEYS_DIR,
    MISSIONS_DIR,
    ACTIVE_MISSIONS_DIR,
    COMPLETED_MISSIONS_DIR,
    ABANDONED_MISSIONS_DIR,
    DEV_BRANCH_PREFIX,
    EVENTS_BRANCH,
    COLORS,
    EMOTIONS,
    AGENT_EMOJI,
    now_iso,
    timestamp_filename,
    ensure_brain_dirs,
    ensure_mission_dirs,
    ensure_key_dirs,
    load_identity,
    require_identity,
    save_identity,
    save_message,
    append_event,
    read_events,
    safe_commit,
    safe_push,
    get_current_branch,
    get_head_commit,
    get_short_commit,
    get_remote_head,
    run_git,
    git_output,
    save_json,
    load_json,
)

# Messaging commands
from brain.messaging import (
    cmd_send,
    cmd_announce,
    cmd_listen,
    cmd_log,
)

# Identity commands
from brain.identity import (
    generate_key_pair,
    save_key_pair,
    load_private_key,
    load_public_key,
    cmd_init,
    cmd_status,
    cmd_keys,
)

# Phase commands
from brain.phases import (
    cmd_claim,
    cmd_release,
    cmd_complete,
    cmd_phases,
    cmd_sync,
    cmd_receipt,
)

# CLI entry point
from brain.cli import main
