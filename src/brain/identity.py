"""
brain/identity.py - Identity and Key Management

Single Responsibility: Handles identity creation, keys, and status display.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

from .core import (
    SELF_FILE, PRIVATE_KEYS_DIR, PUBLIC_KEYS_DIR,
    now_iso, generate_color_emotion_id, get_agent_emoji,
    ensure_brain_dirs, ensure_key_dirs,
    get_current_branch, get_head_commit,
    load_identity, save_identity,
    safe_commit, safe_push,
    EVENTS_FILE, CLAIMS_DIR,
)


# =============================================================================
# Key Generation (Ed25519) - Uses OpenSSL (no external Python dependencies)
# =============================================================================

def generate_key_pair(identity_name: str) -> tuple[str, str]:
    """
    Generate an Ed25519 key pair for signing using OpenSSL.
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


def save_key_pair(full_id: str, private_pem: str, public_pem: str) -> tuple[Path, Path]:
    """
    Save key pair to appropriate directories.

    Args:
        full_id: Full identity (e.g., 'claude-emerald-swift')
    """
    ensure_key_dirs()

    # Private key uses full identity for uniqueness
    private_path = PRIVATE_KEYS_DIR / f"{full_id}.pem"
    # Public key also uses full identity
    public_path = PUBLIC_KEYS_DIR / f"{full_id}.pem"

    private_path.write_text(private_pem)
    os.chmod(private_path, 0o600)

    public_path.write_text(public_pem)

    return private_path, public_path


def load_private_key(full_id: str) -> Optional[str]:
    """Load private key for identity using full_id."""
    private_path = PRIVATE_KEYS_DIR / f"{full_id}.pem"
    if private_path.exists():
        return private_path.read_text()
    return None


def load_public_key(full_id: str) -> Optional[str]:
    """Load public key for identity using full_id."""
    public_path = PUBLIC_KEYS_DIR / f"{full_id}.pem"
    if public_path.exists():
        return public_path.read_text()
    return None


def get_public_key_fingerprint(public_pem: str) -> str:
    """Get a short fingerprint of a public key."""
    import hashlib
    import base64
    hash_bytes = hashlib.sha256(public_pem.encode('utf-8')).digest()
    return base64.b64encode(hash_bytes).decode('utf-8')[:16]


# =============================================================================
# Commands
# =============================================================================

SHORT_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{1,23}$")


def validate_name(name: str) -> bool:
    """Validate short name format."""
    if not name or len(name) < 2 or len(name) > 24:
        return False
    return bool(SHORT_NAME_PATTERN.match(name))


def cmd_init(args):
    """Initialize participant identity."""
    import uuid

    existing = load_identity()

    if existing and not getattr(args, 'reset', False):
        print("\u2705 Identity already exists:")
        cmd_status(args)
        return

    if args.name:
        short_name = args.name.lower()
        if not validate_name(short_name):
            print("\u274C Invalid name. Use 2-24 chars, start with letter, only a-z 0-9 - _")
            sys.exit(1)
    elif existing:
        short_name = existing["short_name"]
    else:
        print("Enter short name (e.g., claude, gpt, gemini, human):")
        short_name = input("> ").strip().lower()
        if not validate_name(short_name):
            print("\u274C Invalid name")
            sys.exit(1)

    # Generate color-emotion identity
    color, emotion, color_emotion = generate_color_emotion_id()
    emoji = get_agent_emoji(short_name)
    full_id = f"{short_name}-{color}-{emotion}"

    print(f"\n{emoji} Generating identity for @{short_name}...")
    print(f"   \U0001F3A8 Color:   {color}")
    print(f"   \U0001F4AB Emotion: {emotion}")
    print(f"   \U0001F3F7\uFE0F  Full ID: {full_id}")

    # Generate cryptographic key pair
    print("\n\U0001F510 Generating Ed25519 key pair...")
    try:
        private_pem, public_pem = generate_key_pair(full_id)
        private_path, public_path = save_key_pair(full_id, private_pem, public_pem)
        public_key_fingerprint = get_public_key_fingerprint(public_pem)
        has_keys = True
        print("\u2705 Keys generated")
        print(f"   \U0001F4C1 Private: {private_path} (gitignored)")
        print(f"   \U0001F4C1 Public:  {public_path} (committed to repo)")
        print(f"   \U0001F511 Fingerprint: {public_key_fingerprint}")
    except Exception as e:
        print(f"\u26A0\uFE0F  Key generation failed: {e}")
        print("   Continuing without cryptographic keys (signing disabled)")
        public_key_fingerprint = None
        has_keys = False
        public_path = None

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

    save_identity(identity)

    print(f"\n\u2705 Identity created: {emoji} {full_id}")
    print(f"\U0001F4C1 Saved to: {SELF_FILE}")

    # Commit public key to repo
    if has_keys and public_path:
        print("\U0001F4E4 Committing public key to repository...")
        success, commit_hash, _ = safe_commit(
            f"brain: add public key for {short_name}",
            [str(public_path)]
        )
        if success:
            print(f"\u2705 Public key committed")
        else:
            print("\u26A0\uFE0F  Public key saved but NOT committed.", file=sys.stderr)


