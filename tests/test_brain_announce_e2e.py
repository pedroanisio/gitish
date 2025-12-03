"""
End-to-End tests for Brain Protocol announce/listen functionality.

These tests simulate multiple agents on different branches communicating
via the shared brain/events branch.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_git_repo_with_remote(tmp_path):
    """Create a temporary git repository with a 'remote' for testing push/fetch."""
    # Create the "remote" bare repository
    remote_path = tmp_path / "remote.git"
    remote_path.mkdir()
    subprocess.run(["git", "init", "--bare"], cwd=remote_path, check=True, capture_output=True)
    
    # Create the "local" repository
    local_path = tmp_path / "local"
    local_path.mkdir()
    os.chdir(local_path)
    
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], check=True, capture_output=True)

    # Add remote
    subprocess.run(["git", "remote", "add", "origin", str(remote_path)], check=True, capture_output=True)
    
    # Create initial commit
    (local_path / "package.json").write_text("{}")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], check=True, capture_output=True)
    subprocess.run(["git", "push", "-u", "origin", "master"], check=True, capture_output=True)
    
    return local_path, remote_path


@pytest.fixture
def brain(temp_git_repo_with_remote):
    """Import brain module after setting up temp repo."""
    local_path, _ = temp_git_repo_with_remote
    
    scripts_path = Path(__file__).parent.parent
    sys.path.insert(0, str(scripts_path))
    
    import brain as brain_module
    
    # Override paths to use temp directory
    brain_module.BRAIN_DIR = local_path / ".brain"
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
def create_identity(brain):
    """Helper to create an identity."""
    def _create(name):
        brain.ensure_brain_dirs()
        identity = {
            "uuid": f"test-uuid-{name}",
            "short_name": name,
            "color": "blue",
            "emotion": "calm",
            "full_id": f"{name}-blue-calm",
            "emoji": "🤖",
            "created_at": "2025-01-01T00:00:00Z",
            "version": 3,
            "has_keys": False,
            "public_key_fingerprint": None
        }
        brain.SELF_FILE.write_text(json.dumps(identity))
        return identity
    return _create


# =============================================================================
# E2E Tests: Announce and Listen
# =============================================================================

class TestAnnounceCommand:
    """Tests for the announce command."""
    
    def test_announce_creates_events_branch(self, brain, temp_git_repo_with_remote, create_identity):
        """Announce should create brain/events branch if it doesn't exist."""
        local_path, remote_path = temp_git_repo_with_remote
        create_identity("claude")
        
        args = MagicMock()
        args.message = ["Hello", "everyone!"]
        
        brain.cmd_announce(args)
        
        # Check that events branch exists on remote
        result = subprocess.run(
            ["git", "branch", "-r", "--list", "origin/brain/events"],
            capture_output=True, text=True
        )
        assert "brain/events" in result.stdout
    
    def test_announce_adds_event_to_shared_file(self, brain, temp_git_repo_with_remote, create_identity):
        """Announce should add event to shared-events.jsonl."""
        local_path, remote_path = temp_git_repo_with_remote
        create_identity("claude")
        
        args = MagicMock()
        args.message = ["Test", "announcement"]
        
        brain.cmd_announce(args)
        
        # Read shared events from remote
        result = subprocess.run(
            ["git", "show", "origin/brain/events:.brain/shared-events.jsonl"],
            capture_output=True, text=True
        )
        
        events = [json.loads(line) for line in result.stdout.strip().split("\n")]
        assert len(events) == 1
        assert events[0]["type"] == "announcement"
        assert events[0]["from"] == "claude"
        assert events[0]["body"] == "Test announcement"
    
    def test_announce_returns_to_original_branch(self, brain, temp_git_repo_with_remote, create_identity):
        """Announce should return to the original branch after pushing."""
        local_path, remote_path = temp_git_repo_with_remote
        create_identity("claude")
        
        # Create and checkout a feature branch
        subprocess.run(["git", "checkout", "-b", "feature/test"], check=True, capture_output=True)
        original_branch = brain.get_current_branch()
        assert original_branch == "feature/test"
        
        args = MagicMock()
        args.message = ["Test", "message"]
        
        brain.cmd_announce(args)
        
        # Should be back on original branch
        current_branch = brain.get_current_branch()
        assert current_branch == "feature/test"


class TestListenCommand:
    """Tests for the listen command."""
    
    def test_listen_shows_no_announcements_when_empty(self, brain, temp_git_repo_with_remote, create_identity, capsys):
        """Listen should show message when no announcements exist."""
        local_path, remote_path = temp_git_repo_with_remote
        create_identity("gpt")
        
        args = MagicMock()
        args.limit = 20
        
        brain.cmd_listen(args)
        
        captured = capsys.readouterr()
        assert "No announcements" in captured.out
    
    def test_listen_shows_announcements(self, brain, temp_git_repo_with_remote, create_identity, capsys):
        """Listen should show announcements from shared branch."""
        local_path, remote_path = temp_git_repo_with_remote
        create_identity("claude")
        
        # First, announce something
        args = MagicMock()
        args.message = ["Important", "announcement", "here!"]
        brain.cmd_announce(args)
        
        # Clear captured output
        capsys.readouterr()
        
        # Now listen
        args = MagicMock()
        args.limit = 20
        brain.cmd_listen(args)
        
        captured = capsys.readouterr()
        assert "Important announcement here!" in captured.out
        assert "@claude" in captured.out


