"""
brain/phases.py - Phase Coordination Module

Multi-Agent Hierarchy:
    Mission (see missions.py)
        └── Phase (THIS MODULE - coordination unit, one agent at a time)
             └── Task (see missions.py)

Phases prevent conflicts when multiple agents work on shared code.
Each phase is claimed by exactly one agent via git-backed claims.

Commands:
- phase claim <N>: Claim a phase (prevents other agents from claiming)
- phase release <N>: Release a claimed phase
- phase complete <N> <PR>: Mark phase complete with PR reference
- phase list: Show all phases and their status
- sync: Fetch all remote branches and show activity
- receipt: Post cryptographic read receipt (proof-of-read)

Storage: .brain/claims/ (git-tracked, multi-agent aware)
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .core import (
    BRAIN_DIR, CLAIMS_DIR, RECEIPTS_DIR, DEV_BRANCH_PREFIX,
    now_iso, ensure_brain_dirs,
    run_git, git_output, get_current_branch, get_head_commit,
    require_identity,
    append_event, save_message, save_json,
    safe_commit, safe_push,
)


# =============================================================================
# Commands
# =============================================================================

def cmd_claim(args):
    """Claim a phase for work."""
    identity = require_identity()
    phase = args.phase

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
    ensure_brain_dirs()
    CLAIMS_DIR.mkdir(parents=True, exist_ok=True)
    claim_file = CLAIMS_DIR / f"phase-{phase}-claim.json"
    save_json(claim_file, event)

    # Append to local events
    append_event(event)

    # Save message
    save_message(identity, "claim", {"phase": phase})

    # Git commit
    run_git("add", "-A")
    success, commit_hash, _ = safe_commit(f"claim: Phase {phase} by @{identity['short_name']}")

    if not success:
        print("\n\u26A0\uFE0F  Claim saved but NOT committed.", file=sys.stderr)
        sys.exit(1)

    print(f"\u2705 Claimed Phase {phase}")
    print(f"\U0001F4DD Commit: {commit_hash}")
    print(f"\U0001F33F Suggested branch: {event['branch']}")

    if getattr(args, 'push', False):
        safe_push(get_current_branch())


def cmd_release(args):
    """Release a claimed phase."""
    identity = require_identity()
    phase = args.phase
    reason = getattr(args, 'reason', None) or "released"

    event = {
        "type": "release",
        "phase": phase,
        "developer": f"@{identity['short_name']}",
        "reason": reason,
        "ts": now_iso()
    }

    # Remove claim file
    claim_file = CLAIMS_DIR / f"phase-{phase}-claim.json"
    if claim_file.exists():
        claim_file.unlink()

    append_event(event)
    save_message(identity, "release", {"phase": phase, "reason": reason})

    run_git("add", "-A")
    success, commit_hash, _ = safe_commit(f"release: Phase {phase} by @{identity['short_name']} ({reason})")

    if not success:
        print("\n\u26A0\uFE0F  Release saved but NOT committed.", file=sys.stderr)
        sys.exit(1)

    print(f"\u2705 Released Phase {phase}: {reason}")

    if getattr(args, 'push', False):
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
    save_json(complete_file, event)

    append_event(event)
    save_message(identity, "complete", {"phase": phase, "pr": pr})

    run_git("add", "-A")
    success, commit_hash, _ = safe_commit(f"complete: Phase {phase} (PR {pr}) by @{identity['short_name']}")

    if not success:
        print("\n\u26A0\uFE0F  Completion saved but NOT committed.", file=sys.stderr)
        sys.exit(1)

    print(f"\u2705 Phase {phase} marked complete (PR {pr})")

    if getattr(args, 'push', False):
        safe_push(get_current_branch())


def cmd_phases(args):
    """Show all phases from .brain/claims/."""
    claims_dir = BRAIN_DIR / "claims"

    print("\n\U0001F9E0 Phase Claims:")
    print("-" * 70)

    if not claims_dir.exists():
        print("   (no claims directory)")
        print("-" * 70)
        return

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
                    ts = ts[:10]
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

    if active_claims:
        print("  Active Claims:")
        for claim in sorted(active_claims, key=lambda x: str(x["phase"])):
            dev_display = claim["developer_id"] or claim["developer"]
            print(f"    \U0001F7E1 Phase {claim['phase']}: {dev_display}")
            print(f"       Branch: {claim['branch']}")
            print(f"       Started: {claim['ts']}")
    else:
        print("   (no active claims)")

    if completed:
        print("\n  Completed:")
        for comp in sorted(completed, key=lambda x: str(x["phase"])):
            print(f"    \u2705 Phase {comp['phase']}: {comp['developer']} (PR: {comp['pr']})")

    print("-" * 70)


def cmd_sync(args):
    """Sync with all remote branches."""
    identity = require_identity()

    print("\U0001F504 Fetching all branches...")
    run_git("fetch", "--all")

    result = run_git("branch", "-r", "--list", "origin/dev/*")
    dev_branches = [b.strip() for b in result.stdout.split("\n") if b.strip()]

    if not dev_branches:
        print("\U0001F4ED No dev/* branches found")
        return

    print(f"\U0001F4E5 Found {len(dev_branches)} dev branches")

    print("\n\U0001F4E8 Recent messages:")
    print("-" * 60)

    for branch in dev_branches[:10]:
        dev_name = branch.replace("origin/dev/", "").split("/")[0]

        try:
            result = run_git(
                "log", branch, "--oneline", "-5",
                "--grep=msg(", "--grep=claim:", "--grep=complete:",
                check=False
            )
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n")[:3]:
                    print(f"  [{dev_name}] {line}")
        except subprocess.CalledProcessError:
            pass

    print("-" * 60)
    print(f"\n\u2705 Synced. You are: @{identity['short_name']}")


def cmd_receipt(args):
    """Post a read receipt."""
    identity = require_identity()

    run_git("fetch", "--all", check=False)
    current_head = get_head_commit()

    receipt = {
        "type": "read-receipt",
        "from": identity["short_name"],
        "from_id": identity["full_id"],
        "up_to_commit": current_head,
        "ts": now_iso()
    }

    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    receipt_file = RECEIPTS_DIR / identity["short_name"] / f"{ts}.json"
    receipt_file.parent.mkdir(parents=True, exist_ok=True)

    save_json(receipt_file, receipt)
    append_event(receipt)

    success, commit_hash, _ = safe_commit(
        f"receipt({identity['short_name']}): read up to {current_head[:8]}",
        [str(receipt_file)]
    )

    if not success:
        print("\n\u26A0\uFE0F  Receipt saved but NOT committed.", file=sys.stderr)
        sys.exit(1)

    print("\u2705 Read receipt posted")
    print(f"\U0001F4CD Up to commit: {current_head[:8]}")

    if getattr(args, 'push', False):
        safe_push(get_current_branch())
