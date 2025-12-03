#!/usr/bin/env python3
"""
brain-init.py - Initialize participant identity for decentralized collaboration

Creates a local identity file at .brain/self.json containing:
- UUID: unique identifier for this participant
- short_name: human-readable short name (e.g., "claude", "alice", "gpt-4")
- created_at: timestamp of identity creation

The identity file is gitignored to keep participant identity local.

Usage:
    python scripts/brain-init.py                    # Interactive mode
    python scripts/brain-init.py --name claude      # Set name directly
    python scripts/brain-init.py --show             # Show current identity
    python scripts/brain-init.py --reset            # Reset identity (new UUID)
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Constants
BRAIN_DIR = Path(".brain")
SELF_FILE = BRAIN_DIR / "self.json"
SHORT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,23}$")


def generate_short_uuid() -> str:
    """Generate a short UUID (first 8 chars of UUID4)."""
    return str(uuid.uuid4())[:8]


def validate_short_name(name: str) -> tuple[bool, str]:
    """
    Validate short name format.
    
    Rules:
    - 2-24 characters
    - Starts with lowercase letter
    - Only lowercase letters, numbers, underscores, hyphens
    - No consecutive special characters
    
    Returns:
        (is_valid, error_message)
    """
    if not name:
        return False, "Name cannot be empty"
    
    if len(name) < 2:
        return False, "Name must be at least 2 characters"
    
    if len(name) > 24:
        return False, "Name must be 24 characters or less"
    
    if not SHORT_NAME_PATTERN.match(name):
        return False, (
            "Name must start with lowercase letter, "
            "contain only lowercase letters, numbers, underscores, hyphens"
        )
    
    if "--" in name or "__" in name or "-_" in name or "_-" in name:
        return False, "Name cannot have consecutive special characters"
    
    return True, ""


def create_identity(short_name: str) -> dict:
    """Create a new identity dictionary."""
    return {
        "uuid": str(uuid.uuid4()),
        "short_uuid": generate_short_uuid(),
        "short_name": short_name,
        "full_id": f"{short_name}-{generate_short_uuid()}",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "version": 1
    }


def load_identity() -> dict | None:
    """Load existing identity from file."""
    if not SELF_FILE.exists():
        return None
    
    try:
        with open(SELF_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"⚠️  Warning: Could not read identity file: {e}", file=sys.stderr)
        return None


def save_identity(identity: dict) -> bool:
    """Save identity to file."""
    try:
        BRAIN_DIR.mkdir(parents=True, exist_ok=True)
        
        with open(SELF_FILE, "w") as f:
            json.dump(identity, f, indent=2)
        
        # Set restrictive permissions (owner read/write only)
        os.chmod(SELF_FILE, 0o600)
        
        return True
    except IOError as e:
        print(f"❌ Error saving identity: {e}", file=sys.stderr)
        return False


def show_identity(identity: dict) -> None:
    """Display identity information."""
    print()
    print("┌─────────────────────────────────────────────────────┐")
    print("│              🧠 BRAIN IDENTITY                      │")
    print("├─────────────────────────────────────────────────────┤")
    print(f"│  Short Name:  {identity['short_name']:<37} │")
    print(f"│  Full ID:     {identity['full_id']:<37} │")
    print(f"│  UUID:        {identity['uuid'][:36]:<37} │")
    print(f"│  Created:     {identity['created_at'][:19]:<37} │")
    print("└─────────────────────────────────────────────────────┘")
    print()


def prompt_short_name() -> str:
    """Interactively prompt for short name."""
    print()
    print("🧠 BRAIN IDENTITY SETUP")
    print("=" * 40)
    print()
    print("Choose a short name for this participant.")
    print("Examples: claude, alice, bob, gpt-4, dev-main")
    print()
    print("Rules:")
    print("  • 2-24 characters")
    print("  • Start with lowercase letter")
    print("  • Only: a-z, 0-9, -, _")
    print()
    
    while True:
        try:
            name = input("Enter short name: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n\nAborted.")
            sys.exit(1)
        
        is_valid, error = validate_short_name(name)
        if is_valid:
            return name
        
        print(f"❌ Invalid: {error}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Initialize participant identity for decentralized collaboration"
    )
    parser.add_argument(
        "--name", "-n",
        type=str,
        help="Short name for this participant (e.g., claude, alice)"
    )
    parser.add_argument(
        "--show", "-s",
        action="store_true",
        help="Show current identity and exit"
    )
    parser.add_argument(
        "--reset", "-r",
        action="store_true",
        help="Reset identity (generates new UUID, keeps name unless --name provided)"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output identity as JSON (for scripting)"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Minimal output"
    )
    
    args = parser.parse_args()
    
    # Check if we're in the right directory
    if not Path("package.json").exists():
        print("❌ Error: Must run from project root (where package.json is)", file=sys.stderr)
        sys.exit(1)
    
    existing = load_identity()
    
    # --show: Display current identity
    if args.show:
        if existing:
            if args.json:
                print(json.dumps(existing, indent=2))
            else:
                show_identity(existing)
        else:
            print("❌ No identity found. Run without --show to create one.")
            sys.exit(1)
        return
    
    # Determine short name
    if args.name:
        is_valid, error = validate_short_name(args.name.lower())
        if not is_valid:
            print(f"❌ Invalid name: {error}", file=sys.stderr)
            sys.exit(1)
        short_name = args.name.lower()
    elif existing and not args.reset:
        # Identity exists and no reset requested
        if not args.quiet:
            print("✅ Identity already exists.")
            show_identity(existing)
            print("Use --reset to generate a new UUID, or --name to change name.")
        elif args.json:
            print(json.dumps(existing, indent=2))
        return
    elif existing and args.reset and not args.name:
        # Reset but keep existing name
        short_name = existing["short_name"]
        if not args.quiet:
            print(f"♻️  Resetting identity (keeping name: {short_name})")
    else:
        # Interactive prompt
        short_name = prompt_short_name()
    
    # Create new identity
    identity = create_identity(short_name)
    
    if not save_identity(identity):
        sys.exit(1)
    
    if args.json:
        print(json.dumps(identity, indent=2))
    elif not args.quiet:
        print()
        print("✅ Identity created successfully!")
        show_identity(identity)
        print(f"📁 Saved to: {SELF_FILE}")
        print()
        print("Next steps:")
        print(f"  1. Use '@{identity['short_name']}' or '{identity['full_id']}' in claims")
        print(f"  2. Create branch: dev/{identity['short_name']}/...")
        print()


if __name__ == "__main__":
    main()

