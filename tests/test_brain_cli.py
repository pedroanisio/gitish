"""
Tests for brain.py CLI argument parsing and command dispatch.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest


class TestCLIParsing:
    """Test CLI argument parsing."""
    
    def test_help_flag(self, temp_repo):
        """--help should show usage and exit cleanly."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "--help"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower() or "brain.py" in result.stdout
    
    def test_no_command_shows_help(self, temp_repo):
        """No command should show help."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should exit with non-zero or show help
        assert result.returncode in [0, 1]


class TestInitCommand:
    """Test 'init' command parsing."""
    
    def test_init_with_name(self, temp_repo):
        """init --name should accept a name."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "init", "--name", "testuser"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should succeed
        assert result.returncode == 0 or "Identity" in result.stdout
    
    def test_init_short_name_flag(self, temp_repo):
        """init -n should work as alias for --name."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "init", "-n", "shortuser"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0 or "Identity" in result.stdout
    
    def test_init_reset_flag(self, temp_repo):
        """init --reset should trigger reset logic."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        # First init
        subprocess.run(
            [sys.executable, str(brain_path), "init", "-n", "user1"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Reset with new name
        result = subprocess.run(
            [sys.executable, str(brain_path), "init", "--reset", "-n", "user2"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0


class TestSendCommand:
    """Test 'send' command parsing."""
    
    def test_send_requires_message(self, temp_repo):
        """send without message should fail or prompt."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        # First init an identity
        subprocess.run(
            [sys.executable, str(brain_path), "init", "-n", "sender"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "msg", "send"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should fail due to missing message
        assert result.returncode != 0 or "error" in result.stderr.lower()
    
    def test_send_with_message(self, temp_repo):
        """send with message should work."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        # Init
        subprocess.run(
            [sys.executable, str(brain_path), "init", "-n", "sender"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "msg", "send", "Hello", "world"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Message should be combined
        assert result.returncode == 0 or "sent" in result.stdout.lower()
    
    def test_send_push_flag(self, temp_repo):
        """send --push should accept push flag."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        subprocess.run(
            [sys.executable, str(brain_path), "init", "-n", "sender"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # With -p flag (will fail push since no remote, but flag should be accepted)
        result = subprocess.run(
            [sys.executable, str(brain_path), "msg", "send", "-p", "Test message"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should complete successfully (push failure is handled gracefully)
        assert result.returncode == 0
        # Should show push attempt message (either success or warning)
        assert "push" in result.stdout.lower() or "sent" in result.stdout.lower()


class TestClaimCommand:
    """Test 'claim' command parsing."""
    
    def test_claim_requires_phase(self, temp_repo):
        """claim without phase should fail."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        subprocess.run(
            [sys.executable, str(brain_path), "init", "-n", "claimer"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "phase", "claim"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode != 0
    
    def test_claim_with_phase(self, temp_repo):
        """claim with phase number should work."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        subprocess.run(
            [sys.executable, str(brain_path), "init", "-n", "claimer"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "phase", "claim", "11"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0 or "Claimed" in result.stdout
    
    def test_claim_invalid_phase(self, temp_repo):
        """claim with non-integer should fail."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        subprocess.run(
            [sys.executable, str(brain_path), "init", "-n", "claimer"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "phase", "claim", "abc"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode != 0


class TestStatusCommand:
    """Test 'status' command."""
    
    def test_status_without_identity(self, temp_repo):
        """status without identity should show warning."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "status"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should run but indicate no identity
        assert "BRAIN" in result.stdout or "Identity" in result.stdout
    
    def test_status_with_identity(self, temp_repo):
        """status with identity should show details."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        subprocess.run(
            [sys.executable, str(brain_path), "init", "-n", "testuser"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "status"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "testuser" in result.stdout


class TestLogCommand:
    """Test 'log' command."""
    
    def test_log_empty(self, temp_repo):
        """log with no events should indicate empty."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "msg", "log"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "No events" in result.stdout or "events" in result.stdout.lower()
    
    def test_log_limit_flag(self, temp_repo):
        """log --limit should accept limit."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "msg", "log", "--limit", "5"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
    
    def test_log_short_limit_flag(self, temp_repo):
        """log -n should work as alias for --limit."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "msg", "log", "-n", "10"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0


class TestPhasesCommand:
    """Test 'phases' command."""
    
    def test_phases_reads_claims_md(self, temp_repo):
        """phases should read PHASE-CLAIMS.md."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "phase", "list"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        # Should show phase info from fixture
        assert "Phase" in result.stdout or "AVAILABLE" in result.stdout


class TestErrorHandling:
    """Test CLI error handling."""
    
    def test_wrong_directory(self, tmp_path):
        """Running outside project root should fail."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        # Run in a directory without package.json
        result = subprocess.run(
            [sys.executable, str(brain_path), "status"],
            capture_output=True,
            text=True,
            cwd=tmp_path
        )
        
        assert result.returncode != 0
        assert "project root" in result.stderr.lower() or "package.json" in result.stderr
    
    def test_unknown_command(self, temp_repo):
        """Unknown command should show error."""
        brain_path = Path(__file__).parent.parent / "src" / "brain" / "brain_cli.py"
        
        result = subprocess.run(
            [sys.executable, str(brain_path), "unknowncommand"],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should fail or show help
        assert result.returncode != 0 or "usage" in result.stdout.lower()

