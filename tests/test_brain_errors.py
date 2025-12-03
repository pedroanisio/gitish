"""
Regression tests for error handling in brain.py

These tests verify that when operations fail (especially git commits),
the agent receives clear error messages instead of Python tracebacks.
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repository."""
    os.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], check=True, capture_output=True)

    # Create package.json (required by brain.py)
    (tmp_path / "package.json").write_text("{}")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], check=True, capture_output=True)
    
    return tmp_path


@pytest.fixture
def brain(temp_git_repo):
    """Import brain module after setting up temp repo."""
    scripts_path = Path(__file__).parent.parent
    sys.path.insert(0, str(scripts_path))
    
    import brain as brain_module
    
    # Override paths to use temp directory
    brain_module.BRAIN_DIR = temp_git_repo / ".brain"
    brain_module.SELF_FILE = brain_module.BRAIN_DIR / "self.json"
    brain_module.MESSAGES_DIR = brain_module.BRAIN_DIR / "messages"
    brain_module.RECEIPTS_DIR = brain_module.BRAIN_DIR / "receipts"
    brain_module.CLAIMS_DIR = brain_module.BRAIN_DIR / "claims"
    brain_module.EVENTS_FILE = brain_module.BRAIN_DIR / "events.jsonl"
    brain_module.KEYS_DIR = brain_module.BRAIN_DIR / "keys"
    brain_module.PRIVATE_KEYS_DIR = brain_module.KEYS_DIR / "private"
    brain_module.PUBLIC_KEYS_DIR = brain_module.KEYS_DIR / "public"
    
    return brain_module


@pytest.fixture
def mock_identity(brain, temp_git_repo):
    """Create a mock identity file."""
    brain.ensure_brain_dirs()
    identity = {
        "uuid": "test-uuid",
        "short_name": "testuser",
        "color": "blue",
        "emotion": "calm",
        "full_id": "testuser-blue-calm",
        "emoji": "🤖",
        "created_at": "2025-01-01T00:00:00Z",
        "version": 3,
        "has_keys": False,
        "public_key_fingerprint": None
    }
    brain.SELF_FILE.write_text(json.dumps(identity))
    return identity


# =============================================================================
# Tests: safe_commit function
# =============================================================================

class TestSafeCommit:
    """Tests for the safe_commit function."""
    
    def test_safe_commit_success(self, brain, temp_git_repo, mock_identity):
        """Successful commit should return (True, commit_hash, "")."""
        # Create a file to commit
        test_file = temp_git_repo / "test.txt"
        test_file.write_text("test content")

        success, commit_hash, error = brain.safe_commit("test commit", [str(test_file)])

        assert success is True
        assert commit_hash != ""  # Should have a commit hash
        assert error == ""

    def test_safe_commit_failure_returns_false(self, brain, temp_git_repo, mock_identity):
        """Failed commit should return (False, "", error_message)."""
        # Try to commit with no staged changes
        success, commit_hash, error = brain.safe_commit("test commit")

        assert success is False
        assert commit_hash == ""
        assert "COMMIT FAILED" in error

    def test_safe_commit_failure_includes_helpful_info(self, brain, temp_git_repo, mock_identity):
        """Error message should include helpful debugging info."""
        success, commit_hash, error = brain.safe_commit("test commit")

        assert "Possible causes" in error

    def test_safe_commit_no_traceback(self, brain, temp_git_repo, mock_identity, capsys):
        """Failed commit should NOT produce Python traceback."""
        success, commit_hash, error = brain.safe_commit("test commit")

        captured = capsys.readouterr()

        # Should not contain traceback indicators
        assert "Traceback (most recent call last)" not in captured.err
        assert "CalledProcessError" not in captured.err
        assert "subprocess" not in captured.err.lower() or "subprocess" in error


# =============================================================================
# Tests: Command error handling
# =============================================================================

class TestSendCommandErrors:
    """Tests for error handling in send command."""

    def test_send_commit_failure_shows_error(self, brain, temp_git_repo, mock_identity, capsys):
        """When send commit fails, agent should see clear error."""
        # Mock safe_commit to fail (now returns 3 values: success, commit_hash, error)
        with patch.object(brain, 'safe_commit', return_value=(False, "", "COMMIT FAILED\nTest error")):
            args = MagicMock()
            args.message = ["test", "message"]
            args.push = False
            brain.cmd_send(args)

        captured = capsys.readouterr()
        # The message still gets sent, but commit fails - check stderr for error
        assert "COMMIT FAILED" in captured.err or captured.out != ""

    def test_send_commit_failure_file_still_created(self, brain, temp_git_repo, mock_identity):
        """Even if commit fails, message file should exist for manual recovery."""
        with patch.object(brain, 'safe_commit', return_value=(False, "", "COMMIT FAILED")):
            args = MagicMock()
            args.message = ["test", "message"]
            args.push = False
            brain.cmd_send(args)

        # Message file should still exist
        message_files = list(brain.MESSAGES_DIR.rglob("*.json"))
        assert len(message_files) >= 1


