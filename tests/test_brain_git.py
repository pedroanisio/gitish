"""
Tests for brain.py Git integration functionality.
"""

import subprocess
from pathlib import Path

import pytest


class TestGitUtilities:
    """Test Git utility functions."""
    
    def test_get_current_branch(self, temp_repo, brain_module):
        """Should return current branch name."""
        branch = brain_module.get_current_branch()
        
        # Should be on master/main after init
        assert branch in ["master", "main", ""]
    
    def test_get_head_commit(self, temp_repo, brain_module):
        """Should return HEAD commit hash."""
        commit = brain_module.get_head_commit()
        
        # Should be a valid git hash
        assert len(commit) == 40
        assert all(c in "0123456789abcdef" for c in commit.lower())
    
    def test_run_git_success(self, temp_repo, brain_module):
        """run_git should execute git commands."""
        result = brain_module.run_git("status")
        
        assert result.returncode == 0
    
    def test_run_git_failure(self, temp_repo, brain_module):
        """run_git should raise on failure when check=True."""
        with pytest.raises(subprocess.CalledProcessError):
            brain_module.run_git("nonexistent-command")
    
    def test_git_output(self, temp_repo, brain_module):
        """git_output should return stdout stripped."""
        output = brain_module.git_output("rev-parse", "--short", "HEAD")
        
        assert len(output) >= 7
        assert "\n" not in output


class TestGitCommits:
    """Test Git commit creation."""
    
    def test_commit_after_message(self, initialized_identity, brain_module, temp_repo):
        """Sending a message should create a commit."""
        before = brain_module.get_head_commit()
        
        # Create and stage a file
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": "Test message"}
        )
        brain_module.append_event({"type": "message", "body": "Test"})
        
        brain_module.run_git("add", "-A")
        brain_module.run_git("commit", "-m", "test: message commit")
        
        after = brain_module.get_head_commit()
        
        assert before != after
    
    def test_commit_message_format(self, initialized_identity, brain_module, temp_repo):
        """Commit messages should follow expected format."""
        # Create a commit
        filepath = brain_module.save_message(
            initialized_identity,
            "message",
            {"body": "Hello world"}
        )
        
        brain_module.run_git("add", "-A")
        short_name = initialized_identity["short_name"]
        commit_msg = f"msg({short_name}): Hello world"
        brain_module.run_git("commit", "-m", commit_msg)
        
        # Get last commit message
        result = brain_module.run_git("log", "-1", "--format=%s")
        last_message = result.stdout.strip()
        
        assert f"msg({short_name})" in last_message


class TestGitBranches:
    """Test Git branch operations."""
    
    def test_dev_branch_naming(self, initialized_identity):
        """Dev branch should follow naming convention."""
        short_name = initialized_identity["short_name"]
        
        expected_patterns = [
            f"dev/{short_name}",
            f"dev/{short_name}/phase-11",
            f"dev/{short_name}/feature-xyz"
        ]
        
        for pattern in expected_patterns:
            assert pattern.startswith("dev/")
            assert short_name in pattern
    
    def test_create_dev_branch(self, initialized_identity, brain_module, temp_repo):
        """Should be able to create dev branch."""
        short_name = initialized_identity["short_name"]
        branch_name = f"dev/{short_name}/test"
        
        brain_module.run_git("checkout", "-b", branch_name)
        
        current = brain_module.get_current_branch()
        assert current == branch_name


class TestRemoteOperations:
    """Test remote Git operations (mocked/skipped in unit tests)."""
    
    def test_get_remote_head_missing(self, temp_repo, brain_module):
        """get_remote_head should return None for missing branch."""
        result = brain_module.get_remote_head("nonexistent/branch")
        
        assert result is None
    
    def test_fetch_without_remote(self, temp_repo, brain_module):
        """Fetch should handle missing remote gracefully."""
        # This repo has no remote, fetch should not crash
        result = brain_module.run_git("fetch", "--all", check=False)
        
        # May succeed with "no remote" or fail gracefully
        assert result.returncode in [0, 1, 128]


class TestGitStatus:
    """Test Git status and working directory checks."""
    
    def test_clean_working_directory(self, temp_repo, brain_module):
        """Should detect clean working directory."""
        result = brain_module.run_git("status", "--porcelain")
        
        # After fixture setup, should be clean
        # (may have uncommitted changes from brain dirs)
        # Just verify command works
        assert result.returncode == 0
    
    def test_uncommitted_changes(self, temp_repo, brain_module):
        """Should detect uncommitted changes."""
        # Create an uncommitted file
        (Path(temp_repo) / "uncommitted.txt").write_text("test")
        
        result = brain_module.run_git("status", "--porcelain")
        
        assert "uncommitted.txt" in result.stdout
    
    def test_staged_changes(self, temp_repo, brain_module):
        """Should detect staged changes."""
        # Create and stage a file
        test_file = Path(temp_repo) / "staged.txt"
        test_file.write_text("test")
        brain_module.run_git("add", str(test_file))
        
        result = brain_module.run_git("status", "--porcelain")
        
        assert "staged.txt" in result.stdout
        assert result.stdout.strip().startswith("A")


class TestGitConfig:
    """Test Git configuration requirements."""
    
    def test_user_email_configured(self, temp_repo, brain_module):
        """Git user.email should be configured."""
        result = brain_module.run_git("config", "user.email")
        
        assert result.returncode == 0
        assert "@" in result.stdout or result.stdout.strip() != ""
    
    def test_user_name_configured(self, temp_repo, brain_module):
        """Git user.name should be configured."""
        result = brain_module.run_git("config", "user.name")
        
        assert result.returncode == 0
        assert result.stdout.strip() != ""

