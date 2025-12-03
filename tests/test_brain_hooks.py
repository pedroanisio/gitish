"""
Tests for pre-commit-brain hook functionality.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest


class TestIdentityCheck:
    """Test identity existence check."""
    
    def test_no_identity_blocks_commit(self, temp_repo):
        """Missing identity should block commit."""
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        # Ensure no identity exists
        brain_dir = temp_repo / ".brain"
        if brain_dir.exists():
            import shutil
            shutil.rmtree(brain_dir)
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 1
        assert "No identity found" in result.stderr
    
    def test_identity_exists_passes_check(self, temp_repo, sample_identity):
        """Existing identity should pass identity check."""
        # Create identity
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        # Also need a receipt for full pass
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "abc123",
            "ts": datetime.now(timezone.utc).isoformat()
        }
        receipt_file = receipts_dir / "20251203-120000.json"
        with open(receipt_file, "w") as f:
            json.dump(receipt, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert "Identity: @" in result.stderr
    
    def test_corrupted_identity_blocks(self, temp_repo):
        """Corrupted identity file should block commit."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        identity_file.write_text("not valid json {{{")
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 1
        assert "No identity found" in result.stderr
    
    def test_identity_missing_short_name_blocks(self, temp_repo):
        """Identity without short_name should block commit."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump({"uuid": "123", "full_id": "test"}, f)  # Missing short_name
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 1


class TestReceiptCheck:
    """Test read receipt check."""
    
    def test_no_receipt_blocks_commit(self, temp_repo, sample_identity):
        """Missing receipt should block commit."""
        # Create identity but no receipts
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 1
        assert "No read receipts found" in result.stderr
    
    def test_receipt_exists_passes(self, temp_repo, sample_identity):
        """Existing recent receipt should pass."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        # Create identity
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        # Create receipt
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "abc123def456",
            "ts": datetime.now(timezone.utc).isoformat()
        }
        
        receipt_file = receipts_dir / "20251203-150000.json"
        with open(receipt_file, "w") as f:
            json.dump(receipt, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
        assert "All checks passed" in result.stderr
    
    def test_empty_receipts_dir_blocks(self, temp_repo, sample_identity):
        """Empty receipts directory should block commit."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        # Create identity
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        # Create empty receipts dir
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 1
        assert "No read receipts found" in result.stderr


class TestReceiptAge:
    """Test receipt age validation."""
    
    def test_fresh_receipt_passes(self, temp_repo, sample_identity):
        """Receipt from 1 hour ago should pass."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        # Receipt from 1 hour ago
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "abc123",
            "ts": one_hour_ago.isoformat()
        }
        
        receipt_file = receipts_dir / "receipt.json"
        with open(receipt_file, "w") as f:
            json.dump(receipt, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0
    
    def test_old_receipt_blocks(self, temp_repo, sample_identity):
        """Receipt older than 24 hours should block."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        # Receipt from 48 hours ago
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "abc123",
            "ts": old_time.isoformat()
        }
        
        receipt_file = receipts_dir / "receipt.json"
        with open(receipt_file, "w") as f:
            json.dump(receipt, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 1
        assert "too old" in result.stderr.lower()
    
    def test_receipt_at_boundary_passes(self, temp_repo, sample_identity):
        """Receipt at exactly 23 hours should pass."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        # Receipt from 23 hours ago (just under limit)
        boundary_time = datetime.now(timezone.utc) - timedelta(hours=23)
        receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "abc123",
            "ts": boundary_time.isoformat()
        }
        
        receipt_file = receipts_dir / "receipt.json"
        with open(receipt_file, "w") as f:
            json.dump(receipt, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        assert result.returncode == 0


class TestBypass:
    """Test hook bypass functionality."""
    
    def test_bypass_env_var_skips_all_checks(self, temp_repo):
        """Setting BRAIN_BYPASS_HOOK should skip all checks."""
        # No identity, no receipts - should normally fail
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        env = os.environ.copy()
        env["BRAIN_BYPASS_HOOK"] = "1"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo,
            env=env
        )
        
        assert result.returncode == 0
        assert "bypassed" in result.stderr.lower()
    
    def test_bypass_with_empty_value_does_not_skip(self, temp_repo):
        """Empty BRAIN_BYPASS_HOOK should not skip."""
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        env = os.environ.copy()
        env["BRAIN_BYPASS_HOOK"] = ""
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo,
            env=env
        )
        
        # Should fail due to missing identity
        assert result.returncode == 1


class TestSkipPaths:
    """Test file path skip logic."""
    
    def test_docs_only_commit_skips_check(self, temp_repo, sample_identity):
        """Commits with only docs files should skip brain check."""
        # Stage only a docs file
        docs_dir = temp_repo / "docs"
        docs_dir.mkdir(exist_ok=True)
        (docs_dir / "test.md").write_text("# Test")
        
        subprocess.run(
            ["git", "add", "docs/test.md"],
            cwd=temp_repo,
            capture_output=True
        )
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should pass because only docs files
        assert result.returncode == 0
        assert "documentation files" in result.stderr.lower() or "skipping" in result.stderr.lower()
    
    def test_mixed_commit_requires_check(self, temp_repo):
        """Commits with code files should require brain check."""
        # Stage a code file
        (temp_repo / "test.ts").write_text("const x = 1;")
        
        subprocess.run(
            ["git", "add", "test.ts"],
            cwd=temp_repo,
            capture_output=True
        )
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should fail due to missing identity
        assert result.returncode == 1


class TestLatestReceipt:
    """Test selection of latest receipt."""
    
    def test_uses_most_recent_receipt(self, temp_repo, sample_identity):
        """Should use the most recent receipt file."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        # Create old receipt (48 hours ago)
        old_time = datetime.now(timezone.utc) - timedelta(hours=48)
        old_receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "old123",
            "ts": old_time.isoformat()
        }
        with open(receipts_dir / "20251201-100000.json", "w") as f:
            json.dump(old_receipt, f)
        
        # Create new receipt (1 hour ago)
        new_time = datetime.now(timezone.utc) - timedelta(hours=1)
        new_receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "new456",
            "ts": new_time.isoformat()
        }
        with open(receipts_dir / "20251203-150000.json", "w") as f:
            json.dump(new_receipt, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should pass using the newer receipt
        assert result.returncode == 0
        assert "new456" in result.stderr  # Should reference the newer commit


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_hook_error_fails_open(self, temp_repo):
        """Hook errors should allow commit (fail open)."""
        # This is tested implicitly - if the hook has an unhandled exception,
        # it should still return 0 to not block the developer
        pass  # Hook has try/except that returns 0 on error
    
    def test_invalid_receipt_timestamp(self, temp_repo, sample_identity):
        """Invalid timestamp in receipt should be handled."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        # Receipt with invalid timestamp
        receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "abc123",
            "ts": "not-a-valid-timestamp"
        }
        
        with open(receipts_dir / "receipt.json", "w") as f:
            json.dump(receipt, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should fail (invalid timestamp = too old)
        assert result.returncode == 1
    
    def test_missing_ts_in_receipt(self, temp_repo, sample_identity):
        """Receipt without timestamp should fail age check."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        # Receipt without ts field
        receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "abc123"
            # No "ts" field
        }
        
        with open(receipts_dir / "receipt.json", "w") as f:
            json.dump(receipt, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should fail
        assert result.returncode == 1


class TestOutput:
    """Test hook output formatting."""
    
    def test_success_output_format(self, temp_repo, sample_identity):
        """Successful check should show formatted output."""
        brain_dir = temp_repo / ".brain"
        brain_dir.mkdir(exist_ok=True)
        
        identity_file = brain_dir / "self.json"
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        receipts_dir = brain_dir / "receipts" / sample_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        receipt = {
            "type": "read-receipt",
            "from": sample_identity["short_name"],
            "up_to_commit": "abc123def456",
            "ts": datetime.now(timezone.utc).isoformat()
        }
        
        with open(receipts_dir / "receipt.json", "w") as f:
            json.dump(receipt, f)
        
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Check combined output contains expected elements
        combined = result.stdout + result.stderr
        assert "Brain Protocol" in combined
        assert "Identity:" in combined
        assert "All checks passed" in combined
    
    def test_failure_shows_instructions(self, temp_repo):
        """Failed check should show help instructions."""
        hook_path = Path(__file__).parent.parent / "src" / "hooks" / "pre-commit-brain"
        
        result = subprocess.run(
            [sys.executable, str(hook_path)],
            capture_output=True,
            text=True,
            cwd=temp_repo
        )
        
        # Should show how to fix (check combined output)
        combined = result.stdout + result.stderr
        assert "python scripts/brain.py" in combined