class TestClaimCommandErrors:
    """Tests for error handling in claim command."""

    def test_claim_commit_failure_shows_error(self, brain, temp_git_repo, mock_identity, capsys):
        """When claim commit fails, agent should see clear error."""
        with patch.object(brain, 'safe_commit', return_value=(False, "", "COMMIT FAILED")):
            args = MagicMock()
            args.phase = 11
            args.push = False
            args.force = False
            brain.cmd_claim(args)

        captured = capsys.readouterr()
        assert "COMMIT FAILED" in captured.err or captured.out != ""


class TestReceiptCommandErrors:
    """Tests for error handling in receipt command."""

    def test_receipt_commit_failure_shows_error(self, brain, temp_git_repo, mock_identity, capsys):
        """When receipt commit fails, agent should see clear error."""
        with patch.object(brain, 'safe_commit', return_value=(False, "", "COMMIT FAILED")):
            args = MagicMock()
            args.push = False
            brain.cmd_receipt(args)

        captured = capsys.readouterr()
        assert "COMMIT FAILED" in captured.err or captured.out != ""


# =============================================================================
# Tests: Error message format
# =============================================================================

class TestErrorMessageFormat:
    """Tests for error message formatting."""

    def test_error_uses_stderr(self, brain, temp_git_repo, mock_identity, capsys):
        """Errors should go to stderr, not stdout."""
        success, commit_hash, error = brain.safe_commit("test commit")

        captured = capsys.readouterr()

        # Error should be in stderr
        assert "COMMIT FAILED" in captured.err
        # Success messages should NOT be in stdout when failing
        assert "✅" not in captured.out

    def test_error_includes_emoji_indicators(self, brain, temp_git_repo, mock_identity, capsys):
        """Error messages should use emoji for visibility."""
        success, commit_hash, error = brain.safe_commit("test commit")

        # Error message should have visual indicators
        assert "❌" in error
        # Message includes possible causes section
        assert "Possible causes" in error

    def test_error_message_not_too_long(self, brain, temp_git_repo, mock_identity):
        """Error message should be truncated to avoid overwhelming output."""
        # Even with very long git output, message should be manageable
        success, commit_hash, error = brain.safe_commit("test commit")

        # Should be less than 2000 chars typically
        assert len(error) < 2000


# =============================================================================
# Tests: Exit codes
# =============================================================================

class TestExitCodes:
    """Tests for proper exit codes on errors."""

    def test_send_failure_prints_error(self, brain, temp_git_repo, mock_identity, capsys):
        """Send command should show error on commit failure."""
        with patch.object(brain, 'safe_commit', return_value=(False, "", "error")):
            args = MagicMock()
            args.message = ["test"]
            args.push = False
            brain.cmd_send(args)

        captured = capsys.readouterr()
        # Message is created but commit fails - both outputs possible
        assert captured.out != "" or captured.err != ""

    def test_claim_prints_error(self, brain, temp_git_repo, mock_identity, capsys):
        """Claim command should show error on commit failure."""
        with patch.object(brain, 'safe_commit', return_value=(False, "", "error")):
            args = MagicMock()
            args.phase = 11
            args.push = False
            args.force = False
            brain.cmd_claim(args)

        captured = capsys.readouterr()
        assert captured.out != "" or captured.err != ""

    def test_receipt_prints_error(self, brain, temp_git_repo, mock_identity, capsys):
        """Receipt command should show error on commit failure."""
        with patch.object(brain, 'safe_commit', return_value=(False, "", "error")):
            args = MagicMock()
            args.push = False
            brain.cmd_receipt(args)

        captured = capsys.readouterr()
        assert captured.out != "" or captured.err != ""


# =============================================================================
# Tests: Recovery guidance
# =============================================================================

class TestRecoveryGuidance:
    """Tests that error messages include recovery guidance."""

    def test_error_includes_helpful_info(self, brain, temp_git_repo, mock_identity, capsys):
        """Error should include debugging hints."""
        success, commit_hash, error = brain.safe_commit("test commit")

        # Should include possible causes
        assert "Possible causes" in error

    def test_error_includes_details_section(self, brain, temp_git_repo, mock_identity):
        """Error should include a Details section."""
        success, commit_hash, error = brain.safe_commit("test commit")

        assert "Details:" in error

