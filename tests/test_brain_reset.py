"""
Tests for brain reset command.

TDD: Tests written BEFORE implementation.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest


class TestResetCommandParsing:
    """Test 'reset' command CLI argument parsing."""

    def test_reset_command_exists(self, temp_repo, brain_cli_path):
        """reset command should be recognized."""
        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--help"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        # Should show help, not error
        assert result.returncode == 0
        assert "reset" in result.stdout.lower()

    def test_reset_without_force_fails(self, temp_repo, brain_cli_path, initialized_identity):
        """reset without --force should fail (safety)."""
        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        # Should fail because --force not specified
        assert result.returncode != 0
        assert "force" in result.stderr.lower() or "confirm" in result.stderr.lower()

    def test_reset_with_force_succeeds(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --force should succeed."""
        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert "reset" in result.stdout.lower()

    def test_reset_short_force_flag(self, temp_repo, brain_cli_path, initialized_identity):
        """reset -f should work as alias for --force."""
        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "-f"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0


class TestResetIdentity:
    """Test reset clears identity."""

    def test_reset_removes_identity(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --force should remove identity file."""
        self_file = temp_repo / ".brain" / "self.json"
        assert self_file.exists()

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not self_file.exists()

    def test_reset_identity_only(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --identity --force should only remove identity."""
        self_file = temp_repo / ".brain" / "self.json"
        events_file = temp_repo / ".brain" / "events.jsonl"

        # Create events file
        events_file.parent.mkdir(parents=True, exist_ok=True)
        events_file.write_text('{"type": "test"}\n')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--identity", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not self_file.exists()
        # Events should still exist
        assert events_file.exists()


class TestResetEvents:
    """Test reset clears events."""

    def test_reset_removes_events(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --force should remove events.jsonl."""
        events_file = temp_repo / ".brain" / "events.jsonl"
        events_file.write_text('{"type": "test-event"}\n')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not events_file.exists()

    def test_reset_events_only(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --events --force should only remove events."""
        self_file = temp_repo / ".brain" / "self.json"
        events_file = temp_repo / ".brain" / "events.jsonl"

        events_file.write_text('{"type": "test-event"}\n')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--events", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not events_file.exists()
        # Identity should still exist
        assert self_file.exists()


class TestResetClaims:
    """Test reset clears claims."""

    def test_reset_removes_claims(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --force should remove claims directory."""
        claims_dir = temp_repo / ".brain" / "claims"
        claims_dir.mkdir(parents=True, exist_ok=True)
        claim_file = claims_dir / "phase-11-claim.json"
        claim_file.write_text('{"phase": 11, "by": "testuser"}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not claim_file.exists()

    def test_reset_claims_only(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --claims --force should only remove claims."""
        self_file = temp_repo / ".brain" / "self.json"
        claims_dir = temp_repo / ".brain" / "claims"
        claims_dir.mkdir(parents=True, exist_ok=True)
        claim_file = claims_dir / "phase-11-claim.json"
        claim_file.write_text('{"phase": 11, "by": "testuser"}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--claims", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not claim_file.exists()
        # Identity should still exist
        assert self_file.exists()


class TestResetMissions:
    """Test reset clears missions."""

    def test_reset_removes_missions(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --force should remove missions directory."""
        missions_dir = temp_repo / ".brain" / "missions" / "active"
        missions_dir.mkdir(parents=True, exist_ok=True)
        mission_file = missions_dir / "mission-test.json"
        mission_file.write_text('{"id": "mission-test", "title": "Test"}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not mission_file.exists()

    def test_reset_missions_only(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --missions --force should only remove missions."""
        self_file = temp_repo / ".brain" / "self.json"
        missions_dir = temp_repo / ".brain" / "missions" / "active"
        missions_dir.mkdir(parents=True, exist_ok=True)
        mission_file = missions_dir / "mission-test.json"
        mission_file.write_text('{"id": "mission-test", "title": "Test"}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--missions", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not mission_file.exists()
        # Identity should still exist
        assert self_file.exists()


class TestResetMessages:
    """Test reset clears messages."""

    def test_reset_removes_messages(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --force should remove messages directory."""
        messages_dir = temp_repo / ".brain" / "messages" / "testuser"
        messages_dir.mkdir(parents=True, exist_ok=True)
        msg_file = messages_dir / "20251203-120000-msg.json"
        msg_file.write_text('{"type": "msg", "content": "Hello"}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not msg_file.exists()

    def test_reset_messages_only(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --messages --force should only remove messages."""
        self_file = temp_repo / ".brain" / "self.json"
        messages_dir = temp_repo / ".brain" / "messages" / "testuser"
        messages_dir.mkdir(parents=True, exist_ok=True)
        msg_file = messages_dir / "20251203-120000-msg.json"
        msg_file.write_text('{"type": "msg", "content": "Hello"}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--messages", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not msg_file.exists()
        # Identity should still exist
        assert self_file.exists()


class TestResetReceipts:
    """Test reset clears receipts."""

    def test_reset_removes_receipts(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --force should remove receipts directory."""
        receipts_dir = temp_repo / ".brain" / "receipts" / "testuser"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_file = receipts_dir / "20251203-120000.json"
        receipt_file.write_text('{"type": "read-receipt", "from": "testuser"}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not receipt_file.exists()

    def test_reset_receipts_only(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --receipts --force should only remove receipts."""
        self_file = temp_repo / ".brain" / "self.json"
        receipts_dir = temp_repo / ".brain" / "receipts" / "testuser"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_file = receipts_dir / "20251203-120000.json"
        receipt_file.write_text('{"type": "read-receipt", "from": "testuser"}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--receipts", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not receipt_file.exists()
        # Identity should still exist
        assert self_file.exists()


class TestResetKeys:
    """Test reset clears keys."""

    def test_reset_removes_keys(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --force should remove keys directory."""
        keys_dir = temp_repo / ".brain" / "keys" / "private"
        keys_dir.mkdir(parents=True, exist_ok=True)
        key_file = keys_dir / "testuser-emerald-swift.pem"
        key_file.write_text('-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not key_file.exists()

    def test_reset_keys_only(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --keys --force should only remove keys."""
        self_file = temp_repo / ".brain" / "self.json"
        keys_dir = temp_repo / ".brain" / "keys" / "private"
        keys_dir.mkdir(parents=True, exist_ok=True)
        key_file = keys_dir / "testuser-emerald-swift.pem"
        key_file.write_text('-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--keys", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert not key_file.exists()
        # Identity should still exist
        assert self_file.exists()


class TestResetAll:
    """Test reset --all clears everything."""

    def test_reset_all_clears_everything(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --all --force should clear all brain state."""
        # Create various state
        brain_dir = temp_repo / ".brain"

        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        claims_dir = brain_dir / "claims"
        claims_dir.mkdir(exist_ok=True)
        (claims_dir / "phase-11-claim.json").write_text('{}')

        missions_dir = brain_dir / "missions" / "active"
        missions_dir.mkdir(parents=True, exist_ok=True)
        (missions_dir / "mission-test.json").write_text('{}')

        messages_dir = brain_dir / "messages" / "testuser"
        messages_dir.mkdir(parents=True, exist_ok=True)
        (messages_dir / "test.json").write_text('{}')

        receipts_dir = brain_dir / "receipts" / "testuser"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        (receipts_dir / "test.json").write_text('{}')

        keys_dir = brain_dir / "keys" / "private"
        keys_dir.mkdir(parents=True, exist_ok=True)
        (keys_dir / "test.pem").write_text('key')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--all", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        # Everything should be cleared
        assert not (brain_dir / "self.json").exists()
        assert not events_file.exists()
        assert not (claims_dir / "phase-11-claim.json").exists()
        assert not (missions_dir / "mission-test.json").exists()
        assert not (messages_dir / "test.json").exists()
        assert not (receipts_dir / "test.json").exists()
        assert not (keys_dir / "test.pem").exists()


class TestResetSoft:
    """Test reset --soft keeps identity but clears state."""

    def test_reset_soft_keeps_identity(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --soft --force should keep identity but clear other state."""
        brain_dir = temp_repo / ".brain"
        self_file = brain_dir / "self.json"

        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        claims_dir = brain_dir / "claims"
        claims_dir.mkdir(exist_ok=True)
        claim_file = claims_dir / "phase-11-claim.json"
        claim_file.write_text('{}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--soft", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        # Identity should still exist
        assert self_file.exists()
        # State should be cleared
        assert not events_file.exists()
        assert not claim_file.exists()


class TestResetMultipleTargets:
    """Test reset with multiple target flags."""

    def test_reset_multiple_targets(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --events --claims --force should reset both."""
        brain_dir = temp_repo / ".brain"
        self_file = brain_dir / "self.json"

        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        claims_dir = brain_dir / "claims"
        claims_dir.mkdir(exist_ok=True)
        claim_file = claims_dir / "phase-11-claim.json"
        claim_file.write_text('{}')

        messages_dir = brain_dir / "messages" / "testuser"
        messages_dir.mkdir(parents=True, exist_ok=True)
        msg_file = messages_dir / "test.json"
        msg_file.write_text('{}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--events", "--claims", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        # Identity should still exist
        assert self_file.exists()
        # Specified targets should be cleared
        assert not events_file.exists()
        assert not claim_file.exists()
        # Other state should remain
        assert msg_file.exists()


class TestResetOutput:
    """Test reset command output messages."""

    def test_reset_shows_what_was_cleared(self, temp_repo, brain_cli_path, initialized_identity):
        """reset should show what was cleared."""
        brain_dir = temp_repo / ".brain"
        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        # Should show what was reset
        output = result.stdout.lower()
        assert "reset" in output or "cleared" in output

    def test_reset_dry_run(self, temp_repo, brain_cli_path, initialized_identity):
        """reset --dry-run should show what would be cleared without doing it."""
        brain_dir = temp_repo / ".brain"
        self_file = brain_dir / "self.json"
        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        # Should show what would be reset
        assert "would" in result.stdout.lower() or "dry" in result.stdout.lower()
        # Nothing should actually be deleted
        assert self_file.exists()
        assert events_file.exists()


class TestResetWithNoState:
    """Test reset when there's nothing to reset."""

    def test_reset_empty_brain_dir(self, temp_repo, brain_cli_path):
        """reset with no state should succeed gracefully."""
        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        # Should succeed even with nothing to reset
        assert result.returncode == 0


# =============================================================================
# ACID Tests for Reset Messages
# =============================================================================

class TestResetACIDAtomicity:
    """
    ACID Atomicity: Reset operation completes entirely or not at all.

    If a partial failure occurs, the operation should be rolled back
    or at minimum, reported clearly.
    """

    def test_atomicity_all_targets_cleared_together(self, temp_repo, brain_cli_path, initialized_identity):
        """All specified targets should be cleared in a single atomic operation."""
        brain_dir = temp_repo / ".brain"

        # Create multiple targets
        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        claims_dir = brain_dir / "claims"
        claims_dir.mkdir(exist_ok=True)
        claim_file = claims_dir / "phase-11-claim.json"
        claim_file.write_text('{"phase": 11}')

        messages_dir = brain_dir / "messages" / "testuser"
        messages_dir.mkdir(parents=True, exist_ok=True)
        msg_file = messages_dir / "test.json"
        msg_file.write_text('{"msg": "hello"}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0

        # All targets should be cleared (atomicity - all or nothing)
        assert not events_file.exists(), "Events file should be cleared"
        assert not claim_file.exists(), "Claim file should be cleared"
        assert not msg_file.exists(), "Message file should be cleared"

    def test_atomicity_partial_target_selection(self, temp_repo, brain_cli_path, initialized_identity):
        """Partial target selection should only affect specified targets atomically."""
        brain_dir = temp_repo / ".brain"

        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        messages_dir = brain_dir / "messages" / "testuser"
        messages_dir.mkdir(parents=True, exist_ok=True)
        msg_file = messages_dir / "test.json"
        msg_file.write_text('{"msg": "hello"}')

        # Only reset events
        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--events", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        # Events cleared, messages untouched
        assert not events_file.exists(), "Events should be cleared"
        assert msg_file.exists(), "Messages should remain untouched"


class TestResetACIDConsistency:
    """
    ACID Consistency: State before and after reset is valid and consistent.

    Messages should accurately reflect the actual state changes.
    """

    def test_consistency_output_matches_state(self, temp_repo, brain_cli_path, initialized_identity):
        """Output messages should accurately reflect actual state changes."""
        brain_dir = temp_repo / ".brain"

        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--events", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        # Output should mention events being cleared
        output = result.stdout.lower()
        assert "events" in output or "cleared" in output

        # State should be consistent with message
        assert not events_file.exists()

    def test_consistency_identity_state_valid_after_soft_reset(self, temp_repo, brain_cli_path, initialized_identity):
        """After soft reset, identity should remain valid and parseable."""
        brain_dir = temp_repo / ".brain"
        self_file = brain_dir / "self.json"

        # Add state to reset
        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--soft", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0
        assert self_file.exists()

        # Identity should be valid JSON
        with open(self_file) as f:
            identity = json.load(f)

        # Should have required fields
        assert "short_name" in identity
        assert "full_id" in identity
        assert identity["short_name"] == "testuser"

    def test_consistency_dry_run_no_state_change(self, temp_repo, brain_cli_path, initialized_identity):
        """Dry run should not change any state - consistency preserved."""
        brain_dir = temp_repo / ".brain"
        self_file = brain_dir / "self.json"

        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test-event", "id": 123}\n')

        # Read original content
        original_identity = self_file.read_text()
        original_events = events_file.read_text()

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0

        # State should be exactly the same
        assert self_file.read_text() == original_identity
        assert events_file.read_text() == original_events


class TestResetACIDIsolation:
    """
    ACID Isolation: Reset operations are isolated from other operations.

    Dry-run should be completely isolated. Partial resets should not
    affect unrelated targets.
    """

    def test_isolation_dry_run_isolated(self, temp_repo, brain_cli_path, initialized_identity):
        """Dry run is completely isolated - no side effects."""
        brain_dir = temp_repo / ".brain"

        # Create various state
        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        claims_dir = brain_dir / "claims"
        claims_dir.mkdir(exist_ok=True)
        claim_file = claims_dir / "phase-5-claim.json"
        claim_file.write_text('{"phase": 5}')

        # Get state before dry-run
        files_before = set(brain_dir.rglob("*"))

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0

        # Get state after dry-run
        files_after = set(brain_dir.rglob("*"))

        # No files should be added or removed
        assert files_before == files_after, "Dry run should not modify file system"

    def test_isolation_targets_independent(self, temp_repo, brain_cli_path, initialized_identity):
        """Resetting one target should not affect others."""
        brain_dir = temp_repo / ".brain"

        # Create independent targets
        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "event1"}\n{"type": "event2"}\n')

        messages_dir = brain_dir / "messages" / "testuser"
        messages_dir.mkdir(parents=True, exist_ok=True)
        msg_file = messages_dir / "important.json"
        msg_file.write_text('{"important": true, "data": "preserve me"}')

        receipts_dir = brain_dir / "receipts" / "testuser"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_file = receipts_dir / "receipt.json"
        receipt_file.write_text('{"type": "read-receipt"}')

        # Only reset events
        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--events", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0

        # Events cleared
        assert not events_file.exists()

        # Other targets completely isolated - content unchanged
        assert msg_file.exists()
        assert msg_file.read_text() == '{"important": true, "data": "preserve me"}'
        assert receipt_file.exists()
        assert receipt_file.read_text() == '{"type": "read-receipt"}'

    def test_isolation_multiple_resets_independent(self, temp_repo, brain_cli_path, initialized_identity):
        """Multiple sequential resets should be independent operations."""
        brain_dir = temp_repo / ".brain"

        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        claims_dir = brain_dir / "claims"
        claims_dir.mkdir(exist_ok=True)
        claim_file = claims_dir / "claim.json"
        claim_file.write_text('{}')

        # First reset - events only
        result1 = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--events", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        assert result1.returncode == 0
        assert not events_file.exists()
        assert claim_file.exists()  # Claims still there

        # Second reset - claims only
        result2 = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--claims", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        assert result2.returncode == 0
        assert not claim_file.exists()


class TestResetACIDDurability:
    """
    ACID Durability: Once reset completes, changes persist.

    Reset state should survive re-reading and be permanent.
    """

    def test_durability_reset_persists(self, temp_repo, brain_cli_path, initialized_identity):
        """Reset changes should persist after operation completes."""
        brain_dir = temp_repo / ".brain"

        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--events", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0

        # Verify persistence - file should still not exist on re-check
        assert not events_file.exists()
        assert not Path(events_file).exists()  # Double check with fresh Path

    def test_durability_partial_reset_stable(self, temp_repo, brain_cli_path, initialized_identity):
        """Partial reset should leave remaining state stable and unchanged."""
        brain_dir = temp_repo / ".brain"
        self_file = brain_dir / "self.json"

        # Read original identity
        original_identity = json.loads(self_file.read_text())

        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--events", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0

        # Identity should be exactly the same (durable, unchanged)
        current_identity = json.loads(self_file.read_text())
        assert current_identity == original_identity

    def test_durability_message_accuracy(self, temp_repo, brain_cli_path, initialized_identity):
        """Reset messages should accurately reflect durable state changes."""
        brain_dir = temp_repo / ".brain"

        # Create multiple targets
        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        claims_dir = brain_dir / "claims"
        claims_dir.mkdir(exist_ok=True)
        (claims_dir / "claim1.json").write_text('{}')
        (claims_dir / "claim2.json").write_text('{}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0

        # Message should indicate completion
        output = result.stdout.lower()
        assert "complete" in output or "reset" in output or "cleared" in output

        # Verify all claimed deletions are durable
        assert not events_file.exists()
        assert not (claims_dir / "claim1.json").exists()
        assert not (claims_dir / "claim2.json").exists()

    def test_durability_empty_state_after_full_reset(self, temp_repo, brain_cli_path, initialized_identity):
        """Full reset should result in durably empty brain state."""
        brain_dir = temp_repo / ".brain"

        # Create comprehensive state
        events_file = brain_dir / "events.jsonl"
        events_file.write_text('{"type": "test"}\n')

        for subdir in ["claims", "messages/user", "receipts/user", "missions/active"]:
            d = brain_dir / subdir
            d.mkdir(parents=True, exist_ok=True)
            (d / "test.json").write_text('{}')

        result = subprocess.run(
            [sys.executable, str(brain_cli_path), "reset", "--all", "--force"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )

        assert result.returncode == 0

        # All content should be durably removed
        # Only empty directories might remain
        remaining_files = [f for f in brain_dir.rglob("*") if f.is_file()]
        assert len(remaining_files) == 0, f"Expected no files, found: {remaining_files}"
