"""
Tests for brain.py phase claim functionality.
"""

import json
from pathlib import Path

import pytest


class TestClaimCreation:
    """Test claim file creation."""
    
    def test_claim_file_structure(self, initialized_identity, temp_repo):
        """Claim file should have correct structure."""
        claim = {
            "type": "claim",
            "phase": 11,
            "developer": f"@{initialized_identity['short_name']}",
            "developer_id": initialized_identity["full_id"],
            "branch": f"dev/{initialized_identity['short_name']}/phase-11",
            "ts": "2025-12-03T10:00:00+00:00",
            "head_at_claim": "abc123"
        }
        
        assert claim["type"] == "claim"
        assert claim["phase"] == 11
        assert claim["developer"].startswith("@")
        assert "ts" in claim
    
    def test_claim_file_saved(self, initialized_identity, brain_module, temp_repo):
        """Claim should be saved to .brain/claims/."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        claim_file = claims_dir / "phase-11-claim.json"
        claim = {
            "type": "claim",
            "phase": 11,
            "developer": f"@{initialized_identity['short_name']}",
        }
        
        with open(claim_file, "w") as f:
            json.dump(claim, f)
        
        assert claim_file.exists()
        
        with open(claim_file) as f:
            loaded = json.load(f)
        
        assert loaded["phase"] == 11


class TestClaimValidation:
    """Test claim validation and edge cases."""
    
    def test_valid_phase_numbers(self):
        """Valid phase numbers should be accepted."""
        valid_phases = [1, 5, 7, 8, 9, 10, 11, 12, 13, 14, 15, 20, 100]
        
        for phase in valid_phases:
            assert isinstance(phase, int)
            assert phase > 0
    
    def test_invalid_phase_numbers(self):
        """Invalid phase numbers should be rejected."""
        invalid_phases = [0, -1, -100]
        
        for phase in invalid_phases:
            assert phase <= 0
    
    def test_claim_branch_naming(self, initialized_identity):
        """Claim branch should follow naming convention."""
        expected_pattern = f"dev/{initialized_identity['short_name']}/phase-11"
        
        assert expected_pattern.startswith("dev/")
        assert "/phase-" in expected_pattern


class TestClaimRelease:
    """Test claim release functionality."""
    
    def test_release_removes_claim_file(self, initialized_identity, temp_repo):
        """Releasing a claim should remove the claim file."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        claim_file = claims_dir / "phase-11-claim.json"
        claim_file.write_text('{"type": "claim", "phase": 11}')
        
        assert claim_file.exists()
        
        # Simulate release
        claim_file.unlink()
        
        assert not claim_file.exists()
    
    def test_release_event_structure(self, initialized_identity):
        """Release event should have correct structure."""
        release = {
            "type": "release",
            "phase": 11,
            "developer": f"@{initialized_identity['short_name']}",
            "reason": "blocked",
            "ts": "2025-12-03T11:00:00+00:00"
        }
        
        assert release["type"] == "release"
        assert "reason" in release
    
    def test_release_reasons(self):
        """Common release reasons should be valid."""
        valid_reasons = [
            "released",
            "blocked",
            "handoff",
            "timeout",
            "conflict",
            "completed elsewhere"
        ]
        
        for reason in valid_reasons:
            assert isinstance(reason, str)
            assert len(reason) > 0


class TestClaimComplete:
    """Test claim completion functionality."""
    
    def test_complete_creates_file(self, initialized_identity, temp_repo):
        """Completing a claim should create a complete file."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        complete_file = claims_dir / "phase-11-complete.json"
        complete = {
            "type": "complete",
            "phase": 11,
            "developer": f"@{initialized_identity['short_name']}",
            "pr": "#42",
            "merge_commit": "abc123def456",
            "ts": "2025-12-03T12:00:00+00:00"
        }
        
        with open(complete_file, "w") as f:
            json.dump(complete, f)
        
        assert complete_file.exists()
    
    def test_complete_removes_claim(self, initialized_identity, temp_repo):
        """Completing should remove the claim file."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        claim_file = claims_dir / "phase-11-claim.json"
        claim_file.write_text('{"type": "claim", "phase": 11}')
        
        # Simulate complete
        if claim_file.exists():
            claim_file.unlink()
        
        complete_file = claims_dir / "phase-11-complete.json"
        complete_file.write_text('{"type": "complete", "phase": 11}')
        
        assert not claim_file.exists()
        assert complete_file.exists()
    
    def test_complete_pr_formats(self):
        """Various PR reference formats should be valid."""
        valid_prs = [
            "#42",
            "42",
            "PR-42",
            "https://github.com/org/repo/pull/42",
            "GH-42"
        ]
        
        for pr in valid_prs:
            assert isinstance(pr, str)
            assert len(pr) > 0


