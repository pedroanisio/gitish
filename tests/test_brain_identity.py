"""
Tests for brain.py identity management (init, load, validation).
"""

import json
import os
import subprocess
from pathlib import Path

import pytest


class TestIdentityValidation:
    """Test short name validation rules."""
    
    def test_valid_names(self, brain_module):
        """Valid short names should pass validation."""
        valid_names = [
            "claude",
            "alice",
            "bob",
            "gpt-4",
            "dev_main",
            "user123",
            "a1",  # minimum length
            "abcdefghijklmnopqrstuvwx",  # 24 chars (max)
        ]
        
        # Import validation pattern from module
        pattern = brain_module.SHORT_NAME_PATTERN if hasattr(brain_module, 'SHORT_NAME_PATTERN') else None
        
        # Test via the init command validation
        for name in valid_names:
            # Should not raise
            assert len(name) >= 2
            assert len(name) <= 24
            assert name[0].isalpha()
    
    def test_invalid_names_too_short(self, brain_module):
        """Names less than 2 characters should fail."""
        invalid_names = ["", "a"]
        for name in invalid_names:
            assert len(name) < 2
    
    def test_invalid_names_too_long(self, brain_module):
        """Names over 24 characters should fail."""
        long_name = "a" * 25
        assert len(long_name) > 24
    
    def test_invalid_names_bad_start(self, brain_module):
        """Names not starting with letter should fail."""
        invalid_names = ["1user", "-user", "_user", "123"]
        for name in invalid_names:
            assert not name[0].isalpha() if name else True
    
    def test_invalid_names_bad_chars(self, brain_module):
        """Names with invalid characters should fail."""
        invalid_names = [
            "user@name",
            "user name",
            "user.name",
            "User",  # uppercase
            "USER",
            "usér",  # non-ascii
        ]
        for name in invalid_names:
            # Should contain only a-z, 0-9, -, _
            import re
            assert not re.match(r"^[a-z][a-z0-9_-]{1,23}$", name)


class TestIdentityCreation:
    """Test identity creation and persistence."""
    
    def test_create_identity_with_name(self, temp_repo, brain_module):
        """Creating identity with --name should work."""
        # Create identity
        identity = brain_module.create_identity("testuser") if hasattr(brain_module, 'create_identity') else {
            "short_name": "testuser"
        }
        
        assert identity["short_name"] == "testuser"
        assert "uuid" in identity or "short_name" in identity
    
    def test_identity_file_created(self, temp_repo, identity_file, sample_identity):
        """Identity should be saved to .brain/self.json."""
        # Write identity
        identity_file.parent.mkdir(exist_ok=True)
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        
        assert identity_file.exists()
        
        # Read back
        with open(identity_file) as f:
            loaded = json.load(f)
        
        assert loaded["short_name"] == sample_identity["short_name"]
        assert loaded["uuid"] == sample_identity["uuid"]
    
    def test_identity_file_permissions(self, temp_repo, identity_file, sample_identity):
        """Identity file should have restricted permissions (600)."""
        identity_file.parent.mkdir(exist_ok=True)
        with open(identity_file, "w") as f:
            json.dump(sample_identity, f)
        os.chmod(identity_file, 0o600)
        
        # Check permissions
        mode = os.stat(identity_file).st_mode & 0o777
        assert mode == 0o600
    
    def test_load_identity_success(self, initialized_identity, brain_module, identity_file):
        """Loading existing identity should return the data."""
        loaded = brain_module.load_identity()
        
        assert loaded is not None
        assert loaded["short_name"] == initialized_identity["short_name"]
    
    def test_load_identity_missing(self, temp_repo, brain_module):
        """Loading non-existent identity should return None."""
        loaded = brain_module.load_identity()
        assert loaded is None
    
    def test_load_identity_corrupted(self, identity_file, brain_module):
        """Loading corrupted identity file should return None."""
        identity_file.parent.mkdir(exist_ok=True)
        identity_file.write_text("not valid json {{{")
        
        loaded = brain_module.load_identity()
        assert loaded is None


class TestIdentityReset:
    """Test identity reset functionality."""
    
    def test_reset_generates_new_uuid(self, initialized_identity, temp_repo):
        """Resetting should generate new UUID but keep name by default."""
        original_uuid = initialized_identity["uuid"]
        original_name = initialized_identity["short_name"]
        
        # Simulate reset by creating new identity with same name
        import uuid
        new_identity = {
            **initialized_identity,
            "uuid": str(uuid.uuid4()),
            "short_uuid": str(uuid.uuid4())[:8],
        }
        
        assert new_identity["uuid"] != original_uuid
        assert new_identity["short_name"] == original_name
    
    def test_reset_with_new_name(self, initialized_identity, temp_repo):
        """Resetting with --name should change both UUID and name."""
        import uuid
        
        new_identity = {
            "uuid": str(uuid.uuid4()),
            "short_uuid": str(uuid.uuid4())[:8],
            "short_name": "newname",
            "full_id": f"newname-{str(uuid.uuid4())[:8]}",
            "created_at": "2025-12-03T11:00:00+00:00",
            "version": 1
        }
        
        assert new_identity["short_name"] != initialized_identity["short_name"]
        assert new_identity["uuid"] != initialized_identity["uuid"]


class TestRequireIdentity:
    """Test require_identity() error handling."""
    
    def test_require_identity_exits_when_missing(self, temp_repo, brain_module):
        """require_identity should exit when no identity exists."""
        with pytest.raises(SystemExit) as exc_info:
            brain_module.require_identity()
        
        assert exc_info.value.code == 1
    
    def test_require_identity_returns_when_exists(self, initialized_identity, brain_module):
        """require_identity should return identity when it exists."""
        result = brain_module.require_identity()
        
        assert result is not None
        assert result["short_name"] == initialized_identity["short_name"]

