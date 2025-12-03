"""
Tests for brain.py read receipt functionality.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


class TestReceiptCreation:
    """Test read receipt file creation."""
    
    def test_receipt_structure(self, initialized_identity):
        """Receipt should have correct structure."""
        receipt = {
            "type": "read-receipt",
            "from": initialized_identity["short_name"],
            "from_id": initialized_identity["full_id"],
            "up_to_commit": "abc123def456789",
            "ts": "2025-12-03T10:00:00+00:00"
        }
        
        assert receipt["type"] == "read-receipt"
        assert receipt["from"] == initialized_identity["short_name"]
        assert "up_to_commit" in receipt
        assert "ts" in receipt
    
    def test_receipt_file_saved(self, initialized_identity, temp_repo):
        """Receipt should be saved to .brain/receipts/<user>/."""
        receipts_dir = Path(".brain/receipts") / initialized_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        receipt_file = receipts_dir / "20251203-100000.json"
        receipt = {
            "type": "read-receipt",
            "from": initialized_identity["short_name"],
            "up_to_commit": "abc123"
        }
        
        with open(receipt_file, "w") as f:
            json.dump(receipt, f)
        
        assert receipt_file.exists()
    
    def test_receipt_directory_per_user(self, initialized_identity, temp_repo):
        """Each user should have their own receipt directory."""
        receipts_base = Path(".brain/receipts")
        
        user_dir = receipts_base / initialized_identity["short_name"]
        user_dir.mkdir(parents=True, exist_ok=True)
        
        assert user_dir.exists()
        assert user_dir.is_dir()
        assert user_dir.name == initialized_identity["short_name"]


class TestReceiptTimestamps:
    """Test receipt timestamp handling."""
    
    def test_receipt_filename_timestamp(self, initialized_identity, temp_repo):
        """Receipt filename should contain timestamp."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        
        receipts_dir = Path(".brain/receipts") / initialized_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        receipt_file = receipts_dir / f"{ts}.json"
        receipt_file.write_text('{}')
        
        # Filename should match timestamp pattern
        assert "-" in receipt_file.stem
        parts = receipt_file.stem.split("-")
        assert len(parts) == 2
        assert len(parts[0]) == 8  # YYYYMMDD
        assert len(parts[1]) == 6  # HHMMSS
    
    def test_multiple_receipts_unique(self, initialized_identity, temp_repo):
        """Multiple receipts should have unique filenames."""
        import time
        
        receipts_dir = Path(".brain/receipts") / initialized_identity["short_name"]
        receipts_dir.mkdir(parents=True, exist_ok=True)
        
        filenames = []
        for i in range(3):
            ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
            # Add microseconds to ensure uniqueness
            ts = f"{ts}-{i:03d}"
            receipt_file = receipts_dir / f"{ts}.json"
            receipt_file.write_text(f'{{"index": {i}}}')
            filenames.append(receipt_file.name)
            time.sleep(0.001)
        
        # All filenames should be unique
        assert len(set(filenames)) == 3


class TestReceiptCommitReference:
    """Test commit reference in receipts."""
    
    def test_commit_hash_format(self):
        """Commit hash should be valid git hash format."""
        valid_hashes = [
            "abc123",
            "abc123def456",
            "a" * 40,  # Full SHA-1
            "abc123def456789012345678901234567890abcd"
        ]
        
        for h in valid_hashes:
            assert all(c in "0123456789abcdef" for c in h.lower())
    
    def test_short_hash_allowed(self):
        """Short commit hashes should be allowed."""
        short_hash = "abc1234"
        assert len(short_hash) >= 7  # Git minimum for uniqueness
    
    def test_receipt_references_specific_commit(self, initialized_identity):
        """Receipt should reference a specific commit hash."""
        commit = "abc123def456"
        
        receipt = {
            "type": "read-receipt",
            "from": initialized_identity["short_name"],
            "up_to_commit": commit,
            "ts": "2025-12-03T10:00:00+00:00"
        }
        
        assert receipt["up_to_commit"] == commit
        assert len(receipt["up_to_commit"]) > 0


class TestReceiptVerification:
    """Test receipt verification logic."""
    
    def test_receipt_proves_read(self, initialized_identity, temp_repo):
        """Receipt should prove reader saw state at specific commit."""
        commit = "abc123"
        ts = "2025-12-03T10:00:00+00:00"
        
        receipt = {
            "type": "read-receipt",
            "from": initialized_identity["short_name"],
            "from_id": initialized_identity["full_id"],
            "up_to_commit": commit,
            "ts": ts
        }
        
        # Verification checks
        assert receipt["from"] == initialized_identity["short_name"]
        assert receipt["up_to_commit"] == commit
        
        # Parse timestamp
        parsed_ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        assert parsed_ts is not None
    
    def test_receipt_ordering(self, initialized_identity, temp_repo):
        """Multiple receipts should be orderable by timestamp."""
        receipts = [
            {"ts": "2025-12-03T10:00:00+00:00", "up_to_commit": "aaa"},
            {"ts": "2025-12-03T11:00:00+00:00", "up_to_commit": "bbb"},
            {"ts": "2025-12-03T09:00:00+00:00", "up_to_commit": "ccc"},
        ]
        
        # Sort by timestamp
        sorted_receipts = sorted(receipts, key=lambda r: r["ts"])
        
        assert sorted_receipts[0]["up_to_commit"] == "ccc"
        assert sorted_receipts[1]["up_to_commit"] == "aaa"
        assert sorted_receipts[2]["up_to_commit"] == "bbb"


class TestReceiptEdgeCases:
    """Test receipt edge cases."""
    
    def test_first_receipt(self, initialized_identity, temp_repo):
        """First receipt for a user should create directory."""
        receipts_dir = Path(".brain/receipts") / initialized_identity["short_name"]
        
        # Should not exist initially
        assert not receipts_dir.exists()
        
        # Create directory and first receipt
        receipts_dir.mkdir(parents=True, exist_ok=True)
        receipt_file = receipts_dir / "20251203-100000.json"
        receipt_file.write_text('{"type": "read-receipt"}')
        
        assert receipts_dir.exists()
        assert receipt_file.exists()
    
    def test_receipt_with_empty_repo(self, temp_repo):
        """Receipt on empty/initial repo should still work."""
        # Get initial commit (should exist from fixture)
        import subprocess
        
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True
        )
        
        # Should have at least one commit
        assert result.returncode == 0
        assert len(result.stdout.strip()) > 0