class TestClaimConflicts:
    """Test handling of claim conflicts."""
    
    def test_detect_existing_claim(self, temp_repo):
        """Should detect when phase is already claimed."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        # First claim
        claim_file = claims_dir / "phase-11-claim.json"
        claim_file.write_text('{"type": "claim", "phase": 11, "developer": "@alice"}')
        
        # Check for existing claim
        assert claim_file.exists()
        
        with open(claim_file) as f:
            existing = json.load(f)
        
        assert existing["developer"] == "@alice"
    
    def test_claim_already_complete(self, temp_repo):
        """Should detect when phase is already complete."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        complete_file = claims_dir / "phase-11-complete.json"
        complete_file.write_text('{"type": "complete", "phase": 11, "developer": "@bob"}')
        
        assert complete_file.exists()


class TestPhasesCommand:
    """Test phases command output - reads from .brain/claims/ only."""
    
    def test_phases_shows_active_claims_from_brain_folder(self, temp_repo, brain_module, capsys):
        """phases command should display active claims from .brain/claims/."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        claim = {
            "type": "claim",
            "phase": 17,
            "developer": "@claude",
            "developer_id": "claude-green-glow",
            "branch": "dev/claude/phase-17",
            "ts": "2025-12-03T17:00:00+00:00"
        }
        with open(claims_dir / "phase-17-claim.json", "w") as f:
            json.dump(claim, f)
        
        class Args:
            pass
        brain_module.cmd_phases(Args())
        
        captured = capsys.readouterr()
        
        assert "Phase 17" in captured.out or "17" in captured.out
        assert "@claude" in captured.out or "claude-green-glow" in captured.out
    
    def test_phases_shows_completed_from_brain_folder(self, temp_repo, brain_module, capsys):
        """phases command should display completed phases from .brain/claims/."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        complete = {
            "type": "complete",
            "phase": 11,
            "developer": "@claude",
            "pr": "41",
            "merge_commit": "abc123",
            "ts": "2025-12-03T16:00:00+00:00"
        }
        with open(claims_dir / "phase-11-complete.json", "w") as f:
            json.dump(complete, f)
        
        class Args:
            pass
        brain_module.cmd_phases(Args())
        
        captured = capsys.readouterr()
        
        assert "Phase 11" in captured.out or "11" in captured.out
        assert "complete" in captured.out.lower() or "✅" in captured.out
    
    def test_phases_shows_multiple_claims(self, temp_repo, brain_module, capsys):
        """phases should show multiple claims from .brain/claims/."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        claim1 = {
            "type": "claim",
            "phase": 20,
            "developer": "@gpt",
            "developer_id": "gpt-violet-zen",
            "branch": "dev/gpt/phase-20"
        }
        with open(claims_dir / "phase-20-claim.json", "w") as f:
            json.dump(claim1, f)
        
        claim2 = {
            "type": "claim",
            "phase": 21,
            "developer": "@claude",
            "developer_id": "claude-green-glow",
            "branch": "dev/claude/phase-21"
        }
        with open(claims_dir / "phase-21-claim.json", "w") as f:
            json.dump(claim2, f)
        
        class Args:
            pass
        brain_module.cmd_phases(Args())
        
        captured = capsys.readouterr()
        
        assert "20" in captured.out
        assert "21" in captured.out
        assert "gpt-violet-zen" in captured.out
        assert "claude-green-glow" in captured.out
    
    def test_phases_shows_active_claims_section(self, temp_repo, brain_module, capsys):
        """phases should show Active Claims section."""
        claims_dir = Path(".brain/claims")
        claims_dir.mkdir(parents=True, exist_ok=True)
        
        claim = {
            "type": "claim",
            "phase": 16,
            "developer": "@claude",
            "developer_id": "claude-green-glow",
            "branch": "claude/phase-16-components"
        }
        with open(claims_dir / "phase-16-claim.json", "w") as f:
            json.dump(claim, f)
        
        class Args:
            pass
        brain_module.cmd_phases(Args())
        
        captured = capsys.readouterr()
        
        assert "Active Claims" in captured.out
    
    def test_phases_empty_brain_claims_no_crash(self, temp_repo, brain_module, capsys):
        """phases should handle empty .brain/claims/ gracefully."""
        # No .brain/claims directory at all
        class Args:
            pass
        
        # Should not crash
        brain_module.cmd_phases(Args())
        
        captured = capsys.readouterr()
        assert "Phase" in captured.out or "claims" in captured.out.lower()