def cmd_status(args):
    """Show current status."""
    identity = load_identity()

    print()
    print("\u250C" + "\u2500" * 57 + "\u2510")
    print("\u2502" + "                    \U0001F9E0 BRAIN STATUS                      " + "\u2502")
    print("\u251C" + "\u2500" * 57 + "\u2524")

    if identity:
        emoji = identity.get("emoji", get_agent_emoji(identity["short_name"]))
        print(f"\u2502  {emoji} Identity: @{identity['short_name']:<39} \u2502")
        print(f"\u2502  Full ID:     {identity['full_id']:<42} \u2502")

        color = identity.get("color")
        emotion = identity.get("emotion")
        if color and emotion:
            print(f"\u2502  \U0001F3A8 Color:    {color:<42} \u2502")
            print(f"\u2502  \U0001F4AB Emotion:  {emotion:<42} \u2502")

        has_keys = identity.get("has_keys", False)
        if has_keys:
            fingerprint = identity.get("public_key_fingerprint", "N/A")
            print(f"\u2502  \U0001F511 Keys:     \u2705 Configured                            \u2502")
            print(f"\u2502  Fingerprint: {fingerprint:<42} \u2502")
        else:
            print(f"\u2502  \U0001F511 Keys:     \u274C Not configured                         \u2502")
    else:
        print("\u2502  Identity:    \u274C Not initialized                        \u2502")

    print(f"\u2502  Branch:      {get_current_branch():<42} \u2502")
    print(f"\u2502  HEAD:        {get_head_commit()[:8]:<42} \u2502")

    # Count events
    event_count = 0
    if EVENTS_FILE.exists():
        with open(EVENTS_FILE) as f:
            event_count = sum(1 for _ in f)
    print(f"\u2502  Events:      {event_count:<42} \u2502")

    # Show active claims
    print("\u251C" + "\u2500" * 57 + "\u2524")
    print("\u2502  Active Claims:                                        \u2502")

    claims = list(CLAIMS_DIR.glob("*-claim.json")) if CLAIMS_DIR.exists() else []
    if claims:
        import json
        for claim_file in claims[:5]:
            with open(claim_file) as f:
                claim = json.load(f)
            phase = claim.get("phase", "?")
            dev = claim.get("developer", "?")
            print(f"\u2502    Phase {phase}: {dev:<44} \u2502")
    else:
        print("\u2502    (none)                                               \u2502")

    print("\u2514" + "\u2500" * 57 + "\u2518")
    print()