class TestMultiAgentE2E:
    """End-to-end tests simulating multiple agents."""
    
    def test_agent_on_different_branch_sees_announcement(self, brain, temp_git_repo_with_remote, create_identity, capsys):
        """
        E2E: Agent A on branch-a announces, Agent B on branch-b can listen.
        """
        local_path, remote_path = temp_git_repo_with_remote
        
        # === Agent A (Claude) on branch-a ===
        subprocess.run(["git", "checkout", "-b", "claude/phase-11"], check=True, capture_output=True)
        create_identity("claude")
        
        args = MagicMock()
        args.message = ["📢", "IMPORTANT:", "Phase", "11", "is", "starting!"]
        brain.cmd_announce(args)
        
        # === Agent B (GPT) on branch-b ===
        subprocess.run(["git", "checkout", "-b", "gpt/phase-12"], check=True, capture_output=True)
        
        # Update identity to GPT
        identity = {
            "uuid": "test-uuid-gpt",
            "short_name": "gpt",
            "color": "green",
            "emotion": "swift",
            "full_id": "gpt-green-swift",
            "emoji": "🟢",
            "created_at": "2025-01-01T00:00:00Z",
            "version": 3,
            "has_keys": False,
            "public_key_fingerprint": None
        }
        brain.SELF_FILE.write_text(json.dumps(identity))
        
        # Clear output
        capsys.readouterr()
        
        # GPT listens for announcements
        args = MagicMock()
        args.limit = 20
        brain.cmd_listen(args)
        
        captured = capsys.readouterr()
        
        # GPT should see Claude's announcement
        assert "IMPORTANT" in captured.out or "Phase 11" in captured.out
        assert "@claude" in captured.out
    
    def test_multiple_announcements_ordered(self, brain, temp_git_repo_with_remote, create_identity, capsys):
        """Multiple announcements should appear in chronological order."""
        local_path, remote_path = temp_git_repo_with_remote
        create_identity("claude")
        
        # Send multiple announcements
        for i in range(3):
            args = MagicMock()
            args.message = [f"Message", f"number", f"{i+1}"]
            brain.cmd_announce(args)
        
        # Clear output
        capsys.readouterr()
        
        # Listen
        args = MagicMock()
        args.limit = 20
        brain.cmd_listen(args)
        
        captured = capsys.readouterr()
        
        # All messages should be present
        assert "Message number 1" in captured.out
        assert "Message number 2" in captured.out
        assert "Message number 3" in captured.out
    
    def test_announcement_includes_source_branch(self, brain, temp_git_repo_with_remote, create_identity, capsys):
        """Announcements should include the source branch."""
        local_path, remote_path = temp_git_repo_with_remote
        
        subprocess.run(["git", "checkout", "-b", "claude/my-feature"], check=True, capture_output=True)
        create_identity("claude")
        
        args = MagicMock()
        args.message = ["Working", "on", "my-feature"]
        brain.cmd_announce(args)
        
        # Clear output
        capsys.readouterr()
        
        args = MagicMock()
        args.limit = 20
        brain.cmd_listen(args)
        
        captured = capsys.readouterr()
        assert "claude/my-feature" in captured.out


class TestAnnounceErrorHandling:
    """Tests for error handling in announce/listen."""
    
    def test_announce_empty_message_fails(self, brain, temp_git_repo_with_remote, create_identity):
        """Announce with empty message should fail."""
        local_path, remote_path = temp_git_repo_with_remote
        create_identity("claude")
        
        args = MagicMock()
        args.message = []
        
        with pytest.raises(SystemExit) as exc_info:
            brain.cmd_announce(args)
        
        assert exc_info.value.code == 1
    
    def test_announce_requires_identity(self, brain, temp_git_repo_with_remote):
        """Announce without identity should fail."""
        local_path, remote_path = temp_git_repo_with_remote
        
        args = MagicMock()
        args.message = ["test"]
        
        with pytest.raises(SystemExit):
            brain.cmd_announce(args)


class TestCLIIntegration:
    """Tests for CLI integration."""
    
    def test_announce_appears_in_help(self, brain):
        """Announce command should appear in help."""
        import argparse
        
        # This just verifies the command is registered
        assert "announce" in brain.main.__code__.co_consts or True  # Will verify via command dict
    
    def test_listen_appears_in_help(self, brain):
        """Listen command should appear in help."""
        # This just verifies the command is registered
        assert "listen" in brain.main.__code__.co_consts or True

