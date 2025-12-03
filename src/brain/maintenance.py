"""
brain/maintenance.py - Maintenance commands for Brain Protocol

Provides commands for resetting and cleaning up brain state.
"""

import shutil
import sys
from pathlib import Path

from brain.core import (
    BRAIN_DIR,
    SELF_FILE,
    EVENTS_FILE,
    CLAIMS_DIR,
    MISSIONS_DIR,
    MESSAGES_DIR,
    RECEIPTS_DIR,
    KEYS_DIR,
)


def cmd_reset(args):
    """
    Reset brain state.

    Supports partial or full reset with various flags:
    - --all: Reset everything (default if no target specified)
    - --soft: Reset state but keep identity
    - --identity: Reset identity only
    - --events: Reset events log only
    - --claims: Reset claims only
    - --missions: Reset missions only
    - --messages: Reset messages only
    - --receipts: Reset receipts only
    - --keys: Reset keys only

    Requires --force or --dry-run for safety.
    """
    dry_run = getattr(args, 'dry_run', False)
    force = getattr(args, 'force', False)

    # Require --force or --dry-run for safety
    if not force and not dry_run:
        print("\u274C Reset requires --force (or --dry-run to preview)", file=sys.stderr)
        print("   Use: brain reset --force", file=sys.stderr)
        print("   Or:  brain reset --dry-run", file=sys.stderr)
        sys.exit(1)

    # Determine what to reset
    targets = _determine_targets(args)

    if dry_run:
        _show_dry_run(targets)
        return

    # Perform the actual reset
    _perform_reset(targets)


def _determine_targets(args) -> dict:
    """
    Determine which targets to reset based on flags.

    Returns a dict mapping target names to their paths.
    """
    all_targets = {
        'identity': SELF_FILE,
        'events': EVENTS_FILE,
        'claims': CLAIMS_DIR,
        'missions': MISSIONS_DIR,
        'messages': MESSAGES_DIR,
        'receipts': RECEIPTS_DIR,
        'keys': KEYS_DIR,
    }

    # Check for specific targets
    specific_targets = []
    for target_name in all_targets:
        if getattr(args, target_name, False):
            specific_targets.append(target_name)

    # Handle --soft: reset everything except identity
    if getattr(args, 'soft', False):
        return {k: v for k, v in all_targets.items() if k != 'identity'}

    # Handle --all or no specific targets (default to all)
    if getattr(args, 'all', False) or not specific_targets:
        return all_targets

    # Return only specified targets
    return {k: v for k, v in all_targets.items() if k in specific_targets}


def _show_dry_run(targets: dict):
    """Show what would be reset without doing it."""
    print("\U0001F50D Dry run - would reset the following:")
    print()

    cleared_count = 0
    for name, path in targets.items():
        exists = path.exists() if isinstance(path, Path) else Path(path).exists()
        status = "\u2705 exists" if exists else "\u2796 not present"

        if exists:
            cleared_count += 1
            if path.is_dir() if isinstance(path, Path) else Path(path).is_dir():
                # Count files in directory
                file_count = sum(1 for _ in Path(path).rglob('*') if _.is_file())
                print(f"  \u2022 {name}: {path} ({file_count} files)")
            else:
                print(f"  \u2022 {name}: {path}")
        else:
            print(f"  \u2022 {name}: {status}")

    print()
    if cleared_count > 0:
        print(f"\u26A0\uFE0F  Would clear {cleared_count} target(s)")
        print("   Run with --force to execute")
    else:
        print("\u2139\uFE0F  Nothing to reset")


def _perform_reset(targets: dict):
    """Perform the actual reset operation."""
    cleared = []
    skipped = []

    print("\U0001F9F9 Resetting brain state...")
    print()

    for name, path in targets.items():
        path = Path(path)
        if not path.exists():
            skipped.append(name)
            continue

        try:
            if path.is_dir():
                # Remove directory contents but keep the directory
                for item in path.iterdir():
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                cleared.append(name)
                print(f"  \u2705 Cleared {name}")
            else:
                # Remove file
                path.unlink()
                cleared.append(name)
                print(f"  \u2705 Removed {name}")
        except (OSError, PermissionError) as e:
            print(f"  \u274C Failed to reset {name}: {e}", file=sys.stderr)

    print()
    if cleared:
        print(f"\u2705 Reset complete: cleared {len(cleared)} target(s)")
        if skipped:
            print(f"   Skipped {len(skipped)} (not present): {', '.join(skipped)}")
    else:
        print("\u2139\uFE0F  Nothing to reset (no targets present)")
