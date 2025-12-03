"""
brain/messaging.py - Communication Module

Single Responsibility: Handles all messaging operations.
- send: Message on current branch
- announce: Cross-branch broadcast
- listen: Receive announcements
- log: View local event history
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from .core import (
    BRAIN_DIR, MESSAGES_DIR, EVENTS_FILE, EVENTS_BRANCH,
    now_iso, ensure_brain_dirs,
    run_git, git_output, get_current_branch, get_head_commit,
    require_identity, load_identity,
    append_event, read_events,
    save_message, safe_commit, safe_push, save_json,
)


# =============================================================================
# Commands
# =============================================================================

def cmd_send(args):
    """Send a message on current branch."""
    identity = require_identity()
    message = " ".join(args.message)

    if not message:
        print("\u274C Message cannot be empty")
        sys.exit(1)

    # Save message file
    filepath = save_message(identity, "message", {"body": message})

    # Append to local events
    append_event({
        "type": "message",
        "from": identity["short_name"],
        "body": message,
        "ts": now_iso(),
        "head_commit": get_head_commit()
    })

    # Git commit
    commit_msg = f"msg({identity['short_name']}): {message[:50]}{'...' if len(message) > 50 else ''}"
    success, commit_hash, _ = safe_commit(commit_msg, [str(filepath)])

    if not success:
        print(f"\n\u26A0\uFE0F  Message saved to {filepath} but NOT committed.", file=sys.stderr)
        sys.exit(1)

    print(f"\u2705 Message sent: {message[:60]}{'...' if len(message) > 60 else ''}")
    print(f"\U0001F4DD Commit: {commit_hash}")

    if getattr(args, 'push', False):
        safe_push(get_current_branch())


def cmd_announce(args):
    """
    Announce a message to all participants via shared events branch.

    Pushes to brain/events branch which all participants can fetch.
    """
    identity = require_identity()
    message = " ".join(args.message)

    if not message:
        print("\u274C Message cannot be empty")
        sys.exit(1)

    emoji = identity.get("emoji", "\U0001F916")
    original_branch = get_current_branch()

    print(f"{emoji} Announcing to all participants...")

    # Stash changes
    stash_ts = now_iso().replace(":", "-").replace(".", "-")
    stash_name = f"brain-announce-{stash_ts}"
    stash_result = run_git("stash", "push", "-u", "-m", stash_name, check=False)
    has_stash = "No local changes" not in stash_result.stdout

    # Fetch events branch
    run_git("fetch", "origin", EVENTS_BRANCH, check=False)

    # Check if events branch exists
    result = run_git("branch", "-r", "--list", f"origin/{EVENTS_BRANCH}", check=False)
    events_branch_exists = bool(result.stdout.strip())

    # Checkout events branch
    if events_branch_exists:
        run_git("checkout", EVENTS_BRANCH, check=False)
        run_git("pull", "origin", EVENTS_BRANCH, check=False)
    else:
        try:
            run_git("checkout", "--orphan", EVENTS_BRANCH)
            run_git("rm", "-rf", ".", check=False)
        except subprocess.CalledProcessError:
            run_git("checkout", EVENTS_BRANCH)

    ensure_brain_dirs()

    # Get head from original branch
    try:
        original_head = git_output("rev-parse", original_branch)
    except subprocess.CalledProcessError:
        original_head = None

    event = {
        "type": "announcement",
        "from": identity["short_name"],
        "from_id": identity["full_id"],
        "body": message,
        "ts": now_iso(),
        "source_branch": original_branch,
        "head_commit": original_head
    }

    # Append to shared events
    shared_events_file = BRAIN_DIR / "shared-events.jsonl"
    with open(shared_events_file, "a") as f:
        f.write(json.dumps(event) + "\n")

    run_git("add", str(shared_events_file))

    commit_msg = f"\U0001F4E2 {identity['short_name']}: {message[:50]}{'...' if len(message) > 50 else ''}"

    env = os.environ.copy()
    env["SKIP_SIMPLE_GIT_HOOKS"] = "1"

    try:
        result = subprocess.run(
            ["git", "commit", "-m", commit_msg],
            capture_output=True, text=True, env=env
        )
        if result.returncode == 0:
            print("\u2705 Announcement committed")
        else:
            print("\u26A0\uFE0F  No changes to commit")
    except subprocess.CalledProcessError:
        print("\u26A0\uFE0F  No changes to commit")

    # Push
    try:
        run_git("push", "-u", "origin", EVENTS_BRANCH)
        print(f"\U0001F4E4 Pushed to origin/{EVENTS_BRANCH}")
    except subprocess.CalledProcessError as e:
        print(f"\u26A0\uFE0F  Push failed: {e}", file=sys.stderr)

    # Return to original branch
    checkout_result = run_git("checkout", original_branch, check=False)
    if checkout_result.returncode != 0:
        run_git("checkout", "-f", original_branch)

    # Restore stash
    if has_stash:
        run_git("stash", "pop", check=False)

    print(f"\n\u2705 Announced: {message[:60]}{'...' if len(message) > 60 else ''}")

    # Auto-listen after announce to show all announcements
    print("\n" + "─" * 50)
    cmd_listen(args)


def cmd_listen(args):
    """Listen for announcements from all participants."""
    identity = load_identity()

    print("\U0001F442 Listening for announcements...")

    # Fetch events branch
    try:
        run_git("fetch", "origin", EVENTS_BRANCH)
    except subprocess.CalledProcessError:
        print("\U0001F4ED No announcements yet (brain/events branch doesn't exist)")
        return

    result = run_git("branch", "-r", "--list", f"origin/{EVENTS_BRANCH}", check=False)
    if not result.stdout.strip():
        print("\U0001F4ED No announcements yet")
        return

    # Read events without checkout
    try:
        result = run_git("show", f"origin/{EVENTS_BRANCH}:.brain/shared-events.jsonl", check=False)
        if not result.stdout.strip():
            print("\U0001F4ED No announcements yet")
            return

        events = [json.loads(line) for line in result.stdout.strip().split("\n") if line.strip()]
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        print("\U0001F4ED No announcements yet")
        return

    announcements = [e for e in events if e.get("type") == "announcement"]

    if not announcements:
        print("\U0001F4ED No announcements yet")
        return

    limit = getattr(args, 'limit', 20) or 20
    recent = announcements[-limit:]

    print(f"\n\U0001F4E2 Last {len(recent)} announcements:")
    print("=" * 70)

    for event in recent:
        ts = event.get("ts", "")[:19]
        sender_id = event.get("from_id", event.get("from", "?"))
        sender_short = event.get("from", "?")
        body = event.get("body", "")
        branch = event.get("source_branch", "")

        marker = "\u2192" if identity and sender_short == identity.get("short_name") else " "

        print(f"{marker} [{ts}] @{sender_id} (from {branch}):")
        for i in range(0, len(body), 65):
            print(f"    {body[i:i+65]}")
        print()

    print("=" * 70)
    print("\U0001F4A1 To announce: brain msg announce \"Your message\"")


def cmd_log(args):
    """Show recent events from local log."""
    if not EVENTS_FILE.exists():
        print("\U0001F4ED No events yet")
        return

    limit = getattr(args, 'limit', 20) or 20
    events = read_events(limit)

    print(f"\n\U0001F4DC Last {len(events)} events:")
    print("-" * 60)

    for event in events:
        ts = event.get("ts", "")[:19]
        event_type = event.get("type", "?")

        if event_type == "message":
            body = event.get("body", "")[:50]
            print(f"[{ts}] \U0001F4AC {event.get('from', '?')}: {body}")
        elif event_type == "claim":
            print(f"[{ts}] \U0001F3AF {event.get('developer', '?')} claimed Phase {event.get('phase')}")
        elif event_type == "release":
            print(f"[{ts}] \U0001F513 {event.get('developer', '?')} released Phase {event.get('phase')}")
        elif event_type == "complete":
            print(f"[{ts}] \u2705 {event.get('developer', '?')} completed Phase {event.get('phase')}")
        elif event_type == "read-receipt":
            print(f"[{ts}] \U0001F441\uFE0F {event.get('from', '?')} read up to {event.get('up_to_commit', '?')[:8]}")
        else:
            print(f"[{ts}] \u2753 {event_type}: {event}")

    print("-" * 60)