def cmd_keys(args):
    """Manage cryptographic keys."""
    identity = load_identity()
    subcommand = getattr(args, 'subcommand', 'show') or 'show'

    if subcommand == "show":
        print()
        print("\u250C" + "\u2500" * 57 + "\u2510")
        print("\u2502" + "                    \U0001F511 KEY STATUS                        " + "\u2502")
        print("\u251C" + "\u2500" * 57 + "\u2524")

        if not identity:
            print("\u2502  \u274C No identity found. Run: brain init               \u2502")
            print("\u2514" + "\u2500" * 57 + "\u2518")
            return

        short_name = identity["short_name"]
        full_id = identity.get("full_id", short_name)

        private_path = PRIVATE_KEYS_DIR / f"{full_id}.pem"
        if private_path.exists():
            print(f"\u2502  Private Key: \u2705 Found                                  \u2502")
            print(f"\u2502    {str(private_path):<53} \u2502")
        else:
            print(f"\u2502  Private Key: \u274C Not found                             \u2502")

        public_path = PUBLIC_KEYS_DIR / f"{full_id}.pem"
        if public_path.exists():
            print(f"\u2502  Public Key:  \u2705 Found                                  \u2502")
            print(f"\u2502    {str(public_path):<53} \u2502")
            public_pem = public_path.read_text()
            fingerprint = get_public_key_fingerprint(public_pem)
            print(f"\u2502  Fingerprint: {fingerprint:<42} \u2502")
        else:
            print(f"\u2502  Public Key:  \u274C Not found                             \u2502")

        print("\u251C" + "\u2500" * 57 + "\u2524")
        print("\u2502  Known Participants (Public Keys):                      \u2502")

        if PUBLIC_KEYS_DIR.exists():
            for key_file in sorted(PUBLIC_KEYS_DIR.glob("*.pem")):
                key_id = key_file.stem  # full_id: name-color-emotion
                pub_pem = key_file.read_text()
                fp = get_public_key_fingerprint(pub_pem)
                is_me = " (you)" if key_id == full_id else ""
                # Truncate long IDs for display
                display_id = key_id[:24] if len(key_id) > 24 else key_id
                print(f"\u2502    {display_id:<24} {fp:<16}{is_me:<8} \u2502")
        else:
            print("\u2502    (none)                                              \u2502")

        print("\u2514" + "\u2500" * 57 + "\u2518")

    elif subcommand == "verify":
        target = getattr(args, 'target', None)
        if not target:
            print("\u274C Usage: brain keys verify <name>")
            sys.exit(1)

        public_path = PUBLIC_KEYS_DIR / f"{target}.pem"
        if not public_path.exists():
            print(f"\u274C No public key found for @{target}")
            sys.exit(1)

        public_pem = public_path.read_text()
        fingerprint = get_public_key_fingerprint(public_pem)

        print(f"\u2705 Public key for @{target}")
        print(f"   Fingerprint: {fingerprint}")
        print(f"   File: {public_path}")

    elif subcommand == "regenerate":
        from .core import require_identity
        identity = require_identity()
        full_id = identity["full_id"]

        print(f"\u26A0\uFE0F  This will regenerate keys for {full_id}")
        print("   Your old signatures will become invalid.")
        confirm = input("   Continue? [y/N]: ").strip().lower()

        if confirm != "y":
            print("Cancelled.")
            return

        print("\U0001F510 Generating new Ed25519 key pair...")
        private_pem, public_pem = generate_key_pair(full_id)
        private_path, public_path = save_key_pair(full_id, private_pem, public_pem)
        fingerprint = get_public_key_fingerprint(public_pem)

        identity["has_keys"] = True
        identity["public_key_fingerprint"] = fingerprint
        identity["keys_regenerated_at"] = now_iso()

        save_identity(identity)

        print(f"\u2705 New keys generated")
        print(f"   Fingerprint: {fingerprint}")

        success, commit_hash, _ = safe_commit(
            f"brain: regenerate public key for {short_name}",
            [str(public_path)]
        )
        if success:
            print(f"\u2705 Public key committed to repository")

    else:
        print("Usage: brain keys [show|verify|regenerate]")
        sys.exit(1)
